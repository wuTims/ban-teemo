# UI Bug Fixes & Improvements Design

**Date:** 2026-01-29
**Status:** Approved

## Overview

This document covers bug fixes and improvements for both Replay and Simulator modes in the DeepDraft application.

## Bug List

| # | Area | Issue | Complexity |
|---|------|-------|------------|
| 1 | Replay | Insights not hooked up - needs scrolling log | Medium |
| 2 | Simulator | Champion icon tiles too large vs icons | Low |
| 3 | Simulator | Champion grid needs infinite scroll (virtualization) | Medium |
| 4 | Simulator | Role filter buttons don't work | Medium |
| 5 | Simulator | Recommendations lack score breakdown (top 3 factors) | Medium |
| 6 | Simulator | Recommendations don't show which player they're for | Medium |
| 7 | Simulator | Recommendations not filtering by filled roles | Backend fix |
| 8 | Simulator | "Who won?" screen interrupts draft view | Low |
| 9 | Both | Need final draft score comparison | Medium |

---

## Design Details

### 1. Replay Mode - Detailed Insights Log

**Problem:** Recommendations come via WebSocket but aren't accumulated or displayed meaningfully.

**Solution:**

1. **Add `recommendationHistory` to `useReplaySession`**
   - Accumulate recommendations like `actionHistory`
   - Each entry: `{ sequence, action_type, team, recommendations }`

2. **Create `InsightsLog` component**
   - Replaces current `RecommendationPanel` in replay mode
   - Scrollable container with max-height
   - Each entry shows top 3 recommendations with reasons
   - Latest entry highlighted with "LIVE" badge
   - Auto-scrolls to bottom

3. **Slow down default replay speed**
   - Change default `delaySeconds` from 3.0 to 5.0
   - Add speed controls: 0.5x, 1x, 2x buttons

**UI Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ Draft Insights                              [0.5x][1x][2x] │
├─────────────────────────────────────────────────────────────┤
│ ┌─ Blue Ban #1 ──────────────────────────────────────────┐ │
│ │ 1. Yone (87%)                                          │ │
│ │    • Chovy's comfort pick (23 games)                   │ │
│ │    • S-tier meta champion                              │ │
│ │ 2. Aurora (82%)                                        │ │
│ │    • Canyon's comfort pick (15 games)                  │ │
│ │ 3. Rell (79%)                                          │ │
│ │    • Lehends' comfort pick (18 games)                  │ │
│ └────────────────────────────────────────────────────────┘ │
│ ┌─ Blue Ban #2 ─────────────────────────────── LIVE ────┐ │
│ │ (highlighted as current)                               │ │
│ └────────────────────────────────────────────────────────┘ │
│                                            [auto-scroll ▼] │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Champion Icon Sizing (Bug #2)

**Problem:** Grid tiles are 90% larger than actual icons.

**Fix:**
- Remove wrapper padding/gaps - icon fills the tile
- Increase icon sizes: `sm: w-12 h-12` (was w-10)
- Grid cell IS the portrait, not a button wrapping it
- Tighten grid gap from `gap-1` to `gap-0.5`

---

### 3. Champion Grid Virtualization (Bug #3)

**Problem:** Renders all 162 champions causing long scroll.

**Fix:**
- Use `@tanstack/react-virtual` for virtualization
- Fixed height container (400px)
- Render only visible rows (~8 rows × 6 columns = 48 champions)
- Overscan of 2 rows for smooth scrolling

---

### 4. Role Filtering (Bug #4)

**Problem:** Role filter buttons exist but logic not implemented.

**Fix:**
- Bundle static `championRoles.json` in frontend (extracted from `knowledge/champion_role_history.json`)
- Filter champions where `canonical_role` or `canonical_all` includes selected role
- Role mapping: "Top" → "TOP", "Jungle" → "JNG", "Mid" → "MID", "ADC" → "ADC", "Support" → "SUP"

---

### 5. Recommendation Score Breakdown (Bug #5)

**Problem:** Backend returns detailed `components` but frontend only shows overall score.

**Fix - Enhanced RecommendationCard:**
```
┌─────────────────────────────────────────┐
│ [Icon] Rumble          For: Zeus (TOP)  │
│        87% overall                      │
├─────────────────────────────────────────┤
│ Top Factors:                            │
│ ▸ Proficiency: 0.82 - Zeus 76% WR (12g) │
│ ▸ Meta: 0.75 - S-tier pick              │
│ ▸ Synergy: 0.71 - Strong with Rell      │
├─────────────────────────────────────────┤
│ • Favorable lane matchups               │
│ • Strong team synergy                   │
└─────────────────────────────────────────┘
```

- Show top 3 factors sorted by value (descending)
- Each factor: name, numeric score (0.00-1.00), insight text
- Keep existing reasons as secondary info

---

### 6. Player Labels on Recommendations (Bug #6)

**Problem:** Pick recommendations have `suggested_role` but don't show player name.

**Fix:**
- Match `suggested_role` to team roster to get player name
- Display as "For: {PlayerName} ({Role})" in card header
- Ban recommendations already show "Target: {player}" - keep as-is

---

### 7. Filter Filled Roles (Bug #7)

**Problem:** Recommendations include champions for already-filled roles.

**Fix (Backend):**
- In `get_recommendations`, after computing candidates, filter out any where `suggested_role` is in `filled_roles`
- Only recommend for unfilled positions

---

### 8. Draft Completion UI (Bug #8)

**Problem:** "Who won?" screen immediately replaces draft view.

**Fix:**
- Keep `SimulatorView` visible when draft completes
- Add `DraftCompletePanel` banner at bottom (not replacing view)
- Banner contains: completion message, draft scores, "Who won?" buttons

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ [Team Panel]     [Champion Pool]     [Team Panel]       │
│                  (still visible)                        │
│ [Ban Row]                                               │
├─────────────────────────────────────────────────────────┤
│ DRAFT COMPLETE                                          │
│ ┌───────────────────┐    ┌───────────────────┐         │
│ │ T1: 72 pts        │ vs │ Gen.G: 68 pts     │         │
│ │ Strong engage     │    │ Strong poke       │         │
│ └───────────────────┘    └───────────────────┘         │
│                                                         │
│ Who won this game?  [T1 Won]  [Gen.G Won]              │
└─────────────────────────────────────────────────────────┘
```

---

### 9. Final Draft Score (Bug #9)

**Data source:**
- `TeamEvaluationService` provides `composition_score`, `synergy_score`, `matchup_advantage`
- `GET /sessions/{id}/evaluation` returns evaluations for both teams

**Display:**
- Convert `composition_score` to points (× 100)
- Show for both teams: "T1: 72 pts" vs "Gen.G: 68 pts"
- Show `matchup_description` as summary
- Show top strength from `strengths` array

**Replay mode:**
- Fetch evaluation at draft completion
- Display same scoring UI

---

## Implementation Plan

### Files to Create

| File | Purpose |
|------|---------|
| `deepdraft/src/data/championRoles.json` | Static role data bundled from knowledge |
| `deepdraft/src/components/InsightsLog/index.tsx` | Scrolling insights log for replay |
| `deepdraft/src/components/DraftCompletePanel/index.tsx` | Draft completion banner with scores |

### Files to Modify

| File | Changes |
|------|---------|
| `deepdraft/src/hooks/useReplaySession.ts` | Add `recommendationHistory`, default delay 5s |
| `deepdraft/src/components/RecommendationPanel/index.tsx` | Replace with InsightsLog for replay mode |
| `deepdraft/src/components/ChampionPool/index.tsx` | Virtualization, role filtering, tighter sizing |
| `deepdraft/src/components/shared/ChampionPortrait.tsx` | Increase sm size, remove extra padding |
| `deepdraft/src/components/SimulatorView/index.tsx` | Enhanced RecommendationCard with score breakdown, player labels |
| `deepdraft/src/App.tsx` | Keep SimulatorView visible on completion, add DraftCompletePanel |
| `backend/src/ban_teemo/services/pick_recommendation_engine.py` | Filter out filled roles from results |

### Dependencies to Add

- `@tanstack/react-virtual` - Champion grid virtualization

### Task Order

1. Backend fix: Filter filled roles from recommendations
2. Bundle champion role data JSON
3. Fix champion icon sizing
4. Implement virtualized champion grid with role filtering
5. Enhance RecommendationCard with score breakdown + player labels
6. Create InsightsLog component for replay
7. Update replay hook with recommendation history
8. Create DraftCompletePanel with scoring
9. Update App.tsx to show completion inline
