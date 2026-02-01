// frontend/src/components/recommendations/RecommendationCard.tsx
import { ChampionPortrait, RECOMMENDATION_ICON_SIZE_CLASS } from "../shared";
import type { PickRecommendation, RecommendationFlag } from "../../types";

interface RecommendationCardProps {
  recommendation: PickRecommendation;
  isTopPick?: boolean;
  rank?: number;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const fillColor =
    confidence >= 0.7 ? "bg-success" :
    confidence >= 0.5 ? "bg-warning" : "bg-danger";

  return (
    <div className="w-24 h-2 bg-lol-darkest rounded-full overflow-hidden">
      <div
        className={`h-full ${fillColor} transition-all duration-500`}
        style={{ width: `${confidence * 100}%` }}
      />
    </div>
  );
}

function FlagBadge({ flag }: { flag: RecommendationFlag }) {
  if (!flag) return null;

  const styles = flag === "SURPRISE_PICK"
    ? "bg-warning/20 text-warning"
    : "bg-danger/20 text-danger";

  const label = flag === "SURPRISE_PICK"
    ? "Surprise Pick"
    : "Low Confidence";

  return (
    <div className={`
      text-xs uppercase tracking-widest font-semibold
      py-1 px-2 rounded mb-3
      ${styles}
    `}>
      {label}
    </div>
  );
}

export function RecommendationCard({
  recommendation,
  isTopPick = false,
  rank,
}: RecommendationCardProps) {
  const { champion_name, confidence, flag, reasons } = recommendation;

  const confidenceColor =
    confidence >= 0.7 ? "text-success" :
    confidence >= 0.5 ? "text-warning" : "text-danger";

  const cardBorder = isTopPick
    ? "border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)]"
    : "border-gold-dim";

  return (
    <div className={`
      bg-lol-light rounded-lg p-4 border-2 ${cardBorder}
      transition-all duration-300
      hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
    `}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <ChampionPortrait
          championName={champion_name}
          state="picked"
          team="blue"
          className={`${RECOMMENDATION_ICON_SIZE_CLASS} shrink-0`}
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {rank && !isTopPick && (
              <span className="text-text-tertiary text-sm">#{rank}</span>
            )}
            <h3 className="font-semibold text-lg uppercase text-gold-bright">
              {champion_name}
            </h3>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-sm font-semibold ${confidenceColor}`}>
              {Math.round(confidence * 100)}%
            </span>
            <ConfidenceBar confidence={confidence} />
          </div>
        </div>
      </div>

      {/* Flag Banner */}
      <FlagBadge flag={flag} />

      {/* Reasons */}
      <ul className="space-y-1.5">
        {reasons.slice(0, 3).map((reason, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
            <span className="text-gold mt-0.5">•</span>
            <span>{reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
