// frontend/src/components/draft/BanTrack.tsx
import { ChampionPortrait } from "../shared";
import type { Team } from "../../types";
import { CHAMPION_ICON_SIZE_CLASS } from "../shared";

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
  // Display bans grouped by team (simpler, works regardless of ban order)
  // Each team has up to 5 bans (3 in phase 1, 2 in phase 2)

  const renderBanSlot = (team: Team, index: number) => {
    const bans = team === "blue" ? blueBans : redBans;
    const ban = bans[index] || null;
    const isCurrent = currentBanTeam === team && currentBanIndex === index;

    return (
      <ChampionPortrait
        key={`${team}-${index}`}
        championName={ban}
        state={ban ? "banned" : isCurrent ? "picking" : "empty"}
        team={team}
        className={`${CHAMPION_ICON_SIZE_CLASS} shrink-0`}
      />
    );
  };

  const renderTeamBans = (team: Team, label: string) => {
    const colorClass = team === "blue" ? "text-blue-team" : "text-red-team";
    return (
      <div className="flex items-center gap-3">
        <span className={`text-xs font-medium uppercase w-12 ${colorClass}`}>
          {label}
        </span>
        <div className="flex items-center gap-2">
          {/* Phase 1 bans (indices 0-2) */}
          {[0, 1, 2].map((i) => renderBanSlot(team, i))}
          {/* Divider */}
          <div className="w-px h-8 bg-gold-dim/30 mx-1" />
          {/* Phase 2 bans (indices 3-4) */}
          {[3, 4].map((i) => renderBanSlot(team, i))}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col items-center gap-3">
      <span className="text-xs text-text-tertiary uppercase tracking-wider">
        Bans
      </span>
      {renderTeamBans("blue", "Blue")}
      {renderTeamBans("red", "Red")}
    </div>
  );
}
