// frontend/src/components/SimulatorView/index.tsx
import { useMemo, useState, useCallback } from "react";
import { PhaseIndicator, TeamPanel, BanRow } from "../draft";
import { ChampionPool } from "../ChampionPool";
import { RoleRecommendationPanel } from "../recommendations/RoleRecommendationPanel";
import { InsightPanel } from "../recommendations/InsightPanel";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import { getAllChampionNames } from "../../utils/dataDragon";
import type {
  TeamContext,
  DraftState,
  SimulatorRecommendation,
  SimulatorPickRecommendation,
  SimulatorBanRecommendation,
  FearlessBlocked,
  DraftMode,
  RoleGroupedRecommendations,
  FinalizedPick,
  LLMInsightsResponse,
} from "../../types";

// Champion list derived from Data Dragon mapping
const ALL_CHAMPIONS = getAllChampionNames();

// Type guard to differentiate recommendation types
function isPickRecommendation(rec: SimulatorRecommendation): rec is SimulatorPickRecommendation {
  return "score" in rec && "suggested_role" in rec;
}

function isBanRecommendation(rec: SimulatorRecommendation): rec is SimulatorBanRecommendation {
  return "priority" in rec && "target_player" in rec;
}

// Helper to get top 3 scoring factors with labels
function getTopFactors(components: Record<string, number>): Array<{ name: string; value: number; label: string }> {
  const factorLabels: Record<string, string> = {
    meta: "Meta",
    proficiency: "Proficiency",
    matchup: "Matchup",
    counter: "Counter",
    synergy: "Synergy",
    archetype: "Archetype",
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

interface SimulatorViewProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  coachingSide: "blue" | "red";
  draftState: DraftState;
  recommendations: SimulatorRecommendation[] | null;
  roleGroupedRecommendations: RoleGroupedRecommendations | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesScore: [number, number];
  fearlessBlocked: FearlessBlocked;
  draftMode: DraftMode;
  onChampionSelect: (champion: string) => void;
  blueCompWithRoles?: FinalizedPick[] | null;
  redCompWithRoles?: FinalizedPick[] | null;
  llmLoading?: boolean;
  llmInsight?: LLMInsightsResponse | null;
}

function RecommendationCard({
  recommendation,
  isTopPick,
  onClick,
  ourTeam,
  isExpanded,
  onToggleExpand,
}: {
  recommendation: SimulatorRecommendation;
  isTopPick?: boolean;
  onClick: (champion: string) => void;
  ourTeam: TeamContext;
  isExpanded: boolean;
  onToggleExpand: () => void;
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
      ? `${playerName} (${recommendation.suggested_role})`
      : recommendation.suggested_role;

    // Get top 3 factors
    topFactors = getTopFactors(recommendation.components);
  } else if (isBanRecommendation(recommendation)) {
    displayScore = recommendation.priority;
    displayLabel = `${Math.round(displayScore * 100)}%`;
    playerInfo = recommendation.target_player || null;
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
    <div
      className={`
        bg-lol-light rounded-lg border ${cardBorder}
        transition-all duration-200
        hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
        text-left w-full
      `}
    >
      {/* Compact Header - always visible, clickable to select */}
      <button
        onClick={() => onClick(championName)}
        className="w-full p-2 lg:p-3 text-left"
      >
        <div className="flex items-center gap-2 lg:gap-3">
          <ChampionPortrait
            championName={championName}
            state="picked"
            className="w-8 h-8 sm:w-10 sm:h-10 lg:w-11 lg:h-11 2xl:w-[52px] 2xl:h-[52px] shrink-0"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <h3 className="font-semibold text-xs sm:text-sm uppercase text-gold-bright truncate">
                {championName}
              </h3>
              <span className={`text-xs sm:text-sm font-bold ${scoreColor} shrink-0`}>
                {displayLabel}
              </span>
            </div>
            {playerInfo && (
              <div className="text-[10px] sm:text-xs text-magic truncate">
                {playerInfo}
              </div>
            )}
          </div>
        </div>
      </button>

      {/* Expandable Details - toggle is inline, no separate button background */}
      <div className="px-2 lg:px-3 pb-1.5 lg:pb-2">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleExpand();
          }}
          className="text-[10px] text-text-tertiary hover:text-magic transition-colors flex items-center gap-1"
        >
          <span className={`transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`}>▶</span>
          <span>{isExpanded ? "Hide" : "Details"}</span>
        </button>

        {/* Animated container using grid for smooth height transition */}
        <div
          className={`grid transition-[grid-template-rows] duration-200 ease-out ${
            isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
          }`}
        >
          <div className="overflow-hidden">
            <div className="mt-1.5 space-y-1.5">
              {/* Top Factors (only for pick recommendations) */}
              {topFactors.length > 0 && (
                <div className="space-y-0.5">
                  {topFactors.map((factor) => (
                    <div key={factor.name} className="flex items-center gap-2 text-[10px] sm:text-xs">
                      <span className="text-gold-dim">▸</span>
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
              )}

              {/* Reasons */}
              {reasons.length > 0 && (
                <div className="text-[10px] sm:text-xs text-text-secondary space-y-0.5">
                  {reasons.slice(0, 3).map((reason, i) => (
                    <div key={i} className="flex items-start gap-1">
                      <span className="text-gold-dim shrink-0">•</span>
                      <span className="line-clamp-2">{reason}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SimulatorView({
  blueTeam,
  redTeam,
  coachingSide,
  draftState,
  recommendations,
  roleGroupedRecommendations,
  isOurTurn,
  isEnemyThinking,
  gameNumber,
  seriesScore,
  fearlessBlocked,
  draftMode,
  onChampionSelect,
  blueCompWithRoles,
  redCompWithRoles,
  llmLoading = false,
  llmInsight,
}: SimulatorViewProps) {
  // Toggle state for showing role-grouped view (default OFF as it's supplemental)
  const [showRoleGrouped, setShowRoleGrouped] = useState(false);
  // Track which recommendation cards are expanded
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const toggleCardExpand = useCallback((championName: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(championName)) {
        next.delete(championName);
      } else {
        next.add(championName);
      }
      return next;
    });
  }, []);

  const unavailable = useMemo(() => {
    return new Set([
      ...draftState.blue_bans,
      ...draftState.red_bans,
      ...draftState.blue_picks,
      ...draftState.red_picks,
    ]);
  }, [draftState]);

  const fearlessCount = Object.keys(fearlessBlocked).length;
  const isBanPhase = draftState.next_action === "ban";

  return (
    <div className="space-y-2 sm:space-y-3 lg:space-y-4">
      {/* Series Status - responsive */}
      <div className="flex flex-wrap justify-center items-center gap-2 sm:gap-4 text-xs sm:text-sm">
        <span className="text-text-secondary">Game {gameNumber}</span>
        <span className="text-gold-bright font-bold text-center">
          <span className="hidden sm:inline">{blueTeam.name}</span>
          <span className="sm:hidden">{blueTeam.name.slice(0, 3)}</span>
          {" "}{seriesScore[0]} - {seriesScore[1]}{" "}
          <span className="hidden sm:inline">{redTeam.name}</span>
          <span className="sm:hidden">{redTeam.name.slice(0, 3)}</span>
        </span>
        {draftMode === "fearless" && fearlessCount > 0 && (
          <span className="text-danger text-[10px] sm:text-xs">
            Fearless: {fearlessCount}
          </span>
        )}
      </div>

      {/* Phase Indicator */}
      <div className="flex justify-center items-center gap-2 sm:gap-4">
        <PhaseIndicator
          currentPhase={draftState.phase}
          nextTeam={draftState.next_team}
          nextAction={draftState.next_action}
        />
        {isEnemyThinking && (
          <span className="text-text-tertiary animate-pulse text-xs sm:text-sm">
            Enemy thinking...
          </span>
        )}
      </div>

      {/* Main Layout - Stacked on mobile, 3-column on desktop */}
      <div className="flex flex-col gap-2 sm:gap-3 lg:gap-4 lg:grid lg:grid-cols-[180px_1fr_180px] xl:grid-cols-[220px_1fr_220px] lg:items-start">
        {/* Blue Team - does not expand with center */}
        <div
          className={`flex flex-col lg:self-start ${
            coachingSide === "blue" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={blueTeam}
            picks={draftState.blue_picks}
            side="blue"
            isActive={draftState.next_team === "blue" && draftState.next_action === "pick"}
            picksWithRoles={blueCompWithRoles ?? undefined}
          />
          {coachingSide === "blue" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>

        {/* Champion Pool - center, grows to fit */}
        <ChampionPool
          allChampions={ALL_CHAMPIONS}
          unavailable={unavailable}
          fearlessBlocked={fearlessBlocked}
          onSelect={onChampionSelect}
          disabled={!isOurTurn}
        />

        {/* Red Team - does not expand with center */}
        <div
          className={`flex flex-col lg:self-start ${
            coachingSide === "red" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={redTeam}
            picks={draftState.red_picks}
            side="red"
            isActive={draftState.next_team === "red" && draftState.next_action === "pick"}
            picksWithRoles={redCompWithRoles ?? undefined}
          />
          {coachingSide === "red" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>
      </div>

      {/* Ban Row */}
      <BanRow blueBans={draftState.blue_bans} redBans={draftState.red_bans} />

      {/* Recommendations */}
      {isOurTurn && recommendations && recommendations.length > 0 && (
        <div className="bg-lol-dark rounded-lg p-2 sm:p-3 lg:p-4">
          <div className="flex items-center justify-between mb-2 sm:mb-3">
            <h3 className="text-xs sm:text-sm font-semibold uppercase tracking-wide text-gold-bright">
              {isBanPhase ? "Ban" : "Pick"} Recommendations
            </h3>
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Role-Grouped Toggle - only show during pick phase, hide on small screens */}
              {!isBanPhase && roleGroupedRecommendations && (
                <button
                  onClick={() => setShowRoleGrouped(!showRoleGrouped)}
                  className={`
                    hidden sm:block text-xs font-medium px-2 py-0.5 rounded border transition-colors
                    ${showRoleGrouped
                      ? "bg-gold-dim/20 border-gold-dim text-gold"
                      : "bg-transparent border-gold-dim/30 text-text-tertiary hover:text-text-secondary hover:border-gold-dim/50"
                    }
                  `}
                >
                  {showRoleGrouped ? "Hide" : "Show"} By Role
                </button>
              )}
              <span className={`
                text-[10px] sm:text-xs font-medium uppercase px-1.5 sm:px-2 py-0.5 rounded
                ${coachingSide === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
              `}>
                Your Turn
              </span>
            </div>
          </div>
          {/* Responsive grid: 2 columns on mobile, 3 on sm, 5 on lg+ - items-start prevents row height sync */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-2.5 lg:gap-3 items-start">
            {recommendations.slice(0, 5).map((rec, i) => (
              <RecommendationCard
                key={rec.champion_name}
                recommendation={rec}
                isTopPick={i === 0}
                onClick={onChampionSelect}
                ourTeam={coachingSide === "blue" ? blueTeam : redTeam}
                isExpanded={expandedCards.has(rec.champion_name)}
                onToggleExpand={() => toggleCardExpand(rec.champion_name)}
              />
            ))}
          </div>

          {/* Role-Grouped Supplemental Panel */}
          {!isBanPhase && showRoleGrouped && roleGroupedRecommendations && (
            <div className="mt-3 sm:mt-4">
              <RoleRecommendationPanel
                roleGrouped={roleGroupedRecommendations}
                ourTeam={coachingSide === "blue" ? blueTeam : redTeam}
                onChampionClick={onChampionSelect}
              />
            </div>
          )}

          {/* AI Insights Panel */}
          <div className="mt-4">
            <InsightPanel
              insight={llmInsight?.draft_analysis ?? null}
              isLoading={llmLoading}
            />

            {/* Show reranked recommendations if available */}
            {llmInsight?.status === "ready" && llmInsight.reranked && llmInsight.reranked.length > 0 && (
              <div className="mt-3 space-y-2">
                <h4 className="text-sm font-medium text-magic uppercase tracking-wide">
                  AI Reranked Picks
                </h4>
                {llmInsight.reranked.slice(0, 3).map((rec) => (
                  <div
                    key={rec.champion_name}
                    className="bg-lol-dark/50 rounded p-2 border border-magic/20"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-gold-bright font-medium">
                        #{rec.new_rank} {rec.champion_name}
                      </span>
                      <span className="text-xs text-text-tertiary">
                        (was #{rec.original_rank})
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary mt-1">
                      {rec.reasoning}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Waiting indicator when not our turn */}
      {!isOurTurn && !isEnemyThinking && draftState.phase !== "COMPLETE" && (
        <div className="bg-lol-dark rounded-lg p-4 text-center">
          <span className="text-text-tertiary">
            Waiting for {draftState.next_team === "blue" ? blueTeam.name : redTeam.name}...
          </span>
        </div>
      )}
    </div>
  );
}
