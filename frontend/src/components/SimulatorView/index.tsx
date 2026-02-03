// frontend/src/components/SimulatorView/index.tsx
import { useMemo, useState, useCallback, useEffect } from "react";
import { PhaseIndicator, TeamPanel, ChampionPortrait } from "../shared";
import { SimulatorBanRow, SimulatorInsightPanel } from "../simulator";
import { ChampionPool } from "../ChampionPool";
import { getAllChampionNames } from "../../utils/dataDragon";
import {
  PICK_COMPONENT_LABELS,
  BAN_COMPONENT_LABELS,
  BAN_COMPONENT_ORDER,
} from "../../utils/scoreLabels";
import type {
  TeamContext,
  DraftState,
  SimulatorRecommendation,
  SimulatorPickRecommendation,
  SimulatorBanRecommendation,
  FearlessBlocked,
  DraftMode,
  FinalizedPick,
  LLMInsightsResponse,
} from "../../types";

// Champion list derived from Data Dragon mapping
const ALL_CHAMPIONS = getAllChampionNames();

type ScoreAnchor = { min: number; max: number };

// Simulator display normalization: map 30-70% scores to 0-100% for friendlier colors.
const SCORE_ANCHORS: Record<"ban" | "pick", ScoreAnchor> = {
  ban: { min: 0.30, max: 0.70 },
  pick: { min: 0.30, max: 0.70 },
};

function normalizeScore(rawScore: number, type: "ban" | "pick"): number {
  const { min, max } = SCORE_ANCHORS[type];
  const normalized = (rawScore - min) / (max - min);
  return Math.max(0, Math.min(1, normalized));
}

// Type guard to differentiate recommendation types
function isPickRecommendation(rec: SimulatorRecommendation): rec is SimulatorPickRecommendation {
  return "score" in rec && "suggested_role" in rec;
}

function isBanRecommendation(rec: SimulatorRecommendation): rec is SimulatorBanRecommendation {
  return "priority" in rec && "target_player" in rec;
}

type ScoreBreakdownItem = { key: string; label: string; value: number; weighted?: boolean };

function getPickScoreBreakdown(weightedComponents?: Record<string, number | undefined>): ScoreBreakdownItem[] {
  // Use weighted components for display (same scale as ban components)
  if (!weightedComponents) return [];
  const items: ScoreBreakdownItem[] = [];
  const hasTournament =
    weightedComponents.tournament_priority !== undefined ||
    weightedComponents.tournament_performance !== undefined;

  if (hasTournament) {
    if (weightedComponents.tournament_priority !== undefined) {
      items.push({
        key: "tournament_priority",
        label: PICK_COMPONENT_LABELS.tournament_priority,
        value: weightedComponents.tournament_priority,
        weighted: true,
      });
    }
    if (weightedComponents.tournament_performance !== undefined) {
      items.push({
        key: "tournament_performance",
        label: PICK_COMPONENT_LABELS.tournament_performance,
        value: weightedComponents.tournament_performance,
        weighted: true,
      });
    }
  }

  if (weightedComponents.matchup_counter !== undefined) {
    items.push({
      key: "matchup_counter",
      label: PICK_COMPONENT_LABELS.matchup_counter,
      value: weightedComponents.matchup_counter,
      weighted: true,
    });
  }

  if (weightedComponents.archetype !== undefined) {
    items.push({
      key: "archetype",
      label: PICK_COMPONENT_LABELS.archetype,
      value: weightedComponents.archetype,
      weighted: true,
    });
  }

  if (weightedComponents.synergy !== undefined) {
    items.push({
      key: "synergy",
      label: PICK_COMPONENT_LABELS.synergy,
      value: weightedComponents.synergy,
      weighted: true,
    });
  }

  return items;
}

// Components to hide from the ban score display (still used in scoring, just not surfaced)
const HIDDEN_BAN_COMPONENTS = new Set(["confidence"]);

function getBanScoreBreakdown(components?: Record<string, number | undefined>): ScoreBreakdownItem[] {
  if (!components) return [];
  const items: ScoreBreakdownItem[] = [];
  BAN_COMPONENT_ORDER.forEach((key) => {
    if (HIDDEN_BAN_COMPONENTS.has(key)) return;
    const value = components[key];
    if (typeof value === "number") {
      items.push({
        key,
        label: BAN_COMPONENT_LABELS[key] ?? key,
        value,
        weighted: true,
      });
    }
  });
  return items;
}

function getComponentColor(value: number, weighted: boolean): string {
  if (weighted) {
    return value >= 0.2 ? "text-success" : value >= 0.1 ? "text-warning" : "text-danger";
  }
  return value >= 0.7 ? "text-success" : value >= 0.5 ? "text-warning" : "text-danger";
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
  let rawScore: number;
  let normalizedScore: number;
  let displayLabel: string;
  let playerInfo: string | null = null;
  let breakdownItems: ScoreBreakdownItem[] = [];

  if (isPickRecommendation(recommendation)) {
    rawScore = recommendation.score;
    normalizedScore = normalizeScore(rawScore, "pick");
    displayLabel = `${Math.round(normalizedScore * 100)}%`;

    // Get player for suggested role
    const playerName = getPlayerForRole(ourTeam, recommendation.suggested_role);
    playerInfo = playerName
      ? `${playerName} (${recommendation.suggested_role})`
      : recommendation.suggested_role;

    // Score breakdown - use weighted_components for display (same scale as bans)
    // Fall back to raw components for backwards compatibility
    breakdownItems = getPickScoreBreakdown(recommendation.weighted_components ?? recommendation.components);
  } else if (isBanRecommendation(recommendation)) {
    rawScore = recommendation.priority;
    normalizedScore = normalizeScore(rawScore, "ban");
    displayLabel = `${Math.round(normalizedScore * 100)}%`;
    playerInfo = recommendation.target_player || null;
    breakdownItems = getBanScoreBreakdown(recommendation.components);
  } else {
    rawScore = 0.5;
    normalizedScore = normalizeScore(rawScore, "pick");
    displayLabel = "N/A";
  }

  // Color thresholds based on normalized score
  const scoreColor =
    normalizedScore >= 0.7 ? "text-success" :
    normalizedScore >= 0.5 ? "text-warning" : "text-danger";

  const cardBorder = isTopPick
    ? "border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)]"
    : "border-gold-dim/50";

  return (
    <div
      onClick={() => onClick(championName)}
      className={`
        bg-lol-light rounded-lg border ${cardBorder}
        transition-all duration-200
        hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
        text-left w-full cursor-pointer
      `}
    >
      {/* Compact Header - always visible */}
      <div
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
      </div>

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
              {/* Score breakdown */}
              {breakdownItems.length > 0 && (
                <div className="space-y-0.5">
                  <div className="text-[9px] uppercase text-text-tertiary">Score Breakdown</div>
                  {breakdownItems.map((factor) => (
                    <div key={factor.key} className="flex items-center gap-2 text-[10px] sm:text-xs">
                      <span className="text-gold-dim">▸</span>
                      <span className="text-text-secondary">{factor.label}:</span>
                      <span className={`font-mono ${getComponentColor(factor.value, !!factor.weighted)}`}>
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

              {/* Raw score for transparency */}
              <div className="text-[9px] text-text-tertiary mt-1 pt-1 border-t border-gold-dim/20">
                Raw score: {(rawScore * 100).toFixed(1)}%
              </div>
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
  // Track which recommendation cards are collapsed (all expanded by default)
  const [collapsedCards, setCollapsedCards] = useState<Set<string>>(new Set());

  useEffect(() => {
    setCollapsedCards(new Set());
  }, [draftState.action_count]);

  const toggleCardExpand = useCallback((championName: string) => {
    setCollapsedCards(prev => {
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
  const recommendationList = recommendations ?? [];

  const showRecommendations = isOurTurn && recommendationList.length > 0;
  const showInsights =
    llmLoading ||
    !!llmInsight?.draft_analysis ||
    (llmInsight?.status === "ready" && (llmInsight.reranked?.length ?? 0) > 0) ||
    llmInsight?.status === "error";

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
      <div className="flex flex-col gap-2 sm:gap-3 lg:gap-4 xl:grid xl:grid-cols-[220px_1fr_220px] xl:items-start">
        {/* Blue Team - does not expand with center */}
        <div
          className={`flex flex-col xl:self-start ${
            coachingSide === "blue" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={blueTeam}
            picks={draftState.blue_picks}
            side="blue"
            isActive={draftState.next_team === "blue" && draftState.next_action === "pick"}
            picksWithRoles={blueCompWithRoles ?? undefined}
            players={blueTeam?.players}
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
          className={`flex flex-col xl:self-start ${
            coachingSide === "red" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={redTeam}
            picks={draftState.red_picks}
            side="red"
            isActive={draftState.next_team === "red" && draftState.next_action === "pick"}
            picksWithRoles={redCompWithRoles ?? undefined}
            players={redTeam?.players}
          />
          {coachingSide === "red" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>
      </div>

      {/* Ban Row */}
      <SimulatorBanRow blueBans={draftState.blue_bans} redBans={draftState.red_bans} />

      {/* Recommendations */}
      {(showRecommendations || showInsights) && (
        <div className="bg-lol-dark rounded-lg p-2 sm:p-3 lg:p-4">
          {showRecommendations && (
            <>
              <div className="flex items-center justify-between mb-2 sm:mb-3">
                <h3 className="text-xs sm:text-sm font-semibold uppercase tracking-wide text-gold-bright">
                  {isBanPhase ? "Ban" : "Pick"} Recommendations
                </h3>
                <div className="flex items-center gap-2 sm:gap-3">
                  {/* Role-Grouped Toggle - hidden for now, keeping code for future use */}
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
                {recommendationList.slice(0, 5).map((rec, i) => (
                  <RecommendationCard
                    key={rec.champion_name}
                    recommendation={rec}
                    isTopPick={i === 0}
                    onClick={onChampionSelect}
                    ourTeam={coachingSide === "blue" ? blueTeam : redTeam}
                    isExpanded={!collapsedCards.has(rec.champion_name)}
                    onToggleExpand={() => toggleCardExpand(rec.champion_name)}
                  />
                ))}
              </div>
            </>
          )}

          {/* AI Insights Panel - includes analysis and reranked picks */}
          {showInsights && (
            <div className={showRecommendations ? "mt-4" : ""}>
              <SimulatorInsightPanel
                insight={
                  llmInsight?.draft_analysis ??
                  (llmInsight?.status === "error" ? llmInsight.message ?? null : null)
                }
                isLoading={llmLoading}
                reranked={llmInsight?.status === "ready" ? llmInsight.reranked : undefined}
              />
            </div>
          )}
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
