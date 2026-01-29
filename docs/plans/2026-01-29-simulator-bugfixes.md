# Draft Simulator Bugfixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical UI bugs blocking multi-game series functionality in the Draft Simulator.

**Architecture:** These are surgical fixes to existing components - no new files needed. Task 1 adds the missing "Next Game" flow to App.tsx. Task 2 fixes loading state management in SimulatorSetupModal. Task 3 prevents double-submission of game winners.

**Tech Stack:** TypeScript, React

**Reference:** See code review findings in conversation history and `docs/plans/2026-01-27-draft-simulator-implementation.md`

---

## Task 1: Add "Next Game" Button for Multi-Game Series

**Files:**
- Modify: `deepdraft/src/App.tsx:144-165`

**Problem:** After recording winner in Bo3/Bo5, status stays `game_complete` but no button exists to call `nextGame()`. Users are stuck.

**Step 1: Review current game_complete UI**

Read `deepdraft/src/App.tsx` lines 144-165 to understand the current structure.

**Step 2: Modify game_complete section to add conditional "Next Game" button**

Replace the entire `game_complete` section (lines 144-165) with:

```tsx
{simulator.status === "game_complete" && (
  <div className="text-center py-12 space-y-6">
    <h2 className="text-2xl font-bold text-gold-bright uppercase tracking-wide">
      Draft Complete!
    </h2>

    {/* Show winner selection if no series status yet */}
    {!simulator.seriesStatus?.games_played ||
     simulator.seriesStatus.games_played < simulator.gameNumber ? (
      <>
        <p className="text-text-secondary">Who won this game?</p>
        <div className="flex justify-center gap-4">
          <button
            onClick={() => simulator.recordWinner("blue")}
            className="px-6 py-2 bg-blue-team/80 text-white rounded font-semibold hover:bg-blue-team transition-colors"
          >
            {simulator.blueTeam?.name || "Blue"} Won
          </button>
          <button
            onClick={() => simulator.recordWinner("red")}
            className="px-6 py-2 bg-red-team/80 text-white rounded font-semibold hover:bg-red-team transition-colors"
          >
            {simulator.redTeam?.name || "Red"} Won
          </button>
        </div>
      </>
    ) : (
      <>
        {/* Winner recorded, show score and next game button */}
        <div className="text-lg text-text-primary">
          <span className="text-blue-team">{simulator.blueTeam?.name}</span>
          <span className="mx-4 text-gold-bright font-bold">
            {simulator.seriesStatus?.blue_wins} - {simulator.seriesStatus?.red_wins}
          </span>
          <span className="text-red-team">{simulator.redTeam?.name}</span>
        </div>
        <button
          onClick={() => simulator.nextGame()}
          className="px-6 py-3 bg-magic text-lol-darkest rounded-lg font-semibold hover:bg-magic-bright transition-colors"
        >
          Continue to Game {simulator.gameNumber + 1}
        </button>
      </>
    )}
  </div>
)}
```

**Step 3: Verify the frontend builds**

Run: `cd deepdraft && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 4: Manual test**

1. Start the dev server: `cd deepdraft && npm run dev`
2. Open browser, go to Simulator mode
3. Start a Bo3 series
4. Complete a draft (or use dev tools to simulate)
5. Record winner - verify "Continue to Game 2" button appears
6. Click it - verify Game 2 starts

**Step 5: Commit**

```bash
git add deepdraft/src/App.tsx
git commit -m "fix(simulator): add Next Game button for multi-game series"
```

---

## Task 2: Fix Loading State in SimulatorSetupModal

**Files:**
- Modify: `deepdraft/src/components/SimulatorSetupModal/index.tsx:36-46`
- Modify: `deepdraft/src/App.tsx:21-24`

**Problem:** `setLoading(true)` is never reset on success/failure. Modal becomes unusable after errors.

**Step 1: Update handleStartSimulator in App.tsx to pass error handling to modal**

Replace lines 21-24 in `deepdraft/src/App.tsx` with:

```tsx
const handleStartSimulator = async (config: SimulatorConfig) => {
  await simulator.startSession(config);
  // Only close modal if session actually started
  if (simulator.status === "drafting" || !simulator.error) {
    setShowSetup(false);
  }
};
```

Wait - this won't work because `simulator.status` won't be updated yet when `startSession` returns. The state update is async. Let me reconsider.

Better approach: Have the modal reset loading when it closes or opens.

**Step 1 (revised): Add loading reset on modal open/close**

In `deepdraft/src/components/SimulatorSetupModal/index.tsx`, modify the useEffect and handleStart:

Find the existing useEffect (lines 23-34):
```tsx
useEffect(() => {
  if (isOpen) {
    setFetchError(null);
    fetch(`${API_BASE}/api/simulator/teams`)
      // ...
  }
}, [isOpen]);
```

Replace with:
```tsx
useEffect(() => {
  if (isOpen) {
    setLoading(false);  // Reset loading state when modal opens
    setFetchError(null);
    fetch(`${API_BASE}/api/simulator/teams`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch teams");
        return res.json();
      })
      .then((data) => setTeams(data.teams || []))
      .catch((err) => setFetchError(err.message));
  }
}, [isOpen]);
```

**Step 2: Verify the frontend builds**

Run: `cd deepdraft && npm run build`
Expected: Build succeeds

**Step 3: Manual test**

1. Open Simulator mode, click "Start New Draft"
2. Select teams, click "Start Draft"
3. If it fails (e.g., backend not running), close modal
4. Reopen modal - verify button says "Start Draft" not "Starting..."

**Step 4: Commit**

```bash
git add deepdraft/src/components/SimulatorSetupModal/index.tsx
git commit -m "fix(simulator): reset loading state when setup modal opens"
```

---

## Task 3: Prevent Double-Click on Winner Buttons

**Files:**
- Modify: `deepdraft/src/hooks/useSimulatorSession.ts`
- Modify: `deepdraft/src/App.tsx` (winner button section)

**Problem:** Users can click winner buttons multiple times before state updates, potentially recording multiple results.

**Step 1: Add isRecordingWinner state to hook**

In `deepdraft/src/hooks/useSimulatorSession.ts`, add to the SimulatorState interface (around line 21):

Find:
```tsx
interface SimulatorState {
  status: SimulatorStatus;
  sessionId: string | null;
  // ...
  error: string | null;
}
```

Add `isRecordingWinner` field:
```tsx
interface SimulatorState {
  status: SimulatorStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  coachingSide: "blue" | "red" | null;
  draftMode: DraftMode;
  draftState: DraftState | null;
  recommendations: SimulatorRecommendation[] | null;
  teamEvaluation: TeamEvaluation | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  isRecordingWinner: boolean;  // NEW
  gameNumber: number;
  seriesStatus: SeriesStatus | null;
  fearlessBlocked: FearlessBlocked;
  error: string | null;
}
```

**Step 2: Update initialState**

Find the initialState (around line 39):
```tsx
const initialState: SimulatorState = {
  // ...
  isEnemyThinking: false,
  gameNumber: 1,
  // ...
};
```

Add the new field:
```tsx
const initialState: SimulatorState = {
  status: "setup",
  sessionId: null,
  blueTeam: null,
  redTeam: null,
  coachingSide: null,
  draftMode: "normal",
  draftState: null,
  recommendations: null,
  teamEvaluation: null,
  isOurTurn: false,
  isEnemyThinking: false,
  isRecordingWinner: false,  // NEW
  gameNumber: 1,
  seriesStatus: null,
  fearlessBlocked: {},
  error: null,
};
```

**Step 3: Update recordWinner function to set/clear loading state**

Find the recordWinner function (around line 285):
```tsx
const recordWinner = useCallback(async (winner: "blue" | "red") => {
  if (!state.sessionId) return;

  try {
    const res = await fetch(`${API_BASE}/api/simulator/sessions/${state.sessionId}/games/complete`, {
      // ...
    });
    // ...
  } catch (err) {
    setState((s) => ({ ...s, error: String(err) }));
  }
}, [state.sessionId]);
```

Replace with:
```tsx
const recordWinner = useCallback(async (winner: "blue" | "red") => {
  if (!state.sessionId || state.isRecordingWinner) return;

  setState((s) => ({ ...s, isRecordingWinner: true }));

  try {
    const res = await fetch(`${API_BASE}/api/simulator/sessions/${state.sessionId}/games/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ winner }),
    });

    if (!res.ok) throw new Error("Failed to record winner");

    const data: CompleteGameResponse = await res.json();

    setState((s) => ({
      ...s,
      status: data.series_status.series_complete ? "series_complete" : "game_complete",
      seriesStatus: data.series_status,
      fearlessBlocked: data.fearless_blocked,
      isRecordingWinner: false,
    }));
  } catch (err) {
    setState((s) => ({ ...s, error: String(err), isRecordingWinner: false }));
  }
}, [state.sessionId, state.isRecordingWinner]);
```

**Step 4: Update App.tsx winner buttons to use disabled state**

In `deepdraft/src/App.tsx`, update the winner buttons in the game_complete section (from Task 1).

Find the winner buttons:
```tsx
<button
  onClick={() => simulator.recordWinner("blue")}
  className="px-6 py-2 bg-blue-team/80 text-white rounded font-semibold hover:bg-blue-team transition-colors"
>
```

Update both buttons to include disabled state:
```tsx
<button
  onClick={() => simulator.recordWinner("blue")}
  disabled={simulator.isRecordingWinner}
  className="px-6 py-2 bg-blue-team/80 text-white rounded font-semibold hover:bg-blue-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
>
  {simulator.isRecordingWinner ? "Recording..." : `${simulator.blueTeam?.name || "Blue"} Won`}
</button>
<button
  onClick={() => simulator.recordWinner("red")}
  disabled={simulator.isRecordingWinner}
  className="px-6 py-2 bg-red-team/80 text-white rounded font-semibold hover:bg-red-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
>
  {simulator.isRecordingWinner ? "Recording..." : `${simulator.redTeam?.name || "Red"} Won`}
</button>
```

**Step 5: Verify the frontend builds**

Run: `cd deepdraft && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add deepdraft/src/hooks/useSimulatorSession.ts deepdraft/src/App.tsx
git commit -m "fix(simulator): prevent double-click on winner buttons"
```

---

## Task 4: Update Implementation Plan Documentation

**Files:**
- Modify: `docs/plans/2026-01-27-draft-simulator-implementation.md`

**Step 1: Update Stage 6 status in the plan**

In `docs/plans/2026-01-27-draft-simulator-implementation.md`, find the Status Overview table (around line 29) and update Stage 6:

Find:
```markdown
| Stage 6: Frontend UI | 🔲 Not Started | ChampionPool, SimulatorSetupModal, SimulatorView, App integration |
```

Replace with:
```markdown
| Stage 6: Frontend UI | ✅ Complete | ChampionPool, SimulatorSetupModal, SimulatorView, App integration |
```

**Step 2: Add bugfix notes after Stage 6**

After the Stage 6 row, add a new row for the bugfixes:

```markdown
| Bugfixes (2026-01-29) | ✅ Complete | Next Game button, loading state reset, double-click prevention |
```

**Step 3: Commit**

```bash
git add docs/plans/2026-01-27-draft-simulator-implementation.md
git commit -m "docs: update implementation plan with Stage 6 completion and bugfixes"
```

---

## Summary

| Task | Priority | Description |
|------|----------|-------------|
| 1 | P0 (Blocker) | Add "Next Game" button for multi-game series |
| 2 | P0 (High) | Fix loading state reset in setup modal |
| 3 | P1 (Medium) | Prevent double-click on winner buttons |
| 4 | P2 (Low) | Update documentation |

**Estimated time:** 15-20 minutes total
