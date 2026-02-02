// frontend/src/components/DraftCompletePanel/index.tsx
import type { TeamContext, TeamEvaluation, DraftQuality } from "../../types";
import { DraftAnalysis } from "./DraftAnalysis";
import { DraftReport } from "./DraftReport";

interface DraftCompletePanelProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  evaluation?: TeamEvaluation | null;
  // Simulator mode: onSelectWinner handler
  onSelectWinner?: (winner: "blue" | "red") => void;
  isRecordingWinner?: boolean;
  // Replay mode: known winner
  winnerSide?: "blue" | "red" | null;
  // Draft quality - simulator passes single, replay passes both
  draftQuality?: DraftQuality | null;
  blueDraftQuality?: DraftQuality | null;
  redDraftQuality?: DraftQuality | null;
}

export function DraftCompletePanel({
  blueTeam,
  redTeam,
  evaluation,
  onSelectWinner,
  isRecordingWinner = false,
  winnerSide,
  draftQuality,
  blueDraftQuality,
  redDraftQuality,
}: DraftCompletePanelProps) {
  const blueScore = evaluation?.our_evaluation?.composition_score ?? 0;
  const redScore = evaluation?.enemy_evaluation?.composition_score ?? 0;
  const bluePoints = Math.round(blueScore * 100);
  const redPoints = Math.round(redScore * 100);

  const blueStrength = evaluation?.our_evaluation?.strengths?.[0] ?? "Balanced composition";
  const redStrength = evaluation?.enemy_evaluation?.strengths?.[0] ?? "Balanced composition";

  const matchupDesc = evaluation?.matchup_description ?? "Even matchup";

  // For simulator: coached team is "our" side, use draftQuality
  // For replay: use blueDraftQuality/redDraftQuality directly
  const effectiveBlueDraftQuality = blueDraftQuality ?? draftQuality ?? null;
  const effectiveRedDraftQuality = redDraftQuality ?? null;

  // Build analysis data from evaluation
  const blueAnalysisData = {
    synergy_score: evaluation?.our_evaluation?.synergy_score ?? 0.5,
    composition_score: evaluation?.our_evaluation?.composition_score ?? 0.5,
    archetype: evaluation?.our_evaluation?.archetype ?? null,
  };

  const redAnalysisData = {
    synergy_score: evaluation?.enemy_evaluation?.synergy_score ?? 0.5,
    composition_score: evaluation?.enemy_evaluation?.composition_score ?? 0.5,
    archetype: evaluation?.enemy_evaluation?.archetype ?? null,
  };

  return (
    <div className="space-y-4">
      {/* Existing Header Section */}
      <div className="bg-gradient-to-r from-lol-dark via-lol-medium to-lol-dark rounded-lg p-6 border border-gold-dim/50">
        <div className="text-center mb-4">
          <h2 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            Draft Complete
          </h2>
          <p className="text-sm text-text-tertiary mt-1">{matchupDesc}</p>
        </div>

        <div className="flex items-stretch justify-center gap-4 mb-6">
          <div className="flex-1 max-w-[200px] bg-blue-team/10 border border-blue-team/30 rounded-lg p-4 text-center">
            <div className="text-blue-team font-semibold text-sm uppercase mb-2">
              {blueTeam.name}
            </div>
            <div className="text-3xl font-bold text-blue-team mb-2">
              {bluePoints}
              <span className="text-sm font-normal text-text-tertiary ml-1">pts</span>
            </div>
            <div className="text-xs text-text-secondary truncate" title={blueStrength}>
              {blueStrength}
            </div>
          </div>

          <div className="flex items-center">
            <span className="text-gold-dim font-bold text-lg">VS</span>
          </div>

          <div className="flex-1 max-w-[200px] bg-red-team/10 border border-red-team/30 rounded-lg p-4 text-center">
            <div className="text-red-team font-semibold text-sm uppercase mb-2">
              {redTeam.name}
            </div>
            <div className="text-3xl font-bold text-red-team mb-2">
              {redPoints}
              <span className="text-sm font-normal text-text-tertiary ml-1">pts</span>
            </div>
            <div className="text-xs text-text-secondary truncate" title={redStrength}>
              {redStrength}
            </div>
          </div>
        </div>

        {/* Simulator mode: Select winner buttons */}
        {onSelectWinner && (
          <div className="text-center">
            <p className="text-sm text-text-secondary mb-3">Who won this game?</p>
            <div className="flex justify-center gap-4">
              <button
                onClick={() => onSelectWinner("blue")}
                disabled={isRecordingWinner}
                className="px-6 py-2 bg-blue-team/80 text-white rounded font-semibold hover:bg-blue-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRecordingWinner ? "Recording..." : `${blueTeam.name} Won`}
              </button>
              <button
                onClick={() => onSelectWinner("red")}
                disabled={isRecordingWinner}
                className="px-6 py-2 bg-red-team/80 text-white rounded font-semibold hover:bg-red-team transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRecordingWinner ? "Recording..." : `${redTeam.name} Won`}
              </button>
            </div>
          </div>
        )}

        {/* Replay mode: Show known winner */}
        {!onSelectWinner && winnerSide && (
          <div className="text-center">
            <p className="text-sm text-text-secondary mb-2">Game Winner</p>
            <div className={`inline-block px-4 py-2 rounded font-semibold ${
              winnerSide === "blue"
                ? "bg-blue-team/20 text-blue-team border border-blue-team/50"
                : "bg-red-team/20 text-red-team border border-red-team/50"
            }`}>
              {winnerSide === "blue" ? blueTeam.name : redTeam.name}
            </div>
          </div>
        )}
      </div>

      {/* NEW: Draft Analysis Section */}
      {evaluation && (
        <DraftAnalysis
          blueTeam={blueTeam}
          redTeam={redTeam}
          blueData={blueAnalysisData}
          redData={redAnalysisData}
          matchupAdvantage={evaluation.matchup_advantage}
        />
      )}

      {/* NEW: Draft Report Section */}
      <DraftReport
        blueTeam={blueTeam}
        redTeam={redTeam}
        blueDraftQuality={effectiveBlueDraftQuality}
        redDraftQuality={effectiveRedDraftQuality}
      />
    </div>
  );
}
