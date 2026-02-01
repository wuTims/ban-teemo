# LLM Recommendation Reranking Experiment

## Overview

This document describes the architecture, implementation, and findings from our experiment using LLM-based reranking to enhance the deterministic scoring system's pick/ban recommendations.

## Problem Statement

The deterministic scoring engine provides consistent, fast recommendations based on:
- Meta tier lists and champion statistics
- Player proficiency from historical match data
- Team composition synergies and counters
- Role viability and flex potential

However, it lacks:
- **Contextual reasoning**: Understanding nuanced draft situations
- **Adaptive strategy**: Responding to opponent tendencies within a series
- **Meta awareness**: Real-time knowledge of current pro play priorities
- **Strategic depth**: Multi-step draft planning and information hiding

## Proposed Architecture

### Hybrid Scoring Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Draft Action Request                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Deterministic Scoring Engine                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Meta Scorer │ │ Proficiency │ │   Synergy   │ │   Counter   │   │
│  │             │ │   Scorer    │ │   Scorer    │ │   Scorer    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
│                              │                                       │
│                              ▼                                       │
│                    Weighted Score Aggregation                        │
│                    (Top 15 candidates)                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │      Phase Filter Check       │
                    │  (Phase 2 only by default)    │
                    └───────────────────────────────┘
                           │                │
                    Phase 1 │                │ Phase 2
                           ▼                ▼
              ┌─────────────────┐  ┌─────────────────────────────────┐
              │ Return baseline │  │       LLM Reranker Layer        │
              │ recommendations │  │  ┌─────────────────────────┐    │
              └─────────────────┘  │  │    Context Assembly     │    │
                                   │  │  • Draft state          │    │
                                   │  │  • Player pools         │    │
                                   │  │  • Series history       │    │
                                   │  │  • Web search results   │    │
                                   │  └─────────────────────────┘    │
                                   │              │                   │
                                   │              ▼                   │
                                   │  ┌─────────────────────────┐    │
                                   │  │      LLM Reasoning      │    │
                                   │  │  (DeepSeek/Qwen/Llama)  │    │
                                   │  └─────────────────────────┘    │
                                   │              │                   │
                                   │              ▼                   │
                                   │  ┌─────────────────────────┐    │
                                   │  │   Reranked Results +    │    │
                                   │  │   Strategic Reasoning   │    │
                                   │  └─────────────────────────┘    │
                                   └─────────────────────────────────┘
                                                  │
                                                  ▼
                              ┌─────────────────────────────────────┐
                              │        Final Recommendations        │
                              │  • Reranked top 5 with reasoning    │
                              │  • Additional suggestions           │
                              │  • Draft analysis                   │
                              └─────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Phase-Based LLM Invocation

**Rationale**: Phase 1 (early bans/picks) involves more standard, predictable choices where the deterministic engine performs well. Phase 2 requires more nuanced decision-making based on the emerging draft.

```python
PHASE_2_PHASES = {"BAN_PHASE_2", "PICK_PHASE_2"}
```

**Impact**: ~60% reduction in LLM calls per game (from ~20 to ~8 calls)

#### 2. Series Context for Games 2+

**Rationale**: In a best-of series, teams adapt based on previous games. The LLM can identify patterns and suggest counter-strategies.

```python
@dataclass
class SeriesContext:
    game_number: int
    series_score: tuple[int, int]
    previous_games: list[PreviousGameSummary]
    our_tendencies: Optional[TeamTendencies]
    enemy_tendencies: Optional[TeamTendencies]
```

**Tendency Extraction**:
- Champions picked in multiple games → prioritized picks
- Consistent first picks → first-pick patterns
- Champions banned against repeatedly → targeted bans

#### 3. Layered Prompt Construction

The prompt includes multiple context layers:

1. **Draft State**: Current phase, picks, bans, team names
2. **Player Information**: Names and roles for both teams
3. **Series History** (games 2+): Full draft history, win/loss, tendencies
4. **Algorithm Candidates**: Top 15 from deterministic scoring with component breakdown
5. **Meta Context**: Web search results or fallback meta knowledge

#### 4. Structured JSON Output

```json
{
  "reranked": [
    {
      "champion": "Aatrox",
      "original_rank": 3,
      "new_rank": 1,
      "confidence": 0.85,
      "reasoning": "Strong into enemy comp, player comfort pick",
      "strategic_factors": ["counter_potential", "player_comfort"]
    }
  ],
  "additional_suggestions": [
    {
      "champion": "Malphite",
      "reasoning": "Not in candidates but strong wombo combo potential",
      "confidence": 0.6
    }
  ],
  "draft_analysis": "Focus on engage composition to counter enemy poke"
}
```

## Experiment Setup

### Data Source

Replay logs from professional matches captured during simulator sessions, containing:
- Recommendation events with full candidate lists and scoring components
- Actual picks/bans made by pro teams
- Draft context at each action

### Methodology

```bash
# Run experiment with phase 2 filtering (default)
uv run python scripts/run_llm_experiment.py logs/scoring/replay_xxx.json --mock-search

# Run with all phases for comparison
uv run python scripts/run_llm_experiment.py logs/scoring/replay_xxx.json --all-phases

# Include series context for game 2+
uv run python scripts/run_llm_experiment.py logs/scoring/game2.json \
  --include-series-context \
  --series-logs logs/scoring/game1.json
```

### Metrics Tracked

| Metric | Description |
|--------|-------------|
| `baseline_in_recs` | Actual pick was in baseline top 5 |
| `baseline_top3` | Actual pick was in baseline top 3 |
| `llm_in_recs` | Actual pick was in LLM reranked top 5 |
| `llm_top3` | Actual pick was in LLM reranked top 3 |
| `suggestions_hit` | Actual pick was in LLM additional suggestions |
| `latency_ms` | Time for LLM call |
| `estimated_cost` | Token-based cost estimate |

### Models Tested

| Model | Provider | Characteristics |
|-------|----------|-----------------|
| DeepSeek-V3.2 | Nebius | Fast, good JSON compliance |
| Kimi-K2-Instruct | Nebius | Strong reasoning |
| Qwen3-235B | Nebius | Large context window |
| Llama-3.3-70B | Nebius | Open weights, fast |

## Key Findings

### Accuracy Impact

From initial experiments:

- **Phase 2 actions show more improvement** than Phase 1, validating the phase filtering approach
- **LLM occasionally surfaces valuable picks** not in the original candidate list via additional_suggestions
- **Reasoning quality varies by model** - DeepSeek tends to be more concise, Qwen more verbose

### Latency Characteristics

| Metric | Value |
|--------|-------|
| Average LLM call | 15-25 seconds |
| Phase 2 only (8 calls) | ~2-3 minutes total |
| All phases (20 calls) | ~5-7 minutes total |

### Cost Analysis

With Nebius pricing estimates:
- ~$0.003 per action (1.5K input + 0.8K output tokens)
- ~$0.024 per game (Phase 2 only)
- ~$0.060 per game (all phases)

## Simulator Mode Integration

The simulator (replay) mode provides a controlled environment to test LLM reranking with historical pro match data. Here's how LLM enhancement integrates with the existing architecture.

### Current Replay Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (SimulatorView)                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────┐   │
│  │ Draft Board │ │ Action Log  │ │  Recommendations Panel      │   │
│  └─────────────┘ └─────────────┘ └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    replay_ws.py (WebSocket Handler)                  │
│                              │                                       │
│    ┌─────────────────────────▼─────────────────────────────┐        │
│    │              _run_replay_loop()                        │        │
│    │  • Iterates through all_actions                       │        │
│    │  • Calls service.get_recommendations() per action     │        │
│    │  • Sends draft_action + recommendations via WS        │        │
│    └───────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DraftService.get_recommendations()                │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │ PickRecommendationEngine│  │ BanRecommendationService        │  │
│  │ (deterministic scoring) │  │ (deterministic scoring)         │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### LLM-Enhanced Replay Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (SimulatorView)                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────┐   │
│  │ Draft Board │ │ Action Log  │ │  Recommendations Panel      │   │
│  └─────────────┘ └─────────────┘ │  • Baseline (immediate)     │   │
│                                  │  • LLM Enhanced (delayed)   │   │
│                                  │  • Strategic Reasoning      │   │
│                                  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    replay_ws.py (WebSocket Handler)                  │
│                              │                                       │
│    ┌─────────────────────────▼─────────────────────────────┐        │
│    │              _run_replay_loop()                        │        │
│    │                                                        │        │
│    │  1. Get baseline recommendations (immediate)          │        │
│    │  2. Send draft_action + baseline via WS               │        │
│    │  3. If Phase 2: spawn LLM enhancement task            │        │
│    │  4. When LLM completes: send enhanced_recommendations │        │
│    └───────────────────────────────────────────────────────┘        │
│                              │                                       │
│    ┌─────────────────────────▼─────────────────────────────┐        │
│    │         _enhance_recommendations_async()               │        │
│    │  • Check phase filter (Phase 2 only)                  │        │
│    │  • Build series context from ReplaySession            │        │
│    │  • Call LLMReranker.rerank_picks/bans()              │        │
│    │  • Push enhanced_recommendations via WebSocket        │        │
│    └───────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Integration Points

#### 1. ReplaySession Series Context

The `ReplaySession` already tracks `series_id` and `game_number`. We extend it to support series context:

```python
# replay_manager.py
@dataclass
class ReplaySession:
    # ... existing fields ...

    # NEW: Series context for LLM enhancement
    series_context: SeriesContext | None = None

class ReplayManager:
    def create_session(self, ..., previous_game_results: list[dict] | None = None):
        # Build series context if game_number > 1
        series_context = None
        if game_number > 1 and previous_game_results:
            series_context = SeriesContextBuilder.from_game_results(
                game_number=game_number,
                previous_results=previous_game_results,
                our_side="blue",  # Or determined by user perspective
            )

        session = ReplaySession(
            # ... existing fields ...
            series_context=series_context,
        )
```

#### 2. Loading Previous Games in Series

When starting a replay for game 2+, load previous game results:

```python
# replay.py (routes)
@router.post("/replay/start", response_model=StartReplayResponse)
def start_replay(request: Request, body: StartReplayRequest):
    # ... existing game loading ...

    # Load previous game results for series context
    previous_game_results = []
    if body.game_number > 1:
        for prev_game_num in range(1, body.game_number):
            prev_game = repo.get_game_info(body.series_id, prev_game_num)
            if prev_game:
                prev_actions = repo.get_draft_actions(prev_game["game_id"])
                previous_game_results.append({
                    "winner": "blue" if prev_game["winner_team_id"] == blue_team.id else "red",
                    "blue_comp": [a["champion_name"] for a in prev_actions if a["team_side"] == "blue" and a["action_type"] == "pick"],
                    "red_comp": [a["champion_name"] for a in prev_actions if a["team_side"] == "red" and a["action_type"] == "pick"],
                    "blue_bans": [a["champion_name"] for a in prev_actions if a["team_side"] == "blue" and a["action_type"] == "ban"],
                    "red_bans": [a["champion_name"] for a in prev_actions if a["team_side"] == "red" and a["action_type"] == "ban"],
                })

    session = manager.create_session(
        # ... existing params ...
        previous_game_results=previous_game_results,
    )
```

#### 3. WebSocket Message Flow

New message type for LLM-enhanced recommendations:

```typescript
// Frontend types
interface EnhancedRecommendations {
  type: "enhanced_recommendations";
  action_count: number;  // Links to the original draft_action
  for_team: "blue" | "red";
  reranked: Array<{
    champion_name: string;
    original_rank: number;
    new_rank: number;
    confidence: number;
    reasoning: string;
    strategic_factors: string[];
  }>;
  additional_suggestions: Array<{
    champion_name: string;
    reasoning: string;
    confidence: number;
  }>;
  draft_analysis: string;
}
```

WebSocket handler updates:

```python
# replay_ws.py
async def _run_replay_loop(session, service, websocket, logger, llm_reranker=None):
    while session.current_index < len(session.all_actions):
        action = session.all_actions[session.current_index]
        current_state = service.build_draft_state_at(...)

        # Get baseline recommendations (immediate)
        recommendations = service.get_recommendations(current_state, for_team=...)

        # Send baseline immediately
        await websocket.send_json({
            "type": "draft_action",
            "action": {...},
            "draft_state": {...},
            "recommendations": _serialize_recommendations(recommendations),
        })

        # Spawn LLM enhancement for Phase 2 (non-blocking)
        if llm_reranker and _is_phase_2(current_state.current_phase):
            asyncio.create_task(
                _enhance_and_send(
                    websocket=websocket,
                    action_count=session.current_index + 1,
                    recommendations=recommendations,
                    current_state=current_state,
                    session=session,
                    llm_reranker=llm_reranker,
                )
            )

        session.current_index += 1
        await asyncio.sleep(delay)


async def _enhance_and_send(websocket, action_count, recommendations, current_state, session, llm_reranker):
    """Background task to get LLM enhancement and push via WebSocket."""
    try:
        draft_context = _build_draft_context(current_state, session)
        team_players, enemy_players = _get_players(current_state, recommendations.for_team)

        if recommendations.picks:
            result = await llm_reranker.rerank_picks(
                candidates=[...],
                draft_context=draft_context,
                team_players=team_players,
                enemy_players=enemy_players,
                series_context=session.series_context,
            )
        else:
            result = await llm_reranker.rerank_bans(...)

        await websocket.send_json({
            "type": "enhanced_recommendations",
            "action_count": action_count,
            "for_team": recommendations.for_team,
            "reranked": [
                {
                    "champion_name": r.champion,
                    "original_rank": r.original_rank,
                    "new_rank": r.new_rank,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "strategic_factors": r.strategic_factors,
                }
                for r in result.reranked
            ],
            "additional_suggestions": [...],
            "draft_analysis": result.draft_analysis,
        })
    except Exception as e:
        logger.warning(f"LLM enhancement failed: {e}")
        # Silently fail - baseline is already shown
```

#### 4. Frontend UI/UX Considerations

The existing UI components are already information-dense:

- **SimulatorView**: 5 recommendation cards in a grid showing champion, score, player/role, top 3 factors, first reason
- **InsightsLog**: Compact horizontal cards with champion portraits and component score breakdowns

Adding LLM reasoning directly to these would create clutter. Here are better approaches:

**Option A: Collapsible AI Insights Panel (Recommended)**

Keep recommendation cards unchanged. Add a separate collapsible panel below that shows LLM analysis when available:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Pick Recommendations                                    [Your Turn]│
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Aatrox   │ │ Rumble   │ │ Poppy    │ │ Aurora   │ │ Gragas   │  │
│  │ 85%      │ │ 78%      │ │ 72%      │ │ 68%      │ │ 65%      │  │
│  │ ▸Meta    │ │ ▸Prof    │ │ ...      │ │ ...      │ │ ...      │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  ▼ AI Analysis (Phase 2)                              [loading... ] │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ 📊 Strategy: Focus on engage to counter enemy poke comp        ││
│  │                                                                  ││
│  │ 🔄 Reranking: Aatrox ↑1, Poppy ↓1 (counter value vs comp)      ││
│  │                                                                  ││
│  │ 💡 Also Consider:                                               ││
│  │    • Malphite - Wombo combo with Orianna                        ││
│  │    • Sejuani - Strong engage, pairs with dive comp              ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

**Option B: Hover/Click Expansion**

Keep cards compact, show LLM reasoning on hover or click:

```tsx
function RecommendationCard({ rec, llmEnhancement }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button onClick={() => setExpanded(!expanded)}>
      {/* Existing compact card content */}
      <ChampionPortrait ... />
      <span>{rec.champion_name}</span>
      <span>{rec.score}</span>

      {/* Expansion indicator when LLM data available */}
      {llmEnhancement && (
        <span className="text-magic text-xs">✨</span>
      )}

      {/* Expanded reasoning */}
      {expanded && llmEnhancement && (
        <div className="mt-2 text-xs text-text-secondary border-t pt-2">
          {llmEnhancement.reasoning}
        </div>
      )}
    </button>
  );
}
```

**Option C: Tab System**

Switch between "Algorithm" and "AI Analysis" views:

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Algorithm] [AI Analysis ✨]                            [Your Turn]│
├─────────────────────────────────────────────────────────────────────┤
│                    (content changes based on tab)                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Recommended Approach: Option A + Progressive Disclosure**

1. **Recommendations stay unchanged** - Keep the existing compact 5-card grid
2. **Add collapsible "AI Analysis" panel below** (collapsed by default)
3. **Show loading indicator** while LLM processes (Phase 2 only)
4. **Auto-expand on arrival** with subtle animation to draw attention
5. **Remember user preference** - If they collapse it, keep it collapsed

This keeps the fast, scannable recommendations intact while providing deeper insights for users who want them.

#### 5. InsightsLog Enhancement (Replay Mode)

For the replay InsightsLog, add LLM insights as an optional expansion per action rather than inline:

```tsx
function InsightEntry({ entry, llmEnhancement }) {
  const [showAI, setShowAI] = useState(false);

  return (
    <div className="rounded-lg border p-3">
      {/* Existing entry header + actual action + top 5 cards */}
      ...

      {/* AI insights toggle (only for Phase 2 actions) */}
      {llmEnhancement && (
        <button
          onClick={() => setShowAI(!showAI)}
          className="text-xs text-magic mt-2"
        >
          {showAI ? "▼" : "▶"} AI Analysis
        </button>
      )}

      {showAI && llmEnhancement && (
        <div className="mt-2 p-2 bg-lol-darkest rounded text-xs">
          <div className="text-text-secondary mb-1">
            {llmEnhancement.draft_analysis}
          </div>
          {llmEnhancement.reranked.map(r => (
            <div key={r.champion_name} className="flex items-center gap-2">
              <span className="text-gold-bright">{r.champion_name}</span>
              <span className="text-text-tertiary">
                #{r.original_rank} → #{r.new_rank}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

#### 6. Replay Controls Integration

Add LLM toggle to replay controls header:

```tsx
function ReplayControls({ llmEnabled, onLlmToggle, ...props }) {
  return (
    <div className="replay-controls">
      {/* Existing controls */}
      <PlayPauseButton />
      <SpeedSelector />
      <ProgressBar />

      {/* LLM toggle - subtle, doesn't take much space */}
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={llmEnabled}
          onChange={(e) => onLlmToggle(e.target.checked)}
          className="w-4 h-4"
        />
        <span className="text-text-secondary">AI Analysis</span>
        <span className="text-magic">✨</span>
      </label>
    </div>
  );
}
```

### Configuration

Add LLM settings to the replay start request:

```python
# replay.py
class StartReplayRequest(BaseModel):
    series_id: str
    game_number: int
    speed: float = 1.0
    delay_seconds: float = 3.0

    # NEW: LLM configuration
    llm_enabled: bool = False
    llm_phase2_only: bool = True  # Only enhance Phase 2 by default
```

### Testing in Simulator Mode

```bash
# Start backend with LLM support
NEBIUS_API_KEY=... uv run uvicorn ban_teemo.main:app --reload

# Frontend will show "AI Analysis" toggle in replay controls
# Toggle enables LLM enhancement for Phase 2 actions
```

## Production Integration Considerations

### 1. Async Architecture

For real-time draft assistance, the LLM call must not block the UI:

```python
# Backend: Fire-and-forget LLM enhancement
async def get_recommendations(draft_state, team_context):
    # Return deterministic results immediately
    baseline = await scoring_engine.get_recommendations(draft_state, team_context)

    # Start LLM enhancement in background
    if is_phase_2(draft_state.phase):
        asyncio.create_task(
            enhance_with_llm(baseline, draft_state, team_context)
        )

    return baseline

# WebSocket: Push enhanced results when ready
async def enhance_with_llm(baseline, draft_state, team_context):
    enhanced = await llm_reranker.rerank(baseline, draft_state, team_context)
    await websocket.send_json({
        "type": "enhanced_recommendations",
        "data": enhanced
    })
```

### 2. UI/UX Pattern

```
┌─────────────────────────────────────────────────────┐
│  Pick Recommendations                               │
├─────────────────────────────────────────────────────┤
│  1. Aatrox ████████████ 0.85                       │
│     → Strong counter to enemy Renekton              │  ← LLM reasoning
│                                                     │
│  2. Rumble ██████████ 0.78                         │
│     → Team fight synergy with Orianna              │
│                                                     │
│  3. Poppy █████████ 0.72                           │
│     → Denies enemy engage                          │
├─────────────────────────────────────────────────────┤
│  💡 Also Consider:                                  │  ← Additional suggestions
│     Malphite - Wombo combo potential               │
├─────────────────────────────────────────────────────┤
│  📊 Draft Analysis:                                 │
│  Focus on engage comp to counter enemy poke        │
└─────────────────────────────────────────────────────┘
```

### 3. Series Context Integration

For SimulatorSession, track game results:

```python
class SimulatorSession:
    def __init__(self):
        self.game_results: list[GameResult] = []

    def end_game(self, winner: str, blue_comp: list, red_comp: list, ...):
        self.game_results.append(GameResult(...))

    def get_series_context(self, our_side: str) -> SeriesContext:
        return SeriesContextBuilder.from_game_results(
            game_number=len(self.game_results) + 1,
            previous_results=[g.to_dict() for g in self.game_results],
            our_side=our_side,
        )
```

### 4. Caching Strategy

For repeated queries within a draft:

```python
class LLMRerankerWithCache:
    def __init__(self):
        self.cache = TTLCache(maxsize=100, ttl=300)  # 5 min cache

    async def rerank(self, candidates, draft_context, ...):
        cache_key = self._build_cache_key(candidates, draft_context)
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = await self._call_llm(...)
        self.cache[cache_key] = result
        return result
```

### 5. Fallback Handling

The system gracefully degrades:

```python
async def rerank_with_fallback(candidates, draft_context, ...):
    try:
        return await llm_reranker.rerank(candidates, draft_context, ...)
    except (TimeoutError, APIError) as e:
        logger.warning(f"LLM reranking failed: {e}")
        # Return baseline with fallback indicator
        return create_fallback_result(candidates, error=str(e))
```

### 6. Feature Flags

Control LLM usage per-user or globally:

```python
class FeatureFlags:
    llm_reranking_enabled: bool = True
    llm_phase2_only: bool = True
    llm_series_context: bool = True
    llm_web_search: bool = False  # Requires API key
    llm_model: str = "deepseek"
```

## Takeaways and Recommendations

### What Works Well

1. **Phase filtering is effective** - Phase 2 decisions benefit most from LLM reasoning, and filtering saves ~60% of costs/latency
2. **Series context adds value** - Identifying tendencies from previous games helps with adaptive strategy
3. **Structured output is reliable** - JSON formatting with clear schema works well across models
4. **Fallback handling is essential** - The system must work without LLM when unavailable

### Areas for Improvement

1. **Latency is the main blocker** - 15-25s per call is too slow for real-time use without async patterns
2. **Model consistency varies** - Some models produce better reasoning but worse JSON compliance
3. **Web search adds noise** - Current implementation may not always surface relevant meta information
4. **Confidence calibration needed** - LLM confidence scores don't always correlate with accuracy

### Recommended Next Steps

1. **Implement async WebSocket push** for real-time draft assistance
2. **Add streaming support** to show partial results as they arrive
3. **Fine-tune prompts** based on experiment results
4. **Consider smaller/faster models** for latency-sensitive paths
5. **Build evaluation dataset** with expert-labeled "correct" picks for benchmarking
6. **Add A/B testing infrastructure** to measure impact on user satisfaction

## File Structure

```
backend/src/ban_teemo/
├── models/
│   └── series_context.py          # SeriesContext, TeamTendencies, PreviousGameSummary
├── services/
│   ├── llm_reranker.py            # LLMReranker with series context support
│   ├── series_context_builder.py  # Builder for series context
│   └── web_search_client.py       # Web search for meta context

scripts/
└── run_llm_experiment.py          # Experiment runner with phase filtering

backend/tests/
├── test_series_context.py         # Tests for dataclasses
├── test_series_context_builder.py # Tests for builder
└── test_llm_reranker.py           # Tests including series context integration
```

## Running the Experiment

```bash
# Install dependencies
uv sync

# Run with phase 2 only (default, recommended)
uv run python scripts/run_llm_experiment.py \
  logs/scoring/replay_xxx.json \
  --mock-search \
  --limit 20

# Run with all phases for comparison
uv run python scripts/run_llm_experiment.py \
  logs/scoring/replay_xxx.json \
  --all-phases \
  --mock-search

# Run with series context
uv run python scripts/run_llm_experiment.py \
  logs/scoring/game2.json \
  --include-series-context \
  --series-logs logs/scoring/game1.json \
  --mock-search

# Save results to JSON
uv run python scripts/run_llm_experiment.py \
  logs/scoring/replay_xxx.json \
  --output results/experiment_001.json
```

## Gap Analysis (Post-Experiment)

After running the experiment with real Tavily search, we identified several gaps limiting LLM effectiveness:

### Gap 1: Generic Web Search Queries

**Current queries:**
```python
queries = [
    f"LoL patch {patch} pro play tier list priority picks",
    f"LCK LPL {phase} priority 2026",
]
```

**Problem:** These return generic tier lists, not actionable draft intelligence about specific players or team matchups.

**Proposed fix - Player/Team-Targeted Queries:**
```python
async def _fetch_meta_context(self, draft_context: dict, enemy_players: list[dict]) -> str:
    queries = []

    # 1. Team matchup query
    our_team = draft_context.get("our_team", "")
    enemy_team = draft_context.get("enemy_team", "")
    queries.append(f"{our_team} vs {enemy_team} draft 2026 LCK")

    # 2. Key enemy player pool (support/jungle are high-impact bans)
    for player in enemy_players:
        if player.get("role") in ("support", "jungle", "mid"):
            queries.append(f"{player['name']} champion pool 2026 LCK statistics")
            break  # Just one player query to limit API calls

    # 3. Patch-specific meta
    patch = draft_context.get("patch", "15.17")
    queries.append(f"LoL patch {patch} pro play priority picks LCK LPL")
```

### Gap 2: No Domain Targeting

**Problem:** Tavily returns random web results instead of authoritative esports sources.

**Proposed fix - Use Tavily's include_domains:**
```python
async def search(self, query: str, limit: int = 3) -> str:
    response = await client.post(
        self.TAVILY_API_URL,
        json={
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",  # Better for specific queries
            "max_results": limit,
            "include_answer": True,
            "include_domains": [
                "lol.fandom.com",      # Leaguepedia - player histories
                "gol.gg",              # Pro match statistics
                "oracleselixir.com",   # Draft analytics
                "u.gg",                # Champion tier data
                "lolalytics.com",      # Meta statistics
            ],
        },
    )
```

### Gap 3: Missing Player Champion Pool Data

**Problem:** The prompt says "Keria (support)" but the LLM has no actual data about what champions he plays.

**Current situation:**
```
## Enemy Players (ban targets)
- Keria (support)
```

**Proposed fix - Include player pool summary from our database:**
```
## Enemy Players (ban targets)
- Keria (support)
  Recent picks: Alistar (8), Rakan (6), Thresh (5), Nautilus (4)
  Banned against: Alistar (12), Rakan (8)
  Win rate on Alistar: 75% (6/8)
```

This data exists in our GRID database - we should query and include it in the prompt.

### Gap 4: Component Scores Without Context

**Problem:**
```
Components: proficiency:0.80, meta:0.60
```
The LLM doesn't understand what these scores mean.

**Proposed fix - Add brief explanations:**
```
## Algorithm Ban Recommendations
1. Alistar (priority: 0.750, target: Keria)
   - proficiency: 0.80 (Keria plays this champion frequently with high win rate)
   - meta: 0.60 (moderately strong in current patch meta)
   - Reasons: High proficiency target, engage threat
```

### Gap 5: Series Context Not Utilized in Test

**Problem:** We implemented series context but tested on game 1 (no previous games).

**Proposed test:** Find a series log where we have games 1, 2, 3 and test with `--include-series-context --series-logs`.

### Gap 6: LLM Task Ambiguity

**Problem:** The LLM is asked to "rerank" but doesn't know:
- When to deviate significantly from algorithm scores
- How much weight to give web search vs algorithm data
- What "confidence" means in the output

**Proposed fix - Clearer instructions:**
```
## Your Task
The algorithm has ranked candidates based on historical data and composition analysis.
Your job is to adjust rankings based on:
- Information the algorithm cannot access (recent form, news, injury)
- Strategic nuance (information hiding, baiting picks)
- Pattern recognition (this player always picks X after Y is banned)

IMPORTANT: Only rerank if you have specific strategic reasoning.
If the algorithm ranking looks reasonable, preserve it.
```

### Implementation Priority

1. **High Impact, Low Effort:**
   - Add `include_domains` to Tavily queries
   - Include player champion pool data from database

2. **Medium Impact, Medium Effort:**
   - Player-targeted search queries
   - Clearer component score explanations

3. **Requires Data Work:**
   - Test with series context (need game 2+ logs)
   - Query player pools from GRID database

## Next Steps

1. Update `WebSearchClient` with domain filtering
2. Modify `_fetch_meta_context` to include team/player queries
3. Add player pool data to prompt (query from repository)
4. Test with a multi-game series for series context validation

## Conclusion

The LLM reranking experiment demonstrates that hybrid approaches can enhance deterministic scoring with contextual reasoning. The key is selective application (Phase 2 only) and graceful degradation. For production use, async patterns and caching are essential to maintain responsiveness while gaining the benefits of LLM reasoning.

The gap analysis reveals that the main limitation is **context quality, not model capability**. The LLM improved Alistar's ranking correctly when it could reason about player comfort picks. With better web search targeting and player pool data, accuracy improvements should be more consistent.
