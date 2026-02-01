// frontend/src/components/recommendations/InsightPanel.tsx
import { useState, useEffect, useRef } from "react";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import type { RerankedRecommendation } from "../../types";

interface InsightPanelProps {
  insight: string | null;
  isLoading?: boolean;
  reranked?: RerankedRecommendation[] | null;
}

export function InsightPanel({ insight, isLoading = false, reranked }: InsightPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const wasLoadingRef = useRef(false);

  const hasInsight = !!insight;
  const hasReranked = reranked && reranked.length > 0;
  const hasContent = hasInsight || hasReranked;

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

  return (
    <div className="
      bg-gradient-to-br from-lol-dark to-lol-medium
      rounded-lg border border-magic/30
      relative overflow-hidden
    ">
      {/* Ambient glow background */}
      <div className="absolute inset-0 bg-magic/5" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 bg-magic/10 rounded-full blur-3xl" />

      {/* Header - clickable to expand/collapse */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="relative w-full flex items-center justify-between p-3 hover:bg-lol-light/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm uppercase tracking-widest text-magic">
            AI Insight
          </h3>
          {/* Status indicator */}
          {hasContent ? (
            <span className="text-[10px] px-1.5 py-0.5 bg-magic/20 text-magic rounded">
              Ready
            </span>
          ) : null}
        </div>
        {/* Expand/collapse icon with hint */}
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
          <div className="relative px-4 pb-4 space-y-3">
            {/* Loading state */}
            {isLoading && (
              <div className="flex items-center gap-3 text-text-secondary py-2">
                <div className="w-5 h-5 border-2 border-magic border-t-transparent rounded-full animate-spin" />
                <span className="text-sm">Analyzing draft state...</span>
              </div>
            )}

            {/* Draft Analysis */}
            {insight && !isLoading && (
              <div>
                <div className="text-[10px] text-text-tertiary uppercase mb-1">Analysis</div>
                <p className="text-sm text-gold-bright leading-relaxed">
                  "{insight}"
                </p>
              </div>
            )}

            {/* Reranked Recommendations */}
            {hasReranked && !isLoading && (
              <div>
                <div className="text-[10px] text-text-tertiary uppercase mb-2">AI Reranked Picks</div>
                <div className="space-y-2">
                  {reranked!.slice(0, 3).map((rec) => (
                    <div
                      key={rec.champion_name}
                      className="bg-lol-dark/50 rounded p-2 border border-magic/20 flex items-start gap-2"
                    >
                      <ChampionPortrait
                        championName={rec.champion_name}
                        state="picked"
                        className="w-8 h-8 rounded-sm shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-gold-bright font-medium text-sm">
                            #{rec.new_rank} {rec.champion_name}
                          </span>
                          {rec.original_rank !== rec.new_rank && (
                            <span className="text-[10px] text-text-tertiary">
                              (was #{rec.original_rank})
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                          {rec.reasoning}
                        </p>
                      </div>
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
