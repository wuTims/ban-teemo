# Recommendation Service Overview

**Status:** Design Complete
**Date:** 2026-01-24

A high-level guide to how the recommendation engine handles uncertainty in draft predictions.

---

## The Core Problem

When recommending picks during a draft, we face two types of uncertainty:

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNCERTAINTY IN DRAFTS                        │
├────────────────────────────┬────────────────────────────────────┤
│     FLEX PICK AMBIGUITY    │        SURPRISE PICKS              │
├────────────────────────────┼────────────────────────────────────┤
│ Enemy picks Aurora         │ We want to recommend Aurora        │
│ Is she going MID or TOP?   │ But player has only 2 stage games  │
│                            │                                    │
│ We can't calculate an      │ We can't trust our proficiency     │
│ accurate matchup score     │ score for this player-champion     │
└────────────────────────────┴────────────────────────────────────┘
```

**Our approach:** Don't pretend we have certainty. Instead:
1. Calculate best estimates using probabilities
2. Track confidence alongside every score
3. Surface uncertainty to users transparently

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                            │
│            "Recommend picks for Blue team, MID lane"            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FLEX PICK RESOLVER                         │
│                                                                 │
│  For each enemy pick, estimate role probability:                │
│                                                                 │
│  Aurora (G2 picks it) → who plays it? → { MID: 73%, TOP: 27% }  │
│  Rumble (already have TOP) → { TOP: 100% }                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION ENGINE                        │
│                                                                 │
│  For each candidate champion, calculate:                        │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Meta Score  │ │ Proficiency │ │  Matchup    │               │
│  │   (0.15)    │ │   (0.30)    │ │   (0.20)    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐                               │
│  │  Synergy    │ │  Counter    │                               │
│  │   (0.20)    │ │   (0.15)    │                               │
│  └─────────────┘ └─────────────┘                               │
│                                                                 │
│  Combine with confidence-adjusted weights                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        RECOMMENDATIONS                          │
│                                                                 │
│  1. Syndra (78% confidence)                                     │
│     "Strong meta pick, counters likely Aurora mid"              │
│                                                                 │
│  2. Azir (72% confidence)                                       │
│     "Safe scaling, good team synergy"                           │
│                                                                 │
│  3. Orianna (55% confidence) [SURPRISE PICK]                    │
│     "⚠️ 2 stage games, but strong synergy + skill transfer"     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Flex Pick Resolution

When the enemy picks a champion that can play multiple roles, we need to estimate where they're going.

### Key Insight: Players Trade Champions

In pro play, the player who clicks "pick" doesn't necessarily play that champion. Teams frequently **trade champions** after the draft phase. For example:
- Caps picks Aurora
- BrokenBlade picks Rumble
- They swap → Caps plays Rumble mid, BrokenBlade plays Aurora top

**Our data captures this:** We see which team picked a champion AND which player actually played it. This lets us compute real trading patterns.

### Team-Champion-Player Probability

```
┌─────────────────────────────────────────────────────────────────┐
│         HISTORICAL: "When Team X picks Champion Y,              │
│                      which player ends up playing it?"          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  When G2 picks Aurora:                                          │
│    → Caps (MID) plays it: 73%                                   │
│    → BrokenBlade (TOP) plays it: 27%                            │
│                                                                 │
│  When T1 picks Tristana:                                        │
│    → Gumayusi (ADC) plays it: 85%                               │
│    → Faker (MID) plays it: 15%                                  │
│                                                                 │
│  When FNC picks Neeko:                                          │
│    → Humanoid (MID) plays it: 60%                               │
│    → Oscarinin (TOP) plays it: 30%                              │
│    → Upset (ADC) plays it: 10%                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Resolution Priority

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLEX RESOLUTION ORDER                        │
│                  (highest certainty first)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. FILLED ROLES ──────────────────────────────── [CERTAIN]     │
│     │                                                           │
│     │  If enemy already has a mid laner picked,                 │
│     │  Aurora cannot be mid → eliminate that option             │
│     │                                                           │
│     ▼                                                           │
│  2. TEAM-CHAMPION-PLAYER HISTORY ──────────────── [HIGH CONF]   │
│     │                                                           │
│     │  "When G2 picks Aurora, who usually plays it?"            │
│     │  Historical data: Caps 73%, BrokenBlade 27%               │
│     │  → Infer role from player's position                      │
│     │                                                           │
│     ▼                                                           │
│  3. REMAINING PLAYER ROLES ────────────────────── [HIGH CONF]   │
│     │                                                           │
│     │  "Which players on this team haven't picked yet?"         │
│     │  If only MID and TOP players remain → 50/50               │
│     │  If only MID player remains → 100% MID                    │
│     │                                                           │
│     ▼                                                           │
│  4. BASE FLEX RATES ───────────────────────────── [FALLBACK]    │
│                                                                 │
│     Global historical data: Aurora goes MID 65%, TOP 35%        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Example Scenarios

| Scenario | Known Info | Resolution |
|----------|------------|------------|
| Aurora picked, 4 roles filled | TOP, JNG, ADC, SUP taken | MID: 100% (only option) |
| Aurora picked by G2, MID+TOP open | G2 history: Caps 73%, BB 27% | MID: 73%, TOP: 27% |
| Aurora picked, unknown team | No team-specific data | MID: 65%, TOP: 35% (global rates) |
| Tristana picked by T1, ADC+MID open | T1 history: Guma 85%, Faker 15% | ADC: 85%, MID: 15% |

---

## Part 2: Scoring with Matchup Uncertainty

When we don't know the enemy's role for certain, we calculate a **weighted expected value**.

### The Math (Conceptual)

```
┌─────────────────────────────────────────────────────────────────┐
│                   MATCHUP WITH UNCERTAINTY                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  We want to pick Syndra for MID lane.                           │
│  Enemy has Aurora (85% MID, 15% TOP).                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ If Aurora goes MID:                                     │    │
│  │   Syndra vs Aurora = 48% win rate                       │    │
│  │   Weight: 85%                                           │    │
│  │                                                         │    │
│  │ If Aurora goes TOP:                                     │    │
│  │   Syndra vs ??? = 50% (no direct opponent yet)          │    │
│  │   Weight: 15%                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Expected Matchup = (0.85 × 48%) + (0.15 × 50%) = 48.3%         │
│  Confidence = 85% (probability of most likely scenario)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### How Confidence Affects Weights

When matchup confidence is low, we reduce its influence and rely more on certain factors:

```
                    HIGH CONFIDENCE              LOW CONFIDENCE
                    (matchup certain)            (flex uncertainty)

Meta Score          ████░░░░░░ 15%              █████░░░░░ 18%
Proficiency         ████████░░░░ 30%            █████████░░░ 36%
Matchup             ██████░░░░ 20%              ███░░░░░░░ 10%    ← reduced
Synergy             ██████░░░░ 20%              ██████░░░░ 22%
Counter             ████░░░░░░ 15%              ████░░░░░░ 14%
```

---

## Part 3: Proficiency Scoring

### Player Performance Metrics

We use multiple data points to assess how well a player performs on a champion:

```
┌─────────────────────────────────────────────────────────────────┐
│                   PROFICIENCY DATA SOURCES                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  VOLUME METRICS                                                 │
│  ├── Games played (raw count)                                   │
│  └── Games weighted (recency-adjusted)                          │
│                                                                 │
│  OUTCOME METRICS                                                │
│  └── Win rate                                                   │
│                                                                 │
│  PERFORMANCE METRICS (from GRID API)                            │
│  ├── KDA ratio (kills + assists / deaths)                       │
│  ├── Kill participation (% of team kills involved in)           │
│  ├── Net worth (total gold value)                               │
│  ├── Money per minute (gold generation rate)                    │
│  ├── Objectives (dragons, heralds, towers contributed to)       │
│  └── Vision score                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why Multiple Metrics Matter

KDA alone can be misleading:

```
┌─────────────────────────────────────────────────────────────────┐
│                    KDA IS NOT ENOUGH                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Player A on Orianna: 3.2 KDA, 48% win rate                     │
│  Player B on Orianna: 2.8 KDA, 56% win rate                     │
│                                                                 │
│  KDA says A is better. Win rate says B is better.               │
│                                                                 │
│  Looking deeper:                                                │
│    Player A: High KDA but low kill participation (32%)          │
│              Playing safe, not impacting fights                 │
│              Low objective contribution                         │
│                                                                 │
│    Player B: Lower KDA but high kill participation (71%)        │
│              High objective contribution                        │
│              Better money per minute (carrying games)           │
│                                                                 │
│  Player B is actually more impactful despite lower KDA          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Composite Proficiency Score

```
┌─────────────────────────────────────────────────────────────────┐
│              PROFICIENCY SCORE CALCULATION                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OUTCOME WEIGHT: 40%                                            │
│  └── Win rate (the ultimate measure of success)                 │
│                                                                 │
│  IMPACT WEIGHT: 35%                                             │
│  ├── Kill participation (20%)                                   │
│  │   → Normalized vs role average                               │
│  ├── Objective contribution (10%)                               │
│  │   → Dragons, heralds, towers                                 │
│  └── Money per minute (5%)                                      │
│      → Normalized vs role average                               │
│                                                                 │
│  EFFICIENCY WEIGHT: 25%                                         │
│  ├── KDA ratio (15%)                                            │
│  │   → Normalized vs champion average                           │
│  └── Net worth efficiency (10%)                                 │
│      → Gold relative to game time and role                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Normalization Is Critical

Raw stats are meaningless without context:

| Metric | Raw Value | Needs Normalization Because... |
|--------|-----------|-------------------------------|
| KDA | 4.2 | Supports have higher KDA than tops |
| Kill Participation | 65% | Junglers naturally have higher KP |
| Money/min | 420g | ADCs earn more than supports |
| Net Worth | 14,200g | Depends on game length |
| Objectives | 3 | Junglers get more objectives |

**Normalization approach:**

```
Normalized Score = (Player Value - Role Average) / Role Std Dev

Example:
  Caps on Aurora: 4.8 KDA
  Mid average: 3.2 KDA
  Mid std dev: 1.1

  Normalized = (4.8 - 3.2) / 1.1 = +1.45 (1.45 std devs above average)
```

---

## Part 4: Surprise Pick Detection

A "surprise pick" is when we recommend a champion the player has rarely played on stage, but contextual signals suggest it could work.

### Proficiency Confidence Levels

| Games Played | Confidence | Behavior |
|--------------|------------|----------|
| 8+ games | HIGH | Trust the proficiency score directly |
| 4-7 games | MEDIUM | Trust with slight caution |
| 1-3 games | LOW | Calculate contextual strength |
| 0 games | NO DATA | Rely entirely on context |

### Contextual Strength (Pure Statistics)

When direct proficiency data is lacking, we look at indirect signals:

```
┌─────────────────────────────────────────────────────────────────┐
│              CONTEXTUAL STRENGTH CALCULATION                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Player: Caps                                                   │
│  Champion: Orianna (only 2 stage games)                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ META TIER (30%)                                         │    │
│  │   Orianna presence: 45% (A-tier)                        │    │
│  │   Score: 0.75                                           │    │
│  │                                                         │    │
│  │ COUNTER VALUE (25%)                                     │    │
│  │   vs enemy Azir: 54% win rate in matchup                │    │
│  │   Score: 0.70                                           │    │
│  │                                                         │    │
│  │ SYNERGY VALUE (25%)                                     │    │
│  │   With ally Nocturne: +8% above expected                │    │
│  │   Score: 0.80                                           │    │
│  │                                                         │    │
│  │ SKILL TRANSFER (20%)                                    │    │
│  │   Caps has 23 games on Syndra (similar via co-play)     │    │
│  │   Score: 0.85                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Contextual Strength = 0.77 (weighted average)                  │
│  Threshold for "surprise eligible" = 0.65                       │
│                                                                 │
│  Result: Flag as SURPRISE PICK                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Skill Transfer (Automated via Co-Play Patterns)

```
┌─────────────────────────────────────────────────────────────────┐
│                     SKILL TRANSFER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Computed from CO-PLAY PATTERNS:                                │
│                                                                 │
│  "Players who play Orianna also tend to play..."                │
│                                                                 │
│    Orianna ──┬── Syndra (78% co-play rate)                      │
│              ├── Azir (71% co-play rate)                        │
│              └── Viktor (65% co-play rate)                      │
│                                                                 │
│  Does Caps play any of these?                                   │
│    → Syndra: 23 games, 67% WR ✓                                 │
│    → Azir: 18 games, 61% WR ✓                                   │
│                                                                 │
│  Skill Transfer Score: 0.85 (strong)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Synergy Scoring (Normalized)

### The Problem with Raw Win Rates

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE CONFLATION PROBLEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Aurora + Nocturne: 62% win rate together                       │
│                                                                 │
│  But WHY do they win?                                           │
│                                                                 │
│    A) True synergy (dive combo, CC chaining)          ← SIGNAL  │
│    B) Both are S-tier meta picks                      ← NOISE   │
│    C) Strong teams pick them together                 ← NOISE   │
│    D) Picked in favorable game states                 ← NOISE   │
│                                                                 │
│  Raw win rate = A + B + C + D all mixed together                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Normalized Synergy Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                 ISOLATING TRUE SYNERGY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Question: "Does Aurora win MORE with Nocturne than with        │
│             other junglers of similar meta strength?"           │
│                                                                 │
│  Step 1: Calculate Aurora's baseline with same-tier junglers    │
│                                                                 │
│    Aurora + A-tier junglers average: 55% win rate               │
│      Nocturne (A-tier): 62%                                     │
│      Lee Sin (A-tier): 54%                                      │
│      Maokai (A-tier): 53%                                       │
│      Elise (A-tier): 51%                                        │
│                                                                 │
│  Step 2: Calculate delta from baseline                          │
│                                                                 │
│    Nocturne synergy = 62% - 55% = +7%                           │
│    Lee Sin synergy = 54% - 55% = -1%                            │
│                                                                 │
│  Step 3: Convert to score                                       │
│                                                                 │
│    +7% delta → Synergy score: 0.85 (strong positive)            │
│    -1% delta → Synergy score: 0.48 (neutral)                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Adding Co-Pick Frequency Signal

Pro teams intentionally pair certain champions. High co-pick rate suggests believed synergy:

```
┌─────────────────────────────────────────────────────────────────┐
│                   CO-PICK FREQUENCY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  When teams pick Aurora, how often do they also pick...         │
│                                                                 │
│    Nocturne: 34% of Aurora games (high)                         │
│    Lee Sin: 18% of Aurora games (medium)                        │
│    Maokai: 8% of Aurora games (low)                             │
│                                                                 │
│  Compare to Nocturne's overall pick rate: 22%                   │
│                                                                 │
│  Co-pick lift = 34% / 22% = 1.55x (picked together 55% more     │
│                                    often than expected)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Final Synergy Formula

```
Synergy Score = (Normalized Win Delta × 0.6) + (Co-Pick Lift × 0.4)
```

---

## Part 6: Counter Value Scoring

### Lane Counter vs Team Counter

```
┌─────────────────────────────────────────────────────────────────┐
│               TWO TYPES OF COUNTER VALUE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LANE COUNTER (direct matchup)                                  │
│    "How does Syndra perform vs Azir in lane?"                   │
│    Data: Role-specific head-to-head win rates                   │
│                                                                 │
│  TEAM COUNTER (composition level)                               │
│    "How does Syndra perform when enemy team has Azir?"          │
│    Data: Game outcomes regardless of lane assignment            │
│                                                                 │
│  These can differ:                                              │
│    Syndra may lose lane to Azir (45% lane) but                  │
│    outperform in teamfights (53% game win rate)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Counter Score Calculation

```
┌─────────────────────────────────────────────────────────────────┐
│                 COUNTER SCORE FORMULA                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Lane Counter (when we know the matchup):                       │
│    Win rate in direct matchup, minimum 5 games                  │
│                                                                 │
│  Team Counter (when matchup uncertain):                         │
│    Win rate when enemy team contains that champion              │
│                                                                 │
│  Combined (for flex uncertainty):                               │
│    Weighted by matchup confidence                               │
│                                                                 │
│  Example:                                                       │
│    Enemy has Aurora (70% MID, 30% TOP)                          │
│    We're picking for MID                                        │
│                                                                 │
│    Syndra vs Aurora MID: 48% (lane counter)                     │
│    Syndra when enemy has Aurora: 52% (team counter)             │
│                                                                 │
│    Counter Score = (0.70 × 48%) + (0.30 × 52%) = 49.2%          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 7: Recommendation Output

### Final Recommendation Structure

Each recommendation includes both a score and transparency about uncertainty:

```
┌─────────────────────────────────────────────────────────────────┐
│                      RECOMMENDATION                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Champion: Syndra                                               │
│  Role: MID                                                      │
│                                                                 │
│  ┌─ SCORES ─────────────────────────────────────────────────┐   │
│  │ Overall: 0.78                                            │   │
│  │ Confidence: 0.85                                         │   │
│  │                                                          │   │
│  │ Components:                                              │   │
│  │   Meta:        0.72  ████████████████░░░░                │   │
│  │   Proficiency: 0.81  ████████████████████░               │   │
│  │   Matchup:     0.68  ████████████████░░░░  (conf: 85%)   │   │
│  │   Synergy:     0.75  ██████████████████░░                │   │
│  │   Counter:     0.70  █████████████████░░░                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Flag: None                                                     │
│                                                                 │
│  Reasons:                                                       │
│    • A-tier meta pick (45% presence)                            │
│    • Player: 15 games, 67% WR, high impact metrics              │
│    • +7% synergy with Nocturne                                  │
│                                                                 │
│  Warnings: None                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Flag Types

| Flag | Meaning | When Applied |
|------|---------|--------------|
| None | Standard recommendation | High confidence in all factors |
| `SURPRISE_PICK` | Low games but strong context | <4 games AND contextual strength >0.65 |
| `LOW_CONFIDENCE` | Weak data, proceed with caution | <4 games AND contextual strength <0.65 |

### Warnings (can have multiple)

| Warning | Trigger |
|---------|---------|
| "Uncertain matchup: [champ] role unclear" | Matchup confidence < 70% |
| "Only N stage games on record" | Games < 4 AND not surprise eligible |
| "Small sample size for matchup" | Matchup based on <10 games |
| "No recent games (8+ months)" | Recency-weighted games very low |

---

## Part 8: Potential Misleading Signals

### Critical Analysis of Our Statistical Approach

Every data-driven signal can be misleading. Here's our analysis:

```
┌─────────────────────────────────────────────────────────────────┐
│                   SIGNAL RELIABILITY ANALYSIS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL: Meta Tier (Presence-based)                             │
│  ─────────────────────────────────────────────────────────────  │
│  Misleading when:                                               │
│    • High ban rate ≠ strong (could mean annoying/unfun)         │
│    • New/reworked champions have artificial low presence        │
│    • Regional meta differences (LPL vs LEC)                     │
│  Mitigation:                                                    │
│    • Separate pick rate from ban rate in calculation            │
│    • Weight recent patches more heavily                         │
│    • Flag champions with <20 total games as "insufficient data" │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL: Skill Transfer (Co-Play Patterns)                      │
│  ─────────────────────────────────────────────────────────────  │
│  Misleading when:                                               │
│    • Players play meta champions (not skill-related)            │
│    • Small champion pools inflate co-play rates                 │
│    • Role-specific (mid players play mid champs, not transfer)  │
│  Mitigation:                                                    │
│    • Normalize for meta presence (remove "everyone plays Azir") │
│    • Require minimum games on both champions                    │
│    • Compare within-role vs cross-role co-play                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL: Matchup Win Rates                                      │
│  ─────────────────────────────────────────────────────────────  │
│  Misleading when:                                               │
│    • Small sample size (<10 games)                              │
│    • Player skill diff (Faker vs mid loses, not champion)       │
│    • Meta shifts (old patch data no longer relevant)            │
│    • Counter-pick context (loser was counter-picked)            │
│  Mitigation:                                                    │
│    • Require minimum 10 games for "confident" matchup           │
│    • Apply recency weighting to matchup data                    │
│    • Flag when matchup is often counter-pick scenario           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL: Synergy (Normalized Win Rate)                          │
│  ─────────────────────────────────────────────────────────────  │
│  Misleading when:                                               │
│    • Coincidental correlation (both picked by winning teams)    │
│    • Comp-dependent (works in dive, not poke)                   │
│    • Third variable (strong jungler makes all pairs look good)  │
│  Mitigation:                                                    │
│    • Normalize against same-tier alternatives                   │
│    • Add co-pick frequency as secondary signal                  │
│    • Require minimum 15 games together                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SIGNAL: Player Proficiency                                     │
│  ─────────────────────────────────────────────────────────────  │
│  Misleading when:                                               │
│    • Role swaps (player changed from TOP to MID)                │
│    • Team context (player on strong team inflates stats)        │
│    • Champion rework (old data no longer applies)               │
│    • Recency bias (recent form may not reflect true skill)      │
│  Mitigation:                                                    │
│    • Use multiple metrics (not just KDA or win rate)            │
│    • Normalize stats against role/champion averages             │
│    • Filter out pre-rework games                                │
│    • Balance recency weighting (not too extreme)                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Minimum Sample Size Requirements

| Signal | Minimum Games | Below Threshold Action |
|--------|---------------|------------------------|
| Meta Tier | 20 picks + bans | Flag as "emerging pick" |
| Matchup | 10 head-to-heads | Use team counter instead |
| Synergy | 15 games together | Use co-pick frequency only |
| Proficiency | 4 games | Trigger surprise pick logic |
| Skill Transfer | 5 games on source champ | Exclude from calculation |

### Confidence Penalties

When data quality is low, we reduce that signal's weight:

```
┌─────────────────────────────────────────────────────────────────┐
│                  CONFIDENCE PENALTY SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Each signal gets a data quality score (0.0 - 1.0):             │
│                                                                 │
│    quality = min(1.0, games / required_minimum)                 │
│                                                                 │
│  Signal weight is adjusted:                                     │
│                                                                 │
│    effective_weight = base_weight × quality                     │
│                                                                 │
│  Remaining weight redistributed to higher-quality signals       │
│                                                                 │
│  Example:                                                       │
│    Matchup: 6 games (quality = 6/10 = 0.60)                     │
│    Base weight: 20%                                             │
│    Effective weight: 20% × 0.60 = 12%                           │
│    Redistributed: 8% goes to meta/proficiency/synergy           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 9: Complex Scenarios Requiring Contextual Data

### When Statistics Aren't Enough

Some scenarios require domain knowledge that cannot be derived from win/loss data:

```
┌─────────────────────────────────────────────────────────────────┐
│            SCENARIOS BEYOND STATISTICAL INFERENCE               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CHAMPION REWORKS                                            │
│     Problem: Skarner rework (2024) makes all prior data         │
│              irrelevant. Stats say 52% WR, but that's old       │
│              Skarner, not current kit.                          │
│     Need: Rework date database to filter stale data             │
│                                                                 │
│  2. META SHIFTS WITHIN PATCH                                    │
│     Problem: A counter-strategy emerges mid-patch. Stats        │
│              don't reflect it yet.                              │
│     Need: Domain expert flag for "meta has shifted"             │
│                                                                 │
│  3. HIDDEN CHAMPION POOLS                                       │
│     Problem: Player has 0 stage games on Aurora, but we         │
│              know from scrims/solo queue they're practicing it. │
│     Need: Domain expert intel on hidden comfort picks           │
│                                                                 │
│  4. TEAM STRATEGY CONTEXT                                       │
│     Problem: Stats say pick X, but team is known for            │
│              split-push comp and X doesn't fit.                 │
│     Need: Team playstyle profiles                               │
│                                                                 │
│  5. PLAYER MENTAL/FORM                                          │
│     Problem: Player is in a slump, stats don't reflect it yet.  │
│     Need: Recent form indicators beyond W/L                     │
│                                                                 │
│  6. MECHANICAL SYNERGIES                                        │
│     Problem: Orianna + Nocturne have "ball delivery" combo      │
│              that stats can't capture (requires knowing kits).  │
│     Need: Champion interaction database                         │
│                                                                 │
│  7. COMP ARCHETYPE REQUIREMENTS                                 │
│     Problem: Team needs "engage" but stats just show            │
│              individual champion strength.                      │
│     Need: Champion role/archetype tags                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Contextual Data Sources

| Data Type | Source | Effort | Priority |
|-----------|--------|--------|----------|
| Rework dates | Domain expert (one-time) | Low (30 min) | High |
| Team playstyles | Domain expert (per team) | Medium (2-3 hrs) | Medium |
| Hidden pools | Domain expert (ongoing) | High (continuous) | Low |
| Champion archetypes | Domain expert (one-time) | Medium (2-3 hrs) | Medium |
| Mechanical synergies | Domain expert (one-time) | High (8+ hrs) | Low |

### Recommended Contextual Data Files

**Minimum viable (for hackathon):**

```
knowledge/
├── champion_reworks.json      # Filter stale data
│   {
│     "Skarner": "2024-03-15",
│     "Aurelion Sol": "2023-02-08"
│   }
│
└── team_playstyles.json       # Top 10-15 teams only
    {
      "G2": {
        "style": "aggressive",
        "priorities": ["early_game", "skirmish"],
        "avoid": ["scaling", "protect_adc"]
      }
    }
```

**Nice to have (if time permits):**

```
knowledge/
├── champion_archetypes.json   # Role in team comps
│   {
│     "Orianna": ["teamfight", "zone_control", "ball_delivery"],
│     "Nocturne": ["dive", "pick", "vision_denial"]
│   }
│
├── hidden_pools.json          # Scrim/solo queue intel
│   {
│     "Caps": {
│       "practicing": ["Aurora", "Smolder"],
│       "source": "Korean solo queue bootcamp"
│     }
│   }
│
└── mechanical_synergies.json  # Kit-based combos
    {
      "Orianna+Nocturne": {
        "combo": "Ball delivery via Nocturne ult",
        "synergy_boost": 0.15
      }
    }
```

### How to Procure Contextual Data

```
┌─────────────────────────────────────────────────────────────────┐
│                  DATA PROCUREMENT STRATEGY                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PHASE 1: Essential (Domain Expert - 2 hours)                   │
│  ├── Champion rework dates (30 min)                             │
│  ├── Top 15 team playstyles (1 hour)                            │
│  └── Review automated outputs for errors (30 min)               │
│                                                                 │
│  PHASE 2: Enhanced (Domain Expert - 3 hours)                    │
│  ├── Champion archetype tags for top 50 champions (2 hours)     │
│  └── Known hidden pools for top 20 players (1 hour)             │
│                                                                 │
│  PHASE 3: Advanced (Post-Hackathon)                             │
│  ├── Mechanical synergy database                                │
│  ├── Real-time meta shift detection                             │
│  └── Solo queue/scrim data integration                          │
│                                                                 │
│  AUTOMATION OPPORTUNITIES                                       │
│  ├── LLM-assisted: Generate initial archetypes from             │
│  │   champion descriptions, human reviews                       │
│  ├── Solo queue APIs: Track player practice patterns            │
│  └── Patch notes parsing: Detect significant changes            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Architecture

### Data Sources

**CSV Data** (downloaded via GitHub release `data-v1.0.0`):
```
outputs/full_2024_2025_v2/csv/
├── champions.csv          # Champion metadata
├── draft_actions.csv      # All pick/ban actions (68K+)
├── games.csv              # Game outcomes (3,436)
├── player_game_stats.csv  # Player performance per game (34K+)
├── players.csv            # Player roster (445)
├── series.csv             # Series metadata (1,482)
├── teams.csv              # Team info (57)
├── team_objectives.csv    # Team objective stats (v2 new)
└── tournaments.csv        # Tournament metadata (v2 new)
```

Download: `./scripts/download-data.sh v1.0.0`

### Pre-computed Knowledge Files (committed to repo)

| File | Source | Contents |
|------|--------|----------|
| `champion_counters.json` | Computed from matchup data | Champion pairs → lane and team counter scores |
| `champion_synergies.json` | Computed from game outcomes | Champion pairs → normalized synergy score |
| `flex_champions.json` | Computed from v3.43+ API data | Champion → role probability distribution |
| `meta_stats.json` | Computed from draft_actions | Current patch meta statistics |
| `patch_info.json` | Computed from series data | Patch dates and game counts |
| `player_proficiency.json` | Computed from player_game_stats | Player + Champion → composite performance score |
| `player_roles.json` | Computed from player_game_stats | Player → primary role |
| `role_baselines.json` | Computed from player_game_stats | Role → average stats for normalization |
| `skill_transfers.json` | Computed from co-play patterns | Champion → similar champions |

### Reference Data (committed to repo)

| File | Contents |
|------|----------|
| `knowledge_base.json` | Champion metadata (positions, damage types, base stats) |
| `synergies.json` | Detailed synergy relationships |
| `patch_dates.json` | Patch version → date mapping |
| `rework_patch_mapping.json` | Champion rework history for data filtering |

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERIODIC (weekly/patch)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GRID API ──► Raw JSON ──► CSV Export ──► GitHub Release        │
│      │                                                   │      │
│      │                                                   │      │
│      ▼                                                   ▼      │
│  v2 fields:               Precompute:     Tag: data-vX.Y.Z      │
│  • roles (actual)         • champion_synergies                  │
│  • team_objectives        • champion_counters                   │
│  • tournaments            • player_proficiency                  │
│                           • role_baselines                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DEV SETUP                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ./scripts/download-data.sh v1.0.0                              │
│  Downloads CSVs + raw JSONs to outputs/full_2024_2025_v2/       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AT STARTUP                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Load knowledge/*.json into memory                              │
│  Initialize DuckDB connection to outputs/*/csv/ files           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PER REQUEST                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Flex resolution ─────────► In-memory lookups (fast)         │
│  2. Proficiency lookup ──────► Pre-computed JSON (fast)         │
│  3. Synergy/Counter lookup ──► Pre-computed JSON (fast)         │
│  4. Score combination ───────► CPU (microseconds)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA                                                   │
├─────────────────────────────────────────────────────────────────┤
│ • Update GRID fetch script with new fields                      │
│   (roles, netWorth, moneyPerMinute, objectives)                 │
│ • Re-fetch v3.43+ series (~693 series)                          │
│ • Re-export CSVs with actual role data and performance metrics  │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: PRECOMPUTE                                             │
├─────────────────────────────────────────────────────────────────┤
│ • Build flex_champions.json from role data                      │
│ • Build team_champion_players.json from trading patterns        │
│ • Build role_baselines.json for stat normalization              │
│ • Build player_proficiency.json with composite scores           │
│ • Build champion_synergies.json with normalized win deltas      │
│ • Build skill_transfers.json from co-play mining                │
│ • Fetch champion data from Data Dragon                          │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: CORE ENGINE                                            │
├─────────────────────────────────────────────────────────────────┤
│ • Flex resolver (role probability estimation)                   │
│ • Proficiency scorer (with multiple metrics)                    │
│ • Contextual strength calculator (for surprise picks)           │
│ • Confidence penalty system                                     │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: ANALYTICS                                              │
├─────────────────────────────────────────────────────────────────┤
│ • Matchup calculator (lane + team counter)                      │
│ • Synergy calculator (normalized + co-pick)                     │
│ • Meta tier calculator                                          │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: INTEGRATION                                            │
├─────────────────────────────────────────────────────────────────┤
│ • Combine all components into recommendation engine             │
│ • Weight adjustment for uncertainty/data quality                │
│ • Flag and warning generation                                   │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 6: API                                                    │
├─────────────────────────────────────────────────────────────────┤
│ • Update REST endpoints to use new engine                       │
│ • Update WebSocket messages with confidence/warnings            │
│ • Frontend updates to display uncertainty indicators            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Open Questions

| Question | Options | Decision Needed |
|----------|---------|-----------------|
| Confidence threshold for "uncertain" | 0.6, 0.7, or 0.8? | Test with real data |
| Weight distribution | Current: 15/30/20/20/15 | May need tuning |
| Surprise pick threshold | Current: contextual > 0.65 | Domain expert input |
| Minimum sample sizes | Current: 10/15/20 games | Validate with data |
| Normalization method | Z-score vs percentile | Test both |

---

*Version 1.2 | January 2026*
*v1.2: Removed style fit, added misleading signals analysis, added complex scenarios section, integrated new performance metrics*
*v1.1: Updated flex resolution to use team-champion-player trading patterns*
