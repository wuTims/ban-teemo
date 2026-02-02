# Draft Quality Frontend Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Display draft quality analysis in the DraftCompletePanel with visual metric bars and a "Draft Report" comparing actual picks vs engine recommendations.

**Architecture:** Add TypeScript types for draft quality data, create a reusable MetricBar component, extend DraftCompletePanel with two new sections (Draft Analysis + Draft Report), and wire up data from simulator API and replay WebSocket.

**Tech Stack:** React, TypeScript, Tailwind CSS

---

## Task 1: Add TypeScript Types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add draft quality types**

Add these types after the existing `CompleteGameResponse` interface (around line 355):

```typescript
// === Draft Quality Types ===

export interface DraftQualityDraft {
  picks: string[];
  archetype: string | null;
  composition_score: number;
  synergy_score: number;
  vs_enemy_advantage: number;
  vs_enemy_description: string;
}

export interface DraftQualityComparison {
  score_delta: number;
  advantage_delta: number;
  archetype_insight: string;
  picks_matched: number;
  picks_tracked: number;
}

export interface DraftQuality {
  actual_draft: DraftQualityDraft;
  recommended_draft: DraftQualityDraft;
  comparison: DraftQualityComparison;
}
```

**Step 2: Update CompleteGameResponse**

Modify the existing `CompleteGameResponse` interface to include draft quality:

```typescript
export interface CompleteGameResponse {
  series_status: SeriesStatus;
  fearless_blocked: FearlessBlocked;
  next_game_ready: boolean;
  blue_comp_with_roles?: FinalizedPick[];
  red_comp_with_roles?: FinalizedPick[];
  draft_quality?: DraftQuality | null;  // Add this line
}
```

**Step 3: Update DraftCompleteMessage for replay**

Modify the existing `DraftCompleteMessage` interface:

```typescript
export interface DraftCompleteMessage {
  type: "draft_complete";
  draft_state: DraftState;
  blue_comp: string[];
  red_comp: string[];
  blue_comp_with_roles?: FinalizedPick[];
  red_comp_with_roles?: FinalizedPick[];
  blue_draft_quality?: DraftQuality | null;  // Add this line
  red_draft_quality?: DraftQuality | null;   // Add this line
}
```

**Step 4: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 5: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add DraftQuality types for frontend integration"
```

---

## Task 2: Create MetricBar Component

**Files:**
- Create: `frontend/src/components/shared/MetricBar.tsx`
- Modify: `frontend/src/components/shared/index.ts`

**Step 1: Create MetricBar component**

Create `frontend/src/components/shared/MetricBar.tsx`:

```tsx
interface MetricBarProps {
  label: string;
  value: number; // 0-1 scale
  explanation: string;
  className?: string;
}

function getBarColor(value: number): string {
  if (value >= 0.7) return "bg-success";
  if (value >= 0.5) return "bg-warning";
  return "bg-danger";
}

export function MetricBar({ label, value, explanation, className = "" }: MetricBarProps) {
  const percentage = Math.round(value * 100);

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-text-secondary uppercase tracking-wide">{label}</span>
        <span className="text-xs font-mono text-text-primary">{percentage}%</span>
      </div>
      <div className="h-2 bg-lol-dark rounded-full overflow-hidden">
        <div
          className={`h-full ${getBarColor(value)} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-[10px] text-text-tertiary">{explanation}</p>
    </div>
  );
}
```

**Step 2: Export from shared index**

Add to `frontend/src/components/shared/index.ts`:

```typescript
export { MetricBar } from "./MetricBar";
```

**Step 3: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 4: Commit**

```bash
git add frontend/src/components/shared/MetricBar.tsx frontend/src/components/shared/index.ts
git commit -m "feat(ui): add MetricBar component for draft analysis display"
```

---

## Task 3: Create Draft Analysis Section Component

**Files:**
- Create: `frontend/src/components/DraftCompletePanel/DraftAnalysis.tsx`

**Step 1: Create the component**

Create `frontend/src/components/DraftCompletePanel/DraftAnalysis.tsx`:

```tsx
import { MetricBar } from "../shared";
import type { TeamContext, DraftQuality } from "../../types";

interface DraftAnalysisProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  blueData: {
    synergy_score: number;
    composition_score: number;
    archetype: string | null;
  };
  redData: {
    synergy_score: number;
    composition_score: number;
    archetype: string | null;
  };
  matchupAdvantage: number;
}

function getSynergyExplanation(score: number): string {
  if (score >= 0.6) return "Good champion synergies";
  if (score >= 0.4) return "Average synergies";
  return "Poor champion synergies";
}

function getCompositionExplanation(score: number, archetype: string | null): string {
  if (score >= 0.6) return `Strong ${archetype ?? "team"} identity`;
  if (score >= 0.4) return "Balanced composition";
  return "Lacks clear identity";
}

export function DraftAnalysis({
  blueTeam,
  redTeam,
  blueData,
  redData,
  matchupAdvantage,
}: DraftAnalysisProps) {
  const favoredTeam = matchupAdvantage > 0 ? "blue" : matchupAdvantage < 0 ? "red" : null;
  const favoredName = favoredTeam === "blue" ? blueTeam.name : favoredTeam === "red" ? redTeam.name : null;
  const advantageAbs = Math.abs(matchupAdvantage);

  return (
    <div className="bg-lol-dark rounded-lg p-4 border border-gold-dim/30">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright text-center mb-4">
        Draft Analysis
      </h3>

      <div className="grid grid-cols-2 gap-6">
        {/* Blue Team Column */}
        <div className="space-y-3">
          <div className="text-xs font-semibold text-blue-team uppercase text-center mb-2">
            {blueTeam.name}
          </div>
          <MetricBar
            label="Synergy"
            value={blueData.synergy_score}
            explanation={getSynergyExplanation(blueData.synergy_score)}
          />
          <MetricBar
            label="Composition"
            value={blueData.composition_score}
            explanation={getCompositionExplanation(blueData.composition_score, blueData.archetype)}
          />
          <div className="text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{blueData.archetype ?? "None"}</span>
          </div>
        </div>

        {/* Red Team Column */}
        <div className="space-y-3">
          <div className="text-xs font-semibold text-red-team uppercase text-center mb-2">
            {redTeam.name}
          </div>
          <MetricBar
            label="Synergy"
            value={redData.synergy_score}
            explanation={getSynergyExplanation(redData.synergy_score)}
          />
          <MetricBar
            label="Composition"
            value={redData.composition_score}
            explanation={getCompositionExplanation(redData.composition_score, redData.archetype)}
          />
          <div className="text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{redData.archetype ?? "None"}</span>
          </div>
        </div>
      </div>

      {/* Matchup Indicator */}
      <div className="mt-4 pt-3 border-t border-gold-dim/20 text-center">
        <span className="text-xs text-text-secondary">Matchup: </span>
        {favoredTeam ? (
          <span className={`text-xs font-semibold ${favoredTeam === "blue" ? "text-blue-team" : "text-red-team"}`}>
            {favoredName} favored ({advantageAbs > 0 ? "+" : ""}{(matchupAdvantage * 100).toFixed(0)}%)
          </span>
        ) : (
          <span className="text-xs text-text-tertiary">Even matchup</span>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 3: Commit**

```bash
git add frontend/src/components/DraftCompletePanel/DraftAnalysis.tsx
git commit -m "feat(ui): add DraftAnalysis component with metric bars"
```

---

## Task 4: Create Draft Report Section Component

**Files:**
- Create: `frontend/src/components/DraftCompletePanel/DraftReport.tsx`

**Step 1: Create the component**

Create `frontend/src/components/DraftCompletePanel/DraftReport.tsx`:

```tsx
import type { DraftQuality, TeamContext } from "../../types";

interface DraftReportCardProps {
  teamName: string;
  teamSide: "blue" | "red";
  quality: DraftQuality;
}

function getPicksMatchedLabel(matched: number, total: number): string {
  if (matched === total) return "Perfect alignment";
  if (matched >= total * 0.6) return "Good alignment";
  if (matched >= total * 0.2) return "Different approach";
  return "Fully independent";
}

function getDeltaLabel(delta: number): string {
  if (delta > 0.02) return "Engine would've scored higher";
  if (delta < -0.02) return "Outperformed engine";
  return "Similar outcome";
}

function DraftReportCard({ teamName, teamSide, quality }: DraftReportCardProps) {
  const { comparison } = quality;
  const picksMatched = comparison.picks_matched;
  const picksTotal = comparison.picks_tracked;
  const scoreDelta = comparison.score_delta;

  const deltaColor = scoreDelta > 0.02 ? "text-danger" : scoreDelta < -0.02 ? "text-success" : "text-text-tertiary";
  const sideColor = teamSide === "blue" ? "text-blue-team border-blue-team/30" : "text-red-team border-red-team/30";

  return (
    <div className={`bg-lol-light rounded-lg p-3 border ${teamSide === "blue" ? "border-blue-team/30" : "border-red-team/30"}`}>
      <h4 className={`text-xs font-semibold uppercase text-center mb-3 ${teamSide === "blue" ? "text-blue-team" : "text-red-team"}`}>
        {teamName}'s Draft Report
      </h4>

      {/* Picks Matched */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-text-tertiary uppercase">Picks Matched</span>
          <span className="text-xs font-mono text-text-primary">{picksMatched}/{picksTotal}</span>
        </div>
        <div className="flex gap-1">
          {Array.from({ length: picksTotal }).map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i < picksMatched ? "bg-magic" : "bg-lol-dark"}`}
            />
          ))}
        </div>
        <p className="text-[10px] text-text-tertiary mt-1">{getPicksMatchedLabel(picksMatched, picksTotal)}</p>
      </div>

      {/* Score Delta */}
      <div className="mb-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-text-tertiary uppercase">vs Engine</span>
          <span className={`text-xs font-mono ${deltaColor}`}>
            {scoreDelta >= 0 ? "+" : ""}{(scoreDelta * 100).toFixed(1)}%
          </span>
        </div>
        <p className="text-[10px] text-text-tertiary mt-1">{getDeltaLabel(scoreDelta)}</p>
      </div>

      {/* Archetype Insight */}
      <div className="pt-2 border-t border-gold-dim/20">
        <p className="text-[10px] text-text-secondary italic leading-relaxed">
          "{comparison.archetype_insight}"
        </p>
      </div>
    </div>
  );
}

interface DraftReportProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  blueDraftQuality?: DraftQuality | null;
  redDraftQuality?: DraftQuality | null;
}

export function DraftReport({ blueTeam, redTeam, blueDraftQuality, redDraftQuality }: DraftReportProps) {
  const hasBlue = !!blueDraftQuality;
  const hasRed = !!redDraftQuality;

  if (!hasBlue && !hasRed) return null;

  return (
    <div className="bg-lol-dark rounded-lg p-4 border border-gold-dim/30">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright text-center mb-4">
        Draft Report
      </h3>

      <div className={`grid gap-4 ${hasBlue && hasRed ? "grid-cols-2" : "grid-cols-1 max-w-sm mx-auto"}`}>
        {hasBlue && (
          <DraftReportCard teamName={blueTeam.name} teamSide="blue" quality={blueDraftQuality} />
        )}
        {hasRed && (
          <DraftReportCard teamName={redTeam.name} teamSide="red" quality={redDraftQuality} />
        )}
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 3: Commit**

```bash
git add frontend/src/components/DraftCompletePanel/DraftReport.tsx
git commit -m "feat(ui): add DraftReport component for actual vs engine comparison"
```

---

## Task 5: Integrate Components into DraftCompletePanel

**Files:**
- Modify: `frontend/src/components/DraftCompletePanel/index.tsx`

**Step 1: Update imports and props**

Replace the entire file with:

```tsx
// frontend/src/components/DraftCompletePanel/index.tsx
import type { TeamContext, TeamEvaluation, DraftQuality } from "../../types";
import { DraftAnalysis } from "./DraftAnalysis";
import { DraftReport } from "./DraftReport";

interface DraftCompletePanelProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  evaluation: TeamEvaluation | null;
  onSelectWinner: (winner: "blue" | "red") => void;
  isRecordingWinner: boolean;
  // Draft quality - simulator passes single, replay passes both
  draftQuality?: DraftQuality | null;
  blueDraftQuality?: DraftQuality | null;
  redDraftQuality?: DraftQuality | null;
}

export function DraftCompletePanel({
  blueTeam,
  redTeam,
  evaluation,
  onSelectWinner,
  isRecordingWinner,
  draftQuality,
  blueDraftQuality,
  redDraftQuality,
}: DraftCompletePanelProps) {
  const blueScore = evaluation?.our_evaluation?.composition_score ?? 0;
  const redScore = evaluation?.enemy_evaluation?.composition_score ?? 0;
  const bluePoints = Math.round(blueScore * 100);
  const redPoints = Math.round(redScore * 100);

  const blueStrength = evaluation?.our_evaluation?.strengths?.[0] ?? "Balanced composition";
  const redStrength = evaluation?.enemy_evaluation?.strengths?.[0] ?? "Balanced composition";

  const matchupDesc = evaluation?.matchup_description ?? "Even matchup";

  // For simulator: coached team is "our" side, use draftQuality
  // For replay: use blueDraftQuality/redDraftQuality directly
  const effectiveBlueDraftQuality = blueDraftQuality ?? draftQuality ?? null;
  const effectiveRedDraftQuality = redDraftQuality ?? null;

  // Build analysis data from evaluation
  const blueAnalysisData = {
    synergy_score: evaluation?.our_evaluation?.synergy_score ?? 0.5,
    composition_score: evaluation?.our_evaluation?.composition_score ?? 0.5,
    archetype: evaluation?.our_evaluation?.archetype ?? null,
  };

  const redAnalysisData = {
    synergy_score: evaluation?.enemy_evaluation?.synergy_score ?? 0.5,
    composition_score: evaluation?.enemy_evaluation?.composition_score ?? 0.5,
    archetype: evaluation?.enemy_evaluation?.archetype ?? null,
  };

  return (
    <div className="space-y-4">
      {/* Existing Header Section */}
      <div className="bg-gradient-to-r from-lol-dark via-lol-medium to-lol-dark rounded-lg p-6 border border-gold-dim/50">
        <div className="text-center mb-4">
          <h2 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            Draft Complete
          </h2>
          <p className="text-sm text-text-tertiary mt-1">{matchupDesc}</p>
        </div>

        <div className="flex items-stretch justify-center gap-4 mb-6">
          <div className="flex-1 max-w-[200px] bg-blue-team/10 border border-blue-team/30 rounded-lg p-4 text-center">
            <div className="text-blue-team font-semibold text-sm uppercase mb-2">
              {blueTeam.name}
            </div>
            <div className="text-3xl font-bold text-blue-team mb-2">
              {bluePoints}
              <span className="text-sm font-normal text-text-tertiary ml-1">pts</span>
            </div>
            <div className="text-xs text-text-secondary truncate" title={blueStrength}>
              {blueStrength}
            </div>
          </div>

          <div className="flex items-center">
            <span className="text-gold-dim font-bold text-lg">VS</span>
          </div>

          <div className="flex-1 max-w-[200px] bg-red-team/10 border border-red-team/30 rounded-lg p-4 text-center">
            <div className="text-red-team font-semibold text-sm uppercase mb-2">
              {redTeam.name}
            </div>
            <div className="text-3xl font-bold text-red-team mb-2">
              {redPoints}
              <span className="text-sm font-normal text-text-tertiary ml-1">pts</span>
            </div>
            <div className="text-xs text-text-secondary truncate" title={redStrength}>
              {redStrength}
            </div>
          </div>
        </div>

        <div className="text-center">
          <p className="text-sm text-text-secondary mb-3">Who won this game?</p>
          <div className="flex justify-center gap-4">
            <button
              onClick={() => onSelectWinner("blue")}
              disabled={isRecordingWinner}
              className="px-6 py-2 bg-blue-team/80 text-white rounded font-semibold hover:bg-blue-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRecordingWinner ? "Recording..." : `${blueTeam.name} Won`}
            </button>
            <button
              onClick={() => onSelectWinner("red")}
              disabled={isRecordingWinner}
              className="px-6 py-2 bg-red-team/80 text-white rounded font-semibold hover:bg-red-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isRecordingWinner ? "Recording..." : `${redTeam.name} Won`}
            </button>
          </div>
        </div>
      </div>

      {/* NEW: Draft Analysis Section */}
      {evaluation && (
        <DraftAnalysis
          blueTeam={blueTeam}
          redTeam={redTeam}
          blueData={blueAnalysisData}
          redData={redAnalysisData}
          matchupAdvantage={evaluation.matchup_advantage}
        />
      )}

      {/* NEW: Draft Report Section */}
      <DraftReport
        blueTeam={blueTeam}
        redTeam={redTeam}
        blueDraftQuality={effectiveBlueDraftQuality}
        redDraftQuality={effectiveRedDraftQuality}
      />
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 3: Commit**

```bash
git add frontend/src/components/DraftCompletePanel/
git commit -m "feat(ui): integrate DraftAnalysis and DraftReport into DraftCompletePanel"
```

---

## Task 6: Wire Up Simulator Data

**Files:**
- Modify: `frontend/src/hooks/useSimulatorSession.ts`

**Step 1: Read current hook implementation**

First, read the file to understand current structure:
Run: Read `frontend/src/hooks/useSimulatorSession.ts`

**Step 2: Add draftQuality state**

Add state variable near other state declarations:

```typescript
const [draftQuality, setDraftQuality] = useState<DraftQuality | null>(null);
```

**Step 3: Store draft quality from complete-game response**

In the `completeGame` function, after receiving the response, store the draft quality:

```typescript
// Inside completeGame function, after setSeriesStatus
if (data.draft_quality) {
  setDraftQuality(data.draft_quality);
}
```

**Step 4: Reset draft quality on next game**

In the `nextGame` function, reset draft quality:

```typescript
setDraftQuality(null);
```

**Step 5: Return draftQuality from hook**

Add `draftQuality` to the return object of the hook.

**Step 6: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 7: Commit**

```bash
git add frontend/src/hooks/useSimulatorSession.ts
git commit -m "feat(simulator): wire up draft quality data from complete-game response"
```

---

## Task 7: Pass Draft Quality to DraftCompletePanel (Simulator)

**Files:**
- Modify: File that renders DraftCompletePanel for simulator mode

**Step 1: Find the parent component**

Run: `grep -r "DraftCompletePanel" frontend/src --include="*.tsx" -l`

This will identify which files render the DraftCompletePanel.

**Step 2: Update the parent to pass draftQuality prop**

Wherever `<DraftCompletePanel` is rendered in simulator context, add the `draftQuality` prop:

```tsx
<DraftCompletePanel
  blueTeam={blueTeam}
  redTeam={redTeam}
  evaluation={evaluation}
  onSelectWinner={handleSelectWinner}
  isRecordingWinner={isRecordingWinner}
  draftQuality={draftQuality}  // Add this
/>
```

**Step 3: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(simulator): pass draft quality to DraftCompletePanel"
```

---

## Task 8: Wire Up Replay WebSocket Data

**Files:**
- Modify: Replay WebSocket handler (likely in `frontend/src/components/replay/` or a replay hook)
- Modify: Backend `replay_ws.py` if needed to include draft quality in `draft_complete` message

**Step 1: Check backend sends draft quality in draft_complete**

Read `backend/src/ban_teemo/api/websockets/replay_ws.py` to verify `draft_complete` message includes `blue_draft_quality` and `red_draft_quality`.

If not present, add them to the `draft_complete` message payload.

**Step 2: Update frontend replay handler**

In the replay WebSocket message handler, extract draft quality from `draft_complete` message:

```typescript
case "draft_complete":
  // existing handling...
  setBlueDraftQuality(message.blue_draft_quality ?? null);
  setRedDraftQuality(message.red_draft_quality ?? null);
  break;
```

**Step 3: Pass to DraftCompletePanel in replay context**

```tsx
<DraftCompletePanel
  blueTeam={blueTeam}
  redTeam={redTeam}
  evaluation={evaluation}
  onSelectWinner={handleSelectWinner}
  isRecordingWinner={isRecordingWinner}
  blueDraftQuality={blueDraftQuality}
  redDraftQuality={redDraftQuality}
/>
```

**Step 4: Verify TypeScript compiles**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run build 2>&1 | head -50`
Expected: No type errors

**Step 5: Commit**

```bash
git add frontend/src/ backend/src/
git commit -m "feat(replay): wire up draft quality from WebSocket draft_complete message"
```

---

## Task 9: Manual Testing

**Step 1: Start backend**

Run: `cd /workspaces/web-dev-playground/ban-teemo/backend && uv run uvicorn ban_teemo.api.main:app --reload --port 8000`

**Step 2: Start frontend**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run dev`

**Step 3: Test simulator flow**

1. Open simulator in browser
2. Start a new draft session
3. Complete the draft (make 20 picks/bans)
4. Verify:
   - Draft Analysis section appears below header
   - Metric bars show synergy and composition for both teams
   - Archetype labels display
   - Matchup indicator shows advantage
   - Draft Report section appears (for coached team only in simulator)
   - Picks matched indicator shows X/5
   - Score delta displays with appropriate color
   - Archetype insight text displays

**Step 4: Test replay flow**

1. Start a replay session
2. Let it play through to completion
3. Verify:
   - Draft Analysis section appears
   - Draft Report shows for BOTH teams side-by-side
   - All data populates correctly

**Step 5: Final commit if any fixes needed**

```bash
git add .
git commit -m "fix: address issues found in manual testing"
```
