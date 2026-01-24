// deepdraft/src/components/RecommendationPanel/index.tsx
import { RecommendationCard, InsightPanel } from "../recommendations";
import type { Recommendations, ActionType } from "../../types";

interface RecommendationPanelProps {
  recommendations: Recommendations | null;
  nextAction: ActionType | null;
}

export function RecommendationPanel({
  recommendations,
  nextAction,
}: RecommendationPanelProps) {
  // Only show pick recommendations for now (bans are simpler)
  const picks = recommendations?.picks ?? [];
  const forTeam = recommendations?.for_team;

  // Placeholder insight - will come from LLM later
  const insight = picks.length > 0
    ? `${forTeam?.toUpperCase() ?? "Team"} should consider ${picks[0]?.champion_name} as a strong pick in this position.`
    : null;

  if (!recommendations || nextAction === null) {
    return (
      <div className="bg-lol-dark rounded-lg p-6">
        <div className="text-center text-text-tertiary py-8">
          Waiting for draft to begin...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-lol-dark rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          {nextAction === "pick" ? "Pick" : "Ban"} Recommendations
        </h2>
        <span className={`
          text-sm font-semibold uppercase px-2 py-1 rounded
          ${forTeam === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
        `}>
          For {forTeam}
        </span>
      </div>

      {/* Recommendations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Top Pick */}
        {picks[0] && (
          <RecommendationCard
            recommendation={picks[0]}
            isTopPick
          />
        )}

        {/* Second Pick or Surprise */}
        {picks[1] && (
          <RecommendationCard
            recommendation={picks[1]}
            rank={2}
          />
        )}

        {/* AI Insight Panel */}
        <InsightPanel insight={insight} />
      </div>

      {/* Also Consider Row */}
      {picks.length > 2 && (
        <div className="mt-4 pt-4 border-t border-gold-dim/30">
          <span className="text-xs text-text-tertiary uppercase tracking-wide mr-3">
            Also Consider:
          </span>
          {picks.slice(2, 5).map((rec) => (
            <span
              key={rec.champion_name}
              className="inline-flex items-center gap-1 mr-4 text-sm text-text-secondary"
            >
              <span className="text-gold-bright">{rec.champion_name}</span>
              <span className="text-text-tertiary">
                ({Math.round(rec.confidence * 100)}%)
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
