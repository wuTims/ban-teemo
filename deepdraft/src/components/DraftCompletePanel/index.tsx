// deepdraft/src/components/DraftCompletePanel/index.tsx
import type { TeamContext, TeamEvaluation } from "../../types";

interface DraftCompletePanelProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  evaluation: TeamEvaluation | null;
  onSelectWinner: (winner: "blue" | "red") => void;
  isRecordingWinner: boolean;
}

export function DraftCompletePanel({
  blueTeam,
  redTeam,
  evaluation,
  onSelectWinner,
  isRecordingWinner,
}: DraftCompletePanelProps) {
  const blueScore = evaluation?.our_evaluation?.composition_score ?? 0;
  const redScore = evaluation?.enemy_evaluation?.composition_score ?? 0;
  const bluePoints = Math.round(blueScore * 100);
  const redPoints = Math.round(redScore * 100);

  const blueStrength = evaluation?.our_evaluation?.strengths?.[0] ?? "Balanced composition";
  const redStrength = evaluation?.enemy_evaluation?.strengths?.[0] ?? "Balanced composition";

  const matchupDesc = evaluation?.matchup_description ?? "Even matchup";

  return (
    <div className="bg-gradient-to-r from-lol-dark via-lol-medium to-lol-dark rounded-lg p-6 border border-gold-dim/50">
      {/* Header */}
      <div className="text-center mb-4">
        <h2 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
          Draft Complete
        </h2>
        <p className="text-sm text-text-tertiary mt-1">{matchupDesc}</p>
      </div>

      {/* Score comparison */}
      <div className="flex items-stretch justify-center gap-4 mb-6">
        {/* Blue team card */}
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

        {/* VS divider */}
        <div className="flex items-center">
          <span className="text-gold-dim font-bold text-lg">VS</span>
        </div>

        {/* Red team card */}
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

      {/* Winner selection */}
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
    </div>
  );
}
