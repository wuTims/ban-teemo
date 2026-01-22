# LoL Draft Assistant - Hackathon Spec v2

**Category:** AI Draft Assistant / Draft Predictor  
**Timeline:** 1 month  
**Team:** 1 LoL domain expert, 2 software engineers, AI assistance  
**Required:** GRID API, JetBrains IDE

---

## 1. Hackathon Strategy

### 1.1 Judging Criteria Mapping

| Criteria | Weight | Our Approach |
|----------|--------|--------------|
| **Technological Implementation** | 25% | Clean architecture, layered analytics, quality code with tests |
| **Design** | 25% | Polished draft UI with real-time updates, intuitive recommendation cards |
| **Potential Impact** | 25% | Coaches/analysts save hours of prep; democratizes pro-level draft analysis |
| **Quality of Idea** | 25% | LLM explains *why* picks matter, "Surprise Pick" detection, layered confidence |

### 1.2 Demo Strategy: Historical Replay as "Live"

Since we can't guarantee a live match during judging, we'll build a **replay system** that:

1. Pre-ingests 50+ compelling historical series (upsets, comebacks, interesting drafts)
2. Replays draft actions with configurable delays (e.g., 3-5 seconds between picks)
3. UI behaves **identically** to true live mode
4. Recommendations generate in real-time as actions arrive

**Why this works:**
- Demonstrates all live functionality with zero risk
- Can select narratively interesting drafts ("watch how we would've advised against this upset")
- Judge sees the same experience a user would during a real match

**For video:** Record a "live" replay with voiceover explaining recommendations as they appear.

---

## 2. Feature Prioritization

### 2.1 MVP (Must Have - Weeks 1-3)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CORE DRAFT EXPERIENCE                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │  BLUE SIDE  │  │  BAN TRACK  │  │        RED SIDE             │  │
│  │  Team BDS   │  │  ────────── │  │        G2 Esports           │  │
│  │             │  │  B1: Draven │  │                             │  │
│  │  Picks:     │  │  R1: Cait   │  │  Picks:                     │  │
│  │  [Kalista]  │  │  B2: Bel'V  │  │  [Neeko]                    │  │
│  │  [Nocturne] │  │  R2: Ashe   │  │  [Aphelios]                 │  │
│  │  [Akali]    │  │  ...        │  │  [Renata]                   │  │
│  │  [ ? ]      │  │             │  │  [ ? ]                      │  │
│  │  [ ? ]      │  │             │  │  [ ? ]                      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              RECOMMENDATION PANEL                            │    │
│  │  ─────────────────────────────────────────────────────────  │    │
│  │  🎯 TOP PICK: Renekton (78% confidence)                     │    │
│  │     • Adam plays this 23 games, 67% WR                      │    │
│  │     • Counters enemy Neeko top                              │    │
│  │     • Strong synergy with Nocturne dive comp                │    │
│  │                                                             │    │
│  │  🎲 SURPRISE PICK: Aurora (55% confidence)                  │    │
│  │     • S-tier meta (78% presence)                            │    │
│  │     • Only 2 stage games, but fits playstyle               │    │
│  │                                                             │    │
│  │  📊 Also Consider:                                          │    │
│  │     3. Jax (71%) - Scales well, Adam comfort pick           │    │
│  │     4. Gragas (65%) - Flex potential, team fight            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  💡 AI INSIGHT                                               │    │
│  │  "G2 has banned 3 ADCs - they're targeting Hans Sama's      │    │
│  │   pool. Consider prioritizing a hypercarry if it gets       │    │
│  │   through ban phase 2."                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**MVP Features:**
| Feature | Description | Effort |
|---------|-------------|--------|
| Draft Tracker UI | Real-time ban/pick visualization | M |
| Layered Analytics | Meta, tendencies, proficiency, synergies | L |
| Pick Recommendations | Top 3-5 suggestions with confidence + flags | M |
| Ban Recommendations | Opponent's highest-impact champions | S |
| Surprise Pick Detection | Low sample but contextually strong picks | M |
| Replay Mode | Step through historical drafts | M |
| LLM Insights | Natural language draft commentary | M |

### 2.2 Stretch Goals (Week 4 - if time)

| Feature | Demo Impact | Effort |
|---------|-------------|--------|
| **Post-Game Analysis** | "Here's what optimal draft would've been" | M |
| **What-If Simulator** | Drag-drop to explore alternate drafts | L |
| **Win Probability** | Live % that updates with each pick | M |
| **Head-to-Head History** | "Last 5 times these teams met..." | S |

### 2.3 Explicitly Out of Scope

- Mobile app
- User accounts/auth
- Solo queue data integration
- Full historical ingestion pipeline
- Production deployment/scaling
- Multi-language support

---

## 3. Technical Architecture

### 3.1 Tech Stack

```yaml
Backend:
  - Python 3.12+
  - FastAPI
  - uv (package management)
  - DuckDB (zero-config analytics engine)
  - websockets (FastAPI's built-in WebSocket support)
  - httpx (async HTTP for LLM API)

Frontend:
  - React 18+
  - TypeScript
  - shadcn/ui + Tailwind
  - Vite (build tool)
  - Native WebSocket API

LLM:
  - Llama 3.1 70B via Groq or Together.ai
  - ~$0.90/1M tokens
  - Fast inference for real-time insights

Data:
  - Riot Data Dragon (champion icons)
  - GRID API (match data) - already extracted to CSV
  - DuckDB querying CSV files directly (zero ETL)
  - Domain expert knowledge files (JSON/MD)
```

### 3.2 System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                            │
│   Draft Board │ Recommendation Cards │ AI Insight Panel           │
└───────────────────────────┬────────────────────────────────────────┘
                            │ WebSocket / REST
                            ▼
┌────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                           │
│  /draft/live/{series_id}     - Stream draft updates                │
│  /draft/replay/{series_id}   - Replay historical draft             │
│  /recommend/pick             - Get pick recommendations            │
│  /recommend/ban              - Get ban recommendations             │
│  /insight/generate           - LLM-powered analysis                │
│  /analysis/post-game         - Post-draft analysis (stretch)       │
└───────────────────────────┬────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬────────────────────┐
        ▼                   ▼                   ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│  GRID API    │    │   DuckDB     │    │  Llama 3.1   │    │ Domain Expert │
│  (Live Data) │    │  (Analytics) │    │  (Insights)  │    │ Knowledge     │
│              │    │  ↓ queries   │    │  via Groq    │    │ (JSON/MD)     │
└──────────────┘    │  CSV Files   │    └──────────────┘    └───────────────┘
                    └──────────────┘
```

### 3.3 Domain Expert Knowledge Structure

```
knowledge/
├── system_prompt.md           # Core analyst persona + rules
├── champion_knowledge.json    # Champion-specific notes
│   {
│     "Ksante": {
│       "flex_roles": ["top"],
│       "archetype_tags": ["tank", "teamfight", "engage"],
│       "skill_transferable_from": ["Camille", "Jax"],
│       "rework_date": null,
│       "notes": "Pro-skewed champion, hard to execute"
│     }
│   }
├── team_profiles.json         # Team tendencies/identities
│   {
│     "G2 Esports": {
│       "playstyle": "aggressive",
│       "early_game_focus": 0.8,
│       "signature_strategies": ["early dive", "roaming support"],
│       "draft_tendencies": "prioritizes mid lane counterpick"
│     }
│   }
├── player_hidden_pools.json   # Solo queue / scrim knowledge
│   {
│     "Caps": {
│       "known_comfort_picks": ["Aurora", "Qiyana", "Yone"],
│       "notes": "Spams these in Korean solo queue bootcamps"
│     }
│   }
├── comp_archetypes.json       # Composition definitions
│   {
│     "dive": {
│       "markers": ["Nocturne", "Renekton", "Akali", "Camille", "Diana"],
│       "win_condition": "Pick off carries with coordinated engage",
│       "countered_by": ["disengage", "protect"]
│     }
│   }
├── meta_context.md            # Current meta summary (2025)
├── draft_rules.md             # Phase-by-phase strategy rules
└── champion_reworks.json      # Rework dates for data filtering
    {
      "Skarner": "2024-03-15",
      "Aurelion Sol": "2023-02-08"
    }
```

---

## 4. Layered Analysis System

### 4.1 The Four Layers

The core insight: **different analyses have different time sensitivities.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS LAYERS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: CHAMPION META STRENGTH                                            │
│  ─────────────────────────────────────────────────────────────────────     │
│  Time Range: 2025 only (last 3-6 months)                                   │
│  Metrics: Pick rate, ban rate, win rate (global pro)                        │
│  Why recent: Patches completely change champion viability                   │
│  Refresh: Recalculate after major patches                                   │
│                                                                             │
│  Output: S/A/B/C/D tier + presence %                                       │
│  Example: "Ksante is S-tier (72% presence, 54% WR in 2025)"                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 2: PLAYER TENDENCIES                                                 │
│  ─────────────────────────────────────────────────────────────────────     │
│  Time Range: 2023-2025 (aggregate)                                          │
│  Metrics: Playstyle indicators                                              │
│    - Early game aggression (CSD@15, FB%)                                   │
│    - Vision style (vision score/min)                                       │
│    - Risk tolerance (deaths/game, forward %)                               │
│  Why more history: Player habits persist across metas                       │
│                                                                             │
│  Output: Player profile with tendencies                                     │
│  Example: "Caps plays aggressive (avg +15 CSD@15, 68% first blood)"        │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 3: PLAYER-CHAMPION PROFICIENCY                                       │
│  ─────────────────────────────────────────────────────────────────────     │
│  Time Range: 2023-2025 with RECENCY WEIGHTING                              │
│  Weighting:                                                                 │
│    - Recent (0-12 months): 100% weight                                     │
│    - Older (12-24 months): 50% weight                                      │
│    - Ancient (24+ months): 25% weight                                      │
│                                                                             │
│  Metrics: Games played, win rate, KDA, damage share                         │
│  Sample size flags:                                                         │
│    - 10+ games: High confidence                                            │
│    - 5-9 games: Medium confidence                                          │
│    - 1-4 games: Low confidence (may flag as surprise pick)                 │
│    - 0 games: No data (rely on transferable skills)                        │
│                                                                             │
│  Output: Proficiency score + confidence level                               │
│  Example: "Zeus on Yone: 12 games (weighted), 67% WR, HIGH confidence"     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 4: CHAMPION RELATIONSHIPS                                            │
│  ─────────────────────────────────────────────────────────────────────     │
│  Time Range: 2023-2025 (need volume for statistical significance)          │
│  Filter: Exclude pre-rework data for reworked champions                    │
│                                                                             │
│  Sub-layers:                                                                │
│    4a. Synergies - Champions that win more together                        │
│    4b. Counters - Lane/role-specific matchup advantages                    │
│    4c. Comp fit - How champion fits into archetype                         │
│                                                                             │
│  Output: Synergy/counter scores relative to baseline                        │
│  Example: "Nocturne + Renekton: +8% WR vs expected (32 games)"             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Time Ranges Summary

| Analysis Type | Time Range | Reason |
|---------------|------------|--------|
| Champion Meta Tier | 2025 (3-6 months) | Patches change everything |
| Player Tendencies | 2023-2025 | Habits are stable |
| Player-Champion Stats | 2023-2025 weighted | Balance sample size + recency |
| Synergies & Counters | 2023-2025 | Need volume; kits rarely change |
| Series for Replay | 2024-2025 | Audience recognition, current rosters |

### 4.3 Recency Weighting Formula

```python
def calculate_weighted_stats(player_id: str, champion_id: str, games: list[Game]) -> WeightedStats:
    """
    Apply recency weighting to player-champion statistics.
    """
    now = datetime.now()
    
    weighted_games = 0.0
    weighted_wins = 0.0
    weighted_kda_sum = 0.0
    
    for game in games:
        age_months = (now - game.date).days / 30
        
        # Determine weight based on age
        if age_months <= 12:
            weight = 1.0
        elif age_months <= 24:
            weight = 0.5
        else:
            weight = 0.25
        
        weighted_games += weight
        weighted_wins += weight if game.won else 0
        weighted_kda_sum += game.kda * weight
    
    return WeightedStats(
        games_weighted=weighted_games,
        games_raw=len(games),
        win_rate=weighted_wins / weighted_games if weighted_games > 0 else None,
        avg_kda=weighted_kda_sum / weighted_games if weighted_games > 0 else None,
        confidence=calculate_confidence(weighted_games)
    )

def calculate_confidence(weighted_games: float) -> str:
    if weighted_games >= 8:
        return "HIGH"
    elif weighted_games >= 4:
        return "MEDIUM"
    elif weighted_games >= 1:
        return "LOW"
    else:
        return "NO_DATA"
```

---

## 5. Surprise Pick Detection

### 5.1 Logic

A "surprise pick" is flagged when:
- Player has low stage games on champion (< 3)
- BUT other signals are strong (meta tier, counter value, synergy, style fit)

```python
def evaluate_pick(
    player: Player,
    champion: Champion,
    draft_state: DraftState,
    meta_data: MetaData,
    knowledge: DomainKnowledge
) -> PickEvaluation:
    
    # Layer 1: Meta strength
    meta_score = meta_data.get_tier_score(champion)  # 0-1
    
    # Layer 2: Player style fit
    style_fit = calculate_style_fit(
        player.tendencies,
        champion.playstyle_tags,
        knowledge.skill_transfers.get(champion, [])
    )
    
    # Layer 3: Direct proficiency
    proficiency = get_weighted_proficiency(player, champion)
    
    # Layer 4: Draft context
    counter_score = calculate_counter_value(champion, draft_state.enemy_picks)
    synergy_score = calculate_synergy_value(champion, draft_state.ally_picks)
    comp_fit = calculate_comp_fit(champion, draft_state.ally_picks)
    
    # Check for hidden pool (domain expert knowledge)
    in_hidden_pool = champion.name in knowledge.hidden_pools.get(player.name, [])
    
    # SURPRISE PICK DETECTION
    if proficiency.confidence in ["LOW", "NO_DATA"]:
        contextual_strength = (
            meta_score * 0.3 +
            counter_score * 0.25 +
            synergy_score * 0.25 +
            style_fit * 0.2
        )
        
        if contextual_strength > 0.65 or in_hidden_pool:
            return PickEvaluation(
                champion=champion,
                confidence=0.50 + (contextual_strength * 0.2),  # 50-70%
                flag="SURPRISE_PICK",
                reasons=[
                    f"Low stage games ({proficiency.games_raw})",
                    f"Strong meta pick ({meta_score:.0%} tier score)",
                    f"Good draft fit (synergy: {synergy_score:.0%})",
                    f"Style match: {get_style_explanation(player, champion)}"
                ],
                hidden_pool_note=knowledge.hidden_pools.get(player.name, {}).get("notes") if in_hidden_pool else None
            )
        else:
            return PickEvaluation(
                champion=champion,
                confidence=0.25 + (contextual_strength * 0.15),  # 25-40%
                flag="LOW_CONFIDENCE",
                reasons=[
                    f"Only {proficiency.games_raw} games on record",
                    "Limited contextual justification",
                    "Consider safer alternatives"
                ]
            )
    
    # Standard evaluation for sufficient sample size
    base_confidence = (
        proficiency.win_rate * 0.35 +
        meta_score * 0.15 +
        style_fit * 0.15 +
        counter_score * 0.20 +
        synergy_score * 0.15
    )
    
    return PickEvaluation(
        champion=champion,
        confidence=base_confidence,
        flag=None,
        reasons=generate_standard_reasons(proficiency, meta_score, counter_score, synergy_score)
    )
```

### 5.2 UI Representation

```
┌─────────────────────────────────────────────────────────────────┐
│  🎯 TOP PICK: Renekton                                          │
│  Confidence: 78% ████████████████████░░░░░ HIGH                │
│                                                                 │
│  📊 Stats:                                                      │
│  • Adam: 23 games (weighted), 67% WR                           │
│  • Counters Neeko: 58% WR in matchup                           │
│  • Dive synergy with Nocturne: +12% WR                         │
│                                                                 │
│  💬 "Strong early pressure enables Nocturne's weak pre-6.      │
│      Double-dash engage with Akali creates unavoidable picks." │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🎲 SURPRISE PICK: Aurora                                       │
│  Confidence: 58% ████████████████░░░░░░░░░ MEDIUM              │
│                                                                 │
│  ⚠️ Limited data: 2 stage games on record                      │
│                                                                 │
│  ✅ Why it could work:                                          │
│  • S-tier in current meta (78% presence)                        │
│  • Hard counters enemy Azir mid                                 │
│  • Caps has similar mechanics on Ahri (67% WR, 23 games)       │
│  • Known solo queue comfort pick                                │
│                                                                 │
│  💬 "High-risk, high-reward. Caps has shown willingness to     │
│      debut picks in playoffs. Aurora's kit mirrors his          │
│      Ahri/LeBlanc playmaking style."                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ⚠️ LOW CONFIDENCE: Heimerdinger                                │
│  Confidence: 32% ████████░░░░░░░░░░░░░░░░░ LOW                 │
│                                                                 │
│  ❌ Concerns:                                                   │
│  • 0 stage games for this player                                │
│  • B-tier meta pick (34% presence)                              │
│  • Poor synergy with dive composition                           │
│  • No style match indicators                                    │
│                                                                 │
│  💬 "Statistically unsupported. Consider Jayce or Rumble       │
│      for similar lane pressure with better team synergy."       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Deriving Analytics from Data

### 6.1 Comp Archetype Detection

```python
# Pseudocode: Identify comp archetype from draft

COMP_ARCHETYPES = {
    "dive": {
        "markers": ["Nocturne", "Renekton", "Akali", "Camille", "Diana", "Vi", "Jarvan IV"],
        "required_count": 2,
        "description": "Coordinated engage onto backline"
    },
    "poke": {
        "markers": ["Jayce", "Zoe", "Ezreal", "Xerath", "Varus", "Nidalee", "Corki"],
        "required_count": 2,
        "description": "Siege and whittle before fights"
    },
    "protect": {
        "markers": ["Lulu", "Kog'Maw", "Jinx", "Braum", "Tahm Kench", "Orianna"],
        "required_count": 2,
        "description": "Funnel resources into hypercarry"
    },
    "teamfight": {
        "markers": ["Orianna", "Jarvan IV", "Kennen", "Rumble", "Miss Fortune", "Amumu"],
        "required_count": 2,
        "description": "Win 5v5 with AoE combinations"
    },
    "splitpush": {
        "markers": ["Fiora", "Tryndamere", "Jax", "Camille", "Shen"],
        "required_count": 1,
        "description": "Side lane pressure with TP threat"
    }
}

def identify_comp_archetype(team_picks: list[str]) -> CompAnalysis:
    scores = {}
    for archetype, config in COMP_ARCHETYPES.items():
        matches = [c for c in team_picks if c in config["markers"]]
        if len(matches) >= config["required_count"]:
            scores[archetype] = len(matches) / len(config["markers"])
    
    if not scores:
        return CompAnalysis(primary="flexible", secondary=None, confidence=0.3)
    
    sorted_archetypes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    return CompAnalysis(
        primary=sorted_archetypes[0][0],
        secondary=sorted_archetypes[1][0] if len(sorted_archetypes) > 1 else None,
        confidence=sorted_archetypes[0][1],
        description=COMP_ARCHETYPES[sorted_archetypes[0][0]]["description"]
    )
```

### 6.2 Meta Tier Calculation

```sql
-- Calculate champion meta tier from recent data
WITH recent_games AS (
    SELECT 
        da.champion_id,
        c.name as champion_name,
        da.action_type,
        CASE WHEN g.winner_team_id = da.team_id THEN 1 ELSE 0 END as won
    FROM draft_actions da
    JOIN games g ON da.game_id = g.id
    JOIN series s ON g.series_id = s.id
    JOIN champions c ON da.champion_id = c.id
    WHERE s.match_date >= date('now', '-6 months')
),
champion_stats AS (
    SELECT
        champion_id,
        champion_name,
        COUNT(*) as total_appearances,
        SUM(CASE WHEN action_type = 'pick' THEN 1 ELSE 0 END) as picks,
        SUM(CASE WHEN action_type = 'ban' THEN 1 ELSE 0 END) as bans,
        AVG(CASE WHEN action_type = 'pick' THEN won ELSE NULL END) as win_rate
    FROM recent_games
    GROUP BY champion_id, champion_name
),
total_games AS (
    SELECT COUNT(DISTINCT g.id) as game_count
    FROM games g
    JOIN series s ON g.series_id = s.id
    WHERE s.match_date >= date('now', '-6 months')
)
SELECT
    cs.champion_name,
    cs.total_appearances,
    ROUND(cs.total_appearances * 100.0 / (tg.game_count * 2), 1) as presence_pct,
    cs.picks,
    cs.bans,
    ROUND(cs.win_rate * 100, 1) as win_rate_pct,
    CASE
        WHEN cs.total_appearances * 100.0 / (tg.game_count * 2) >= 70 THEN 'S'
        WHEN cs.total_appearances * 100.0 / (tg.game_count * 2) >= 50 THEN 'A'
        WHEN cs.total_appearances * 100.0 / (tg.game_count * 2) >= 30 THEN 'B'
        WHEN cs.total_appearances * 100.0 / (tg.game_count * 2) >= 15 THEN 'C'
        ELSE 'D'
    END as tier
FROM champion_stats cs, total_games tg
ORDER BY presence_pct DESC;
```

### 6.3 Synergy Detection from Game Data

```sql
-- Find champion pairs with above-baseline win rates
WITH team_comps AS (
    SELECT 
        g.id as game_id,
        da.team_id,
        g.winner_team_id,
        GROUP_CONCAT(c.name, ',') as champions
    FROM draft_actions da
    JOIN games g ON da.game_id = g.id
    JOIN champions c ON da.champion_id = c.id
    WHERE da.action_type = 'pick'
    GROUP BY g.id, da.team_id
),
champion_pairs AS (
    SELECT 
        da1.champion_id as champ_a,
        da2.champion_id as champ_b,
        c1.name as champ_a_name,
        c2.name as champ_b_name,
        da1.team_id,
        g.winner_team_id
    FROM draft_actions da1
    JOIN draft_actions da2 ON da1.game_id = da2.game_id 
        AND da1.team_id = da2.team_id
        AND da1.champion_id < da2.champion_id
    JOIN games g ON da1.game_id = g.id
    JOIN champions c1 ON da1.champion_id = c1.id
    JOIN champions c2 ON da2.champion_id = c2.id
    WHERE da1.action_type = 'pick' AND da2.action_type = 'pick'
)
SELECT
    champ_a_name,
    champ_b_name,
    COUNT(*) as games_together,
    SUM(CASE WHEN team_id = winner_team_id THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN team_id = winner_team_id THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND((AVG(CASE WHEN team_id = winner_team_id THEN 1.0 ELSE 0.0 END) - 0.5) * 100, 1) as synergy_delta
FROM champion_pairs
GROUP BY champ_a, champ_b
HAVING COUNT(*) >= 5
ORDER BY synergy_delta DESC
LIMIT 50;
```

---

## 7. LLM Integration

### 7.1 Model Selection

| Model | Provider | Cost | Use Case |
|-------|----------|------|----------|
| **Llama 3.1 70B** | Groq | ~$0.59/1M in, $0.79/1M out | Primary insights |
| **Llama 3.1 8B** | Groq (free tier) | Free | Development/testing |
| **Mixtral 8x7B** | Together.ai | ~$0.60/1M | Fallback option |

**Recommendation:** Start with Groq free tier (Llama 3.1 8B) for development, upgrade to 70B for final demo.

### 7.2 Prompt Structure

```python
def build_insight_prompt(
    draft_state: DraftState,
    team_profiles: dict,
    meta_context: str,
    domain_rules: str
) -> str:
    return f"""You are an expert League of Legends analyst providing real-time draft insights for professional matches.

## Your Expertise
{domain_rules}

## Current Meta Context (2025)
{meta_context}

## Team Profiles
BLUE SIDE - {draft_state.blue_team.name}:
{team_profiles.get(draft_state.blue_team.name, "No profile available")}

RED SIDE - {draft_state.red_team.name}:
{team_profiles.get(draft_state.red_team.name, "No profile available")}

## Current Draft State
Phase: {draft_state.phase}
Action: {draft_state.action_number}/20

Blue Bans: {', '.join(draft_state.blue_bans) or 'None yet'}
Red Bans: {', '.join(draft_state.red_bans) or 'None yet'}
Blue Picks: {', '.join(draft_state.blue_picks) or 'None yet'}
Red Picks: {', '.join(draft_state.red_picks) or 'None yet'}

Next to act: {draft_state.next_team} ({draft_state.next_action_type})

## Recent Action
{draft_state.last_action_description}

## Your Task
Provide a 1-2 sentence insight that:
1. Explains what the recent action reveals about team strategy
2. Identifies a non-obvious consideration for the next pick/ban
3. References specific player tendencies or team patterns when relevant

Be specific, confident, and actionable. No hedging language.
"""
```

### 7.3 Domain Knowledge Files

**meta_context.md:**
```markdown
# 2025 Pro Meta Summary

## High Priority Champions (S-Tier)
- TOP: Ksante, Jax, Renekton, Rumble
- JNG: Viego, Lee Sin, Maokai, Elise
- MID: Azir, Orianna, Ahri, Syndra
- ADC: Kai'Sa, Jinx, Varus, Kalista
- SUP: Nautilus, Thresh, Renata Glasc, Milio

## Meta Characteristics
- ADC is high-agency; strong ADCs can carry
- Support roaming defines early game
- Dragon soul is game-deciding; teams draft for dragon control
- Dive comps are favored over poke comps
- Flex picks (Neeko, Aurora, Tristana) are highly valued

## Draft Priorities
- First pick should be contested S-tier OR flex pick
- Ban phase 2 is for target bans against specific players
- Red side advantage: counter-pick for last pick
- Blue side advantage: first pick + response to red's picks
```

**draft_rules.md:**
```markdown
# Draft Strategy Rules

## Ban Phase 1 (Bans 1-6)
- Ban S-tier champions that don't fit your comp
- Target opponent's one-trick champions
- Remove hard counters to your planned picks

## Pick Phase 1 (Picks 7-12)  
- Blue first pick: Highest priority contested champion or flex
- Red picks 8-9: Counter blue's first pick OR secure two strong champions
- Blue picks 10-11: Round out composition needs
- Red pick 12: Setup for ban phase 2 information

## Ban Phase 2 (Bans 13-16)
- Target specific players based on what's left
- Remove counters to your existing picks
- Deny obvious synergy completions

## Pick Phase 2 (Picks 17-20)
- Fill remaining roles
- Red pick 17: Deny blue's obvious choice
- Blue picks 18-19: Counter red or complete synergy
- Red pick 20: Hard counter for lane matchup

## Key Principles
- Never reveal your comp too early
- Flex picks force opponent to guess
- Comfort > counter (usually)
- Mental game: ban comfort picks to tilt
```

---

## 8. Data Model

### 8.1 DuckDB + CSV Architecture

**Why DuckDB over SQLite?**

| Criteria | SQLite | DuckDB |
|----------|--------|--------|
| SQL syntax | ✅ Standard | ✅ PostgreSQL-compatible |
| Reads CSV directly | ❌ Requires import | ✅ Zero ETL |
| Returns DataFrames | ❌ Manual conversion | ✅ Native `.df()` |
| Columnar analytics | ❌ Row-based | ✅ Optimized aggregations |
| Setup complexity | Medium | **Zero config** |

**Architecture Decision:** CSV files are the source of truth. DuckDB queries them directly with no import/seed step required. For performance-critical paths, we can optionally persist to a `.duckdb` file.

```
outputs/full_2024_2025/csv/          DuckDB Engine
├── teams.csv          ───────────►  ┌──────────────────┐
├── players.csv        ───────────►  │  SQL Queries     │
├── champions.csv      ───────────►  │  (PostgreSQL     │
├── series.csv         ───────────►  │   compatible)    │
├── games.csv          ───────────►  │                  │
├── draft_actions.csv  ───────────►  │  Returns:        │
└── player_game_stats.csv ────────►  │  pandas DataFrame│
                                     └──────────────────┘
```

### 8.2 CSV Schema (Source of Truth)

These files already exist in `outputs/full_2024_2025/csv/`:

```sql
-- teams.csv (57 rows)
-- Columns: id, name

-- players.csv (445 rows)
-- Columns: id, name, team_id, team_name

-- champions.csv (162 rows)
-- Columns: id, name

-- series.csv (1,482 rows)
-- Columns: id, blue_team_id, red_team_id, format, match_date

-- games.csv (3,436 rows)
-- Columns: id, series_id, game_number, winner_team_id, duration_seconds, patch_version

-- draft_actions.csv (68,529 rows)
-- Columns: game_id, sequence, action_type, team_id, champion_id, champion

-- player_game_stats.csv (34,416 rows)
-- Columns: game_id, player_id, player_name, team_id, team_side, champion_id,
--          champion_name, role, kills, deaths, assists, kda_ratio,
--          damage_dealt, vision_score, kill_participation, first_kill, team_won
```

### 8.3 DuckDB Query Patterns

**Direct CSV Querying (Zero ETL):**

```python
import duckdb

DATA_PATH = "outputs/full_2024_2025/csv"

# Query CSV files directly - no import needed
result = duckdb.query(f"""
    SELECT champion, COUNT(*) as picks
    FROM '{DATA_PATH}/draft_actions.csv'
    WHERE action_type = 'pick'
    GROUP BY champion
    ORDER BY picks DESC
""").df()  # Returns pandas DataFrame
```

**Joining Multiple CSVs:**

```python
# Self-join for matchup analysis
counters = duckdb.query(f"""
    SELECT
        pgs1.champion_name as champion,
        pgs2.champion_name as enemy,
        COUNT(*) as games,
        ROUND(AVG(CASE WHEN pgs1.team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
    FROM '{DATA_PATH}/player_game_stats.csv' pgs1
    JOIN '{DATA_PATH}/player_game_stats.csv' pgs2
        ON pgs1.game_id = pgs2.game_id
        AND pgs1.role = pgs2.role
        AND pgs1.team_side != pgs2.team_side
    WHERE pgs1.role = 'MID'
    GROUP BY pgs1.champion_name, pgs2.champion_name
    HAVING COUNT(*) >= 5
""").df()
```

### 8.4 Computed Analytics (Views or Materialized)

Instead of pre-computed tables, we use DuckDB views or on-demand queries:

```python
# Champion Meta Stats - computed on demand
def get_champion_meta():
    return duckdb.query(f"""
        WITH total_games AS (
            SELECT COUNT(DISTINCT id) as game_count
            FROM '{DATA_PATH}/games.csv'
        ),
        pick_stats AS (
            SELECT champion, COUNT(*) as picks
            FROM '{DATA_PATH}/draft_actions.csv'
            WHERE action_type = 'pick'
            GROUP BY champion
        ),
        ban_stats AS (
            SELECT champion, COUNT(*) as bans
            FROM '{DATA_PATH}/draft_actions.csv'
            WHERE action_type = 'ban'
            GROUP BY champion
        ),
        win_stats AS (
            SELECT champion_name,
                   COUNT(*) as games,
                   SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins
            FROM '{DATA_PATH}/player_game_stats.csv'
            GROUP BY champion_name
        )
        SELECT
            COALESCE(p.champion, b.champion) as champion,
            COALESCE(p.picks, 0) as picks,
            COALESCE(b.bans, 0) as bans,
            COALESCE(p.picks, 0) + COALESCE(b.bans, 0) as presence,
            ROUND((COALESCE(p.picks, 0) + COALESCE(b.bans, 0)) * 100.0 / (tg.game_count * 2), 1) as presence_pct,
            COALESCE(w.games, 0) as games_played,
            ROUND(COALESCE(w.wins, 0) * 100.0 / NULLIF(w.games, 0), 1) as win_rate,
            CASE
                WHEN (COALESCE(p.picks, 0) + COALESCE(b.bans, 0)) * 100.0 / (tg.game_count * 2) >= 35 THEN 'S'
                WHEN (COALESCE(p.picks, 0) + COALESCE(b.bans, 0)) * 100.0 / (tg.game_count * 2) >= 25 THEN 'A'
                WHEN (COALESCE(p.picks, 0) + COALESCE(b.bans, 0)) * 100.0 / (tg.game_count * 2) >= 15 THEN 'B'
                WHEN (COALESCE(p.picks, 0) + COALESCE(b.bans, 0)) * 100.0 / (tg.game_count * 2) >= 8 THEN 'C'
                ELSE 'D'
            END as tier
        FROM pick_stats p
        FULL OUTER JOIN ban_stats b ON p.champion = b.champion
        FULL OUTER JOIN win_stats w ON COALESCE(p.champion, b.champion) = w.champion_name
        CROSS JOIN total_games tg
        ORDER BY presence DESC
    """).df()


# Champion Synergies - same-team pairs
def get_champion_synergies(min_games: int = 5):
    return duckdb.query(f"""
        WITH team_picks AS (
            SELECT game_id, team_id, champion
            FROM '{DATA_PATH}/draft_actions.csv'
            WHERE action_type = 'pick'
        ),
        pairs AS (
            SELECT
                t1.game_id, t1.team_id,
                LEAST(t1.champion, t2.champion) as champ_a,
                GREATEST(t1.champion, t2.champion) as champ_b
            FROM team_picks t1
            JOIN team_picks t2 ON t1.game_id = t2.game_id
                AND t1.team_id = t2.team_id
                AND t1.champion < t2.champion
        )
        SELECT
            champ_a, champ_b,
            COUNT(*) as games_together,
            SUM(CASE WHEN g.winner_team_id = p.team_id THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN g.winner_team_id = p.team_id THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
            ROUND((AVG(CASE WHEN g.winner_team_id = p.team_id THEN 1.0 ELSE 0.0 END) - 0.5) * 100, 1) as synergy_delta
        FROM pairs p
        JOIN '{DATA_PATH}/games.csv' g ON p.game_id = g.id
        GROUP BY champ_a, champ_b
        HAVING COUNT(*) >= {min_games}
        ORDER BY synergy_delta DESC
    """).df()


# Champion Counters - role-specific matchups
def get_champion_counters(champion: str, role: str, min_games: int = 3):
    return duckdb.query(f"""
        SELECT
            pgs2.champion_name as enemy_champion,
            COUNT(*) as games,
            SUM(CASE WHEN pgs1.team_won = 'True' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN pgs1.team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
        FROM '{DATA_PATH}/player_game_stats.csv' pgs1
        JOIN '{DATA_PATH}/player_game_stats.csv' pgs2
            ON pgs1.game_id = pgs2.game_id
            AND pgs1.role = pgs2.role
            AND pgs1.team_side != pgs2.team_side
        WHERE pgs1.champion_name = '{champion}'
          AND pgs1.role = '{role}'
        GROUP BY pgs2.champion_name
        HAVING COUNT(*) >= {min_games}
        ORDER BY win_rate DESC
    """).df()


# Player vs Player Head-to-Head
def get_player_matchup(player1: str, player2: str):
    return duckdb.query(f"""
        SELECT
            pgs1.champion_name as p1_champ,
            pgs2.champion_name as p2_champ,
            pgs1.role,
            CASE WHEN pgs1.team_won = 'True' THEN '{player1}' ELSE '{player2}' END as winner,
            pgs1.kda_ratio as p1_kda,
            pgs2.kda_ratio as p2_kda
        FROM '{DATA_PATH}/player_game_stats.csv' pgs1
        JOIN '{DATA_PATH}/player_game_stats.csv' pgs2
            ON pgs1.game_id = pgs2.game_id
            AND pgs1.role = pgs2.role
            AND pgs1.team_side != pgs2.team_side
        WHERE pgs1.player_name = '{player1}'
          AND pgs2.player_name = '{player2}'
    """).df()
```

### 8.5 Optional: Persistent DuckDB for Performance

For demo day, if CSV queries become slow (they won't at our scale), persist to `.duckdb`:

```python
# One-time: Create persistent database
def materialize_database():
    con = duckdb.connect('data/draft_assistant.duckdb')

    # Import CSVs as tables
    for table in ['teams', 'players', 'champions', 'series', 'games',
                  'draft_actions', 'player_game_stats']:
        con.execute(f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT * FROM '{DATA_PATH}/{table}.csv'
        """)

    # Create materialized analytics views
    con.execute("""
        CREATE OR REPLACE TABLE champion_meta_stats AS
        -- (meta query from above)
    """)

    con.close()

# Later: Query persistent database (3-5x faster)
con = duckdb.connect('data/draft_assistant.duckdb', read_only=True)
result = con.execute("SELECT * FROM champion_meta_stats").df()
```

### 8.6 Actual Data Counts (Exceeds Targets)

| Entity | Spec Target | **Actual** | Status |
|--------|-------------|------------|--------|
| Teams | ~30 | **57** | ✅ 1.9x |
| Players | ~150 | **445** | ✅ 3.0x |
| Champions | ~170 | **162** | ✅ Near complete |
| Series | ~200 | **1,482** | ✅ 7.4x |
| Games | ~500 | **3,436** | ✅ 6.9x |
| Draft Actions | ~10,000 | **68,529** | ✅ 6.9x |
| Player Game Stats | ~5,000 | **34,416** | ✅ 6.9x |

**Regions Covered:** LCK (409), LEC (323), LCS (174), LPL (458), International (117)

### 8.7 Performance at Our Scale

| Query Type | Rows Scanned | Expected Time |
|------------|--------------|---------------|
| Champion meta | 68K + 34K | < 100ms |
| Counter matchups | 34K self-join | < 150ms |
| Player proficiency | 34K filter | < 50ms |
| Synergy pairs | 68K join | < 200ms |

DuckDB's columnar engine handles our entire dataset in milliseconds. No optimization needed for hackathon demo.

### 8.8 DuckDB + FastAPI Async Pattern

**Important:** DuckDB is synchronous-only. This affects how we structure FastAPI routes.

#### The Problem

```python
# ❌ BAD: Blocking call inside async function blocks the event loop
@app.get("/api/meta")
async def get_meta():
    df = duckdb.query("SELECT * FROM ...").df()  # Blocks!
    return df.to_dict()
```

#### The Solution: Use Sync Routes for DuckDB

```python
# ✅ GOOD: Sync function - FastAPI automatically runs in thread pool
@app.get("/api/meta")
def get_meta():  # Note: 'def' not 'async def'
    df = duckdb.query("SELECT * FROM ...").df()
    return df.to_dict(orient="records")
```

FastAPI automatically runs synchronous route handlers in a thread pool, preventing event loop blocking. This is the simplest and recommended pattern.

#### When You Need Async (WebSocket, LLM Streaming)

```python
from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool

# For WebSocket handlers that need DuckDB data
@app.websocket("/ws/draft/{series_id}")
async def draft_websocket(websocket: WebSocket, series_id: str):
    await websocket.accept()

    # Run DuckDB query in thread pool
    draft_actions = await run_in_threadpool(
        lambda: duckdb.query(f"""
            SELECT * FROM '{DATA_PATH}/draft_actions.csv'
            WHERE game_id IN (
                SELECT id FROM '{DATA_PATH}/games.csv'
                WHERE series_id = '{series_id}'
            )
            ORDER BY sequence
        """).df().to_dict(orient="records")
    )

    # Stream actions with delay (replay mode)
    for action in draft_actions:
        await websocket.send_json({"type": "draft_action", "action": action})
        await asyncio.sleep(2)  # 2 second delay between actions
```

#### Recommended Pattern Summary

| Route Type | Pattern | Why |
|------------|---------|-----|
| REST analytics | `def` (sync) | FastAPI thread pool handles it |
| WebSocket | `async def` + `run_in_threadpool` | Need `await` for send/receive |
| LLM streaming | `async def` | Groq/Together clients are async |
| Health check | `async def` | No DuckDB, pure async is fine |

#### Why Not aiosqlite?

| Consideration | aiosqlite | DuckDB |
|---------------|-----------|--------|
| Async native | ✅ Yes | ❌ No (use threadpool) |
| CSV direct query | ❌ Requires ETL | ✅ Zero ETL |
| Analytics speed | ❌ Row-based, slow | ✅ Columnar, 10-100x faster |
| Demo complexity | ⚠️ Need seed script | ✅ Just query CSVs |

**Decision:** DuckDB's performance and zero-ETL benefits outweigh the async limitation. At demo scale (1-2 concurrent users, <200ms queries), the sync/threadpool pattern works perfectly.

---

## 9. API Design

### 9.1 REST Endpoints

```yaml
# Series & Draft
GET /api/series
  Query: ?tournament_id=X&team_id=Y&limit=20
  → { series[]: { id, teams, date, description } }

GET /api/series/{series_id}
  → { id, teams, games[], tournament }

GET /api/draft/{series_id}/{game_number}
  → { draft_actions[], phase, next_team, blue_comp, red_comp }

# Recommendations
POST /api/recommend/pick
  Body: { series_id, game_number, team_id }
  → { recommendations[]: { champion, confidence, flag, reasons[], explanation } }

POST /api/recommend/ban
  Body: { series_id, game_number, team_id, opponent_team_id }
  → { recommendations[]: { champion, priority, target_player, explanation } }

# Analytics
GET /api/player/{player_id}
  → { profile, tendencies, champion_pool[] }

GET /api/player/{player_id}/champions
  → { stats[]: { champion, games, win_rate, confidence } }

GET /api/team/{team_id}
  → { profile, players[], recent_series[] }

GET /api/champion/{champion_id}
  → { meta_stats, synergies[], counters[] }

GET /api/meta/current
  → { tiers: { S: [], A: [], B: [], C: [], D: [] }, meta_summary }

# AI Insights
POST /api/insight
  Body: { draft_state, context }
  → { insight_text, confidence }

POST /api/analysis/comp
  Body: { champions[] }
  → { archetype, win_condition, strengths[], weaknesses[] }

# Replay Control
POST /api/replay/start
  Body: { series_id, game_number, speed_multiplier }
  → { session_id, total_actions }

POST /api/replay/{session_id}/next
  → { action, recommendations, insight, is_complete }

POST /api/replay/{session_id}/jump
  Body: { action_index }
  → { draft_state, recommendations }

DELETE /api/replay/{session_id}
  → { success }
```

### 9.2 WebSocket Protocol

```yaml
# Connection
ws://localhost:8000/ws/draft/{series_id}/{game_number}?mode=live|replay

# Client → Server Messages
{
  "type": "subscribe",
  "team_focus": "blue" | "red" | null  # Which team to generate recs for
}

{
  "type": "replay_control",
  "action": "start" | "pause" | "resume" | "next" | "jump",
  "speed": 1.0 | 2.0 | 0.5,           # For start/resume
  "index": 5                           # For jump
}

{
  "type": "request_insight"            # Force insight generation
}

# Server → Client Messages
{
  "type": "draft_action",
  "action": {
    "sequence": 7,
    "type": "pick",
    "team": "blue",
    "champion": "Kalista",
    "champion_icon": "https://..."
  },
  "draft_state": {
    "phase": "PICK_PHASE_1",
    "blue_bans": [...],
    "red_bans": [...],
    "blue_picks": [...],
    "red_picks": [...],
    "next_team": "red",
    "next_action": "pick"
  }
}

{
  "type": "recommendations",
  "team": "red",
  "picks": [
    {
      "champion": "Neeko",
      "confidence": 0.78,
      "flag": null,
      "reasons": ["Flex potential", "Caps comfort pick"]
    },
    {
      "champion": "Aurora",
      "confidence": 0.55,
      "flag": "SURPRISE_PICK",
      "reasons": ["S-tier meta", "Low stage games"]
    }
  ],
  "bans": [...]
}

{
  "type": "insight",
  "text": "BDS first-picked Kalista, revealing Hans Sama as their carry focus...",
  "timestamp": "2025-01-10T12:00:00Z"
}

{
  "type": "phase_change",
  "from": "BAN_PHASE_1",
  "to": "PICK_PHASE_1",
  "next_team": "blue"
}

{
  "type": "comp_analysis",
  "blue": {
    "archetype": "dive",
    "confidence": 0.75,
    "champions_contributing": ["Nocturne", "Akali"]
  },
  "red": {
    "archetype": "teamfight",
    "confidence": 0.60
  }
}

{
  "type": "draft_complete",
  "blue_comp": { "champions": [...], "archetype": "dive" },
  "red_comp": { "champions": [...], "archetype": "protect" },
  "prediction": {
    "favored": "blue",
    "confidence": 0.54,
    "reasoning": "Dive comp with early game advantage"
  }
}

{
  "type": "error",
  "message": "Rate limit exceeded",
  "retry_after": 3
}
```

### 9.3 FastAPI + DuckDB Integration Pattern

```python
from fastapi import FastAPI, Query, HTTPException
from contextlib import asynccontextmanager
import duckdb

DATA_PATH = "outputs/full_2024_2025/csv"

# DuckDB connection management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify CSV files exist
    app.state.data_path = DATA_PATH
    yield
    # Shutdown: nothing to clean up (DuckDB handles it)

app = FastAPI(title="LoL Draft Assistant API", lifespan=lifespan)


@app.get("/api/meta/current")
def get_current_meta(min_presence: int = Query(10, description="Minimum pick+ban count")):
    """Get current champion meta tier list."""
    df = duckdb.query(f"""
        WITH total_games AS (
            SELECT COUNT(DISTINCT id) as game_count
            FROM '{DATA_PATH}/games.csv'
        ),
        stats AS (
            SELECT
                champion,
                SUM(CASE WHEN action_type = 'pick' THEN 1 ELSE 0 END) as picks,
                SUM(CASE WHEN action_type = 'ban' THEN 1 ELSE 0 END) as bans,
                COUNT(*) as presence
            FROM '{DATA_PATH}/draft_actions.csv'
            GROUP BY champion
        )
        SELECT
            champion,
            picks,
            bans,
            presence,
            ROUND(presence * 100.0 / (tg.game_count * 2), 1) as presence_pct,
            CASE
                WHEN presence * 100.0 / (tg.game_count * 2) >= 35 THEN 'S'
                WHEN presence * 100.0 / (tg.game_count * 2) >= 25 THEN 'A'
                WHEN presence * 100.0 / (tg.game_count * 2) >= 15 THEN 'B'
                WHEN presence * 100.0 / (tg.game_count * 2) >= 8 THEN 'C'
                ELSE 'D'
            END as tier
        FROM stats
        CROSS JOIN total_games tg
        WHERE presence >= {min_presence}
        ORDER BY presence DESC
    """).df()

    # Group by tier for response
    tiers = {"S": [], "A": [], "B": [], "C": [], "D": []}
    for _, row in df.iterrows():
        tiers[row["tier"]].append({
            "champion": row["champion"],
            "picks": int(row["picks"]),
            "bans": int(row["bans"]),
            "presence_pct": float(row["presence_pct"])
        })

    return {"tiers": tiers, "total_games": int(df["presence"].sum() / 2)}


@app.get("/api/champions/{champion}/counters")
def get_champion_counters(
    champion: str,
    role: str = Query(..., description="Role: TOP, JNG, MID, ADC, SUP"),
    min_games: int = Query(3, description="Minimum games for matchup")
):
    """Get counter matchups for a champion in a specific role."""
    df = duckdb.query(f"""
        SELECT
            pgs2.champion_name as enemy_champion,
            COUNT(*) as games,
            SUM(CASE WHEN pgs1.team_won = 'True' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN pgs1.team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
        FROM '{DATA_PATH}/player_game_stats.csv' pgs1
        JOIN '{DATA_PATH}/player_game_stats.csv' pgs2
            ON pgs1.game_id = pgs2.game_id
            AND pgs1.role = pgs2.role
            AND pgs1.team_side != pgs2.team_side
        WHERE pgs1.champion_name = '{champion}'
          AND pgs1.role = '{role}'
        GROUP BY pgs2.champion_name
        HAVING COUNT(*) >= {min_games}
        ORDER BY win_rate DESC
    """).df()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No matchup data for {champion} in {role}")

    return {
        "champion": champion,
        "role": role,
        "counters": df.to_dict(orient="records")
    }


@app.get("/api/players/{player}/proficiency")
def get_player_proficiency(player: str):
    """Get a player's champion pool with stats."""
    df = duckdb.query(f"""
        SELECT
            champion_name,
            COUNT(*) as games,
            SUM(CASE WHEN team_won = 'True' THEN 1 ELSE 0 END) as wins,
            ROUND(AVG(CASE WHEN team_won = 'True' THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
            ROUND(AVG(kda_ratio), 2) as avg_kda,
            CASE
                WHEN COUNT(*) >= 10 THEN 'HIGH'
                WHEN COUNT(*) >= 5 THEN 'MEDIUM'
                ELSE 'LOW'
            END as confidence
        FROM '{DATA_PATH}/player_game_stats.csv'
        WHERE player_name = '{player}'
        GROUP BY champion_name
        ORDER BY games DESC
    """).df()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Player '{player}' not found")

    return {
        "player": player,
        "total_games": int(df["games"].sum()),
        "champions": df.to_dict(orient="records")
    }
```

**Key Patterns:**
1. **No connection management** - DuckDB handles it automatically
2. **Direct DataFrame to dict** - `.to_dict(orient="records")` for JSON responses
3. **Parameterized queries** - Use f-strings for dynamic values (safe for read-only analytics)
4. **Error handling** - Return 404 for missing data

---

## 10. Development Plan

### Week 1: Foundation & Data
| Task | Owner | Days |
|------|-------|------|
| Project setup (repo, CI, uv, FastAPI skeleton) | Eng 1 | 1 |
| ~~GRID API client with rate limiting~~ | ~~Eng 1~~ | ✅ Done |
| ~~CSV data extraction from GRID API~~ | ~~Eng 2~~ | ✅ Done (68K+ records) |
| DuckDB analytics service + query functions | Eng 2 | 1 |
| Domain expert: provide knowledge files (team profiles, archetypes) | Domain | 3 |
| ~~Batch ingestion script~~ | ~~Eng 1~~ | ✅ Done (1,482 series in CSV) |
| ~~Layer 1-4 analytics queries~~ | ~~Eng 2~~ | ✅ DuckDB computes on-demand |
| Champion Data Dragon icon mapping | Eng 2 | 0.5 |
| Knowledge file integration (JSON/MD loading) | Eng 1 | 0.5 |

**Deliverable:** DuckDB analytics layer with all query functions, knowledge files ready

### Week 2: Core Backend Logic
| Task | Owner | Days |
|------|-------|------|
| Pick recommendation algorithm (all 4 layers) | Eng 1 + Domain | 2 |
| Ban recommendation algorithm | Eng 1 | 1 |
| Surprise pick detection logic | Eng 1 + Domain | 1 |
| Replay controller (timer-driven action release) | Eng 2 | 1.5 |
| WebSocket endpoint for draft streaming | Eng 2 | 1.5 |
| REST endpoints for analytics | Eng 1 | 1 |
| Comp archetype detection | Eng 2 | 1 |

**Deliverable:** Backend that can replay drafts and generate layered recommendations

### Week 3: Frontend & LLM
| Task | Owner | Days |
|------|-------|------|
| ~~React app scaffold (Vite + Tailwind)~~ | ~~Eng 2~~ | ✅ Done |
| ~~Data Dragon utilities + icon mapping~~ | ~~Eng 2~~ | ✅ Done |
| Draft board component implementation | Eng 2 | 2 |
| Recommendation panel component | Eng 2 | 1.5 |
| LLM integration (Groq/Together client) | Eng 1 | 1 |
| Insight prompt engineering + iteration | Eng 1 + Domain | 2 |
| WebSocket client integration | Eng 1 | 1 |
| Series selector / replay controls UI | Eng 2 | 1 |

**Deliverable:** Working end-to-end demo with AI insights

### Week 4: Polish & Stretch Features
| Task | Owner | Days |
|------|-------|------|
| Bug fixes and edge cases | Both | 2 |
| UI polish pass (animations, loading states) | Eng 2 | 1.5 |
| Post-game analysis feature (stretch) | Eng 1 | 2 |
| What-if simulator (stretch, if time) | Eng 2 | 2 |
| Demo video recording | All | 1 |
| README, documentation, submission prep | All | 0.5 |

**Deliverable:** Polished submission with video

---

## 11. Demo Script (3 minutes)

### 0:00-0:15 - Hook
*"What if you had a pro analyst whispering in your ear during every draft?"*

Show: App loading, sleek UI

### 0:15-0:40 - Setup
*"We're watching LEC Finals - G2 vs BDS. Our AI has analyzed 200 pro matches to understand these teams..."*

Show: Select series, show team cards with playstyle summaries

### 0:40-1:30 - Live Draft (Ban Phase)
*"Watch as real-time recommendations appear..."*

Show: Draft replay at 2x speed, ban recommendations appearing

Highlight: "Notice how we flagged this - G2 is target-banning Hans Sama's champion pool"

### 1:30-2:15 - Live Draft (Pick Phase + Surprise Pick)
*"Here's where it gets interesting..."*

Show: Pick recommendations with confidence scores

Highlight surprise pick: "Aurora shows as a surprise pick - low stage games, but our AI recognizes Caps has the mechanics from his Ahri play"

### 2:15-2:40 - AI Insight
*"Stats alone don't tell the story. Our LLM explains the WHY..."*

Show: Zoom on AI insight panel

Read aloud: One compelling insight about draft strategy

### 2:40-2:55 - Post-Draft Summary (if built)
*"After the draft, get your full analysis..."*

Show: Draft grade, comp archetype, prediction

### 2:55-3:00 - Close
*"Draft smarter. [App Name]."*

Show: GitHub link, team credits

---

## 12. Submission Checklist

- [ ] Public GitHub repo with MIT license
- [ ] README with:
  - [ ] Project description
  - [ ] Tech stack
  - [ ] Setup instructions (uv, database seeding)
  - [ ] Demo video link
  - [ ] Screenshots
  - [ ] Architecture diagram
  - [ ] Team credits
- [ ] Category: AI Draft Assistant / Draft Predictor
- [ ] 3-minute demo video (YouTube)
- [ ] All source code included
- [ ] Pre-seeded database or seeding script
- [ ] Knowledge files (domain expert contributions)
- [ ] LICENSE file (MIT)

---

## 13. Domain Expert Request List

Please provide the following to maximize AI insight quality:

### Required (Week 1)
1. **Team profiles** for top 20 teams (LCK, LEC priority):
   - Playstyle (aggressive/scaling/flexible)
   - Draft tendencies
   - Signature strategies

2. **200 interesting series** to ingest:
   - Series IDs or "Tournament + Teams + Game" identifiers
   - Brief note on why (upset, draft diff, creative picks)

3. **Current meta summary** (2025):
   - S/A tier champions by role
   - What defines good drafts now
   - Key strategic principles

### Required (Week 2)
4. **Player hidden pools**:
   - Champions players are known for but rarely pick on stage
   - Solo queue comfort picks

5. **Comp archetype definitions**:
   - Champion markers for each archetype
   - Win conditions
   - Counter archetypes

6. **Champion flex mappings**:
   - Which champions flex to which roles
   - "Trap" flexes to avoid

### Required (Week 3)
7. **Prompt review**:
   - Review AI insights for accuracy
   - Suggest domain-specific language
   - Flag any nonsensical outputs

8. **Draft rules document**:
   - Phase-by-phase priorities
   - Blue vs red side strategy
   - Common mistakes to flag

### Nice to Have
9. **Champion rework dates** (for data filtering)
10. **Skill transfer mappings** (if good at X, can play Y)
11. **Red flag picks** (statistically okay but strategically bad)

---

## Appendix A: Sample Series Selection Criteria

Domain expert should prioritize:

| Criteria | Weight | Example |
|----------|--------|---------|
| **Upsets** | High | Lower seed wins; draft was a factor |
| **Draft Disasters** | High | Clear mistakes we would've flagged |
| **Creative Drafts** | Medium | Unusual picks that worked |
| **Meta-Defining** | Medium | Drafts that showed new strategies |
| **Rivalry Matches** | Low | T1 vs Gen.G (audience familiarity) |
| **Recent (2024-2025)** | High | Current rosters, relevant meta |

**Actual Mix (1,482 series):**
- 31% LPL (458 series - full coverage!)
- 28% LCK (409 series)
- 22% LEC (323 series)
- 12% LCS (174 series)
- 8% International (117 series)

---

## Appendix B: LLM Provider Setup

### Groq (Recommended for Development)
```bash
# Sign up at console.groq.com
# Free tier: 30 req/min, 6000 tokens/min

export GROQ_API_KEY=gsk_...
```

```python
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

response = client.chat.completions.create(
    model="llama-3.1-70b-versatile",  # or "llama-3.1-8b-instant" for testing
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=300
)
```

### Together.ai (Alternative)
```bash
export TOGETHER_API_KEY=...
```

```python
import together

response = together.Complete.create(
    model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    prompt=prompt,
    max_tokens=300,
    temperature=0.7
)
```

---

*Spec Version: Hackathon v2.2 | January 2026*
*v2.2 changes: Added DuckDB + FastAPI async/sync implementation patterns (Section 8.8)*
*v2.1 changes: Switched from SQLite to DuckDB for zero-ETL CSV querying, updated data model to reflect 7x data volume*
*v2.0: Layered analysis, recency weighting, surprise pick detection, open source LLM, domain knowledge integration*
