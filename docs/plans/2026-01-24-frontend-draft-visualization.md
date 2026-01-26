# Frontend Draft Visualization Implementation Plan

> **Status:** Implemented ✓
> **Implementation:** `deepdraft/src/components/DraftBoard/`, `RecommendationPanel/`, `ReplayControls/`

~~**For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.~~

**Goal:** Build a polished draft board UI that visualizes the replay WebSocket stream with recommendations panel.

**Architecture:** React components receive draft state via WebSocket, render a LoL-style pick/ban screen with team panels flanking a central ban track. Recommendations display below the draft board. Uses Tailwind v4 with LoL Hextech-inspired theme from style guide.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, WebSocket API, Riot Data Dragon CDN

---

## Prerequisites

- Backend draft simulation service running (`cd backend && uv run uvicorn ban_teemo.main:app`)
- Frontend dev server (`cd deepdraft && npm run dev`)
- Style guide: `docs/lol-draft-assistant-style-guide.md`

---

## Task 1: Update Tailwind Theme with LoL Colors

**Files:**
- Modify: `deepdraft/src/index.css`

**Step 1: Update the theme with Hextech color system**

Replace the current `@theme` block with the full LoL color palette from the style guide:

```css
@import "tailwindcss";

/* LoL Hextech Theme - from style guide */
@theme {
  /* Backgrounds */
  --color-lol-darkest: #010A13;
  --color-lol-dark: #0A1428;
  --color-lol-medium: #0A323C;
  --color-lol-light: #1E2328;
  --color-lol-hover: #1E3A5F;

  /* Hextech Magic (Primary) */
  --color-magic-bright: #0AC8B9;
  --color-magic: #0397AB;
  --color-magic-dim: #005A82;

  /* Gold System (Secondary) */
  --color-gold-bright: #F0E6D2;
  --color-gold: #C8AA6E;
  --color-gold-dim: #785A28;
  --color-gold-dark: #463714;

  /* Team Colors */
  --color-blue-team: #0AC8B9;
  --color-blue-team-bg: #0A323C;
  --color-red-team: #E84057;
  --color-red-team-bg: #3C0A0A;

  /* Semantic */
  --color-success: #1EAD58;
  --color-warning: #F0B232;
  --color-danger: #E84057;

  /* Text */
  --color-text-primary: #F0E6D2;
  --color-text-secondary: #A09B8C;
  --color-text-tertiary: #5B5A56;
}

/* Animations */
@keyframes magic-pulse {
  0%, 100% {
    box-shadow: 0 0 20px rgba(10, 200, 185, 0.4);
    transform: scale(1);
  }
  50% {
    box-shadow: 0 0 40px rgba(10, 200, 185, 0.7);
    transform: scale(1.02);
  }
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-in-left {
  from { transform: translateX(-20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

@keyframes slide-in-right {
  from { transform: translateX(20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

/* Base styles */
body {
  @apply min-h-screen bg-lol-darkest text-text-primary;
  font-family: Inter, system-ui, sans-serif;
}
```

**Step 2: Verify the dev server picks up changes**

Run: `cd deepdraft && npm run dev`
Expected: Page renders with darker background (#010A13)

**Step 3: Commit**

```bash
git add deepdraft/src/index.css
git commit -m "feat(frontend): add LoL Hextech theme colors

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Update TypeScript Types for Backend Alignment

**Files:**
- Modify: `deepdraft/src/types/index.ts`

**Step 1: Update types to match backend WebSocket protocol**

Replace entire file with types matching backend models:

```typescript
/**
 * TypeScript types aligned with backend WebSocket protocol.
 * See: docs/plans/2026-01-23-draft-simulation-service-design.md
 */

// === Enums ===
export type Team = "blue" | "red";
export type ActionType = "ban" | "pick";
export type DraftPhase =
  | "BAN_PHASE_1"
  | "PICK_PHASE_1"
  | "BAN_PHASE_2"
  | "PICK_PHASE_2"
  | "COMPLETE";
export type ReplayStatus = "pending" | "playing" | "paused" | "complete";

// === Core Models ===
export interface Player {
  id: string;
  name: string;
  role: "TOP" | "JNG" | "MID" | "ADC" | "SUP";
}

export interface TeamContext {
  id: string;
  name: string;
  side: Team;
  players: Player[];
}

export interface DraftAction {
  sequence: number;
  action_type: ActionType;
  team_side: Team;
  champion_id: string;
  champion_name: string;
}

export interface DraftState {
  phase: DraftPhase;
  next_team: Team | null;
  next_action: ActionType | null;
  blue_bans: string[];
  red_bans: string[];
  blue_picks: string[];
  red_picks: string[];
  action_count: number;
}

// === Recommendations ===
export type RecommendationFlag = "SURPRISE_PICK" | "LOW_CONFIDENCE" | null;

export interface PickRecommendation {
  champion_name: string;
  confidence: number;
  flag: RecommendationFlag;
  reasons: string[];
}

export interface BanRecommendation {
  champion_name: string;
  priority: number;
  target_player: string | null;
  reasons: string[];
}

export interface Recommendations {
  for_team: Team;
  picks: PickRecommendation[];
  bans: BanRecommendation[];
}

// === WebSocket Messages ===
export interface SessionStartMessage {
  type: "session_start";
  session_id: string;
  blue_team: TeamContext;
  red_team: TeamContext;
  total_actions: number;
  patch: string | null;
}

export interface DraftActionMessage {
  type: "draft_action";
  action: DraftAction;
  draft_state: DraftState;
  recommendations: Recommendations;
}

export interface DraftCompleteMessage {
  type: "draft_complete";
  draft_state: DraftState;
  blue_comp: string[];
  red_comp: string[];
}

export type WebSocketMessage =
  | SessionStartMessage
  | DraftActionMessage
  | DraftCompleteMessage;

// === API Types ===
export interface SeriesInfo {
  id: string;
  match_date: string;
  format: string;
  blue_team_name: string;
  red_team_name: string;
}

export interface GameInfo {
  id: string;
  game_number: number;
  patch_version: string | null;
  winner_team_id: string | null;
}

export interface StartReplayRequest {
  series_id: string;
  game_number: number;
  speed?: number;
  delay_seconds?: number;
}

export interface StartReplayResponse {
  session_id: string;
  total_actions: number;
  blue_team: string;
  red_team: string;
  patch: string | null;
  websocket_url: string;
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd deepdraft && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add deepdraft/src/types/index.ts
git commit -m "feat(frontend): align types with backend WebSocket protocol

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create ChampionPortrait Component

**Files:**
- Create: `deepdraft/src/components/shared/ChampionPortrait.tsx`
- Create: `deepdraft/src/components/shared/index.ts`

**Step 1: Create the ChampionPortrait component**

```typescript
// deepdraft/src/components/shared/ChampionPortrait.tsx
import { getChampionIconUrl } from "../../utils";
import type { Team } from "../../types";

type PortraitState = "empty" | "picking" | "picked" | "banned";
type PortraitSize = "sm" | "md" | "lg";

interface ChampionPortraitProps {
  championName?: string | null;
  state?: PortraitState;
  team?: Team | null;
  size?: PortraitSize;
  className?: string;
}

const SIZE_CLASSES: Record<PortraitSize, string> = {
  sm: "w-10 h-10",
  md: "w-14 h-14",
  lg: "w-20 h-20",
};

export function ChampionPortrait({
  championName,
  state = "empty",
  team = null,
  size = "md",
  className = "",
}: ChampionPortraitProps) {
  const sizeClass = SIZE_CLASSES[size];

  // Base styles
  const baseClasses = `
    relative rounded-sm overflow-hidden
    ${sizeClass}
    transition-all duration-200
  `;

  // State-specific styles
  const stateClasses: Record<PortraitState, string> = {
    empty: "border-2 border-gold-dim bg-lol-darkest",
    picking: "border-2 border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)] animate-[magic-pulse_2s_ease-in-out_infinite]",
    picked: team === "blue"
      ? "border-2 border-blue-team"
      : "border-2 border-red-team",
    banned: "border-2 border-red-team grayscale opacity-60",
  };

  if (state === "empty" || !championName) {
    return (
      <div className={`${baseClasses} ${stateClasses.empty} ${className}`}>
        <div className="w-full h-full flex items-center justify-center">
          <span className="text-gold-dim text-lg">?</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${baseClasses} ${stateClasses[state]} ${className}`}>
      <img
        src={getChampionIconUrl(championName)}
        alt={championName}
        className="w-full h-full object-cover"
        loading="lazy"
      />
      {state === "banned" && (
        <div className="absolute inset-0 flex items-center justify-center bg-lol-darkest/40">
          <span className="text-red-team text-2xl font-bold">✕</span>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Create barrel export**

```typescript
// deepdraft/src/components/shared/index.ts
export { ChampionPortrait } from "./ChampionPortrait";
```

**Step 3: Verify component renders**

Add temporary test in App.tsx to verify:
```tsx
import { ChampionPortrait } from "./components/shared";
// In render: <ChampionPortrait championName="Jinx" state="picked" team="blue" />
```

Run: `npm run dev`
Expected: Jinx icon renders with blue border

**Step 4: Remove test code and commit**

```bash
git add deepdraft/src/components/shared/
git commit -m "feat(frontend): add ChampionPortrait component

States: empty, picking, picked, banned
Sizes: sm, md, lg

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Create TeamPanel Component

**Files:**
- Create: `deepdraft/src/components/draft/TeamPanel.tsx`
- Create: `deepdraft/src/components/draft/index.ts`

**Step 1: Create TeamPanel component**

```typescript
// deepdraft/src/components/draft/TeamPanel.tsx
import { ChampionPortrait } from "../shared";
import type { TeamContext, Team, DraftPhase } from "../../types";

interface TeamPanelProps {
  team: TeamContext | null;
  picks: string[];
  side: Team;
  isActive: boolean;
  currentPickIndex?: number; // Which slot is currently picking (0-4)
}

const ROLE_ORDER = ["TOP", "JNG", "MID", "ADC", "SUP"] as const;

export function TeamPanel({
  team,
  picks,
  side,
  isActive,
  currentPickIndex,
}: TeamPanelProps) {
  const sideColors = side === "blue"
    ? {
        bg: "bg-blue-team-bg",
        border: "border-blue-team",
        text: "text-blue-team",
        glow: isActive ? "shadow-[0_0_30px_rgba(10,200,185,0.3)]" : "",
      }
    : {
        bg: "bg-red-team-bg",
        border: "border-red-team",
        text: "text-red-team",
        glow: isActive ? "shadow-[0_0_30px_rgba(232,64,87,0.3)]" : "",
      };

  return (
    <div className={`
      ${sideColors.bg} rounded-lg p-4
      border-l-4 ${sideColors.border}
      ${sideColors.glow}
      transition-shadow duration-300
    `}>
      {/* Team Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`
          w-10 h-10 rounded bg-lol-dark
          flex items-center justify-center
          border ${sideColors.border}
        `}>
          <span className={`font-bold text-sm ${sideColors.text}`}>
            {team?.name?.substring(0, 2).toUpperCase() || "??"}
          </span>
        </div>
        <div>
          <h2 className={`font-semibold uppercase tracking-wide ${sideColors.text}`}>
            {team?.name || "Unknown Team"}
          </h2>
          <span className="text-xs text-text-tertiary uppercase">
            {side} side
          </span>
        </div>
      </div>

      {/* Player Slots */}
      <div className="space-y-3">
        {ROLE_ORDER.map((role, index) => {
          const player = team?.players.find(p => p.role === role);
          const pick = picks[index] || null;
          const isPicking = currentPickIndex === index;

          return (
            <div
              key={role}
              className={`
                flex items-center gap-3 p-2 rounded
                ${isPicking ? "bg-lol-hover" : ""}
                transition-colors duration-200
              `}
            >
              {/* Role badge */}
              <span className="w-10 text-xs font-medium uppercase text-text-tertiary">
                {role}
              </span>

              {/* Player name */}
              <span className="flex-1 text-sm text-gold-bright truncate">
                {player?.name || "—"}
              </span>

              {/* Champion portrait */}
              <ChampionPortrait
                championName={pick}
                state={pick ? "picked" : isPicking ? "picking" : "empty"}
                team={side}
                size="sm"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 2: Create barrel export**

```typescript
// deepdraft/src/components/draft/index.ts
export { TeamPanel } from "./TeamPanel";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/draft/
git commit -m "feat(frontend): add TeamPanel component

Shows 5 player slots with roles, names, and champion picks

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create BanTrack Component

**Files:**
- Modify: `deepdraft/src/components/draft/index.ts`
- Create: `deepdraft/src/components/draft/BanTrack.tsx`

**Step 1: Create BanTrack component**

```typescript
// deepdraft/src/components/draft/BanTrack.tsx
import { ChampionPortrait } from "../shared";
import type { Team } from "../../types";

interface BanTrackProps {
  blueBans: string[];
  redBans: string[];
  currentBanTeam?: Team | null;
  currentBanIndex?: number; // 0-4 for each team
}

export function BanTrack({
  blueBans,
  redBans,
  currentBanTeam,
  currentBanIndex,
}: BanTrackProps) {
  // Pro draft ban order: B-R-B-R-B-R (phase 1), R-B-R-B (phase 2)
  // We display as two rows: phase 1 (6 bans) | phase 2 (4 bans)

  const phase1Order: Array<{ team: Team; index: number }> = [
    { team: "blue", index: 0 },
    { team: "red", index: 0 },
    { team: "blue", index: 1 },
    { team: "red", index: 1 },
    { team: "blue", index: 2 },
    { team: "red", index: 2 },
  ];

  const phase2Order: Array<{ team: Team; index: number }> = [
    { team: "red", index: 3 },
    { team: "blue", index: 3 },
    { team: "red", index: 4 },
    { team: "blue", index: 4 },
  ];

  const getBan = (team: Team, index: number): string | null => {
    const bans = team === "blue" ? blueBans : redBans;
    return bans[index] || null;
  };

  const isCurrentBan = (team: Team, index: number): boolean => {
    return currentBanTeam === team && currentBanIndex === index;
  };

  const renderBanSlot = (team: Team, index: number, key: string) => {
    const ban = getBan(team, index);
    const isCurrent = isCurrentBan(team, index);

    return (
      <div
        key={key}
        className={`
          relative
          ${team === "blue" ? "border-blue-team/30" : "border-red-team/30"}
        `}
      >
        <ChampionPortrait
          championName={ban}
          state={ban ? "banned" : isCurrent ? "picking" : "empty"}
          team={team}
          size="sm"
        />
        {/* Team indicator dot */}
        <div className={`
          absolute -bottom-1 left-1/2 -translate-x-1/2
          w-2 h-2 rounded-full
          ${team === "blue" ? "bg-blue-team" : "bg-red-team"}
        `} />
      </div>
    );
  };

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Phase 1 Bans */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-tertiary uppercase mr-2">Phase 1</span>
        {phase1Order.map((slot, i) => renderBanSlot(slot.team, slot.index, `p1-${i}`))}
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-gold-dim" />

      {/* Phase 2 Bans */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-tertiary uppercase mr-2">Phase 2</span>
        {phase2Order.map((slot, i) => renderBanSlot(slot.team, slot.index, `p2-${i}`))}
      </div>
    </div>
  );
}
```

**Step 2: Update barrel export**

```typescript
// deepdraft/src/components/draft/index.ts
export { TeamPanel } from "./TeamPanel";
export { BanTrack } from "./BanTrack";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/draft/
git commit -m "feat(frontend): add BanTrack component

Shows 10 ban slots in pro draft order with team indicators

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Create PhaseIndicator Component

**Files:**
- Create: `deepdraft/src/components/draft/PhaseIndicator.tsx`
- Modify: `deepdraft/src/components/draft/index.ts`

**Step 1: Create PhaseIndicator component**

```typescript
// deepdraft/src/components/draft/PhaseIndicator.tsx
import type { DraftPhase, Team, ActionType } from "../../types";

interface PhaseIndicatorProps {
  currentPhase: DraftPhase;
  nextTeam: Team | null;
  nextAction: ActionType | null;
}

const PHASES: Array<{ id: DraftPhase; label: string }> = [
  { id: "BAN_PHASE_1", label: "Ban 1" },
  { id: "PICK_PHASE_1", label: "Pick 1" },
  { id: "BAN_PHASE_2", label: "Ban 2" },
  { id: "PICK_PHASE_2", label: "Pick 2" },
];

export function PhaseIndicator({
  currentPhase,
  nextTeam,
  nextAction,
}: PhaseIndicatorProps) {
  const currentIndex = PHASES.findIndex(p => p.id === currentPhase);
  const isComplete = currentPhase === "COMPLETE";

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Phase Pills */}
      <div className="flex items-center gap-2">
        {PHASES.map((phase, i) => {
          const isActive = phase.id === currentPhase;
          const isPast = currentIndex > i || isComplete;

          return (
            <div
              key={phase.id}
              className={`
                px-3 py-1.5 rounded text-xs uppercase tracking-widest font-semibold
                transition-all duration-300
                ${isActive
                  ? "bg-magic text-lol-darkest shadow-[0_0_20px_rgba(10,200,185,0.4)]"
                  : isPast
                    ? "bg-gold-dark text-gold-dim"
                    : "bg-lol-light text-text-tertiary"
                }
              `}
            >
              {phase.label}
            </div>
          );
        })}
      </div>

      {/* Current Action Indicator */}
      {!isComplete && nextTeam && nextAction && (
        <div className="flex items-center gap-2 text-sm">
          <span className={`
            font-semibold uppercase
            ${nextTeam === "blue" ? "text-blue-team" : "text-red-team"}
          `}>
            {nextTeam}
          </span>
          <span className="text-text-secondary">
            {nextAction === "ban" ? "banning" : "picking"}
          </span>
        </div>
      )}

      {isComplete && (
        <div className="text-sm text-success font-semibold uppercase tracking-wide">
          Draft Complete
        </div>
      )}
    </div>
  );
}
```

**Step 2: Update barrel export**

```typescript
// deepdraft/src/components/draft/index.ts
export { TeamPanel } from "./TeamPanel";
export { BanTrack } from "./BanTrack";
export { PhaseIndicator } from "./PhaseIndicator";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/draft/
git commit -m "feat(frontend): add PhaseIndicator component

Shows 4 phase pills with active/past states and current action

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Create RecommendationCard Component

**Files:**
- Create: `deepdraft/src/components/recommendations/RecommendationCard.tsx`
- Create: `deepdraft/src/components/recommendations/index.ts`

**Step 1: Create RecommendationCard component**

```typescript
// deepdraft/src/components/recommendations/RecommendationCard.tsx
import { ChampionPortrait } from "../shared";
import type { PickRecommendation, RecommendationFlag } from "../../types";

interface RecommendationCardProps {
  recommendation: PickRecommendation;
  isTopPick?: boolean;
  rank?: number;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const fillColor =
    confidence >= 0.7 ? "bg-success" :
    confidence >= 0.5 ? "bg-warning" : "bg-danger";

  return (
    <div className="w-24 h-2 bg-lol-darkest rounded-full overflow-hidden">
      <div
        className={`h-full ${fillColor} transition-all duration-500`}
        style={{ width: `${confidence * 100}%` }}
      />
    </div>
  );
}

function FlagBadge({ flag }: { flag: RecommendationFlag }) {
  if (!flag) return null;

  const styles = flag === "SURPRISE_PICK"
    ? "bg-warning/20 text-warning"
    : "bg-danger/20 text-danger";

  const label = flag === "SURPRISE_PICK"
    ? "Surprise Pick"
    : "Low Confidence";

  return (
    <div className={`
      text-xs uppercase tracking-widest font-semibold
      py-1 px-2 rounded mb-3
      ${styles}
    `}>
      {label}
    </div>
  );
}

export function RecommendationCard({
  recommendation,
  isTopPick = false,
  rank,
}: RecommendationCardProps) {
  const { champion_name, confidence, flag, reasons } = recommendation;

  const confidenceColor =
    confidence >= 0.7 ? "text-success" :
    confidence >= 0.5 ? "text-warning" : "text-danger";

  const cardBorder = isTopPick
    ? "border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)]"
    : "border-gold-dim";

  return (
    <div className={`
      bg-lol-light rounded-lg p-4 border-2 ${cardBorder}
      transition-all duration-300
      hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
    `}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <ChampionPortrait
          championName={champion_name}
          state="picked"
          team="blue"
          size="lg"
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {isTopPick && <span className="text-lg">🎯</span>}
            {flag === "SURPRISE_PICK" && <span className="text-lg">🎲</span>}
            {flag === "LOW_CONFIDENCE" && <span className="text-lg">⚠️</span>}
            {rank && !isTopPick && (
              <span className="text-text-tertiary text-sm">#{rank}</span>
            )}
            <h3 className="font-semibold text-lg uppercase text-gold-bright">
              {champion_name}
            </h3>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-sm font-semibold ${confidenceColor}`}>
              {Math.round(confidence * 100)}%
            </span>
            <ConfidenceBar confidence={confidence} />
          </div>
        </div>
      </div>

      {/* Flag Banner */}
      <FlagBadge flag={flag} />

      {/* Reasons */}
      <ul className="space-y-1.5">
        {reasons.slice(0, 3).map((reason, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
            <span className="text-gold mt-0.5">•</span>
            <span>{reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

**Step 2: Create barrel export**

```typescript
// deepdraft/src/components/recommendations/index.ts
export { RecommendationCard } from "./RecommendationCard";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/recommendations/
git commit -m "feat(frontend): add RecommendationCard component

Shows champion, confidence bar, flag badge, and reasons

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Create InsightPanel Component

**Files:**
- Create: `deepdraft/src/components/recommendations/InsightPanel.tsx`
- Modify: `deepdraft/src/components/recommendations/index.ts`

**Step 1: Create InsightPanel component**

```typescript
// deepdraft/src/components/recommendations/InsightPanel.tsx
interface InsightPanelProps {
  insight: string | null;
  isLoading?: boolean;
}

export function InsightPanel({ insight, isLoading = false }: InsightPanelProps) {
  return (
    <div className="
      bg-gradient-to-br from-lol-dark to-lol-medium
      rounded-lg p-4 border border-magic/30
      relative overflow-hidden
      h-full
    ">
      {/* Ambient glow background */}
      <div className="absolute inset-0 bg-magic/5" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 bg-magic/10 rounded-full blur-3xl" />

      {/* Header */}
      <div className="relative flex items-center gap-2 mb-3">
        <span className="text-2xl">💡</span>
        <h3 className="font-semibold text-sm uppercase tracking-widest text-magic">
          AI Insight
        </h3>
      </div>

      {/* Content */}
      <div className="relative">
        {isLoading ? (
          <div className="flex items-center gap-2 text-text-secondary">
            <div className="w-4 h-4 border-2 border-magic border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Analyzing draft...</span>
          </div>
        ) : insight ? (
          <p className="text-sm text-gold-bright leading-relaxed">
            "{insight}"
          </p>
        ) : (
          <p className="text-sm text-text-tertiary italic">
            Insights will appear as the draft progresses...
          </p>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Update barrel export**

```typescript
// deepdraft/src/components/recommendations/index.ts
export { RecommendationCard } from "./RecommendationCard";
export { InsightPanel } from "./InsightPanel";
```

**Step 3: Commit**

```bash
git add deepdraft/src/components/recommendations/
git commit -m "feat(frontend): add InsightPanel component

Shows AI-generated draft insights with loading state

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Create useReplaySession Hook

**Files:**
- Create: `deepdraft/src/hooks/useReplaySession.ts`
- Modify: `deepdraft/src/hooks/index.ts` (create if doesn't exist)

**Step 1: Create the replay session hook**

```typescript
// deepdraft/src/hooks/useReplaySession.ts
import { useState, useCallback, useEffect, useRef } from "react";
import type {
  TeamContext,
  DraftState,
  Recommendations,
  WebSocketMessage,
  DraftAction,
} from "../types";

type SessionStatus = "idle" | "connecting" | "playing" | "complete" | "error";

interface ReplaySessionState {
  status: SessionStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
  recommendations: Recommendations | null;
  lastAction: DraftAction | null;
  totalActions: number;
  patch: string | null;
  error: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace("http", "ws");

export function useReplaySession() {
  const [state, setState] = useState<ReplaySessionState>({
    status: "idle",
    sessionId: null,
    blueTeam: null,
    redTeam: null,
    draftState: null,
    recommendations: null,
    lastAction: null,
    totalActions: 0,
    patch: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);

  const startReplay = useCallback(async (
    seriesId: string,
    gameNumber: number,
    speed: number = 1.0,
    delaySeconds: number = 3.0,
  ) => {
    setState(prev => ({ ...prev, status: "connecting", error: null }));

    try {
      // Start replay session via REST
      const response = await fetch(`${API_BASE}/api/replay/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series_id: seriesId,
          game_number: gameNumber,
          speed,
          delay_seconds: delaySeconds,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start replay: ${response.statusText}`);
      }

      const data = await response.json();
      const { session_id, websocket_url } = data;

      // Connect WebSocket
      const ws = new WebSocket(`${WS_BASE}${websocket_url}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg: WebSocketMessage = JSON.parse(event.data);

        switch (msg.type) {
          case "session_start":
            setState(prev => ({
              ...prev,
              status: "playing",
              sessionId: msg.session_id,
              blueTeam: msg.blue_team,
              redTeam: msg.red_team,
              totalActions: msg.total_actions,
              patch: msg.patch,
            }));
            break;

          case "draft_action":
            setState(prev => ({
              ...prev,
              draftState: msg.draft_state,
              recommendations: msg.recommendations,
              lastAction: msg.action,
            }));
            break;

          case "draft_complete":
            setState(prev => ({
              ...prev,
              status: "complete",
              draftState: msg.draft_state,
            }));
            break;
        }
      };

      ws.onerror = () => {
        setState(prev => ({
          ...prev,
          status: "error",
          error: "WebSocket connection failed"
        }));
      };

      ws.onclose = () => {
        wsRef.current = null;
      };

    } catch (err) {
      setState(prev => ({
        ...prev,
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  const stopReplay = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setState({
      status: "idle",
      sessionId: null,
      blueTeam: null,
      redTeam: null,
      draftState: null,
      recommendations: null,
      lastAction: null,
      totalActions: 0,
      patch: null,
      error: null,
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    startReplay,
    stopReplay,
  };
}
```

**Step 2: Create hooks barrel export**

```typescript
// deepdraft/src/hooks/index.ts
export { useWebSocket } from "./useWebSocket";
export { useReplaySession } from "./useReplaySession";
```

**Step 3: Commit**

```bash
git add deepdraft/src/hooks/
git commit -m "feat(frontend): add useReplaySession hook

Manages WebSocket connection and draft state for replays

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Rebuild DraftBoard as Main Layout

**Files:**
- Modify: `deepdraft/src/components/DraftBoard/index.tsx`

**Step 1: Rewrite DraftBoard as the main draft visualization**

```typescript
// deepdraft/src/components/DraftBoard/index.tsx
import { TeamPanel, BanTrack, PhaseIndicator } from "../draft";
import type { TeamContext, DraftState, Team, ActionType } from "../../types";

interface DraftBoardProps {
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
}

// Calculate which pick slot is active (0-4 index)
function getCurrentPickIndex(
  picks: string[],
  nextTeam: Team | null,
  nextAction: ActionType | null,
  side: Team
): number | undefined {
  if (nextAction !== "pick" || nextTeam !== side) return undefined;
  return picks.length; // Next empty slot
}

// Calculate which ban slot is active (0-4 index)
function getCurrentBanIndex(
  bans: string[],
  nextTeam: Team | null,
  nextAction: ActionType | null,
  side: Team
): number | undefined {
  if (nextAction !== "ban" || nextTeam !== side) return undefined;
  return bans.length;
}

export function DraftBoard({ blueTeam, redTeam, draftState }: DraftBoardProps) {
  const phase = draftState?.phase ?? "BAN_PHASE_1";
  const nextTeam = draftState?.next_team ?? null;
  const nextAction = draftState?.next_action ?? null;
  const blueBans = draftState?.blue_bans ?? [];
  const redBans = draftState?.red_bans ?? [];
  const bluePicks = draftState?.blue_picks ?? [];
  const redPicks = draftState?.red_picks ?? [];

  return (
    <div className="bg-lol-dark rounded-lg p-6">
      {/* Phase Indicator - Top Center */}
      <div className="flex justify-center mb-6">
        <PhaseIndicator
          currentPhase={phase}
          nextTeam={nextTeam}
          nextAction={nextAction}
        />
      </div>

      {/* Main Draft Grid */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-6 items-start">
        {/* Blue Team Panel - Left */}
        <TeamPanel
          team={blueTeam}
          picks={bluePicks}
          side="blue"
          isActive={nextTeam === "blue" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(bluePicks, nextTeam, nextAction, "blue")}
        />

        {/* Center: Ban Track */}
        <div className="flex flex-col items-center pt-8">
          <BanTrack
            blueBans={blueBans}
            redBans={redBans}
            currentBanTeam={nextAction === "ban" ? nextTeam : null}
            currentBanIndex={
              nextAction === "ban" && nextTeam
                ? (nextTeam === "blue" ? blueBans.length : redBans.length)
                : undefined
            }
          />

          {/* Action Counter */}
          <div className="mt-6 text-center">
            <div className="text-3xl font-bold text-gold-bright">
              {draftState?.action_count ?? 0}
            </div>
            <div className="text-xs text-text-tertiary uppercase">
              / 20 actions
            </div>
          </div>
        </div>

        {/* Red Team Panel - Right */}
        <TeamPanel
          team={redTeam}
          picks={redPicks}
          side="red"
          isActive={nextTeam === "red" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(redPicks, nextTeam, nextAction, "red")}
        />
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/DraftBoard/
git commit -m "feat(frontend): rebuild DraftBoard as main draft layout

3-column grid: blue team | ban track | red team
Integrates PhaseIndicator, TeamPanel, BanTrack

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Rebuild RecommendationPanel

**Files:**
- Modify: `deepdraft/src/components/RecommendationPanel/index.tsx`

**Step 1: Rewrite RecommendationPanel to show recommendations grid**

```typescript
// deepdraft/src/components/RecommendationPanel/index.tsx
import { RecommendationCard, InsightPanel } from "../recommendations";
import type { Recommendations, ActionType } from "../../types";

interface RecommendationPanelProps {
  recommendations: Recommendations | null;
  nextAction: ActionType | null;
}

export function RecommendationPanel({
  recommendations,
  nextAction,
}: RecommendationPanelProps) {
  // Only show pick recommendations for now (bans are simpler)
  const picks = recommendations?.picks ?? [];
  const forTeam = recommendations?.for_team;

  // Placeholder insight - will come from LLM later
  const insight = picks.length > 0
    ? `${forTeam?.toUpperCase() ?? "Team"} should consider ${picks[0]?.champion_name} as a strong pick in this position.`
    : null;

  if (!recommendations || nextAction === null) {
    return (
      <div className="bg-lol-dark rounded-lg p-6">
        <div className="text-center text-text-tertiary py-8">
          Waiting for draft to begin...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-lol-dark rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          {nextAction === "pick" ? "Pick" : "Ban"} Recommendations
        </h2>
        <span className={`
          text-sm font-semibold uppercase px-2 py-1 rounded
          ${forTeam === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
        `}>
          For {forTeam}
        </span>
      </div>

      {/* Recommendations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Top Pick */}
        {picks[0] && (
          <RecommendationCard
            recommendation={picks[0]}
            isTopPick
          />
        )}

        {/* Second Pick or Surprise */}
        {picks[1] && (
          <RecommendationCard
            recommendation={picks[1]}
            rank={2}
          />
        )}

        {/* AI Insight Panel */}
        <InsightPanel insight={insight} />
      </div>

      {/* Also Consider Row */}
      {picks.length > 2 && (
        <div className="mt-4 pt-4 border-t border-gold-dim/30">
          <span className="text-xs text-text-tertiary uppercase tracking-wide mr-3">
            Also Consider:
          </span>
          {picks.slice(2, 5).map((rec, i) => (
            <span
              key={rec.champion_name}
              className="inline-flex items-center gap-1 mr-4 text-sm text-text-secondary"
            >
              <span className="text-gold-bright">{rec.champion_name}</span>
              <span className="text-text-tertiary">
                ({Math.round(rec.confidence * 100)}%)
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/RecommendationPanel/
git commit -m "feat(frontend): rebuild RecommendationPanel with cards grid

Shows top picks with RecommendationCard + InsightPanel

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Update App.tsx with Full Layout

**Files:**
- Modify: `deepdraft/src/App.tsx`

**Step 1: Rewrite App.tsx to integrate all components**

```typescript
// deepdraft/src/App.tsx
import { useState } from "react";
import { DraftBoard } from "./components/DraftBoard";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ReplayControls } from "./components/ReplayControls";
import { useReplaySession } from "./hooks";

export default function App() {
  const {
    status,
    blueTeam,
    redTeam,
    draftState,
    recommendations,
    totalActions,
    patch,
    error,
    startReplay,
    stopReplay,
  } = useReplaySession();

  return (
    <div className="min-h-screen bg-lol-darkest">
      {/* Header */}
      <header className="h-16 bg-lol-dark border-b border-gold-dim/30 flex items-center px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            DeepDraft
          </h1>
          <span className="text-sm text-text-tertiary">
            LoL Draft Assistant
          </span>
        </div>

        <div className="ml-auto flex items-center gap-4">
          {patch && (
            <span className="text-xs text-text-tertiary">
              Patch {patch}
            </span>
          )}
          {status === "playing" && (
            <span className="text-xs text-magic animate-pulse">
              ● Live
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {/* Replay Controls */}
        <ReplayControls
          status={status}
          onStart={startReplay}
          onStop={stopReplay}
          error={error}
        />

        {/* Draft Board */}
        <DraftBoard
          blueTeam={blueTeam}
          redTeam={redTeam}
          draftState={draftState}
        />

        {/* Recommendations Panel */}
        <RecommendationPanel
          recommendations={recommendations}
          nextAction={draftState?.next_action ?? null}
        />
      </main>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/App.tsx
git commit -m "feat(frontend): integrate all draft components in App

Full layout: header, replay controls, draft board, recommendations

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Implement ReplayControls Component

**Files:**
- Modify: `deepdraft/src/components/ReplayControls/index.tsx`

**Step 1: Implement ReplayControls with series selector**

```typescript
// deepdraft/src/components/ReplayControls/index.tsx
import { useState, useEffect } from "react";
import type { SeriesInfo, GameInfo } from "../../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type SessionStatus = "idle" | "connecting" | "playing" | "complete" | "error";

interface ReplayControlsProps {
  status: SessionStatus;
  onStart: (seriesId: string, gameNumber: number, speed?: number) => void;
  onStop: () => void;
  error: string | null;
}

export function ReplayControls({
  status,
  onStart,
  onStop,
  error,
}: ReplayControlsProps) {
  const [seriesList, setSeriesList] = useState<SeriesInfo[]>([]);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [selectedSeries, setSelectedSeries] = useState<string>("");
  const [selectedGame, setSelectedGame] = useState<number>(1);
  const [speed, setSpeed] = useState<number>(1.0);
  const [loading, setLoading] = useState(false);

  // Fetch series list on mount
  useEffect(() => {
    async function fetchSeries() {
      try {
        const res = await fetch(`${API_BASE}/api/series?limit=20`);
        const data = await res.json();
        setSeriesList(data.series || []);
      } catch (err) {
        console.error("Failed to fetch series:", err);
      }
    }
    fetchSeries();
  }, []);

  // Fetch games when series changes
  useEffect(() => {
    if (!selectedSeries) {
      setGames([]);
      return;
    }

    async function fetchGames() {
      try {
        const res = await fetch(`${API_BASE}/api/series/${selectedSeries}/games`);
        const data = await res.json();
        setGames(data.games || []);
        setSelectedGame(1);
      } catch (err) {
        console.error("Failed to fetch games:", err);
      }
    }
    fetchGames();
  }, [selectedSeries]);

  const handleStart = () => {
    if (!selectedSeries) return;
    onStart(selectedSeries, selectedGame, speed);
  };

  const isPlaying = status === "playing" || status === "connecting";

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      <div className="flex flex-wrap items-center gap-4">
        {/* Series Selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Series
          </label>
          <select
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            disabled={isPlaying}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            <option value="">Select a series...</option>
            {seriesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.blue_team_name} vs {s.red_team_name} ({s.match_date?.split("T")[0]})
              </option>
            ))}
          </select>
        </div>

        {/* Game Selector */}
        <div className="w-24">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Game
          </label>
          <select
            value={selectedGame}
            onChange={(e) => setSelectedGame(Number(e.target.value))}
            disabled={isPlaying || games.length === 0}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            {games.map((g) => (
              <option key={g.game_number} value={g.game_number}>
                Game {g.game_number}
              </option>
            ))}
          </select>
        </div>

        {/* Speed Selector */}
        <div className="w-24">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Speed
          </label>
          <select
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            disabled={isPlaying}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={2}>2x</option>
            <option value={4}>4x</option>
          </select>
        </div>

        {/* Start/Stop Button */}
        <div className="pt-5">
          {isPlaying ? (
            <button
              onClick={onStop}
              className="
                px-6 py-2 rounded font-semibold uppercase tracking-wide text-sm
                bg-red-team text-white
                hover:bg-red-team/80 transition-colors
              "
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={!selectedSeries}
              className="
                px-6 py-2 rounded font-semibold uppercase tracking-wide text-sm
                bg-magic text-lol-darkest
                hover:bg-magic-bright transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                shadow-[0_0_15px_rgba(10,200,185,0.3)]
              "
            >
              {status === "connecting" ? "Connecting..." : "Start Replay"}
            </button>
          )}
        </div>

        {/* Status */}
        {status === "complete" && (
          <span className="text-sm text-success font-semibold uppercase">
            ✓ Complete
          </span>
        )}

        {error && (
          <span className="text-sm text-danger">
            {error}
          </span>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/ReplayControls/
git commit -m "feat(frontend): implement ReplayControls with series/game selectors

Fetches series list from API, allows speed selection

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 14: End-to-End Integration Test

**Files:** None (manual testing)

**Step 1: Start the backend**

```bash
cd /workspaces/web-dev-playground/ban-teemo/backend
uv run uvicorn ban_teemo.main:app --reload --host 0.0.0.0 --port 8000
```

Expected: Server running at http://localhost:8000

**Step 2: Start the frontend**

```bash
cd /workspaces/web-dev-playground/ban-teemo/deepdraft
npm run dev
```

Expected: Vite dev server at http://localhost:5173

**Step 3: Test the integration**

1. Open http://localhost:5173
2. Select a series from dropdown
3. Select game number
4. Click "Start Replay"
5. Watch draft actions stream in:
   - Team panels fill with picks
   - Ban track fills with bans
   - Phase indicator updates
   - Recommendations appear below

**Step 4: Verify all states**

- [x] Empty state renders correctly
- [x] Connecting state shows loading
- [x] Playing state streams actions
- [x] Complete state shows final composition
- [x] Stop button works mid-replay
- [x] Different speeds work (2x, 4x)

**Step 5: Commit any fixes**

If bugs found, fix and commit with descriptive message.

---

## Summary

| Task | Component | Purpose |
|------|-----------|---------|
| 1 | index.css | LoL Hextech theme colors |
| 2 | types/index.ts | Backend-aligned TypeScript types |
| 3 | ChampionPortrait | Champion icon with states |
| 4 | TeamPanel | 5 player slots per team |
| 5 | BanTrack | 10 ban slots in pro order |
| 6 | PhaseIndicator | Phase pills + current action |
| 7 | RecommendationCard | Single recommendation display |
| 8 | InsightPanel | AI insight with glow effect |
| 9 | useReplaySession | WebSocket state management |
| 10 | DraftBoard | Main 3-column layout |
| 11 | RecommendationPanel | Recommendations grid |
| 12 | App.tsx | Full app integration |
| 13 | ReplayControls | Series/game selection UI |
| 14 | Integration Test | End-to-end verification |

---

*Plan created: 2026-01-24*
