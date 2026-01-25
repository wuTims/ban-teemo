// deepdraft/src/components/draft/TeamPanel.tsx
import { ChampionPortrait } from "../shared";
import type { TeamContext, Team } from "../../types";
import { getTeamLogoUrl, getTeamInitials } from "../../utils/teamLogos";

interface TeamPanelProps {
  team: TeamContext | null;
  picks: string[];
  side: Team;
  isActive: boolean;
  currentPickIndex?: number; // Which slot is currently picking (0-4)
}

const ROLE_ORDER = ["TOP", "JNG", "MID", "ADC", "SUP"] as const;

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
        <TeamLogo team={team} borderClass={sideColors.border} textClass={sideColors.text} />
        <div>
          <h2 className={`font-semibold uppercase tracking-wide ${sideColors.text}`}>
            {team?.name || "Unknown Team"}
          </h2>
          <span className="text-xs text-text-tertiary uppercase">
            {side} side
          </span>
        </div>
      </div>

      {/* Pick Slots (role display temporarily disabled pending data refetch) */}
      <div className="space-y-3">
        {ROLE_ORDER.map((role, index) => {
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
              {/* Pick slot number */}
              <span className="w-10 text-xs font-medium text-text-tertiary">
                Pick {index + 1}
              </span>

              {/* Champion portrait */}
              <ChampionPortrait
                championName={pick}
                state={pick ? "picked" : isPicking ? "picking" : "empty"}
                team={side}
                size="sm"
              />

              {/* Champion name if picked */}
              {pick && (
                <span className="flex-1 text-sm text-gold-bright truncate">
                  {pick}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
