// frontend/src/components/replay/InsightsLog/index.tsx
import { useEffect, useRef, useState } from "react";
import type {
  InsightEntry,
  PickRecommendation,
  BanRecommendation,
  TeamContext,
  LLMInsight,
} from "../../../types";
import { ChampionPortrait } from "../../shared/ChampionPortrait";
import {
  PICK_COMPONENT_LABELS,
  getTopBanComponents,
} from "../../../utils/scoreLabels";

interface InsightsLogProps {
  entries: InsightEntry[];
  isLive: boolean;
  blueTeam?: TeamContext | null;
  redTeam?: TeamContext | null;
  llmInsights?: Map<number, LLMInsight>;
  llmTimeouts?: Set<number>;
  isWaitingForLLM?: boolean;
  waitingForActionCount?: number | null;
}

// Helper to format component scores with color
// isWeighted: true for weighted components (both picks and bans use weighted display)
// Weighted scores use lower thresholds since max per component is ~0.35
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
  // Weighted scores use lower thresholds (max ~0.35 per component)
  // Raw scores (legacy) use original thresholds (0-1 scale)
  const color = isWeighted
    ? (value >= 0.20 ? "text-success" : value >= 0.10 ? "text-warning" : "text-danger")
    : (value >= 0.7 ? "text-success" : value >= 0.5 ? "text-warning" : "text-danger");
  return (
    <div className="flex justify-between text-xs">
      <span className="text-text-tertiary">{label}</span>
      <span className={`font-mono ${color}`}>{value.toFixed(2)}</span>
    </div>
  );
}


// Compact recommendation card showing champion + all scores
// On mobile: expandable to show details; on desktop: always shows details
function CompactRecommendationCard({
  champion,
  score,
  role,
  components,
  isMatch,
  isPick,
  isExpanded,
  onToggle,
}: {
  champion: string;
  score: number;
  role?: string | null;
  components?: Record<string, number>;
  isMatch: boolean;
  isPick: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const scoreColor =
    score >= 0.7 ? "text-success" :
    score >= 0.5 ? "text-warning" : "text-danger";

  const hasComponents = components && Object.keys(components).length > 0;

  return (
    <div
      className={`
        rounded border p-1.5 w-full
        ${isMatch
          ? "border-success bg-success/10"
          : "border-gold-dim/30 bg-lol-dark/50"
        }
      `}
    >
      {/* Header: champion + score - clickable on mobile to expand */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-1.5 text-left lg:cursor-default"
      >
        <ChampionPortrait
          championName={champion}
          state="picked"
          className="w-8 h-8 rounded-sm shrink-0"
        />
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-medium text-gold-bright truncate">
            {champion}
          </div>
          {isPick && role && (
            <div className="text-[9px] text-magic uppercase">{role}</div>
          )}
        </div>
        <span className={`text-sm font-bold ${scoreColor}`}>
          {Math.round(score * 100)}
        </span>
        {isMatch && <span className="text-success text-[10px]">✓</span>}
        {/* Mobile expand indicator */}
        {hasComponents && (
          <span className={`lg:hidden text-[10px] text-text-tertiary transition-transform ${isExpanded ? "rotate-90" : ""}`}>
            ▶
          </span>
        )}
      </button>

      {/* Component scores - expandable on mobile, always visible on desktop */}
      {hasComponents && (
        <div className={`
          overflow-hidden transition-all duration-200 ease-out
          ${isExpanded ? "max-h-48 opacity-100 mt-1" : "max-h-0 opacity-0 lg:max-h-48 lg:opacity-100 lg:mt-1"}
        `}>
          <div className="space-y-0 border-t border-gold-dim/20 pt-1">
            {isPick ? (
              <>
                {/* Tournament components */}
                {/* All pick components now use weighted display (same scale as bans) */}
                <ScoreCell label={PICK_COMPONENT_LABELS.tournament_priority} value={components.tournament_priority} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.tournament_performance} value={components.tournament_performance} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.proficiency} value={components.proficiency} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.matchup} value={components.matchup} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.counter} value={components.counter} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.archetype} value={components.archetype} isWeighted />
                <ScoreCell label={PICK_COMPONENT_LABELS.synergy} value={components.synergy} isWeighted />
              </>
            ) : (
              <>
                {getTopBanComponents(components).map((item) => (
                  <ScoreCell key={item.key} label={item.label} value={item.value} isWeighted />
                ))}
              </>
            )}
          </div>
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

// Note: For role utilities, use ../../utils/roles (ROLE_INFO, toDisplayRole, etc.)

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
                      className="w-8 h-8 rounded-sm shrink-0"
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
  expandedRecCards: Set<string>; // Track which recommendation cards are expanded (by champion name)
}

export function InsightsLog({
  entries,
  isLive,
  blueTeam: _blueTeam,  // Reserved for future role-grouped view
  redTeam: _redTeam,    // Reserved for future role-grouped view
  llmInsights,
  llmTimeouts,
  isWaitingForLLM = false,
  waitingForActionCount = null,
}: InsightsLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // Per-entry UI state (keyed by action sequence)
  const [entryStates, setEntryStates] = useState<Map<number, EntryUIState>>(new Map());

  // Helper to get or create entry state
  const getEntryState = (sequence: number): EntryUIState => {
    return entryStates.get(sequence) || {
      aiInsightExpanded: false,  // Start collapsed, user expands to view
      expandedRecCards: new Set(),
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

  // Toggle recommendation card expanded state for an entry
  const toggleRecCard = (sequence: number, championName: string) => {
    setEntryStates((prev) => {
      const next = new Map(prev);
      const state = getEntryState(sequence);
      const expandedRecCards = new Set(state.expandedRecCards);
      if (expandedRecCards.has(championName)) {
        expandedRecCards.delete(championName);
      } else {
        expandedRecCards.add(championName);
      }
      next.set(sequence, { ...state, expandedRecCards });
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

      {/* AI Analysis Loading Indicator */}
      {isWaitingForLLM && waitingForActionCount && (
        <div className="mb-3 border border-magic/30 bg-magic/5 rounded-lg p-3">
          <div className="flex items-center gap-3 text-magic">
            <div className="w-5 h-5 border-2 border-magic border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium">
              Analyzing Action #{waitingForActionCount}...
            </span>
          </div>
        </div>
      )}

      {/* Scrollable log - most recent on top */}
      <div className="relative">
        <div
          ref={scrollRef}
          className="space-y-3 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin"
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

              {/* Top Recommendations - 2x2 grid on mobile (top 4), horizontal scroll on desktop (top 5) */}
              {hasRecommendations ? (
                  <div className="mb-2">
                    <div className="text-[10px] text-text-tertiary uppercase mb-1.5">
                      Top Recommendations
                    </div>
                    {/* Mobile: 2x2 grid showing top 4 */}
                    <div className="grid grid-cols-2 gap-1.5 lg:hidden">
                      {top5.slice(0, 4).map((rec) => {
                        const isPick = "score" in rec;
                        const score = isPick
                          ? (rec as PickRecommendation).score ?? (rec as PickRecommendation).confidence
                          : (rec as BanRecommendation).priority;
                        const role = isPick ? (rec as PickRecommendation).suggested_role : null;
                        const components = isPick
                          ? ((rec as PickRecommendation).weighted_components ?? rec.components)
                          : rec.components;
                        const isCardExpanded = entryState.expandedRecCards.has(rec.champion_name);

                        return (
                          <CompactRecommendationCard
                            key={rec.champion_name}
                            champion={rec.champion_name}
                            score={score}
                            role={role}
                            components={components}
                            isMatch={rec.champion_name === actualChampion}
                            isPick={isPick}
                            isExpanded={isCardExpanded}
                            onToggle={() => toggleRecCard(sequenceNum, rec.champion_name)}
                          />
                        );
                      })}
                    </div>
                    {/* Desktop: horizontal row showing top 5 */}
                    <div className="hidden lg:flex gap-1.5 overflow-x-auto pb-1">
                      {top5.map((rec) => {
                        const isPick = "score" in rec;
                        const score = isPick
                          ? (rec as PickRecommendation).score ?? (rec as PickRecommendation).confidence
                          : (rec as BanRecommendation).priority;
                        const role = isPick ? (rec as PickRecommendation).suggested_role : null;
                        const components = isPick
                          ? ((rec as PickRecommendation).weighted_components ?? rec.components)
                          : rec.components;

                        return (
                          <CompactRecommendationCard
                            key={rec.champion_name}
                            champion={rec.champion_name}
                            score={score}
                            role={role}
                            components={components}
                            isMatch={rec.champion_name === actualChampion}
                            isPick={isPick}
                            isExpanded={true}
                            onToggle={() => {}}
                          />
                        );
                      })}
                    </div>
                  </div>
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
                  className="w-10 h-10 rounded"
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
        {/* Fade gradient hint at bottom when content overflows */}
        <div className="pointer-events-none absolute bottom-0 left-0 right-2 h-8 bg-gradient-to-t from-lol-dark to-transparent" />
      </div>
    </div>
  );
}
