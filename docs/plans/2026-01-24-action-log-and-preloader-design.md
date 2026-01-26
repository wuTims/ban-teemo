# Action Log and Champion Preloader Design

**Date:** 2026-01-24
**Status:** Implemented ✓
**Implementation:** `deepdraft/src/components/ActionLog/`, `ChampionPreloader/`

## Overview

Two enhancements to the deepdraft frontend draft simulation:

1. **Champion Icon Preloader** - Load all ~170 champion icons before rendering the app to eliminate timing issues between state transitions and icon loading
2. **Action Log** - Right sidebar showing a live feed of draft actions as they occur

## Problem

Currently, when a pick/ban action occurs:
- Draft state transitions immediately when WebSocket message arrives
- Champion icon fetches from Riot CDN (ddragon.leagueoflegends.com)
- Visual lag between action happening and icon appearing

## Solution

### 1. Champion Icon Preloader

#### New Utility: `preloadChampionIcons()`

Location: `deepdraft/src/utils/dataDragon.ts`

```typescript
export async function preloadChampionIcons(
  onProgress?: (loaded: number, total: number) => void
): Promise<void> {
  const championNames = getAllChampionNames();
  const total = championNames.length;
  let loaded = 0;

  const loadPromises = championNames.map((name) => {
    return new Promise<void>((resolve) => {
      const img = new Image();
      img.onload = () => {
        loaded++;
        onProgress?.(loaded, total);
        resolve();
      };
      img.onerror = () => {
        loaded++;
        onProgress?.(loaded, total);
        resolve(); // Don't fail on individual image errors
      };
      img.src = getChampionIconUrl(name);
    });
  });

  // Race against timeout to prevent blocking forever
  await Promise.race([
    Promise.all(loadPromises),
    new Promise((resolve) => setTimeout(resolve, 10000)),
  ]);
}
```

#### New Component: `ChampionPreloader`

Location: `deepdraft/src/components/ChampionPreloader/index.tsx`

- Wraps the app in `main.tsx`
- Shows loading progress while preloading
- Renders children once complete or timeout reached

```
┌─────────────────────────────────────────┐
│  Loading champion assets...             │
│  ████████████░░░░░░░░  67/170           │
└─────────────────────────────────────────┘
```

UI specs:
- Centered on screen
- Dark background (`bg-lol-darkest`)
- Progress bar with gold accent (`bg-gold-bright`)
- Falls through after 10s timeout

### 2. Action Log

#### New Component: `ActionLog`

Location: `deepdraft/src/components/ActionLog/index.tsx`

Right sidebar showing live feed of draft actions.

```
┌──────────────────────────┐
│  DRAFT LOG               │
├──────────────────────────┤
│  ┌────┐                  │
│  │ 🚫 │ T1 banned Yone   │
│  └────┘                  │
│  ┌────┐                  │
│  │ 🚫 │ BLG banned Rell  │
│  └────┘                  │
│  ┌────┐                  │
│  │ ✓  │ BLG picked Jax   │
│  └────┘                  │
│                          │
└──────────────────────────┘
```

Each action entry shows:
- Small champion icon (40x40, reuses `ChampionPortrait`)
- Team name (colored by side: blue-team / red-team)
- Action type ("banned" / "picked")
- Champion name

Behavior:
- Auto-scrolls to bottom as new actions arrive
- Bans: grayscale icon with X overlay
- Picks: team color border
- Empty state: "Waiting for draft to begin..."

#### Hook Changes: `useReplaySession`

Add action history tracking:

```typescript
interface ReplaySessionState {
  // ... existing fields
  actionHistory: DraftAction[];  // NEW
}

// In draft_action handler:
case "draft_action":
  setState(prev => ({
    ...prev,
    draftState: msg.draft_state,
    recommendations: msg.recommendations,
    lastAction: msg.action,
    actionHistory: [...prev.actionHistory, msg.action],  // NEW
  }));
  break;

// In stopReplay:
actionHistory: [],  // Clear on stop
```

### 3. Layout Changes

Updated App layout structure:

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER                                                         │
├─────────────────────────────────────────────────────────────────┤
│  REPLAY CONTROLS                                                │
├───────────────────────────────────────────────┬─────────────────┤
│                                               │                 │
│  DRAFT BOARD                                  │  ACTION LOG     │
│  (flex-1)                                     │  (w-72, ~288px) │
│                                               │                 │
├───────────────────────────────────────────────┴─────────────────┤
│  RECOMMENDATION PANEL                                           │
└─────────────────────────────────────────────────────────────────┘
```

- Main content area: `flex flex-row gap-6`
- Draft board: `flex-1`
- Action log: `w-72` (fixed 288px width)
- Action log only visible when `status !== "idle"`

## Files to Modify

1. `deepdraft/src/utils/dataDragon.ts` - Add `preloadChampionIcons()`
2. `deepdraft/src/components/ChampionPreloader/index.tsx` - New component
3. `deepdraft/src/components/ActionLog/index.tsx` - New component
4. `deepdraft/src/hooks/useReplaySession.ts` - Add `actionHistory`
5. `deepdraft/src/main.tsx` - Wrap App with ChampionPreloader
6. `deepdraft/src/App.tsx` - Update layout, add ActionLog

## Implementation Order

1. Add `preloadChampionIcons()` utility
2. Create `ChampionPreloader` component
3. Wrap app in preloader
4. Add `actionHistory` to hook
5. Create `ActionLog` component
6. Update App layout
