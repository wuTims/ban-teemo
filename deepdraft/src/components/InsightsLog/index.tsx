// deepdraft/src/components/InsightsLog/index.tsx
import { useEffect, useRef } from "react";
import type { Recommendations, DraftAction } from "../../types";

interface InsightEntry {
  action: DraftAction;
  recommendations: Recommendations;
}

interface InsightsLogProps {
  entries: InsightEntry[];
  isLive: boolean;
}

export function InsightsLog({ entries, isLive }: InsightsLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries.length]);

  if (entries.length === 0) {
    return (
      <div className="bg-lol-dark rounded-lg p-6">
        <div className="text-center text-text-tertiary py-8">
          Insights will appear as the draft progresses...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          Draft Insights
        </h2>
        {isLive && (
          <span className="text-xs text-magic animate-pulse">● LIVE</span>
        )}
      </div>

      {/* Scrollable log */}
      <div
        ref={scrollRef}
        className="space-y-3 max-h-[500px] overflow-y-auto pr-2"
      >
        {entries.map((entry, idx) => {
          const isLatest = idx === entries.length - 1;
          const isBan = entry.action.action_type === "ban";
          const teamColor = entry.action.team_side === "blue" ? "blue-team" : "red-team";
          const teamLabel = entry.action.team_side === "blue" ? "Blue" : "Red";

          // Get recommendations based on action type
          const recs = isBan
            ? entry.recommendations.bans
            : entry.recommendations.picks;
          const top3 = recs.slice(0, 3);

          // Calculate action number within type
          const actionNum = isBan
            ? Math.ceil(entry.action.sequence / 2) <= 3
              ? Math.ceil((entry.action.sequence + 1) / 2)
              : Math.ceil((entry.action.sequence - 5) / 2)
            : entry.action.sequence <= 6
              ? entry.action.sequence - 6
              : entry.action.sequence - 12;

          return (
            <div
              key={entry.action.sequence}
              className={`
                rounded-lg border p-3
                ${isLatest && isLive
                  ? "border-magic bg-magic/5"
                  : `border-${teamColor}/30 bg-lol-light/50`
                }
              `}
            >
              {/* Entry header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded bg-${teamColor}/20 text-${teamColor}`}>
                    {teamLabel}
                  </span>
                  <span className="text-sm text-text-primary font-medium">
                    {isBan ? "Ban" : "Pick"} #{Math.abs(actionNum) || 1}
                  </span>
                </div>
                {isLatest && isLive && (
                  <span className="text-xs bg-magic/20 text-magic px-2 py-0.5 rounded">
                    LIVE
                  </span>
                )}
              </div>

              {/* What actually happened */}
              <div className="text-xs text-text-tertiary mb-2">
                Actual: <span className="text-gold-bright font-medium">{entry.action.champion_name}</span>
              </div>

              {/* Top 3 recommendations */}
              <div className="space-y-1.5">
                {top3.map((rec, i) => {
                  const score = "priority" in rec ? rec.priority : ("confidence" in rec ? rec.confidence : 0);
                  const scorePercent = Math.round(score * 100);
                  const isMatch = rec.champion_name === entry.action.champion_name;

                  return (
                    <div
                      key={rec.champion_name}
                      className={`text-xs ${isMatch ? "text-success" : "text-text-secondary"}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-gold-dim w-4">{i + 1}.</span>
                        <span className={`font-medium ${isMatch ? "text-success" : "text-text-primary"}`}>
                          {rec.champion_name}
                        </span>
                        <span className="text-text-tertiary">({scorePercent}%)</span>
                        {isMatch && <span className="text-success">✓</span>}
                      </div>
                      {rec.reasons[0] && (
                        <div className="ml-6 text-text-tertiary truncate">
                          {rec.reasons[0]}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
