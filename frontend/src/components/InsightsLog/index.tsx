// frontend/src/components/InsightsLog/index.tsx
import { useEffect, useRef, useState } from "react";
import type {
  InsightEntry,
  PickRecommendation,
  BanRecommendation,
  TeamContext,
  LLMInsight,
  RoleGroupedRecommendations,
  SimulatorPickRecommendation,
} from "../../types";
import { ChampionPortrait } from "../shared/ChampionPortrait";

interface InsightsLogProps {
  entries: InsightEntry[];
  isLive: boolean;
  blueTeam?: TeamContext | null;
  redTeam?: TeamContext | null;
  llmInsights?: Map<number, LLMInsight>;
  llmTimeouts?: Set<number>;
}

// Helper to format component scores with color
// isWeighted: true for ban components (max ~0.35), false for pick components (raw 0-1)
function ScoreCell({
  label,
  value,
  isWeighted = false,
}: {
  label: string;
  value: number | undefined;
  isWeighted?: boolean;
}) {
  if (value === undefined) return null;
  // Weighted ban scores use lower thresholds (max ~0.35 per component)
  // Raw pick scores use original thresholds (0-1 scale)
  const color = isWeighted
    ? (value >= 0.20 ? "text-success" : value >= 0.10 ? "text-warning" : "text-danger")
    : (value >= 0.7 ? "text-success" : value >= 0.5 ? "text-warning" : "text-danger");
  return (
    <div className="flex justify-between text-[10px]">
      <span className="text-text-tertiary">{label}</span>
      <span className={`font-mono ${color}`}>{value.toFixed(2)}</span>
    </div>
  );
}

const BAN_COMPONENT_LABELS: Record<string, string> = {
  // Tournament components (simulator mode)
  tournament_priority: "prio",
  // Phase 1 components (weighted)
  meta: "meta",
  presence: "pres",
  flex: "flex",
  proficiency: "prof",
  tier_bonus: "tier",
  // Phase 2 components (weighted)
  comfort: "comf",
  confidence: "conf",
  // Contextual ban components
  archetype_counter: "arch",
  synergy_denial: "syn",
  role_denial: "role",
  counter_our_picks: "cntr",
  counter: "cntr",
};

function getTopBanComponents(
  components?: Record<string, number>,
  limit: number = 5
): Array<{ label: string; value: number }> {
  if (!components) return [];
  return Object.entries(components)
    .filter(([key, value]) => BAN_COMPONENT_LABELS[key] && value !== undefined)
    .map(([key, value]) => ({
      label: BAN_COMPONENT_LABELS[key],
      value,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}

// Compact recommendation card showing champion + all scores
function CompactRecommendationCard({
  champion,
  score,
  role,
  components,
  isMatch,
  isPick,
}: {
  champion: string;
  score: number;
  role?: string | null;
  components?: Record<string, number>;
  isMatch: boolean;
  isPick: boolean;
}) {
  const scoreColor =
    score >= 0.7 ? "text-success" :
    score >= 0.5 ? "text-warning" : "text-danger";

  return (
    <div
      className={`
        rounded border p-1.5 min-w-[100px] flex-1
        ${isMatch
          ? "border-success bg-success/10"
          : "border-gold-dim/30 bg-lol-dark/50"
        }
      `}
    >
      {/* Header: champion + score */}
      <div className="flex items-center gap-1.5 mb-1">
        <ChampionPortrait
          championName={champion}
          state="picked"
          className="w-5 h-5 rounded-sm"
        />
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-medium text-gold-bright truncate">
            {champion}
          </div>
          {isPick && role && (
            <div className="text-[9px] text-magic uppercase">{role}</div>
          )}
        </div>
        <span className={`text-xs font-bold ${scoreColor}`}>
          {Math.round(score * 100)}
        </span>
        {isMatch && <span className="text-success text-[10px]">✓</span>}
      </div>

      {/* Component scores */}
      {components && (
        <div className="space-y-0 border-t border-gold-dim/20 pt-1">
          {isPick ? (
            <>
              {/* Tournament components (simulator mode) or meta (replay mode) */}
              {components.tournament_priority !== undefined ? (
                <>
                  <ScoreCell label="prio" value={components.tournament_priority} />
                  <ScoreCell label="perf" value={components.tournament_performance} />
                </>
              ) : (
                <ScoreCell label="meta" value={components.meta} />
              )}
              <ScoreCell label="prof" value={components.proficiency} />
              <ScoreCell label="match" value={components.matchup} />
              <ScoreCell label="count" value={components.counter} />
              <ScoreCell label="arch" value={components.archetype} />
              <ScoreCell label="syn" value={components.synergy} />
            </>
          ) : (
            <>
              {getTopBanComponents(components).map((item) => (
                <ScoreCell key={item.label} label={item.label} value={item.value} isWeighted />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Calculate ban/pick number based on sequence
function calculateActionNumber(sequence: number, isBan: boolean): number {
  // LoL Draft sequence (1-indexed):
  // 1-6: Ban Phase 1 (alternating: R, B, R, B, R, B = 3 each)
  // 7-12: Pick Phase 1 (R, B, B, R, R, B)
  // 13-16: Ban Phase 2 (R, B, R, B = 2 each)
  // 17-20: Pick Phase 2 (B, R, R, B)

  if (isBan) {
    if (sequence >= 1 && sequence <= 6) {
      // Ban Phase 1: sequences 1-6
      // Each team bans 3: Ban #1 at seq 1 or 2, #2 at seq 3 or 4, #3 at seq 5 or 6
      return Math.ceil(sequence / 2);
    } else if (sequence >= 13 && sequence <= 16) {
      // Ban Phase 2: sequences 13-16
      // Each team bans 2: Ban #4 at seq 13 or 14, #5 at seq 15 or 16
      return 3 + Math.ceil((sequence - 12) / 2);
    }
  } else {
    if (sequence >= 7 && sequence <= 12) {
      // Pick Phase 1: sequences 7-12 (6 picks total)
      // Each team picks 3: Pick #1, #2, #3
      return Math.ceil((sequence - 6) / 2);
    } else if (sequence >= 17 && sequence <= 20) {
      // Pick Phase 2: sequences 17-20 (4 picks total)
      // Each team picks 2: Pick #4, #5
      return 3 + Math.ceil((sequence - 16) / 2);
    }
  }
  return 1;
}

// Frontend display names to backend canonical role names
const ROLE_DISPLAY_ORDER = [
  { display: "TOP", backend: "top" },
  { display: "JNG", backend: "jungle" },
  { display: "MID", backend: "mid" },
  { display: "ADC", backend: "bot" },
  { display: "SUP", backend: "support" },
] as const;

// Confidence bar component for visual score indicator
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

// Inline Role View for per-entry "By Role" display
// Uses same format as CompactRecommendationCard for consistency
function InlineRoleView({
  roleGrouped,
  expandedCards,
  onToggleCard,
}: {
  roleGrouped: RoleGroupedRecommendations;
  expandedCards: Set<string>;
  onToggleCard: (key: string) => void;
}) {
  return (
    <div className="space-y-1">
      {ROLE_DISPLAY_ORDER.map(({ display, backend }) => {
        const picks = (roleGrouped.by_role?.[backend] || []) as SimulatorPickRecommendation[];
        return (
          <div key={display} className="flex items-start gap-2">
            <span className="w-10 text-xs font-medium text-text-tertiary shrink-0 pt-1">{display}</span>
            <div className="flex gap-2 flex-1">
              {picks.length > 0 ? (
                picks.slice(0, 2).map((pick, i) => {
                  const cardKey = `${display}-${i}`;
                  const isExpanded = expandedCards.has(cardKey);
                  const scoreColor =
                    pick.score >= 0.7 ? "text-success" :
                    pick.score >= 0.5 ? "text-warning" : "text-danger";

                  return (
                    <div
                      key={pick.champion_name}
                      className="flex-1 border border-gold-dim/30 rounded p-1.5 bg-lol-dark/50 min-w-[100px]"
                    >
                      {/* Header: champion + score (matching CompactRecommendationCard) */}
                      <button
                        onClick={() => onToggleCard(cardKey)}
                        className="flex items-center gap-1.5 w-full mb-1"
                      >
                        <ChampionPortrait
                          championName={pick.champion_name}
                          state="picked"
                          className="w-5 h-5 rounded-sm"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-[10px] font-medium text-gold-bright truncate">
                            {pick.champion_name}
                          </div>
                        </div>
                        <span className={`text-xs font-bold ${scoreColor}`}>
                          {Math.round(pick.score * 100)}
                        </span>
                        <span className="text-[10px] text-text-tertiary">
                          {isExpanded ? "▼" : "▶"}
                        </span>
                      </button>
                      {/* Component scores (matching CompactRecommendationCard format) */}
                      {isExpanded && pick.components && (
                        <div className="space-y-0 border-t border-gold-dim/20 pt-1">
                          {/* Tournament components (simulator mode) or meta (replay mode) */}
                          {pick.components.tournament_priority !== undefined ? (
                            <>
                              <ScoreCell label="prio" value={pick.components.tournament_priority} />
                              <ScoreCell label="perf" value={pick.components.tournament_performance} />
                            </>
                          ) : (
                            <ScoreCell label="meta" value={pick.components.meta} />
                          )}
                          <ScoreCell label="prof" value={pick.components.proficiency} />
                          <ScoreCell label="match" value={pick.components.matchup} />
                          <ScoreCell label="count" value={pick.components.counter} />
                          <ScoreCell label="arch" value={pick.components.archetype} />
                          <ScoreCell label="syn" value={pick.components.synergy} />
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="flex-1 text-[10px] text-text-tertiary italic py-1">
                  No picks for {display}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Inline AI Insight component for per-entry display
function InlineAIInsight({
  insight,
  actionType,
  isExpanded,
  onToggle,
}: {
  insight: LLMInsight;
  actionType: "pick" | "ban";
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const label = actionType === "pick" ? "Pre-Pick AI Insight" : "Pre-Ban AI Insight";

  return (
    <div className="border border-magic/30 bg-magic/5 rounded p-2 mb-2">
      <button onClick={onToggle} className="flex justify-between w-full items-center">
        <span className="text-magic text-sm font-medium">{label}</span>
        <span className="text-text-tertiary text-xs">{isExpanded ? "▼" : "▶"}</span>
      </button>
      {isExpanded && (
        <div className="mt-2 space-y-2">
          {/* Draft Analysis */}
          {insight.draftAnalysis && (
            <p className="text-sm text-text-secondary bg-lol-darkest/50 rounded p-2">
              {insight.draftAnalysis}
            </p>
          )}

          {/* Reranked recommendations */}
          {insight.reranked.length > 0 && (
            <div>
              <div className="text-[10px] text-text-tertiary uppercase mb-1">
                AI Reranked Picks
              </div>
              <div className="space-y-1">
                {insight.reranked.map((rec, idx) => (
                  <div
                    key={rec.champion_name}
                    className="flex items-start gap-2 bg-lol-light/30 rounded p-1.5"
                  >
                    <span className="text-xs text-gold-dim font-mono w-4">#{idx + 1}</span>
                    <ChampionPortrait
                      championName={rec.champion_name}
                      state="picked"
                      className="w-6 h-6 rounded-sm shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-gold-bright">
                          {rec.champion_name}
                        </span>
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
                      <div className="text-[11px] text-text-secondary line-clamp-2">
                        {rec.reasoning}
                      </div>
                      {rec.strategic_factors && rec.strategic_factors.length > 0 && (
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
        </div>
      )}
    </div>
  );
}

// Entry UI state interface
interface EntryUIState {
  aiInsightExpanded: boolean;
  showRoleGrouped: boolean;
  expandedRoleCards: Set<string>;
}

export function InsightsLog({
  entries,
  isLive,
  blueTeam,
  redTeam,
  llmInsights,
  llmTimeouts,
}: InsightsLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // Per-entry UI state (keyed by action sequence)
  const [entryStates, setEntryStates] = useState<Map<number, EntryUIState>>(new Map());

  // Helper to get or create entry state
  const getEntryState = (sequence: number): EntryUIState => {
    return entryStates.get(sequence) || {
      aiInsightExpanded: false,  // Start collapsed, user expands to view
      showRoleGrouped: false,
      expandedRoleCards: new Set(),
    };
  };

  // Toggle AI insight expanded state for an entry
  const toggleAIInsight = (sequence: number) => {
    setEntryStates((prev) => {
      const next = new Map(prev);
      const state = getEntryState(sequence);
      next.set(sequence, { ...state, aiInsightExpanded: !state.aiInsightExpanded });
      return next;
    });
  };

  // Toggle role-grouped view for an entry
  const toggleRoleGrouped = (sequence: number) => {
    setEntryStates((prev) => {
      const next = new Map(prev);
      const state = getEntryState(sequence);
      next.set(sequence, { ...state, showRoleGrouped: !state.showRoleGrouped });
      return next;
    });
  };

  // Toggle individual role card expansion
  const toggleRoleCard = (sequence: number, cardKey: string) => {
    setEntryStates((prev) => {
      const next = new Map(prev);
      const state = getEntryState(sequence);
      const newExpandedCards = new Set(state.expandedRoleCards);
      if (newExpandedCards.has(cardKey)) {
        newExpandedCards.delete(cardKey);
      } else {
        newExpandedCards.add(cardKey);
      }
      next.set(sequence, { ...state, expandedRoleCards: newExpandedCards });
      return next;
    });
  };

  // Auto-scroll to top when new entries arrive (most recent is on top)
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
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

  // Reverse entries so most recent is on top
  const reversedEntries = [...entries].reverse();

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          Draft Insights
        </h2>
        <div className="flex items-center gap-3">
          {isLive && (
            <span className="text-xs text-magic animate-pulse">● LIVE</span>
          )}
        </div>
      </div>

      {/* Scrollable log - most recent on top */}
      <div
        ref={scrollRef}
        className="space-y-3 max-h-[600px] overflow-y-auto pr-2"
      >
        {reversedEntries.map((entry, idx) => {
          const isLatest = idx === 0;
          if (entry.kind === "marker") {
            const markerBorder = entry.winnerSide === "blue"
              ? "border-blue-team/60"
              : entry.winnerSide === "red"
                ? "border-red-team/60"
                : "border-gold-dim/20";
            return (
              <div
                key={`${entry.sessionId}-marker-${entry.timestamp}-${idx}`}
                className={`text-[11px] text-text-tertiary uppercase tracking-wide px-2 py-1 rounded bg-lol-darkest/70 border ${markerBorder}`}
              >
                <div>{entry.label}</div>
                {entry.score && (
                  <div className="text-[10px] text-text-secondary">
                    Score {entry.score.blue} - {entry.score.red}
                  </div>
                )}
              </div>
            );
          }

          const isBan = entry.action.action_type === "ban";
          const actionTeam = entry.action.team_side;
          const teamColor = actionTeam === "blue" ? "blue-team" : "red-team";
          const teamLabel = actionTeam === "blue" ? "Blue" : "Red";
          // Note: sequence may be string from backend, action_count is number - use Number() for consistency
          const rawSequence = entry.action.sequence;
          const sequenceNum = typeof rawSequence === "string" ? Number(rawSequence) : rawSequence;

          // Calculate action number using the actual action sequence and type
          const actionNum = calculateActionNumber(sequenceNum, isBan);

          // Get recommendations - use the correct array based on action type
          const recs: (PickRecommendation | BanRecommendation)[] = isBan
            ? entry.recommendations?.bans ?? []
            : entry.recommendations?.picks ?? [];
          const top5 = recs.slice(0, 5);
          const hasRecommendations = top5.length > 0;

          // Check if actual champion was recommended
          const actualChampion = entry.action.champion_name;
          const matchedRec = recs.find(r => r.champion_name === actualChampion);

          // Get associated LLM insight (keyed by action_count which matches sequence)
          const associatedInsight = llmInsights?.get(sequenceNum);
          const didTimeout = llmTimeouts?.has(sequenceNum);

          // Get entry UI state
          const entryState = getEntryState(sequenceNum);

          // Get role_grouped data if available (for picks only)
          const roleGrouped = !isBan ? entry.recommendations?.role_grouped : null;

          // Determine which team context to use for role info
          const forTeam = entry.recommendations?.for_team;
          const ourTeam = forTeam === "blue" ? blueTeam : forTeam === "red" ? redTeam : null;

          return (
            <div
              key={`${entry.sessionId}-${sequenceNum}`}
              className={`
                rounded-lg border p-3
                ${isLatest && isLive
                  ? "border-magic bg-magic/5"
                  : `border-${teamColor}/30 bg-lol-light/50`
                }
              `}
            >
              {/* Entry header with per-entry toggle */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded bg-${teamColor}/20 text-${teamColor}`}>
                    {teamLabel}
                  </span>
                  <span className="text-sm text-text-primary font-medium">
                    {isBan ? "Ban" : "Pick"} #{actionNum}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Per-entry By Role toggle - only for picks with role_grouped data */}
                  {roleGrouped && ourTeam && (
                    <button
                      onClick={() => toggleRoleGrouped(sequenceNum)}
                      className={`
                        text-xs px-2 py-0.5 rounded transition-colors
                        ${entryState.showRoleGrouped
                          ? "bg-magic/20 text-magic border border-magic/40"
                          : "bg-lol-light text-text-tertiary hover:text-text-secondary"
                        }
                      `}
                    >
                      {entryState.showRoleGrouped ? "Detailed" : "By Role"}
                    </button>
                  )}
                  {isLatest && isLive && (
                    <span className="text-xs bg-magic/20 text-magic px-2 py-0.5 rounded">
                      LIVE
                    </span>
                  )}
                </div>
              </div>

              {/* Inline AI Insight - show if available for this action */}
              {associatedInsight && (
                <InlineAIInsight
                  insight={associatedInsight}
                  actionType={isBan ? "ban" : "pick"}
                  isExpanded={entryState.aiInsightExpanded}
                  onToggle={() => toggleAIInsight(sequenceNum)}
                />
              )}

              {/* AI Timeout indicator */}
              {didTimeout && !associatedInsight && (
                <div className="text-xs text-warning bg-warning/10 border border-warning/30 rounded px-2 py-1 mb-2">
                  AI analysis timed out
                </div>
              )}

              {/* Recommendations - either role-grouped or detailed top 5 */}
              {hasRecommendations ? (
                entryState.showRoleGrouped && roleGrouped ? (
                  <div className="mb-2">
                    <div className="text-[10px] text-text-tertiary uppercase mb-1.5">
                      Top 2 by Role
                    </div>
                    <InlineRoleView
                      roleGrouped={roleGrouped}
                      expandedCards={entryState.expandedRoleCards}
                      onToggleCard={(key) => toggleRoleCard(sequenceNum, key)}
                    />
                  </div>
                ) : (
                  <div className="mb-2">
                    <div className="text-[10px] text-text-tertiary uppercase mb-1.5">
                      Top 5 Recommendations
                    </div>
                    <div className="flex gap-1.5 overflow-x-auto pb-1">
                      {top5.map((rec) => {
                        const isPick = "score" in rec;
                        const score = isPick
                          ? (rec as PickRecommendation).score ?? (rec as PickRecommendation).confidence
                          : (rec as BanRecommendation).priority;
                        const role = isPick ? (rec as PickRecommendation).suggested_role : null;

                        return (
                          <CompactRecommendationCard
                            key={rec.champion_name}
                            champion={rec.champion_name}
                            score={score}
                            role={role}
                            components={rec.components}
                            isMatch={rec.champion_name === actualChampion}
                            isPick={isPick}
                          />
                        );
                      })}
                    </div>
                  </div>
                )
              ) : (
                <div className="text-xs text-text-tertiary italic mb-2">
                  No recommendations available (draft complete)
                </div>
              )}

              {/* What actually happened */}
              <div className="flex items-center gap-2 p-2 rounded bg-lol-dark/50">
                <ChampionPortrait
                  championName={actualChampion}
                  state="picked"
                  className="w-8 h-8 rounded"
                />
                <div className="flex-1">
                  <span className="text-gold-bright font-medium">{actualChampion}</span>
                  {matchedRec && (
                    <span className="ml-2 text-success text-xs">
                      ✓ #{recs.indexOf(matchedRec) + 1} recommended
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
