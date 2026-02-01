// frontend/src/components/draft/TeamPanel.tsx
import { useMemo } from "react";
import { ChampionPortrait } from "../shared";
import type { TeamContext, Team, FinalizedPick, Player } from "../../types";
import { getTeamLogoUrl, getTeamInitials } from "../../utils/teamLogos";
import { getTeamAbbreviation } from "../../data/teamAbbreviations";

interface TeamPanelProps {
  team: TeamContext | null;
  picks: string[];
  side: Team;
  isActive: boolean;
  currentPickIndex?: number; // Which slot is currently picking (0-4)
  picksWithRoles?: FinalizedPick[]; // Optional finalized role assignments
  players?: Player[]; // Optional player roster for displaying names
}

const ROLE_ORDER = ["TOP", "JNG", "MID", "ADC", "SUP"] as const;

// Map backend role names to display role names
const ROLE_DISPLAY_MAP: Record<string, typeof ROLE_ORDER[number]> = {
  top: "TOP",
  jungle: "JNG",
  mid: "MID",
  bot: "ADC",
  support: "SUP",
};

function TeamLogo({ team, borderClass, textClass }: {
  team: TeamContext | null;
  borderClass: string;
  textClass: string;
}) {
  const logoUrl = team?.id ? getTeamLogoUrl(team.id) : null;

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={`${team?.name} logo`}
        className={`w-10 h-10 rounded bg-lol-dark border ${borderClass} object-contain`}
      />
    );
  }

  return (
    <div className={`w-10 h-10 rounded bg-lol-dark flex items-center justify-center border ${borderClass}`}>
      <span className={`font-bold text-sm ${textClass}`}>
        {team?.name ? getTeamInitials(team.name) : "??"}
      </span>
    </div>
  );
}

export function TeamPanel({
  team,
  picks,
  side,
  isActive,
  currentPickIndex,
  picksWithRoles,
  players,
}: TeamPanelProps) {
  // When finalized roles are available, reorder picks to display in correct role slots
  const orderedPicks = useMemo(() => {
    if (!picksWithRoles || picksWithRoles.length === 0) {
      // No finalized roles, use picks in order
      return picks;
    }

    // Create a map of role -> champion from finalized assignments
    const roleToChampion: Record<string, string> = {};
    for (const fp of picksWithRoles) {
      const displayRole = ROLE_DISPLAY_MAP[fp.role];
      if (displayRole) {
        roleToChampion[displayRole] = fp.champion;
      }
    }

    // Build ordered picks array matching ROLE_ORDER
    return ROLE_ORDER.map((role) => roleToChampion[role] || null);
  }, [picks, picksWithRoles]);

  // Create a map of display role -> player name for showing player names next to champions
  const roleToPlayer = useMemo(() => {
    const map: Record<string, string> = {};
    if (players) {
      for (const player of players) {
        // Player.role is already in display format (TOP, JNG, MID, ADC, SUP)
        map[player.role] = player.name;
      }
    }
    return map;
  }, [players]);

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
        <TeamLogo team={team} borderClass={sideColors.border} textClass={sideColors.text} />
        <div>
          <h2 className={`font-semibold uppercase tracking-wide ${sideColors.text}`} title={team?.name}>
            {team?.name ? getTeamAbbreviation(team.name) : "???"}
          </h2>
          <span className="text-xs text-text-tertiary uppercase">
            {side} side
          </span>
        </div>
      </div>

      {/* Pick Slots - horizontal on mobile, vertical on desktop */}
      <div className="flex gap-1 sm:gap-2 lg:flex-col lg:gap-0 lg:space-y-3">
        {ROLE_ORDER.map((role, index) => {
          const pick = orderedPicks[index] || null;
          const isPicking = currentPickIndex === index;

          return (
            <div
              key={role}
              className={`
                flex flex-col items-center gap-0.5 p-0.5 sm:p-1
                lg:flex-row lg:items-center lg:gap-3 lg:p-2 rounded
                ${isPicking ? "bg-lol-hover" : ""}
                transition-colors duration-200
              `}
            >
              {/* Pick slot number - hidden on mobile */}
              <span className="hidden lg:block w-10 text-xs font-medium text-text-tertiary">
                Pick {index + 1}
              </span>

              {/* Champion portrait - smaller on mobile */}
              <ChampionPortrait
                championName={pick}
                state={pick ? "picked" : isPicking ? "picking" : "empty"}
                team={side}
                className="w-8 h-8 sm:w-10 sm:h-10 lg:w-[66px] lg:h-[66px] 2xl:w-[88px] 2xl:h-[88px] shrink-0"
              />

              {/* Champion name and player - hidden on mobile, shown on desktop */}
              {pick && (
                <div className="hidden lg:flex flex-col flex-1 min-w-0">
                  <span className="text-sm text-gold-bright truncate">
                    {pick}
                  </span>
                  {roleToPlayer[role] && (
                    <span className="text-xs text-text-secondary truncate">
                      {roleToPlayer[role]}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
