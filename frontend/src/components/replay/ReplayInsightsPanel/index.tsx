// frontend/src/components/replay/ReplayInsightsPanel/index.tsx
// Displays AI insights with team context in Replay mode
import { useState, useEffect, useRef } from "react";
import type { LLMInsight, Team } from "../../../types";
import { ChampionPortrait } from "../../shared/ChampionPortrait";

interface ReplayInsightsPanelProps {
  insight: LLMInsight | null;
  isLoading?: boolean;
  forTeam?: Team;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const width = Math.round(confidence * 100);
  const color =
    confidence >= 0.8 ? "bg-success" :
    confidence >= 0.6 ? "bg-magic" :
    "bg-warning";

  return (
    <div className="w-12 h-1.5 bg-lol-dark rounded-full overflow-hidden">
      <div className={`h-full ${color}`} style={{ width: `${width}%` }} />
    </div>
  );
}

export function ReplayInsightsPanel({
  insight,
  isLoading = false,
}: ReplayInsightsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const wasLoadingRef = useRef(false);

  const hasContent = !!insight;

  // Auto-expand when loading starts, auto-collapse when loading finishes
  useEffect(() => {
    if (isLoading && !wasLoadingRef.current) {
      // Loading just started - expand to show loading indicator
      setIsExpanded(true);
    } else if (!isLoading && wasLoadingRef.current && hasContent) {
      // Loading just finished with content - collapse to avoid jumpiness
      setIsExpanded(false);
    }
    wasLoadingRef.current = isLoading;
  }, [isLoading, hasContent]);

  // If no content and not loading, don't render
  if (!hasContent && !isLoading) {
    return null;
  }

  const teamColor = insight?.forTeam === "blue" ? "text-blue-team" : "text-red-team";
  const borderColor = insight?.forTeam === "blue" ? "border-blue-team/30" : "border-red-team/30";

  return (
    <div className={`rounded-lg border ${hasContent ? borderColor : "border-magic/30"} bg-lol-dark/80 overflow-hidden`}>
      {/* Header - clickable to toggle */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-lol-light/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-magic text-sm font-semibold">AI Analysis</span>
          {insight && (
            <span className={`text-xs ${teamColor} uppercase`}>
              {insight.forTeam} side
            </span>
          )}
          {/* Status indicator */}
          {isLoading ? (
            <>
              <div className="w-3 h-3 border-2 border-magic border-t-transparent rounded-full animate-spin" />
              <span className="text-[10px] text-magic">Analyzing...</span>
            </>
          ) : hasContent ? (
            <span className="text-[10px] px-1.5 py-0.5 bg-magic/20 text-magic rounded">
              Ready
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {!isExpanded && hasContent && !isLoading && (
            <span className="text-[10px] text-text-tertiary">Click to view</span>
          )}
          <svg
            className={`w-4 h-4 text-text-tertiary transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Content - smooth transition using grid */}
      <div
        className={`
          grid transition-[grid-template-rows] duration-300 ease-out
          ${isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}
        `}
      >
        <div className="overflow-hidden">
          <div className="px-3 pb-3 space-y-3">
            {/* Loading state */}
            {isLoading && (
              <div className="flex items-center gap-3 text-text-secondary py-2">
                <div className="w-5 h-5 border-2 border-magic border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">Analyzing draft state...</span>
              </div>
            )}

            {/* Draft Analysis */}
            {insight?.draftAnalysis && !isLoading && (
              <div className="text-sm text-text-secondary bg-lol-darkest/50 rounded p-2">
                {insight.draftAnalysis}
              </div>
            )}

            {/* Reranked Recommendations */}
            {insight && insight.reranked.length > 0 && !isLoading && (
              <div>
                <div className="text-[10px] text-text-tertiary uppercase mb-2">
                  AI Picks (Reranked)
                </div>
                <div className="space-y-1.5">
                  {insight.reranked.map((rec, idx) => (
                    <div
                      key={rec.champion_name}
                      className="flex items-start gap-2 bg-lol-light/30 rounded p-2"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs text-gold-dim font-mono w-4">
                          #{idx + 1}
                        </span>
                        <ChampionPortrait
                          championName={rec.champion_name}
                          state="picked"
                          className="w-6 h-6 rounded-sm flex-shrink-0"
                        />
                        <span className="text-sm font-medium text-gold-bright truncate">
                          {rec.champion_name}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <ConfidenceBar confidence={rec.confidence} />
                          <span className="text-[10px] text-text-tertiary">
                            {Math.round(rec.confidence * 100)}%
                          </span>
                          {rec.original_rank !== idx + 1 && (
                            <span className="text-[10px] text-text-tertiary">
                              (was #{rec.original_rank})
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-text-secondary line-clamp-2">
                          {rec.reasoning}
                        </div>
                        {rec.strategic_factors.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {rec.strategic_factors.slice(0, 3).map((factor) => (
                              <span
                                key={factor}
                                className="text-[9px] px-1.5 py-0.5 bg-magic/20 text-magic rounded"
                              >
                                {factor.replace(/_/g, " ")}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Additional Suggestions */}
            {insight && insight.additionalSuggestions.length > 0 && !isLoading && (
              <div>
                <div className="text-[10px] text-text-tertiary uppercase mb-2">
                  Additional Suggestions
                </div>
                <div className="space-y-1.5">
                  {insight.additionalSuggestions.map((sug) => (
                    <div
                      key={sug.champion_name}
                      className="flex items-center gap-2 bg-lol-darkest/30 rounded p-2"
                    >
                      <ChampionPortrait
                        championName={sug.champion_name}
                        state="picked"
                        className="w-5 h-5 rounded-sm"
                      />
                      <span className="text-sm text-text-primary">{sug.champion_name}</span>
                      {sug.role && (
                        <span className="text-[10px] text-magic uppercase">{sug.role}</span>
                      )}
                      <span className="flex-1 text-xs text-text-tertiary truncate">
                        {sug.reasoning}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
