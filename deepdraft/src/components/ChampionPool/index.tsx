// deepdraft/src/components/ChampionPool/index.tsx
import { useState, useMemo } from "react";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import type { FearlessBlocked } from "../../types";

interface ChampionPoolProps {
  allChampions: string[];
  unavailable: Set<string>;
  fearlessBlocked: FearlessBlocked;
  onSelect: (champion: string) => void;
  disabled: boolean;
}

const ROLES = ["All", "Top", "Jungle", "Mid", "ADC", "Support"] as const;

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

  const filteredChampions = useMemo(() => {
    let filtered = allChampions;

    if (search) {
      const query = search.toLowerCase();
      filtered = filtered.filter((c) => c.toLowerCase().includes(query));
    }

    // Note: Role filtering would need champion role data
    // For now, just filter by search

    return filtered.sort();
  }, [allChampions, search, selectedRole]);

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

      {/* Champion Grid */}
      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-6 gap-1">
          {filteredChampions.map((champion) => {
            const isUnavailable = unavailable.has(champion);
            const isFearlessBlocked = fearlessBlockedSet.has(champion);
            const fearlessInfo = fearlessBlocked[champion];
            const isDisabled = disabled || isUnavailable || isFearlessBlocked;

            return (
              <button
                key={champion}
                onClick={() => !isDisabled && onSelect(champion)}
                disabled={isDisabled}
                className={`relative aspect-square rounded overflow-hidden transition-all ${
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
      </div>

      {/* Status footer */}
      {disabled && (
        <div className="mt-2 text-center text-xs text-text-tertiary">
          Waiting for your turn...
        </div>
      )}
    </div>
  );
}
