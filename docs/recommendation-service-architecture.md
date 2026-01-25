# Recommendation Service Architecture

**Status:** Design Complete
**Date:** 2026-01-24
**Authors:** Design session with AI assistance

---

## 1. Problem Statement

The recommendation engine must handle **two types of uncertainty** when generating pick/ban suggestions:

| Uncertainty Type | Example | Impact |
|------------------|---------|--------|
| **Flex Pick Ambiguity** | Enemy picks Aurora (could be MID or TOP) | Can't calculate accurate matchup scores |
| **Surprise Pick** | Recommending a champion with <3 stage games | Low confidence in player proficiency |

**Core insight:** These are about **propagating uncertainty** through our scoring system rather than pretending we have certainty. We should:
1. Calculate best estimates using weighted probabilities
2. Surface low confidence to users transparently

---

## 2. Data Foundation

### 2.1 New GRID API Fields

We discovered additional fields available in GRID API that we're not currently extracting:

| Field | Version | Purpose |
|-------|---------|---------|
| `roles` | v3.43+ | **Actual position played** - ground truth for flex data |
| `netWorth` | Always | Economic performance indicator |
| `moneyPerMinute` | v3.36+ | Carry vs support indicator |
| `objectives` (player) | Always | Player-level objective contribution |

**Coverage:** ~47% of our series (693/1484) are v3.43+ and have the `roles` field.

### 2.2 Data Strategy

| Data Version | % of Data | Role Strategy |
|--------------|-----------|---------------|
| **v3.43+** | 47% | Use API `roles` field (ground truth) |
| **Older** | 53% | Infer from champion + context |

### 2.3 Pre-computed Data Artifacts

All files in `knowledge/` are committed to the repository.

**Computed Analytics:**
```
knowledge/
├── champion_counters.json     # Champion matchup win rates
├── champion_synergies.json    # Normalized synergy scores between champion pairs
├── flex_champions.json        # Champion → role probability distribution
│   {"Aurora": {"MID": 0.65, "TOP": 0.35}, ...}
├── meta_stats.json            # Current patch meta statistics
├── patch_info.json            # Patch dates and game counts per patch
├── player_proficiency.json    # Player + Champion → composite performance score
├── player_roles.json          # Player → primary role
│   {"Caps": {"primary": "MID", "games": 245}, ...}
├── role_baselines.json        # Role → average stats for normalization
└── skill_transfers.json       # Champion similarity from co-play patterns
    {"Aurora": {"similar": ["Ahri", "LeBlanc"], "scores": {...}}, ...}
```

**Reference Data:**
```
knowledge/
├── knowledge_base.json        # Champion metadata (positions, damage types, stats)
├── synergies.json             # Detailed synergy relationships
├── patch_dates.json           # Patch version → date mapping
└── rework_patch_mapping.json  # Champion rework history for data filtering
```

**CSV Data** (downloaded via `./scripts/download-data.sh v1.0.0`):
```
outputs/full_2024_2025_v2/csv/
├── champions.csv              # Champion metadata
├── draft_actions.csv          # All pick/ban actions (68K+)
├── games.csv                  # Game outcomes
├── player_game_stats.csv      # Player performance per game (34K+)
├── players.csv                # Player roster
├── series.csv                 # Series metadata
├── teams.csv                  # Team info
├── team_objectives.csv        # Team objective stats (v2 new)
└── tournaments.csv            # Tournament metadata (v2 new)
```

### 2.4 Automated Data Generation

To avoid manually mapping 189 champions:

| Component | Approach | Effort |
|-----------|----------|--------|
| **skill_transfers** | Co-play pattern mining | Automated |
| **champion_tags** | Riot Data Dragon API | Automated |
| **player_tendencies** | Computed from player_game_stats | Automated |
| **flex_champions** | Computed from v3.43+ role data | Automated |
| **Overrides** | Domain expert exceptions only | Small - only edge cases |

---

## 3. Flex Pick Resolution

When enemy picks a flex champion, estimate role probability to calculate matchup scores.

### 3.1 Resolution Priority

```
1. FILLED ROLES (Certainty)
   → If enemy already has a mid laner, Aurora ≠ MID

2. PLAYER IDENTITY (High confidence)
   → If Caps picked it, 95% chance it's MID

3. PICK SLOT HEURISTICS (Medium confidence)
   → Early pick (7-9) = more likely flex/priority role
   → Late pick (17-20) = more likely filling remaining role

4. BASE FLEX RATES (Fallback)
   → Aurora: 65% MID, 35% TOP (from historical data)
```

### 3.2 Algorithm

```python
def resolve_flex_role(
    champion: str,
    enemy_team_picks: list[Pick],
    player: str | None,
    pick_slot: int
) -> dict[str, float]:
    """Returns probability distribution: {"MID": 0.7, "TOP": 0.3}"""

    # Start with base flex rates
    probs = FLEX_CHAMPIONS.get(champion, {get_default_role(champion): 1.0})

    # 1. Eliminate filled roles (certainty)
    filled = get_filled_roles(enemy_team_picks)
    for role in filled:
        probs.pop(role, None)

    # 2. Weight by player's historical role
    if player:
        player_role = PLAYER_ROLES.get(player, {}).get("primary")
        if player_role and player_role in probs:
            probs[player_role] *= 3.0  # Strong weight toward player's role

    # 3. Normalize and return
    total = sum(probs.values())
    if total == 0:
        return {get_default_role(champion): 1.0}

    return {k: v / total for k, v in probs.items()}
```

### 3.3 Examples

**Certainty achieved:**
```
Enemy draft: [Rumble TOP, Viego JNG, ?, Jinx ADC, Thresh SUP]
Enemy picks: Aurora (slot 18)

Resolution:
1. Filled roles: TOP, JNG, ADC, SUP → Only MID remains
2. Result: {"MID": 1.0}
```

**Ambiguous scenario:**
```
Enemy draft: [?, Viego JNG, ?, Jinx ADC, Thresh SUP]
Enemy picks: Aurora (slot 8) by Caps

Resolution:
1. Filled: JNG, ADC, SUP → TOP and MID open
2. Base rates: {"MID": 0.65, "TOP": 0.35}
3. Caps is MID player → weight MID x3: {"MID": 1.95, "TOP": 0.35}
4. Normalize: {"MID": 0.85, "TOP": 0.15}
```

---

## 4. Matchup Scoring with Uncertainty

### 4.1 Weighted Expected Value

```python
def calculate_matchup_score(
    our_champion: str,
    our_role: str,
    enemy_picks: list[Pick],
    flex_resolutions: dict[str, dict[str, float]]
) -> tuple[float, float]:  # (score, confidence)
    """
    Returns matchup score and confidence.
    Confidence drops when facing flex uncertainty.
    """

    potential_opponents = []

    for pick in enemy_picks:
        role_probs = flex_resolutions.get(pick.champion, {pick.inferred_role: 1.0})

        if our_role in role_probs:
            prob = role_probs[our_role]
            matchup_wr = get_matchup_winrate(our_champion, pick.champion, our_role)
            potential_opponents.append((pick.champion, prob, matchup_wr))

    if not potential_opponents:
        return (0.5, 1.0)  # No opponent yet

    # Calculate expected matchup score
    expected_score = sum(prob * wr for _, prob, wr in potential_opponents)
    total_prob = sum(prob for _, prob, _ in potential_opponents)

    # Confidence = probability of most likely opponent
    max_prob = max(prob for _, prob, _ in potential_opponents)
    confidence = max_prob

    return (expected_score / total_prob, confidence)
```

### 4.2 Example Outputs

| Scenario | Matchup Score | Confidence | Interpretation |
|----------|---------------|------------|----------------|
| Syndra vs confirmed Azir MID | 0.52 | 1.0 | Slight edge, certain |
| Syndra vs Aurora (85% MID) | 0.48 | 0.85 | Slight disadvantage, fairly certain |
| Syndra vs Aurora (50/50) | 0.51 | 0.50 | Unclear, low confidence |

---

## 5. Surprise Pick Detection

### 5.1 Proficiency Scoring

```python
@dataclass
class ProficiencyScore:
    score: float           # 0.0 - 1.0
    confidence: str        # "HIGH" | "MEDIUM" | "LOW" | "NO_DATA"
    games_weighted: float  # Recency-weighted game count
    games_raw: int         # Actual game count
    contextual_strength: float | None
    surprise_eligible: bool


def evaluate_proficiency(
    player: str,
    champion: str,
    draft_context: DraftState,
    meta_data: MetaData
) -> ProficiencyScore:

    stats = get_player_champion_stats(player, champion)

    if stats.games_weighted >= 8:
        return ProficiencyScore(
            score=stats.win_rate,
            confidence="HIGH",
            games_weighted=stats.games_weighted,
            games_raw=stats.games_raw,
            contextual_strength=None,
            surprise_eligible=False
        )

    if stats.games_weighted >= 4:
        return ProficiencyScore(
            score=stats.win_rate,
            confidence="MEDIUM",
            ...
        )

    # LOW or NO_DATA - calculate contextual strength
    contextual = calculate_contextual_strength(champion, player, draft_context, meta_data)

    return ProficiencyScore(
        score=contextual.estimated_score,
        confidence="LOW" if stats.games_raw > 0 else "NO_DATA",
        games_weighted=stats.games_weighted,
        games_raw=stats.games_raw,
        contextual_strength=contextual.strength,
        surprise_eligible=contextual.strength > 0.65
    )
```

### 5.2 Contextual Strength Calculation

When direct proficiency data is lacking, use indirect signals:

```python
def calculate_contextual_strength(champion, player, draft_context, meta_data):
    scores = {
        "meta_tier": meta_data.get_tier_score(champion),
        "counter_value": calc_counter_value(champion, draft_context.enemy_picks),
        "synergy_value": calc_synergy_value(champion, draft_context.ally_picks),
        "style_fit": calc_style_fit(player, champion),
        "skill_transfer": calc_skill_transfer(player, champion),
    }

    strength = (
        scores["meta_tier"] * 0.25 +
        scores["counter_value"] * 0.25 +
        scores["synergy_value"] * 0.20 +
        scores["style_fit"] * 0.15 +
        scores["skill_transfer"] * 0.15
    )

    return ContextualScore(
        strength=strength,
        estimated_score=0.45 + (strength * 0.25),  # 45-70% range
        breakdown=scores
    )
```

### 5.3 Style Fit Calculation

**Player tendencies** (computed from player_game_stats):

```python
def compute_player_tendencies(player: str) -> PlayerTendencies:
    stats = get_player_all_games(player)

    return PlayerTendencies(
        aggression=calc_aggression(stats),      # kills, first_blood %, deaths
        carry_focus=calc_carry_focus(stats),    # damage_dealt, kill_participation
        vision_control=calc_vision(stats),      # vision_score per game
        early_game=calc_early_game(stats),      # first_kill involvement
    )
```

**Champion archetypes** (from Riot Data Dragon tags):

```python
def calc_style_fit(player: str, champion: str) -> float:
    champ_tags = CHAMPION_TAGS[champion]  # ["Mage", "Assassin"]

    # Get player's most-played champion tags
    player_pool = get_player_champion_pool(player)
    player_tags = Counter()
    for champ, games in player_pool.items():
        for tag in CHAMPION_TAGS.get(champ, []):
            player_tags[tag] += games

    # Score = tag overlap
    overlap = sum(player_tags.get(tag, 0) for tag in champ_tags)
    total = sum(player_tags.values())

    return overlap / total if total > 0 else 0.5
```

### 5.4 Skill Transfer Calculation

**Computed from co-play patterns** (players who play X tend to play Y):

```python
def compute_champion_similarity():
    """Mine skill transfers from player champion pools."""

    co_play_matrix = defaultdict(Counter)

    for player in all_players:
        pool = get_player_champions(player)
        for champ_a in pool:
            for champ_b in pool:
                if champ_a != champ_b:
                    co_play_matrix[champ_a][champ_b] += 1

    # Normalize to similarity scores
    return co_play_matrix


def calc_skill_transfer(player: str, champion: str) -> float:
    transfers = SKILL_TRANSFERS.get(champion, {}).get("similar_champions", [])
    if not transfers:
        return 0.5

    player_pool = get_player_champion_pool(player)

    best_score = 0.0
    for source_champ in transfers:
        if source_champ in player_pool:
            games = player_pool[source_champ]
            score = min(1.0, games / 10)
            best_score = max(best_score, score)

    return best_score
```

### 5.5 UI Surfacing

| Proficiency | Flag | Display |
|-------------|------|---------|
| HIGH (8+ games) | None | "Zeus: 23 games, 67% WR" |
| MEDIUM (4-7) | None | "Zeus: 5 games, 60% WR" |
| LOW + surprise eligible | `SURPRISE_PICK` | "2 stage games, but strong meta + style fit" |
| LOW + weak context | `LOW_CONFIDENCE` | "Limited data, consider safer options" |
| NO_DATA + surprise eligible | `SURPRISE_PICK` | "No stage games, but transfers from Ahri" |
| NO_DATA + weak context | `LOW_CONFIDENCE` | "No data, weak contextual support" |

---

## 6. Integrated Recommendation Scoring

### 6.1 Data Structures

```python
@dataclass
class PickRecommendation:
    champion_name: str
    role: str

    # Final scores
    overall_score: float        # 0.0 - 1.0
    confidence: float           # 0.0 - 1.0

    # Component scores
    meta_score: float           # Layer 1
    proficiency: ProficiencyScore  # Layer 3
    matchup_score: float        # Layer 4a
    matchup_confidence: float   # Flex uncertainty indicator
    synergy_score: float        # Layer 4b
    comp_fit_score: float       # Layer 4c

    # Flags
    flag: str | None            # "SURPRISE_PICK" | "LOW_CONFIDENCE" | None
    warnings: list[str]         # ["Uncertain matchup: Aurora may go TOP"]
    reasons: list[str]          # Positive reasons to pick
```

### 6.2 Scoring Algorithm

```python
def score_champion(
    champion: str,
    role: str,
    player: str,
    draft_state: DraftState,
    flex_resolutions: dict
) -> PickRecommendation:

    # Layer 1: Meta strength
    meta_score = META_STATS.get(champion, {}).get("tier_score", 0.5)

    # Layer 3: Player proficiency
    proficiency = evaluate_proficiency(player, champion, draft_state, META_DATA)

    # Layer 4a: Matchup with flex uncertainty
    matchup_score, matchup_confidence = calculate_matchup_score(
        our_champion=champion,
        our_role=role,
        enemy_picks=draft_state.enemy_picks,
        flex_resolutions=flex_resolutions
    )

    # Layer 4b & 4c
    synergy_score = calculate_synergy_score(champion, draft_state.ally_picks)
    comp_fit_score = calculate_comp_fit(champion, draft_state.ally_picks)

    # === WEIGHT ADJUSTMENT FOR UNCERTAINTY ===

    base_weights = {
        "meta": 0.15,
        "proficiency": 0.35,
        "matchup": 0.20,
        "synergy": 0.15,
        "comp_fit": 0.15
    }

    # Reduce matchup weight when uncertain, redistribute
    effective_matchup_weight = base_weights["matchup"] * matchup_confidence
    redistributed = base_weights["matchup"] * (1 - matchup_confidence)

    adjusted_weights = {
        "meta": base_weights["meta"] + redistributed * 0.3,
        "proficiency": base_weights["proficiency"] + redistributed * 0.4,
        "matchup": effective_matchup_weight,
        "synergy": base_weights["synergy"] + redistributed * 0.15,
        "comp_fit": base_weights["comp_fit"] + redistributed * 0.15
    }

    overall_score = (
        meta_score * adjusted_weights["meta"] +
        proficiency.score * adjusted_weights["proficiency"] +
        matchup_score * adjusted_weights["matchup"] +
        synergy_score * adjusted_weights["synergy"] +
        comp_fit_score * adjusted_weights["comp_fit"]
    )

    # === OVERALL CONFIDENCE ===
    prof_conf_value = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4, "NO_DATA": 0.2}
    overall_confidence = (
        prof_conf_value[proficiency.confidence] * 0.6 +
        matchup_confidence * 0.4
    )

    # === FLAGS & WARNINGS ===
    flag = None
    warnings = []
    reasons = []

    if proficiency.surprise_eligible:
        flag = "SURPRISE_PICK"
        reasons.append(f"Strong meta pick ({meta.get('tier')}-tier)")
    elif proficiency.confidence in ["LOW", "NO_DATA"]:
        flag = "LOW_CONFIDENCE"
        warnings.append(f"Only {proficiency.games_raw} stage games")

    if matchup_confidence < 0.7:
        warnings.append(f"Uncertain matchup: enemy flex pick role unclear")

    return PickRecommendation(...)
```

### 6.3 Key Design Decisions

| Decision | Approach |
|----------|----------|
| Low matchup confidence | Reduce matchup weight, redistribute to certain factors |
| Overall confidence | Blend proficiency (60%) + matchup confidence (40%) |
| Flags | One flag per recommendation (most important issue) |
| Warnings | Multiple allowed (shown as list in UI) |
| Transparency | Always show confidence + warnings to user |

---

## 7. Implementation Plan

### 7.1 File Structure

```
backend/src/ban_teemo/
├── services/
│   ├── recommendation_engine.py   # Main scoring logic
│   ├── flex_resolver.py           # Flex pick probability
│   ├── proficiency_scorer.py      # Surprise pick detection
│   └── analytics/
│       ├── meta_stats.py          # Layer 1: Champion meta
│       ├── player_tendencies.py   # Layer 2: Player style
│       ├── matchup_calculator.py  # Layer 4a: Matchups
│       ├── synergy_calculator.py  # Layer 4b: Synergies
│       └── comp_analyzer.py       # Layer 4c: Comp archetypes
│
├── data/
│   └── precompute.py              # Generate knowledge JSONs

knowledge/                          # Pre-computed data
├── flex_champions.json
├── player_roles.json
├── skill_transfers.json
├── skill_transfer_overrides.json
├── champion_tags.json
└── player_tendencies.json
```

### 7.2 Data Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     ONE-TIME / PERIODIC                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Fetch data from GRID API using fetch_lol_series_v3.py       │
│  2. Export to CSVs (outputs/full_2024_2025_v2/csv/)             │
│  3. Run precompute.py to generate knowledge/*.json              │
│  4. Create GitHub release: data-vX.Y.Z                          │
│  5. Commit updated knowledge/*.json to repo                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       DEV SETUP                                 │
├─────────────────────────────────────────────────────────────────┤
│  ./scripts/download-data.sh v1.0.0                              │
│  Downloads CSVs + raw JSONs to outputs/full_2024_2025_v2/       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        AT STARTUP                               │
├─────────────────────────────────────────────────────────────────┤
│  Load all knowledge/*.json into memory                          │
│  Initialize DuckDB connection to outputs/*/csv/ files           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       AT REQUEST TIME                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Resolve flex picks (fast - in-memory lookups)               │
│  2. Score candidates (DuckDB queries for matchups/synergies)    │
│  3. Return recommendations with confidence + warnings           │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Implementation Phases

| Phase | Tasks | Depends On |
|-------|-------|------------|
| **1. Data** | Update fetch script, re-fetch v3.43+, export | GRID API key |
| **2. Precompute** | Build knowledge JSONs from data | Phase 1 |
| **3. Core Engine** | `flex_resolver.py`, `proficiency_scorer.py` | Phase 2 |
| **4. Analytics** | Matchup, synergy, comp calculators | Phase 2 |
| **5. Integration** | `recommendation_engine.py` | Phase 3-4 |
| **6. API** | Update endpoints to use new engine | Phase 5 |

### 7.4 GraphQL Query Update

Add to v3.43+ query in `fetch_lol_series_v3.py`:

```graphql
players {
  id name participationStatus
  character { id name }
  kills deaths killAssistsGiven firstKill
  ... on GamePlayerStateLol {
    roles              # NEW - actual position played
    netWorth           # NEW - economic indicator
    moneyPerMinute     # NEW - v3.36+
    objectives         # NEW - player-level objectives
    damageDealt
    experiencePoints
    visionScore
    kdaRatio
    killParticipation
  }
}
```

---

## 8. Open Questions

1. **Domain expert validation:** Should overrides file be reviewed before launch?
2. **Confidence thresholds:** Is 0.7 the right cutoff for "uncertain" matchups?
3. **Weight tuning:** Base weights (0.15/0.35/0.20/0.15/0.15) may need adjustment after testing
4. **Caching:** Should matchup/synergy queries be cached, or is DuckDB fast enough?

---

*Design Version: 1.0 | January 2026*
