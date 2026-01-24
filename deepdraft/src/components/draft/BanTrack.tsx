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
