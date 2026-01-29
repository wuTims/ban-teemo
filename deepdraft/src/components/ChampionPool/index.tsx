// deepdraft/src/components/ChampionPool/index.tsx
import { useState, useMemo } from "react";
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

const ROLES = ["All", "Top", "Jungle", "Mid", "Bot", "Support"] as const;

// Map display names to backend role codes
const ROLE_MAP: Record<string, string> = {
  "All": "All",
  "Top": "TOP",
  "Jungle": "JNG",
  "Mid": "MID",
  "Bot": "ADC",
  "Support": "SUP",
};

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

  // Track which champions pass the filter (but render all to keep images mounted)
  const filteredSet = useMemo(() => {
    let filtered = allChampions;

    // Search filter
    if (search) {
      const query = search.toLowerCase();
      filtered = filtered.filter((c) => c.toLowerCase().includes(query));
    }

    // Role filter
    const roleKey = ROLE_MAP[selectedRole];
    if (roleKey && roleKey !== "All") {
      filtered = filtered.filter((c) => championPlaysRole(c, roleKey));
    }

    return new Set(filtered);
  }, [allChampions, search, selectedRole]);

  // Sort all champions once
  const sortedChampions = useMemo(() => [...allChampions].sort(), [allChampions]);

  return (
    <div className="bg-lol-dark rounded-lg p-4 flex flex-col h-[400px] lg:h-[550px] xl:h-[650px]">
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

      {/* Champion Grid - renders all champions, hides filtered ones to prevent flash */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden scrollbar-none p-1 lg:p-1.5">
        <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-[repeat(auto-fill,minmax(88px,1fr))] 2xl:grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-1 lg:gap-2 content-start auto-rows-max">
          {sortedChampions.map((champion) => {
            const isVisible = filteredSet.has(champion);
            const isUnavailable = unavailable.has(champion);
            const isFearlessBlocked = fearlessBlockedSet.has(champion);
            const fearlessInfo = fearlessBlocked[champion];
            const isDisabled = disabled || isUnavailable || isFearlessBlocked;

            return (
              <button
                key={champion}
                onClick={() => !isDisabled && onSelect(champion)}
                disabled={isDisabled || !isVisible}
                className={`appearance-none bg-transparent p-0 border-0 focus:outline-none relative w-full aspect-square rounded overflow-hidden ${
                  !isVisible
                    ? "hidden"
                    : isDisabled
                      ? "opacity-40 cursor-not-allowed"
                      : "group cursor-pointer transition-shadow hover:ring-2 hover:ring-gold-bright"
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
                  state={isUnavailable || isFearlessBlocked ? "banned" : "picked"}
                  className="w-full h-full"
                  imageClassName="transition-transform duration-200 ease-out group-hover:scale-[1.06]"
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
      </div>

      {/* Status footer */}
      <div className="mt-2 text-center text-xs text-text-tertiary">
        {disabled ? "Waiting for your turn..." : `${filteredSet.size} champions`}
      </div>
    </div>
  );
}
