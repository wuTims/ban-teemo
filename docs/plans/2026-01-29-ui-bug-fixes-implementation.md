# UI Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 9 UI bugs across Replay and Simulator modes, improving recommendation displays and draft completion UX.

**Architecture:** Backend filter for filled roles, frontend enhancements for virtualized champion grid, detailed recommendation cards, scrolling insights log, and inline draft completion panel.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, @tanstack/react-virtual, FastAPI, Python 3.14

---

## Task 1: Backend - Filter Filled Roles from Recommendations

**Files:**
- Modify: `backend/src/ban_teemo/services/pick_recommendation_engine.py:66-79`
- Test: `backend/tests/test_pick_recommendation_engine.py`

**Step 1: Write the failing test**

Create or add to test file:

```python
# backend/tests/test_pick_recommendation_engine.py
import pytest
from ban_teemo.services.pick_recommendation_engine import PickRecommendationEngine

def test_recommendations_exclude_filled_roles():
    """Recommendations should not suggest champions for already-filled roles."""
    engine = PickRecommendationEngine()

    # T1 roster
    team_players = [
        {"name": "Zeus", "role": "TOP"},
        {"name": "Oner", "role": "JNG"},
        {"name": "Faker", "role": "MID"},
        {"name": "Gumayusi", "role": "ADC"},
        {"name": "Keria", "role": "SUP"},
    ]

    # Already picked: TOP (Renekton), MID (Orianna), JNG (Xin Zhao)
    our_picks = ["Renekton", "Orianna", "Xin Zhao"]
    enemy_picks = ["Yone", "Aurora"]
    banned = ["Rumble", "Rell"]

    recommendations = engine.get_recommendations(
        team_players=team_players,
        our_picks=our_picks,
        enemy_picks=enemy_picks,
        banned=banned,
        limit=10,
    )

    # All recommendations should be for ADC or SUP only
    filled_roles = {"TOP", "MID", "JNG"}
    for rec in recommendations:
        assert rec["suggested_role"] not in filled_roles, \
            f"{rec['champion_name']} suggested for filled role {rec['suggested_role']}"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_recommendations_exclude_filled_roles -v`

Expected: FAIL - recommendations include champions for filled roles

**Step 3: Write minimal implementation**

Modify `backend/src/ban_teemo/services/pick_recommendation_engine.py`:

```python
# In get_recommendations method, after line 78 (recommendations.sort...)
# Add filter before returning:

    def get_recommendations(
        self,
        team_players: list[dict],
        our_picks: list[str],
        enemy_picks: list[str],
        banned: list[str],
        limit: int = 5,
    ) -> list[dict]:
        # ... existing code up to line 77 ...

        recommendations.sort(key=lambda x: -x["score"])

        # Filter out recommendations for filled roles
        filled_roles = self._infer_filled_roles(our_picks)
        recommendations = [
            rec for rec in recommendations
            if rec["suggested_role"] not in filled_roles
        ]

        return recommendations[:limit]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_pick_recommendation_engine.py::test_recommendations_exclude_filled_roles -v`

Expected: PASS

**Step 5: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --tb=short`

Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/src/ban_teemo/services/pick_recommendation_engine.py backend/tests/test_pick_recommendation_engine.py
git commit -m "fix(backend): filter recommendations to exclude filled roles"
```

---

## Task 2: Bundle Champion Role Data

**Files:**
- Create: `deepdraft/src/data/championRoles.ts`

**Step 1: Extract role data from knowledge file**

```bash
cd /workspaces/web-dev-playground/ban-teemo
```

**Step 2: Create the champion roles data file**

Create `deepdraft/src/data/championRoles.ts`:

```typescript
// deepdraft/src/data/championRoles.ts
// Champion role mappings extracted from knowledge/champion_role_history.json
// Format: champion name -> array of viable roles

export const CHAMPION_ROLES: Record<string, string[]> = {
  "Aatrox": ["TOP"],
  "Ahri": ["MID"],
  "Akali": ["MID", "TOP"],
  "Akshan": ["MID", "TOP"],
  "Alistar": ["SUP"],
  "Amumu": ["JNG", "SUP"],
  "Anivia": ["MID"],
  "Annie": ["MID", "SUP"],
  "Aphelios": ["ADC"],
  "Ashe": ["ADC", "SUP"],
  "Aurelion Sol": ["MID"],
  "Aurora": ["MID", "TOP"],
  "Azir": ["MID"],
  "Bard": ["SUP"],
  "Bel'Veth": ["JNG"],
  "Blitzcrank": ["SUP"],
  "Brand": ["SUP", "MID"],
  "Braum": ["SUP"],
  "Briar": ["JNG"],
  "Caitlyn": ["ADC"],
  "Camille": ["TOP"],
  "Cassiopeia": ["MID"],
  "Cho'Gath": ["TOP"],
  "Corki": ["MID"],
  "Darius": ["TOP"],
  "Diana": ["JNG", "MID"],
  "Dr. Mundo": ["TOP", "JNG"],
  "Draven": ["ADC"],
  "Ekko": ["JNG", "MID"],
  "Elise": ["JNG"],
  "Evelynn": ["JNG"],
  "Ezreal": ["ADC"],
  "Fiddlesticks": ["JNG"],
  "Fiora": ["TOP"],
  "Fizz": ["MID"],
  "Galio": ["MID", "SUP"],
  "Gangplank": ["TOP", "MID"],
  "Garen": ["TOP"],
  "Gnar": ["TOP"],
  "Gragas": ["TOP", "JNG", "SUP"],
  "Graves": ["JNG"],
  "Gwen": ["TOP"],
  "Hecarim": ["JNG"],
  "Heimerdinger": ["MID", "TOP"],
  "Illaoi": ["TOP"],
  "Irelia": ["TOP", "MID"],
  "Ivern": ["JNG"],
  "Janna": ["SUP"],
  "Jarvan IV": ["JNG"],
  "Jax": ["TOP", "JNG"],
  "Jayce": ["TOP", "MID"],
  "Jhin": ["ADC"],
  "Jinx": ["ADC"],
  "K'Sante": ["TOP"],
  "Kai'Sa": ["ADC"],
  "Kalista": ["ADC"],
  "Karma": ["SUP"],
  "Karthus": ["JNG"],
  "Kassadin": ["MID"],
  "Katarina": ["MID"],
  "Kayle": ["TOP"],
  "Kayn": ["JNG"],
  "Kennen": ["TOP"],
  "Kha'Zix": ["JNG"],
  "Kindred": ["JNG"],
  "Kled": ["TOP"],
  "Kog'Maw": ["ADC"],
  "LeBlanc": ["MID"],
  "Lee Sin": ["JNG"],
  "Leona": ["SUP"],
  "Lillia": ["JNG", "TOP"],
  "Lissandra": ["MID"],
  "Lucian": ["ADC", "MID"],
  "Lulu": ["SUP"],
  "Lux": ["SUP", "MID"],
  "Malphite": ["TOP"],
  "Malzahar": ["MID"],
  "Maokai": ["SUP", "JNG"],
  "Master Yi": ["JNG"],
  "Milio": ["SUP"],
  "Miss Fortune": ["ADC"],
  "Mordekaiser": ["TOP"],
  "Morgana": ["SUP"],
  "Naafiri": ["MID", "JNG"],
  "Nami": ["SUP"],
  "Nasus": ["TOP"],
  "Nautilus": ["SUP"],
  "Neeko": ["MID", "SUP"],
  "Nidalee": ["JNG"],
  "Nilah": ["ADC"],
  "Nocturne": ["JNG"],
  "Nunu": ["JNG"],
  "Olaf": ["JNG", "TOP"],
  "Orianna": ["MID"],
  "Ornn": ["TOP"],
  "Pantheon": ["SUP", "MID"],
  "Poppy": ["TOP", "JNG", "SUP"],
  "Pyke": ["SUP"],
  "Qiyana": ["MID", "JNG"],
  "Quinn": ["TOP"],
  "Rakan": ["SUP"],
  "Rammus": ["JNG"],
  "Rek'Sai": ["JNG"],
  "Rell": ["SUP"],
  "Renata Glasc": ["SUP"],
  "Renekton": ["TOP"],
  "Rengar": ["JNG", "TOP"],
  "Riven": ["TOP"],
  "Rumble": ["TOP", "MID", "JNG"],
  "Ryze": ["MID"],
  "Samira": ["ADC"],
  "Sejuani": ["JNG"],
  "Senna": ["SUP", "ADC"],
  "Seraphine": ["SUP", "MID", "ADC"],
  "Sett": ["TOP", "SUP"],
  "Shaco": ["JNG"],
  "Shen": ["TOP", "SUP"],
  "Shyvana": ["JNG"],
  "Singed": ["TOP"],
  "Sion": ["TOP"],
  "Sivir": ["ADC"],
  "Skarner": ["JNG"],
  "Smolder": ["ADC", "MID"],
  "Sona": ["SUP"],
  "Soraka": ["SUP"],
  "Swain": ["SUP", "MID"],
  "Sylas": ["MID", "JNG"],
  "Syndra": ["MID"],
  "Tahm Kench": ["SUP", "TOP"],
  "Taliyah": ["JNG", "MID"],
  "Talon": ["MID", "JNG"],
  "Taric": ["SUP"],
  "Teemo": ["TOP"],
  "Thresh": ["SUP"],
  "Tristana": ["ADC", "MID"],
  "Trundle": ["JNG", "TOP"],
  "Tryndamere": ["TOP"],
  "Twisted Fate": ["MID"],
  "Twitch": ["ADC"],
  "Udyr": ["JNG"],
  "Urgot": ["TOP"],
  "Varus": ["ADC"],
  "Vayne": ["ADC", "TOP"],
  "Veigar": ["MID"],
  "Vel'Koz": ["SUP", "MID"],
  "Vex": ["MID"],
  "Vi": ["JNG"],
  "Viego": ["JNG"],
  "Viktor": ["MID"],
  "Vladimir": ["MID", "TOP"],
  "Volibear": ["TOP", "JNG"],
  "Warwick": ["JNG"],
  "Wukong": ["JNG", "TOP"],
  "Xayah": ["ADC"],
  "Xerath": ["SUP", "MID"],
  "Xin Zhao": ["JNG"],
  "Yasuo": ["MID", "ADC"],
  "Yone": ["MID", "TOP"],
  "Yorick": ["TOP"],
  "Yuumi": ["SUP"],
  "Zac": ["JNG"],
  "Zed": ["MID"],
  "Zeri": ["ADC"],
  "Ziggs": ["ADC", "MID"],
  "Zilean": ["SUP", "MID"],
  "Zoe": ["MID"],
  "Zyra": ["SUP"],
};

// Helper to get champions by role
export function getChampionsByRole(role: string): string[] {
  if (role === "All") {
    return Object.keys(CHAMPION_ROLES);
  }
  return Object.entries(CHAMPION_ROLES)
    .filter(([, roles]) => roles.includes(role))
    .map(([name]) => name);
}

// Helper to check if champion plays a role
export function championPlaysRole(champion: string, role: string): boolean {
  if (role === "All") return true;
  return CHAMPION_ROLES[champion]?.includes(role) ?? false;
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd deepdraft && npx tsc --noEmit`

Expected: No errors

**Step 4: Commit**

```bash
git add deepdraft/src/data/championRoles.ts
git commit -m "feat(frontend): add bundled champion role data"
```

---

## Task 3: Fix Champion Icon Sizing

**Files:**
- Modify: `deepdraft/src/components/shared/ChampionPortrait.tsx:16-19`
- Modify: `deepdraft/src/components/ChampionPool/index.tsx:74,86`

**Step 1: Update ChampionPortrait sizes**

Modify `deepdraft/src/components/shared/ChampionPortrait.tsx`:

```typescript
// Change SIZE_CLASSES (lines 16-19) to:
const SIZE_CLASSES: Record<PortraitSize, string> = {
  sm: "w-12 h-12",   // was w-10 h-10
  md: "w-14 h-14",
  lg: "w-20 h-20",
};
```

**Step 2: Tighten grid gap in ChampionPool**

Modify `deepdraft/src/components/ChampionPool/index.tsx`:

```typescript
// Change line 74 from:
<div className="grid grid-cols-6 gap-1">

// To:
<div className="grid grid-cols-6 gap-0.5">
```

**Step 3: Remove extra button wrapper padding**

In `deepdraft/src/components/ChampionPool/index.tsx`, update the button styling (around line 86):

```typescript
// Change from:
className={`relative aspect-square rounded overflow-hidden transition-all ${

// To (remove aspect-square, let portrait define size):
className={`relative rounded overflow-hidden transition-all ${
```

**Step 4: Verify visually**

Run: `cd deepdraft && npm run dev`

Open browser, go to Simulator mode, verify champion icons are tighter with less wasted space.

**Step 5: Commit**

```bash
git add deepdraft/src/components/shared/ChampionPortrait.tsx deepdraft/src/components/ChampionPool/index.tsx
git commit -m "fix(frontend): tighten champion icon sizing in grid"
```

---

## Task 4: Implement Virtualized Champion Grid with Role Filtering

**Files:**
- Modify: `deepdraft/src/components/ChampionPool/index.tsx`
- Modify: `deepdraft/package.json` (add dependency)

**Step 1: Install @tanstack/react-virtual**

Run: `cd deepdraft && npm install @tanstack/react-virtual`

**Step 2: Rewrite ChampionPool with virtualization and role filtering**

Replace `deepdraft/src/components/ChampionPool/index.tsx`:

```typescript
// deepdraft/src/components/ChampionPool/index.tsx
import { useState, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import { championPlaysRole } from "../../data/championRoles";
import type { FearlessBlocked } from "../../types";

interface ChampionPoolProps {
  allChampions: string[];
  unavailable: Set<string>;
  fearlessBlocked: FearlessBlocked;
  onSelect: (champion: string) => void;
  disabled: boolean;
}

const ROLES = ["All", "Top", "Jungle", "Mid", "ADC", "Support"] as const;
const ROLE_MAP: Record<string, string> = {
  "All": "All",
  "Top": "TOP",
  "Jungle": "JNG",
  "Mid": "MID",
  "ADC": "ADC",
  "Support": "SUP",
};

const COLUMNS = 6;
const ROW_HEIGHT = 52; // 48px icon + 4px gap

export function ChampionPool({
  allChampions,
  unavailable,
  fearlessBlocked,
  onSelect,
  disabled,
}: ChampionPoolProps) {
  const fearlessBlockedSet = useMemo(
    () => new Set(Object.keys(fearlessBlocked)),
    [fearlessBlocked]
  );
  const [search, setSearch] = useState("");
  const [selectedRole, setSelectedRole] = useState<string>("All");
  const parentRef = useRef<HTMLDivElement>(null);

  const filteredChampions = useMemo(() => {
    let filtered = allChampions;

    // Search filter
    if (search) {
      const query = search.toLowerCase();
      filtered = filtered.filter((c) => c.toLowerCase().includes(query));
    }

    // Role filter
    const roleKey = ROLE_MAP[selectedRole];
    if (roleKey !== "All") {
      filtered = filtered.filter((c) => championPlaysRole(c, roleKey));
    }

    return filtered.sort();
  }, [allChampions, search, selectedRole]);

  // Group into rows for virtualization
  const rows = useMemo(() => {
    const result: string[][] = [];
    for (let i = 0; i < filteredChampions.length; i += COLUMNS) {
      result.push(filteredChampions.slice(i, i + COLUMNS));
    }
    return result;
  }, [filteredChampions]);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 3,
  });

  return (
    <div className="bg-lol-dark rounded-lg p-4 flex flex-col h-full">
      {/* Search */}
      <input
        type="text"
        placeholder="Search champions..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-3 py-2 bg-lol-light border border-gold-dim/30 rounded text-text-primary placeholder-text-tertiary mb-3 focus:outline-none focus:border-magic"
      />

      {/* Role Filters */}
      <div className="flex gap-1 mb-3 flex-wrap">
        {ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setSelectedRole(role)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              selectedRole === role
                ? "bg-gold-dim text-lol-darkest"
                : "bg-lol-light text-text-secondary hover:bg-lol-hover"
            }`}
          >
            {role}
          </button>
        ))}
      </div>

      {/* Virtualized Champion Grid */}
      <div
        ref={parentRef}
        className="flex-1 overflow-y-auto"
        style={{ maxHeight: "400px" }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = rows[virtualRow.index];
            return (
              <div
                key={virtualRow.index}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="grid grid-cols-6 gap-0.5"
              >
                {row.map((champion) => {
                  const isUnavailable = unavailable.has(champion);
                  const isFearlessBlocked = fearlessBlockedSet.has(champion);
                  const fearlessInfo = fearlessBlocked[champion];
                  const isDisabled = disabled || isUnavailable || isFearlessBlocked;

                  return (
                    <button
                      key={champion}
                      onClick={() => !isDisabled && onSelect(champion)}
                      disabled={isDisabled}
                      className={`relative rounded overflow-hidden transition-all ${
                        isDisabled
                          ? "opacity-40 cursor-not-allowed"
                          : "hover:ring-2 hover:ring-gold-bright cursor-pointer hover:scale-105"
                      }`}
                      title={
                        isFearlessBlocked && fearlessInfo
                          ? `${champion} - Used in Game ${fearlessInfo.game} by ${fearlessInfo.team === "blue" ? "Blue" : "Red"}`
                          : isUnavailable
                            ? `${champion} - Unavailable`
                            : champion
                      }
                    >
                      <ChampionPortrait
                        championName={champion}
                        size="sm"
                        state={isUnavailable || isFearlessBlocked ? "banned" : "picked"}
                      />
                      {(isUnavailable || isFearlessBlocked) && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                          <span className="text-red-team text-2xl font-bold">✕</span>
                        </div>
                      )}
                      {isFearlessBlocked && (
                        <div className="absolute top-0 right-0 bg-danger text-white text-[8px] px-0.5 rounded-bl">
                          G{fearlessInfo?.game}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Status footer */}
      <div className="mt-2 text-center text-xs text-text-tertiary">
        {disabled ? "Waiting for your turn..." : `${filteredChampions.length} champions`}
      </div>
    </div>
  );
}
```

**Step 3: Verify visually**

Run: `cd deepdraft && npm run dev`

Test:
- Role filter buttons now filter champions
- Grid scrolls smoothly with virtualization
- No performance issues with 162 champions

**Step 4: Commit**

```bash
git add deepdraft/package.json deepdraft/package-lock.json deepdraft/src/components/ChampionPool/index.tsx
git commit -m "feat(frontend): virtualized champion grid with role filtering"
```

---

## Task 5: Enhanced RecommendationCard with Score Breakdown

**Files:**
- Modify: `deepdraft/src/components/SimulatorView/index.tsx:64-140`

**Step 1: Create helper to get top 3 factors**

Add at top of SimulatorView file (after imports):

```typescript
// Helper to get top 3 scoring factors with labels
function getTopFactors(components: Record<string, number>): Array<{ name: string; value: number; label: string }> {
  const factorLabels: Record<string, string> = {
    meta: "Meta Strength",
    proficiency: "Player Proficiency",
    matchup: "Lane Matchup",
    counter: "Counter Potential",
    synergy: "Team Synergy",
  };

  return Object.entries(components)
    .map(([name, value]) => ({ name, value, label: factorLabels[name] || name }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 3);
}

// Helper to find player for a role
function getPlayerForRole(team: TeamContext, role: string): string | null {
  const player = team.players.find(p => p.role === role);
  return player?.name ?? null;
}
```

**Step 2: Rewrite RecommendationCard in SimulatorView**

Replace the RecommendationCard function (lines ~64-140):

```typescript
function RecommendationCard({
  recommendation,
  isTopPick,
  onClick,
  ourTeam,
}: {
  recommendation: SimulatorRecommendation;
  isTopPick?: boolean;
  onClick: (champion: string) => void;
  ourTeam: TeamContext;
}) {
  const championName = recommendation.champion_name;
  const reasons = recommendation.reasons;

  // Determine score/priority and player info
  let displayScore: number;
  let displayLabel: string;
  let playerInfo: string | null = null;
  let topFactors: Array<{ name: string; value: number; label: string }> = [];

  if (isPickRecommendation(recommendation)) {
    displayScore = recommendation.score;
    displayLabel = `${Math.round(displayScore * 100)}%`;

    // Get player for suggested role
    const playerName = getPlayerForRole(ourTeam, recommendation.suggested_role);
    playerInfo = playerName
      ? `For: ${playerName} (${recommendation.suggested_role})`
      : `For: ${recommendation.suggested_role}`;

    // Get top 3 factors
    topFactors = getTopFactors(recommendation.components);
  } else if (isBanRecommendation(recommendation)) {
    displayScore = recommendation.priority;
    displayLabel = `${Math.round(displayScore * 100)}%`;
    playerInfo = recommendation.target_player
      ? `Target: ${recommendation.target_player}`
      : null;
  } else {
    displayScore = 0.5;
    displayLabel = "N/A";
  }

  const scoreColor =
    displayScore >= 0.7 ? "text-success" :
    displayScore >= 0.5 ? "text-warning" : "text-danger";

  const cardBorder = isTopPick
    ? "border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)]"
    : "border-gold-dim/50";

  return (
    <button
      onClick={() => onClick(championName)}
      className={`
        bg-lol-light rounded-lg p-3 border ${cardBorder}
        transition-all duration-200
        hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
        text-left w-full
      `}
    >
      {/* Header with champion and player info */}
      <div className="flex items-center gap-3 mb-2">
        <ChampionPortrait
          championName={championName}
          state="picked"
          size="md"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-sm uppercase text-gold-bright truncate">
              {championName}
            </h3>
            <span className={`text-sm font-bold ${scoreColor} shrink-0`}>
              {displayLabel}
            </span>
          </div>
          {playerInfo && (
            <div className="text-xs text-magic mt-0.5">
              {playerInfo}
            </div>
          )}
        </div>
      </div>

      {/* Top Factors (only for pick recommendations) */}
      {topFactors.length > 0 && (
        <div className="border-t border-gold-dim/30 pt-2 mb-2">
          <div className="text-xs text-text-tertiary mb-1">Top Factors:</div>
          <div className="space-y-1">
            {topFactors.map((factor) => (
              <div key={factor.name} className="flex items-center gap-2 text-xs">
                <span className="text-gold">▸</span>
                <span className="text-text-secondary">{factor.label}:</span>
                <span className={`font-mono ${
                  factor.value >= 0.7 ? "text-success" :
                  factor.value >= 0.5 ? "text-warning" : "text-danger"
                }`}>
                  {factor.value.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reasons */}
      {reasons.length > 0 && (
        <div className="text-xs text-text-secondary space-y-0.5">
          {reasons.slice(0, 2).map((reason, i) => (
            <div key={i} className="flex items-start gap-1">
              <span className="text-gold-dim">•</span>
              <span className="truncate">{reason}</span>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}
```

**Step 3: Update RecommendationCard usage to pass ourTeam**

Find where RecommendationCard is rendered (around line 258) and add ourTeam prop:

```typescript
// In the recommendations rendering section, change from:
{recommendations.slice(0, 5).map((rec, i) => (
  <RecommendationCard
    key={rec.champion_name}
    recommendation={rec}
    isTopPick={i === 0}
    onClick={onChampionSelect}
  />
))}

// To:
{recommendations.slice(0, 5).map((rec, i) => (
  <RecommendationCard
    key={rec.champion_name}
    recommendation={rec}
    isTopPick={i === 0}
    onClick={onChampionSelect}
    ourTeam={coachingSide === "blue" ? blueTeam : redTeam}
  />
))}
```

**Step 4: Verify visually**

Run: `cd deepdraft && npm run dev`

Test in Simulator mode:
- Pick recommendations show "For: PlayerName (ROLE)"
- Pick recommendations show top 3 factors with scores
- Ban recommendations show "Target: PlayerName"

**Step 5: Commit**

```bash
git add deepdraft/src/components/SimulatorView/index.tsx
git commit -m "feat(frontend): enhanced recommendation cards with score breakdown and player labels"
```

---

## Task 6: Create InsightsLog Component for Replay

**Files:**
- Create: `deepdraft/src/components/InsightsLog/index.tsx`

**Step 1: Create the InsightsLog component**

Create `deepdraft/src/components/InsightsLog/index.tsx`:

```typescript
// deepdraft/src/components/InsightsLog/index.tsx
import { useEffect, useRef } from "react";
import type { Recommendations, DraftAction } from "../../types";

interface InsightEntry {
  action: DraftAction;
  recommendations: Recommendations;
}

interface InsightsLogProps {
  entries: InsightEntry[];
  isLive: boolean;
}

export function InsightsLog({ entries, isLive }: InsightsLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries.length]);

  if (entries.length === 0) {
    return (
      <div className="bg-lol-dark rounded-lg p-6">
        <div className="text-center text-text-tertiary py-8">
          Insights will appear as the draft progresses...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          Draft Insights
        </h2>
        {isLive && (
          <span className="text-xs text-magic animate-pulse">● LIVE</span>
        )}
      </div>

      {/* Scrollable log */}
      <div
        ref={scrollRef}
        className="space-y-3 max-h-[500px] overflow-y-auto pr-2"
      >
        {entries.map((entry, idx) => {
          const isLatest = idx === entries.length - 1;
          const isBan = entry.action.action_type === "ban";
          const teamColor = entry.action.team_side === "blue" ? "blue-team" : "red-team";
          const teamLabel = entry.action.team_side === "blue" ? "Blue" : "Red";

          // Get recommendations based on action type
          const recs = isBan
            ? entry.recommendations.bans
            : entry.recommendations.picks;
          const top3 = recs.slice(0, 3);

          // Calculate action number within type
          const actionNum = isBan
            ? Math.ceil(entry.action.sequence / 2) <= 3
              ? Math.ceil((entry.action.sequence + 1) / 2)
              : Math.ceil((entry.action.sequence - 5) / 2)
            : entry.action.sequence <= 6
              ? entry.action.sequence - 6
              : entry.action.sequence - 12;

          const phaseNum = entry.action.sequence <= 6 ? 1 :
                          entry.action.sequence <= 12 ? 1 :
                          entry.action.sequence <= 16 ? 2 : 2;

          return (
            <div
              key={entry.action.sequence}
              className={`
                rounded-lg border p-3
                ${isLatest && isLive
                  ? "border-magic bg-magic/5"
                  : `border-${teamColor}/30 bg-lol-light/50`
                }
              `}
            >
              {/* Entry header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded bg-${teamColor}/20 text-${teamColor}`}>
                    {teamLabel}
                  </span>
                  <span className="text-sm text-text-primary font-medium">
                    {isBan ? "Ban" : "Pick"} #{actionNum}
                  </span>
                </div>
                {isLatest && isLive && (
                  <span className="text-xs bg-magic/20 text-magic px-2 py-0.5 rounded">
                    LIVE
                  </span>
                )}
              </div>

              {/* What actually happened */}
              <div className="text-xs text-text-tertiary mb-2">
                Actual: <span className="text-gold-bright font-medium">{entry.action.champion_name}</span>
              </div>

              {/* Top 3 recommendations */}
              <div className="space-y-1.5">
                {top3.map((rec, i) => {
                  const score = "priority" in rec ? rec.priority : ("confidence" in rec ? rec.confidence : 0);
                  const scorePercent = Math.round(score * 100);
                  const isMatch = rec.champion_name === entry.action.champion_name;

                  return (
                    <div
                      key={rec.champion_name}
                      className={`text-xs ${isMatch ? "text-success" : "text-text-secondary"}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-gold-dim w-4">{i + 1}.</span>
                        <span className={`font-medium ${isMatch ? "text-success" : "text-text-primary"}`}>
                          {rec.champion_name}
                        </span>
                        <span className="text-text-tertiary">({scorePercent}%)</span>
                        {isMatch && <span className="text-success">✓</span>}
                      </div>
                      {rec.reasons[0] && (
                        <div className="ml-6 text-text-tertiary truncate">
                          {rec.reasons[0]}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

**Step 2: Export from index**

Create `deepdraft/src/components/InsightsLog/index.ts` (barrel export) or ensure the component is exported properly.

**Step 3: Commit**

```bash
git add deepdraft/src/components/InsightsLog/
git commit -m "feat(frontend): create InsightsLog component for replay mode"
```

---

## Task 7: Update Replay Hook with Recommendation History

**Files:**
- Modify: `deepdraft/src/hooks/useReplaySession.ts`

**Step 1: Add recommendationHistory to state**

Update `deepdraft/src/hooks/useReplaySession.ts`:

```typescript
// Add to imports at top:
import type {
  TeamContext,
  DraftState,
  Recommendations,
  WebSocketMessage,
  DraftAction,
} from "../types";

// Define InsightEntry type
interface InsightEntry {
  action: DraftAction;
  recommendations: Recommendations;
}

// Update ReplaySessionState interface (around line 12):
interface ReplaySessionState {
  status: SessionStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
  recommendations: Recommendations | null;
  lastAction: DraftAction | null;
  actionHistory: DraftAction[];
  recommendationHistory: InsightEntry[];  // ADD THIS LINE
  totalActions: number;
  patch: string | null;
  error: string | null;
}

// Update initial state (around line 31):
const [state, setState] = useState<ReplaySessionState>({
  status: "idle",
  sessionId: null,
  blueTeam: null,
  redTeam: null,
  draftState: null,
  recommendations: null,
  lastAction: null,
  actionHistory: [],
  recommendationHistory: [],  // ADD THIS LINE
  totalActions: 0,
  patch: null,
  error: null,
});

// Update the draft_action case in ws.onmessage (around line 95):
case "draft_action":
  setState(prev => ({
    ...prev,
    draftState: msg.draft_state,
    recommendations: msg.recommendations,
    lastAction: msg.action,
    actionHistory: [...prev.actionHistory, msg.action],
    recommendationHistory: [...prev.recommendationHistory, {
      action: msg.action,
      recommendations: msg.recommendations,
    }],
  }));
  break;

// Update stopReplay to reset recommendationHistory (around line 141):
setState({
  status: "idle",
  sessionId: null,
  blueTeam: null,
  redTeam: null,
  draftState: null,
  recommendations: null,
  lastAction: null,
  actionHistory: [],
  recommendationHistory: [],  // ADD THIS LINE
  totalActions: 0,
  patch: null,
  error: null,
});

// Update default delay_seconds in startReplay function call (around line 64):
// Change:
body: JSON.stringify({
  series_id: seriesId,
  game_number: gameNumber,
  speed,
  delay_seconds: delaySeconds,
}),

// The default parameter should already be 3.0, change to 5.0:
const startReplay = useCallback(async (
  seriesId: string,
  gameNumber: number,
  speed: number = 1.0,
  delaySeconds: number = 5.0,  // CHANGE FROM 3.0 TO 5.0
) => {
```

**Step 2: Export InsightEntry type**

Add to `deepdraft/src/types/index.ts`:

```typescript
// At the end of the file, add:
export interface InsightEntry {
  action: DraftAction;
  recommendations: Recommendations;
}
```

**Step 3: Update hook to use exported type**

In `useReplaySession.ts`, update the import:

```typescript
import type {
  TeamContext,
  DraftState,
  Recommendations,
  WebSocketMessage,
  DraftAction,
  InsightEntry,  // ADD THIS
} from "../types";
```

And remove the local InsightEntry interface definition.

**Step 4: Commit**

```bash
git add deepdraft/src/hooks/useReplaySession.ts deepdraft/src/types/index.ts
git commit -m "feat(frontend): add recommendation history to replay hook"
```

---

## Task 8: Update RecommendationPanel to Use InsightsLog

**Files:**
- Modify: `deepdraft/src/components/RecommendationPanel/index.tsx`
- Modify: `deepdraft/src/App.tsx`

**Step 1: Rewrite RecommendationPanel for replay mode**

Replace `deepdraft/src/components/RecommendationPanel/index.tsx`:

```typescript
// deepdraft/src/components/RecommendationPanel/index.tsx
import { InsightsLog } from "../InsightsLog";
import type { InsightEntry } from "../../types";

interface RecommendationPanelProps {
  recommendationHistory: InsightEntry[];
  isLive: boolean;
}

export function RecommendationPanel({
  recommendationHistory,
  isLive,
}: RecommendationPanelProps) {
  return (
    <InsightsLog
      entries={recommendationHistory}
      isLive={isLive}
    />
  );
}
```

**Step 2: Update App.tsx to pass new props**

In `deepdraft/src/App.tsx`, update the RecommendationPanel usage (around line 106):

```typescript
// Change from:
<RecommendationPanel
  recommendations={replay.recommendations}
  nextAction={replay.draftState?.next_action ?? null}
/>

// To:
<RecommendationPanel
  recommendationHistory={replay.recommendationHistory}
  isLive={replay.status === "playing"}
/>
```

**Step 3: Verify visually**

Run: `cd deepdraft && npm run dev`

Test in Replay mode:
- Start a replay
- Verify insights log appears and accumulates entries
- Verify auto-scroll works
- Verify "LIVE" badge on latest entry

**Step 4: Commit**

```bash
git add deepdraft/src/components/RecommendationPanel/index.tsx deepdraft/src/App.tsx
git commit -m "feat(frontend): integrate InsightsLog into replay mode"
```

---

## Task 9: Create DraftCompletePanel with Scoring

**Files:**
- Create: `deepdraft/src/components/DraftCompletePanel/index.tsx`

**Step 1: Create the DraftCompletePanel component**

Create `deepdraft/src/components/DraftCompletePanel/index.tsx`:

```typescript
// deepdraft/src/components/DraftCompletePanel/index.tsx
import type { TeamContext, TeamEvaluation } from "../../types";

interface DraftCompletePanelProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  evaluation: TeamEvaluation | null;
  onSelectWinner: (winner: "blue" | "red") => void;
  isRecordingWinner: boolean;
}

export function DraftCompletePanel({
  blueTeam,
  redTeam,
  evaluation,
  onSelectWinner,
  isRecordingWinner,
}: DraftCompletePanelProps) {
  const blueScore = evaluation?.our_evaluation?.composition_score ?? 0;
  const redScore = evaluation?.enemy_evaluation?.composition_score ?? 0;
  const bluePoints = Math.round(blueScore * 100);
  const redPoints = Math.round(redScore * 100);

  const blueStrength = evaluation?.our_evaluation?.strengths?.[0] ?? "Balanced composition";
  const redStrength = evaluation?.enemy_evaluation?.strengths?.[0] ?? "Balanced composition";

  const matchupDesc = evaluation?.matchup_description ?? "Even matchup";

  return (
    <div className="bg-gradient-to-r from-lol-dark via-lol-medium to-lol-dark rounded-lg p-6 border border-gold-dim/50">
      {/* Header */}
      <div className="text-center mb-4">
        <h2 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
          Draft Complete
        </h2>
        <p className="text-sm text-text-tertiary mt-1">{matchupDesc}</p>
      </div>

      {/* Score comparison */}
      <div className="flex items-stretch justify-center gap-4 mb-6">
        {/* Blue team card */}
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

        {/* VS divider */}
        <div className="flex items-center">
          <span className="text-gold-dim font-bold text-lg">VS</span>
        </div>

        {/* Red team card */}
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

      {/* Winner selection */}
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
  );
}
```

**Step 2: Commit**

```bash
git add deepdraft/src/components/DraftCompletePanel/
git commit -m "feat(frontend): create DraftCompletePanel component with scoring"
```

---

## Task 10: Update App.tsx for Inline Draft Completion

**Files:**
- Modify: `deepdraft/src/App.tsx`

**Step 1: Import DraftCompletePanel**

Add import at top of `deepdraft/src/App.tsx`:

```typescript
import { DraftCompletePanel } from "./components/DraftCompletePanel";
```

**Step 2: Show SimulatorView with DraftCompletePanel when game_complete**

Replace the `simulator.status === "game_complete"` section (around lines 144-190):

```typescript
{/* Show drafting view OR game complete with panel */}
{(simulator.status === "drafting" || simulator.status === "game_complete") &&
  simulator.blueTeam && simulator.redTeam && simulator.draftState && (
  <>
    <SimulatorView
      blueTeam={simulator.blueTeam}
      redTeam={simulator.redTeam}
      coachingSide={simulator.coachingSide!}
      draftState={simulator.draftState}
      recommendations={simulator.recommendations}
      isOurTurn={simulator.isOurTurn}
      isEnemyThinking={simulator.isEnemyThinking}
      gameNumber={simulator.gameNumber}
      seriesScore={simulator.seriesStatus ? [simulator.seriesStatus.blue_wins, simulator.seriesStatus.red_wins] : [0, 0]}
      fearlessBlocked={simulator.fearlessBlocked}
      draftMode={simulator.draftMode}
      onChampionSelect={simulator.submitAction}
    />

    {/* Draft Complete Panel - shown when game is complete */}
    {simulator.status === "game_complete" && (
      <div className="mt-4">
        {!simulator.seriesStatus?.games_played ||
         simulator.seriesStatus.games_played < simulator.gameNumber ? (
          <DraftCompletePanel
            blueTeam={simulator.blueTeam}
            redTeam={simulator.redTeam}
            evaluation={simulator.teamEvaluation}
            onSelectWinner={simulator.recordWinner}
            isRecordingWinner={simulator.isRecordingWinner}
          />
        ) : (
          /* Winner recorded, show continue button */
          <div className="bg-lol-dark rounded-lg p-6 text-center">
            <div className="text-lg text-text-primary mb-4">
              <span className="text-blue-team">{simulator.blueTeam.name}</span>
              <span className="mx-4 text-gold-bright font-bold">
                {simulator.seriesStatus?.blue_wins} - {simulator.seriesStatus?.red_wins}
              </span>
              <span className="text-red-team">{simulator.redTeam.name}</span>
            </div>
            <button
              onClick={() => simulator.nextGame()}
              className="px-6 py-3 bg-magic text-lol-darkest rounded-lg font-semibold hover:bg-magic-bright transition-colors"
            >
              Continue to Game {simulator.gameNumber + 1}
            </button>
          </div>
        )}
      </div>
    )}
  </>
)}
```

**Step 3: Remove the old standalone game_complete section**

Delete the old `{simulator.status === "game_complete" && (...)}` block that was there before (the one with the centered "Draft Complete!" heading).

**Step 4: Verify visually**

Run: `cd deepdraft && npm run dev`

Test:
- Complete a draft in Simulator mode
- Verify the draft view stays visible
- Verify DraftCompletePanel appears below with scores
- Verify "Who won?" buttons work
- Verify transition to next game works

**Step 5: Commit**

```bash
git add deepdraft/src/App.tsx
git commit -m "feat(frontend): show draft completion inline with scoring panel"
```

---

## Final Verification

**Step 1: Run all backend tests**

```bash
cd backend && uv run pytest tests/ -v
```

Expected: All tests pass

**Step 2: Run frontend type check and lint**

```bash
cd deepdraft && npx tsc --noEmit && npm run lint
```

Expected: No errors

**Step 3: Manual testing checklist**

- [ ] Simulator: Role filter buttons work
- [ ] Simulator: Champion grid is virtualized (smooth scroll, fixed height)
- [ ] Simulator: Icons are properly sized (no excess tile space)
- [ ] Simulator: Pick recommendations show "For: Player (ROLE)"
- [ ] Simulator: Pick recommendations show top 3 factors with scores
- [ ] Simulator: Ban recommendations show "Target: Player"
- [ ] Simulator: Recommendations don't include filled roles
- [ ] Simulator: Draft completion shows inline with scoring panel
- [ ] Replay: Insights log accumulates all recommendations
- [ ] Replay: Latest entry shows "LIVE" badge
- [ ] Replay: Auto-scrolls to bottom

**Step 4: Final commit if any cleanup needed**

```bash
git status
# If clean, proceed. If changes, review and commit appropriately.
```
