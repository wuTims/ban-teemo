# Mobile & UX Improvements Plan

## Summary

Frontend fixes for mobile responsiveness and UX improvements in replay mode.

## Changes

### 1. Reorder DraftCompletePanel in Replay Mode

**File:** `frontend/src/App.tsx`

Move `DraftCompletePanel` to appear between `DraftBoard` and `RecommendationPanel` when `replay.status === "complete"`. During active drafts, only the InsightsLog shows.

**Current order:**
1. ReplayControls
2. DraftBoard + ActionLog
3. RecommendationPanel (InsightsLog)
4. DraftCompletePanel (at bottom)

**New order:**
1. ReplayControls
2. DraftBoard + ActionLog
3. DraftCompletePanel (when complete)
4. RecommendationPanel (InsightsLog)

### 2. Mobile-Friendly DraftCompletePanel

**File:** `frontend/src/components/DraftCompletePanel/index.tsx`

- Stack team boxes vertically at `<400px` (Blue, VS, Red)
- Use abbreviated team names via `getTeamAbbreviation()`
- Allow composition description to wrap to multiple lines
- Adjust padding/sizing for small screens

### 3. Mobile-Friendly Replay DraftBoard

**File:** `frontend/src/components/replay/DraftBoard/index.tsx`

Convert horizontal 3-column layout to vertical stack on mobile:
- Blue Team panel (picks stay horizontal)
- Bans row (centered)
- Red Team panel (picks stay horizontal)

Use responsive classes: `flex flex-col lg:grid lg:grid-cols-[1fr_auto_1fr]`

### 4. Mobile-Friendly InsightsLog

**File:** `frontend/src/components/replay/InsightsLog/index.tsx`

Change recommendation cards from horizontal scroll to 2x2 grid on mobile:
- `grid grid-cols-2 lg:flex lg:flex-row`
- Show top 4 recommendations in grid
- Each card is expandable to show detailed breakdown (score components)
- Cards start collapsed on mobile, tap to expand

### 5. Styled Scrollbars with Fade Hint

**Files:**
- `frontend/src/components/replay/ActionLog/index.tsx`
- `frontend/src/components/replay/InsightsLog/index.tsx`

Add custom scrollbar styling (thin, themed) and bottom fade gradient:

```css
/* Firefox */
scrollbar-width: thin;
scrollbar-color: theme('colors.gold-dim') transparent;

/* WebKit */
&::-webkit-scrollbar { width: 6px; }
&::-webkit-scrollbar-track { background: transparent; }
&::-webkit-scrollbar-thumb {
  background: theme('colors.gold-dim');
  border-radius: 3px;
}
```

Add fade gradient overlay at bottom when content overflows to hint at scrollability.

## Files to Modify

1. `frontend/src/App.tsx` - reorder components
2. `frontend/src/components/DraftCompletePanel/index.tsx` - mobile stack layout
3. `frontend/src/components/replay/DraftBoard/index.tsx` - vertical mobile layout
4. `frontend/src/components/replay/InsightsLog/index.tsx` - 2x2 grid + expandable cards
5. `frontend/src/components/replay/ActionLog/index.tsx` - scrollbar styling
6. `frontend/src/index.css` (or tailwind config) - scrollbar utility classes if needed
