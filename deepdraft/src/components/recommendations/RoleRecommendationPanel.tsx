// deepdraft/src/components/recommendations/RoleRecommendationPanel.tsx
import { useState } from "react";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import type { RoleGroupedRecommendations, SimulatorPickRecommendation, TeamContext } from "../../types";

interface RoleRecommendationPanelProps {
  roleGrouped: RoleGroupedRecommendations;
  ourTeam: TeamContext;
  onChampionClick?: (champion: string) => void;
}

const ROLE_ORDER = ["TOP", "JNG", "MID", "ADC", "SUP"] as const;

const ROLE_DISPLAY_NAMES: Record<string, string> = {
  TOP: "Top",
  JNG: "Jungle",
  MID: "Mid",
  ADC: "Bot",
  SUP: "Support",
};

// Helper to get player for a role
function getPlayerForRole(team: TeamContext, role: string): string | null {
  const player = team.players.find(p => p.role === role);
  return player?.name ?? null;
}

// Helper to get top 3 scoring factors with labels
function getTopFactors(components: Record<string, number>): Array<{ name: string; value: number; label: string }> {
  const factorLabels: Record<string, string> = {
    meta: "Meta",
    proficiency: "Prof",
    matchup: "Match",
    counter: "Cntr",
    synergy: "Syn",
    archetype: "Arch",
  };

  return Object.entries(components)
    .map(([name, value]) => ({ name, value, label: factorLabels[name] || name }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 3);
}

function RolePickCard({
  pick,
  playerName,
  onClick,
}: {
  pick: SimulatorPickRecommendation;
  playerName: string | null;
  onClick?: (champion: string) => void;
}) {
  const topFactors = getTopFactors(pick.components);
  const scoreColor =
    pick.score >= 0.7 ? "text-success" :
    pick.score >= 0.5 ? "text-warning" : "text-danger";

  return (
    <button
      onClick={() => onClick?.(pick.champion_name)}
      className="
        bg-lol-darkest/50 rounded p-2 border border-gold-dim/30
        transition-all duration-200
        hover:border-gold-dim hover:bg-lol-darkest
        text-left w-full
      "
    >
      {/* Champion + Score row */}
      <div className="flex items-center gap-2">
        <ChampionPortrait
          championName={pick.champion_name}
          state="picked"
          className="w-8 h-8 shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="text-xs font-medium text-gold truncate">
              {pick.champion_name}
            </span>
            <span className={`text-xs font-bold ${scoreColor} shrink-0`}>
              {Math.round(pick.score * 100)}%
            </span>
          </div>
          {playerName && (
            <div className="text-[10px] text-text-tertiary truncate">
              {playerName}
            </div>
          )}
        </div>
      </div>

      {/* Component breakdown - compact inline format */}
      {topFactors.length > 0 && (
        <div className="mt-1.5 flex gap-1.5 flex-wrap">
          {topFactors.map((factor) => (
            <span
              key={factor.name}
              className={`
                text-[10px] px-1 py-0.5 rounded bg-lol-dark/50
                ${factor.value >= 0.7 ? "text-success/80" :
                  factor.value >= 0.5 ? "text-warning/80" : "text-danger/80"}
              `}
            >
              {factor.label}: {factor.value.toFixed(2)}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

export function RoleRecommendationPanel({
  roleGrouped,
  ourTeam,
  onChampionClick,
}: RoleRecommendationPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Check if there are any picks to show
  const hasAnyPicks = ROLE_ORDER.some(
    (role) => (roleGrouped.by_role[role] || []).length > 0
  );

  if (!hasAnyPicks) {
    return null;
  }

  return (
    <div className="
      bg-lol-dark/60 rounded-lg border border-gold-dim/20
      transition-all duration-200
    ">
      {/* Header - Collapsible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          w-full flex items-center justify-between p-3
          hover:bg-lol-dark/80 rounded-t-lg transition-colors
        "
      >
        <div className="flex items-center gap-2">
          <span className="
            text-[10px] uppercase tracking-wider font-medium
            px-1.5 py-0.5 rounded bg-gold-dim/20 text-text-tertiary
          ">
            Alternative View
          </span>
          <h4 className="text-sm font-medium text-text-secondary">
            Top Picks by Role
          </h4>
        </div>
        <span className={`
          text-text-tertiary transition-transform duration-200
          ${isExpanded ? "rotate-180" : ""}
        `}>
          ▼
        </span>
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-1">
          <div className="grid grid-cols-5 gap-2">
            {ROLE_ORDER.map((role) => {
              const picks = roleGrouped.by_role[role] || [];
              const playerName = getPlayerForRole(ourTeam, role);

              return (
                <div key={role} className="flex flex-col gap-1.5">
                  {/* Role Header */}
                  <div className="text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-gold-dim">
                      {ROLE_DISPLAY_NAMES[role] || role}
                    </span>
                  </div>

                  {/* Pick Cards - Top 2 */}
                  {picks.length > 0 ? (
                    picks.slice(0, 2).map((pick) => (
                      <RolePickCard
                        key={pick.champion_name}
                        pick={pick}
                        playerName={playerName}
                        onClick={onChampionClick}
                      />
                    ))
                  ) : (
                    <div className="
                      text-[10px] text-text-tertiary italic text-center
                      py-4 bg-lol-darkest/30 rounded
                    ">
                      Filled
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default RoleRecommendationPanel;
