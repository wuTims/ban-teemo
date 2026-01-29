// deepdraft/src/components/SimulatorView/index.tsx
import { useMemo } from "react";
import { PhaseIndicator, TeamPanel, BanRow } from "../draft";
import { ChampionPool } from "../ChampionPool";
import { RECOMMENDATION_ICON_SIZE_CLASS } from "../shared";
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
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesScore: [number, number];
  fearlessBlocked: FearlessBlocked;
  draftMode: DraftMode;
  onChampionSelect: (champion: string) => void;
}

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
          className={`${RECOMMENDATION_ICON_SIZE_CLASS} shrink-0`}
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
          <div className="space-y-0.5">
            {topFactors.map((factor) => (
              <div key={factor.name} className="flex items-center gap-2 text-xs">
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
        </div>
      )}

      {/* Reasons */}
      {reasons.length > 0 && (
        <div className="text-xs text-text-secondary">
          <div className="flex items-start gap-1">
            <span className="text-gold-dim">•</span>
            <span className="truncate">{reasons[0]}</span>
          </div>
        </div>
      )}
    </button>
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
}: SimulatorViewProps) {
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
    <div className="space-y-4">
      {/* Series Status */}
      <div className="flex justify-center items-center gap-4 text-sm">
        <span className="text-text-secondary">Game {gameNumber}</span>
        <span className="text-gold-bright font-bold">
          {blueTeam.name} {seriesScore[0]} - {seriesScore[1]} {redTeam.name}
        </span>
        {draftMode === "fearless" && fearlessCount > 0 && (
          <span className="text-danger text-xs">
            Fearless: {fearlessCount} blocked
          </span>
        )}
      </div>

      {/* Phase Indicator */}
      <div className="flex justify-center items-center gap-4">
        <PhaseIndicator
          currentPhase={draftState.phase}
          nextTeam={draftState.next_team}
          nextAction={draftState.next_action}
        />
        {isEnemyThinking && (
          <span className="text-text-tertiary animate-pulse text-sm">
            Enemy thinking...
          </span>
        )}
      </div>

      {/* Main Layout - Stacked on mobile, 3-column on desktop */}
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[220px_1fr_220px] lg:items-start">
        {/* Blue Team */}
        <div
          className={`flex flex-col h-full ${
            coachingSide === "blue" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={blueTeam}
            picks={draftState.blue_picks}
            side="blue"
            isActive={draftState.next_team === "blue" && draftState.next_action === "pick"}
          />
          {coachingSide === "blue" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>

        {/* Champion Pool */}
        <ChampionPool
          allChampions={ALL_CHAMPIONS}
          unavailable={unavailable}
          fearlessBlocked={fearlessBlocked}
          onSelect={onChampionSelect}
          disabled={!isOurTurn}
        />

        {/* Red Team */}
        <div
          className={`flex flex-col h-full ${
            coachingSide === "red" ? "ring-2 ring-magic rounded-lg" : ""
          }`}
        >
          <TeamPanel
            team={redTeam}
            picks={draftState.red_picks}
            side="red"
            isActive={draftState.next_team === "red" && draftState.next_action === "pick"}
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
        <div className="bg-lol-dark rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright">
              {isBanPhase ? "Ban" : "Pick"} Recommendations
            </h3>
            <span className={`
              text-xs font-medium uppercase px-2 py-0.5 rounded
              ${coachingSide === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
            `}>
              Your Turn
            </span>
          </div>
          <div className="grid grid-cols-5 gap-3">
            {recommendations.slice(0, 5).map((rec, i) => (
              <RecommendationCard
                key={rec.champion_name}
                recommendation={rec}
                isTopPick={i === 0}
                onClick={onChampionSelect}
                ourTeam={coachingSide === "blue" ? blueTeam : redTeam}
              />
            ))}
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
