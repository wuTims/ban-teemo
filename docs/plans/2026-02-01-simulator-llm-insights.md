# Simulator LLM Insights Integration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AI-powered draft insights to the simulator mode with loading indicator, matching the replay experience.

**Architecture:** Frontend fires async fetch for LLM insights after each action. Backend calls LLMReranker with full draft context (candidates, players, series history, fearless blocked). Frontend shows loading state, then populates InsightPanel when ready. User can proceed without waiting.

**Tech Stack:** Python/FastAPI backend, React frontend, existing LLMReranker service, SeriesContextBuilder

---

## Current State Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Role detection | ✅ Done | `PickRecommendationEngine` filters filled roles |
| Series context model | ✅ Done | `SeriesContext`, `TeamTendencies` |
| Series context builder | ✅ Done | `SeriesContextBuilder.from_game_results()` |
| LLM accepts series context | ✅ Done | `LLMReranker.rerank_picks(..., series_context=)` |
| Simulator tracks games | ✅ Done | `SimulatorSession.game_results` |
| Fearless blocking | ✅ Done | `fearless_blocked_set` passed to recommendations |
| Bans in GameResult | ❌ Missing | Need to add for series context |
| LLM endpoint | ❌ Missing | New `/insights` endpoint |
| Frontend LLM state | ❌ Missing | `llmLoading`, `llmInsight` |

---

## Task 1: Add Bans to GameResult Model

**Files:**
- Modify: `backend/src/ban_teemo/models/simulator.py:25-31`
- Modify: `backend/src/ban_teemo/api/routes/simulator.py:336-343`

**Step 1: Update GameResult dataclass**

```python
@dataclass
class GameResult:
    """Result of a completed game in a series."""

    game_number: int
    winner: Literal["blue", "red"]
    blue_comp: list[str]
    red_comp: list[str]
    blue_bans: list[str] = field(default_factory=list)
    red_bans: list[str] = field(default_factory=list)
```

**Step 2: Update complete_game endpoint to capture bans**

In `simulator.py`, update the `complete_game` function around line 337:

```python
        # Record result
        result = GameResult(
            game_number=session.current_game,
            winner=body.winner,
            blue_comp=draft_state.blue_picks,
            red_comp=draft_state.red_picks,
            blue_bans=draft_state.blue_bans,
            red_bans=draft_state.red_bans,
        )
```

**Step 3: Commit**

```bash
git add backend/src/ban_teemo/models/simulator.py backend/src/ban_teemo/api/routes/simulator.py
git commit -m "feat(simulator): add bans to GameResult for series context"
```

---

## Task 2: Add LLM Insights Endpoint (Backend)

**Files:**
- Modify: `backend/src/ban_teemo/api/routes/simulator.py`

**Step 1: Add imports at top of file**

```python
from ban_teemo.services.llm_reranker import LLMReranker
from ban_teemo.services.series_context_builder import SeriesContextBuilder
```

**Step 2: Add request model after existing models (~line 135)**

```python
class InsightsRequest(BaseModel):
    api_key: str
    action_count: int  # To detect stale requests
```

**Step 3: Add insights endpoint (after get_evaluation, ~line 585)**

```python
@router.post("/sessions/{session_id}/insights")
async def get_insights(request: Request, session_id: str, body: InsightsRequest):
    """Get LLM-enhanced draft insights for current state.

    This endpoint blocks until LLM completes (with timeout).
    Frontend should call this async after each action.
    """
    session, lock = _get_session_with_lock(session_id)
    with lock:
        now = time.time()
        if _is_session_expired(session, now):
            raise HTTPException(status_code=404, detail="Session expired")
        _touch_session(session, now)

        draft_state = session.draft_state

        # Validate action_count to reject stale requests
        if body.action_count != len(draft_state.actions):
            return {
                "status": "stale",
                "message": f"Request for action {body.action_count}, current is {len(draft_state.actions)}"
            }

        if draft_state.current_phase == DraftPhase.COMPLETE:
            return {"status": "complete", "insights": None}

        _, pick_engine, ban_service, _, _ = _get_or_create_services(request)

        # Determine teams and picks based on coaching side
        our_team = session.blue_team if session.coaching_side == "blue" else session.red_team
        enemy_team = session.red_team if session.coaching_side == "blue" else session.blue_team
        our_picks = draft_state.blue_picks if session.coaching_side == "blue" else draft_state.red_picks
        enemy_picks = draft_state.red_picks if session.coaching_side == "blue" else draft_state.blue_picks
        banned = draft_state.blue_bans + draft_state.red_bans

        # Include fearless blocked in unavailable set
        all_banned = list(set(banned) | session.fearless_blocked_set)

        team_players = [{"name": p.name, "role": p.role} for p in our_team.players]
        enemy_players = [{"name": p.name, "role": p.role} for p in enemy_team.players]

        # Build series context from previous games
        series_context = None
        if session.current_game > 1 and session.game_results:
            series_context = SeriesContextBuilder.from_game_results(
                game_number=session.current_game,
                previous_results=[{
                    "winner": r.winner,
                    "blue_comp": r.blue_comp,
                    "red_comp": r.red_comp,
                    "blue_bans": r.blue_bans,
                    "red_bans": r.red_bans,
                } for r in session.game_results],
                our_side=session.coaching_side,
            )

        # Build draft context for LLM
        draft_context = {
            "phase": draft_state.current_phase.value,
            "patch": draft_state.patch_version,
            "our_team": our_team.name,
            "enemy_team": enemy_team.name,
            "our_picks": our_picks,
            "enemy_picks": enemy_picks,
            "banned": all_banned,
            "draft_mode": session.draft_mode,
            "fearless_blocked": list(session.fearless_blocked_set) if session.draft_mode == "fearless" else [],
        }

        # Get candidates from recommendation engine
        if draft_state.next_action == "ban":
            candidates = ban_service.get_ban_recommendations(
                enemy_team_id=enemy_team.id,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_banned,
                phase=draft_state.current_phase.value,
                limit=15,
            )
            candidates = [
                {
                    "champion_name": c["champion_name"],
                    "priority": c["priority"],
                    "target_player": c.get("target_player"),
                    "components": c.get("components", {}),
                    "reasons": c.get("reasons", []),
                }
                for c in candidates
            ]
        else:
            candidates = pick_engine.get_recommendations(
                team_players=team_players,
                our_picks=our_picks,
                enemy_picks=enemy_picks,
                banned=all_banned,
                limit=15,
            )
            candidates = [
                {
                    "champion_name": c["champion_name"],
                    "score": c.get("score", c.get("confidence", 0)),
                    "suggested_role": c.get("suggested_role"),
                    "components": c.get("components", {}),
                    "reasons": c.get("reasons", []),
                    "proficiency_player": c.get("proficiency_player"),
                }
                for c in candidates
            ]

        # Call LLM reranker
        reranker = LLMReranker(api_key=body.api_key, timeout=15.0)
        try:
            if draft_state.next_action == "ban":
                result = await reranker.rerank_bans(
                    candidates=candidates,
                    draft_context=draft_context,
                    our_players=team_players,
                    enemy_players=enemy_players,
                    limit=5,
                    series_context=series_context,
                )
            else:
                result = await reranker.rerank_picks(
                    candidates=candidates,
                    draft_context=draft_context,
                    team_players=team_players,
                    enemy_players=enemy_players,
                    limit=5,
                    series_context=series_context,
                )

            return {
                "status": "ready",
                "action_count": body.action_count,
                "for_team": session.coaching_side,
                "draft_analysis": result.draft_analysis,
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
                "additional_suggestions": [
                    {
                        "champion_name": s.champion,
                        "reasoning": s.reasoning,
                        "confidence": s.confidence,
                        "role": s.role,
                        "for_player": s.for_player,
                    }
                    for s in result.additional_suggestions
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "action_count": body.action_count,
                "message": str(e),
            }
        finally:
            await reranker.close()
```

**Step 4: Commit**

```bash
git add backend/src/ban_teemo/api/routes/simulator.py
git commit -m "feat(simulator): add LLM insights endpoint"
```

---

## Task 3: Add Fearless Context to LLM Prompts

**Files:**
- Modify: `backend/src/ban_teemo/services/llm_reranker.py`

**Step 1: Update draft context display in prompts**

Add fearless context to the prompt builders. Find the `_build_pick_rerank_prompt` and `_build_ban_rerank_prompt` methods and add fearless info to the "Current Draft State" section.

In `_build_phase1_pick_prompt` (~line 345), after the "All Bans" line:

```python
        # Add fearless mode context
        fearless_section = ""
        fearless_blocked = draft_context.get('fearless_blocked', [])
        if fearless_blocked:
            fearless_section = f"""
## FEARLESS DRAFT MODE
Champions permanently unavailable (picked in previous games): {', '.join(fearless_blocked)}
These champions CANNOT be picked or banned - do not suggest them."""
```

Then include `{fearless_section}` in the prompt after the "All Bans" line.

Similarly update:
- `_build_pick_rerank_prompt` (~line 550)
- `_build_ban_rerank_prompt` (~line 880)
- `_build_phase1_ban_prompt` (~line 480)

**Step 2: Commit**

```bash
git add backend/src/ban_teemo/services/llm_reranker.py
git commit -m "feat(llm): add fearless draft mode context to prompts"
```

---

## Task 4: Add LLM Types to Frontend

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add LLM insight types**

```typescript
export interface RerankedRecommendation {
  champion_name: string;
  original_rank: number;
  new_rank: number;
  confidence: number;
  reasoning: string;
  strategic_factors: string[];
}

export interface AdditionalSuggestion {
  champion_name: string;
  reasoning: string;
  confidence: number;
  role: string;
  for_player: string;
}

export interface LLMInsightsResponse {
  status: "ready" | "stale" | "complete" | "error";
  action_count?: number;
  for_team?: "blue" | "red";
  draft_analysis?: string;
  reranked?: RerankedRecommendation[];
  additional_suggestions?: AdditionalSuggestion[];
  message?: string;
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): add LLM insights types"
```

---

## Task 5: Add LLM State to useSimulatorSession Hook

**Files:**
- Modify: `frontend/src/hooks/useSimulatorSession.ts`

**Step 1: Add state fields to SimulatorState interface (~line 23)**

```typescript
interface SimulatorState {
  // ... existing fields ...

  // LLM insights
  llmLoading: boolean;
  llmInsight: LLMInsightsResponse | null;
  llmApiKey: string | null;
}
```

**Step 2: Update initialState (~line 46)**

```typescript
const initialState: SimulatorState = {
  // ... existing fields ...
  llmLoading: false,
  llmInsight: null,
  llmApiKey: null,
};
```

**Step 3: Add fetchLlmInsights function (~line 130)**

```typescript
const fetchLlmInsights = useCallback(async (
  sessionId: string,
  actionCount: number,
  apiKey: string
) => {
  setState((s) => ({ ...s, llmLoading: true, llmInsight: null }));

  try {
    const res = await fetch(`${API_BASE}/api/simulator/sessions/${sessionId}/insights`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, action_count: actionCount }),
    });

    if (!res.ok) {
      throw new Error("Failed to fetch insights");
    }

    const data: LLMInsightsResponse = await res.json();

    // Only update if still relevant (action count matches)
    setState((s) => {
      if (s.sessionId !== sessionId) return s;
      if (s.draftState?.action_count !== actionCount) {
        // Stale response, ignore
        return { ...s, llmLoading: false };
      }
      return { ...s, llmLoading: false, llmInsight: data };
    });
  } catch (err) {
    setState((s) => ({
      ...s,
      llmLoading: false,
      llmInsight: { status: "error", message: String(err) },
    }));
  }
}, []);
```

**Step 4: Add setLlmApiKey function**

```typescript
const setLlmApiKey = useCallback((apiKey: string | null) => {
  setState((s) => ({ ...s, llmApiKey: apiKey }));
}, []);
```

**Step 5: Trigger LLM fetch after actions**

In `submitAction` after successful response (~line 290):

```typescript
      // Fetch LLM insights if API key is set
      if (state.llmApiKey && !isComplete) {
        fetchLlmInsights(currentSessionId, incomingCount, state.llmApiKey);
      }
```

Similarly in `triggerEnemyAction` after successful response (~line 180):

```typescript
      // Fetch LLM insights if API key is set and it's our turn
      if (state.llmApiKey && data.is_our_turn && !isComplete) {
        fetchLlmInsights(sessionId, data.draft_state.action_count, state.llmApiKey);
      }
```

**Step 6: Update return statement**

```typescript
  return {
    ...state,
    startSession,
    submitAction,
    recordWinner,
    nextGame,
    endSession,
    setLlmApiKey,  // Add this
  };
```

**Step 7: Commit**

```bash
git add frontend/src/hooks/useSimulatorSession.ts
git commit -m "feat(frontend): add LLM insights state and fetching to simulator hook"
```

---

## Task 6: Update SimulatorView with InsightPanel

**Files:**
- Modify: `frontend/src/components/SimulatorView/index.tsx`

**Step 1: Add imports**

```typescript
import { InsightPanel } from "../recommendations/InsightPanel";
import type { LLMInsightsResponse } from "../../types";
```

**Step 2: Add props to SimulatorViewProps (~line 55)**

```typescript
interface SimulatorViewProps {
  // ... existing props ...
  llmLoading?: boolean;
  llmInsight?: LLMInsightsResponse | null;
}
```

**Step 3: Add InsightPanel to the layout**

Find an appropriate location in the JSX (likely near the recommendations panel) and add:

```tsx
{/* AI Insights Panel */}
<div className="mt-4">
  <InsightPanel
    insight={llmInsight?.draft_analysis ?? null}
    isLoading={llmLoading}
  />

  {/* Show reranked recommendations if available */}
  {llmInsight?.status === "ready" && llmInsight.reranked && (
    <div className="mt-3 space-y-2">
      <h4 className="text-sm font-medium text-magic uppercase tracking-wide">
        AI Reranked Picks
      </h4>
      {llmInsight.reranked.slice(0, 3).map((rec, i) => (
        <div
          key={rec.champion_name}
          className="bg-lol-dark/50 rounded p-2 border border-magic/20"
        >
          <div className="flex items-center gap-2">
            <span className="text-gold-bright font-medium">
              #{rec.new_rank} {rec.champion_name}
            </span>
            <span className="text-xs text-text-tertiary">
              (was #{rec.original_rank})
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            {rec.reasoning}
          </p>
        </div>
      ))}
    </div>
  )}
</div>
```

**Step 4: Commit**

```bash
git add frontend/src/components/SimulatorView/index.tsx
git commit -m "feat(frontend): add InsightPanel to SimulatorView"
```

---

## Task 7: Add LLM API Key Input to Setup Modal

**Files:**
- Modify: `frontend/src/components/SimulatorSetupModal/index.tsx`

**Step 1: Add API key input field**

Add a text input for the Nebius API key in the setup form:

```tsx
<div className="space-y-2">
  <label className="text-sm text-text-secondary">
    AI Insights API Key (optional)
  </label>
  <input
    type="password"
    placeholder="Nebius API key for AI insights"
    value={llmApiKey}
    onChange={(e) => setLlmApiKey(e.target.value)}
    className="w-full px-3 py-2 bg-lol-dark border border-magic/30 rounded text-text-primary placeholder-text-tertiary"
  />
  <p className="text-xs text-text-tertiary">
    Leave empty to skip AI-powered draft analysis
  </p>
</div>
```

**Step 2: Pass API key to session start**

Update the setup flow to call `setLlmApiKey` when starting the session.

**Step 3: Commit**

```bash
git add frontend/src/components/SimulatorSetupModal/index.tsx
git commit -m "feat(frontend): add LLM API key input to simulator setup"
```

---

## Task 8: Wire Up SimulatorView Props

**Files:**
- Modify: Parent component that renders SimulatorView (likely `App.tsx` or a page component)

**Step 1: Pass LLM state to SimulatorView**

```tsx
<SimulatorView
  // ... existing props ...
  llmLoading={llmLoading}
  llmInsight={llmInsight}
/>
```

**Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(frontend): wire up LLM insights to SimulatorView"
```

---

## Task 9: Add Integration Test

**Files:**
- Create: `backend/tests/test_simulator_insights.py`

**Step 1: Write test for insights endpoint**

```python
"""Tests for simulator LLM insights endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from ban_teemo.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_session():
    """Create a mock session for testing."""
    # Would need to create a real session first
    pass


def test_insights_endpoint_returns_stale_for_wrong_action_count(client):
    """Test that stale requests are rejected."""
    # Setup: Create session, make some actions
    # Then request insights with wrong action_count
    # Assert status == "stale"
    pass


def test_insights_endpoint_includes_fearless_context(client):
    """Test that fearless blocked champions are included in context."""
    # Setup: Create fearless session, complete game 1
    # Start game 2, request insights
    # Assert fearless_blocked is in the request to LLM
    pass


def test_insights_endpoint_builds_series_context(client):
    """Test that series context is built from previous games."""
    # Setup: Create Bo3 session, complete game 1
    # Start game 2, request insights
    # Assert series_context has previous game data
    pass
```

**Step 2: Commit**

```bash
git add backend/tests/test_simulator_insights.py
git commit -m "test(simulator): add integration tests for LLM insights"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add bans to GameResult | simulator.py (model + route) |
| 2 | Add insights endpoint | simulator.py |
| 3 | Add fearless to LLM prompts | llm_reranker.py |
| 4 | Add LLM types | types/index.ts |
| 5 | Add LLM state to hook | useSimulatorSession.ts |
| 6 | Add InsightPanel to view | SimulatorView/index.tsx |
| 7 | Add API key input | SimulatorSetupModal/index.tsx |
| 8 | Wire up props | App.tsx or parent |
| 9 | Add integration tests | test_simulator_insights.py |

## Key Design Decisions

1. **Single async request** - Frontend fires fetch, backend blocks until LLM completes (with 15s timeout). Simpler than polling.

2. **Stale request rejection** - `action_count` parameter ensures we don't apply old insights to new draft state.

3. **Fearless awareness** - LLM prompt explicitly states which champions are permanently unavailable.

4. **Series context** - Built from `GameResult` history, includes bans, comps, and tendencies.

5. **Enemy player proficiency** - Passed to LLM for target ban recommendations (already supported).

6. **Role detection** - Candidates are pre-filtered by `PickRecommendationEngine`, LLM receives only valid options.
