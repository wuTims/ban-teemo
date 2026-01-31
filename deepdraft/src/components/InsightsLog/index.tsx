// deepdraft/src/components/InsightsLog/index.tsx
import { useEffect, useRef, useState } from "react";
import type { InsightEntry, PickRecommendation, BanRecommendation, TeamContext } from "../../types";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import { RoleRecommendationPanel } from "../recommendations/RoleRecommendationPanel";

interface InsightsLogProps {
  entries: InsightEntry[];
  isLive: boolean;
  blueTeam?: TeamContext | null;
  redTeam?: TeamContext | null;
}

// Helper to format component scores with color
function ScoreCell({ label, value }: { label: string; value: number | undefined }) {
  if (value === undefined) return null;
  const color =
    value >= 0.7 ? "text-success" :
    value >= 0.5 ? "text-warning" : "text-danger";
  return (
    <div className="flex justify-between text-[10px]">
      <span className="text-text-tertiary">{label}</span>
      <span className={`font-mono ${color}`}>{value.toFixed(2)}</span>
    </div>
  );
}

const BAN_COMPONENT_LABELS: Record<string, string> = {
  presence: "pres",
  flex: "flex",
  archetype_counter: "arch",
  synergy_denial: "syn",
  role_denial: "role",
  counter: "cntr",
  proficiency: "prof",
  meta: "meta",
  comfort: "comf",
  confidence_bonus: "conf",
  pool_depth_bonus: "pool",
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
              <ScoreCell label="meta" value={components.meta} />
              <ScoreCell label="prof" value={components.proficiency} />
              <ScoreCell label="match" value={components.matchup} />
              <ScoreCell label="count" value={components.counter} />
              <ScoreCell label="arch" value={components.archetype} />
              <ScoreCell label="syn" value={components.synergy} />
            </>
          ) : (
            <>
              {getTopBanComponents(components).map((item) => (
                <ScoreCell key={item.label} label={item.label} value={item.value} />
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

export function InsightsLog({ entries, isLive, blueTeam, redTeam }: InsightsLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // Toggle for role-grouped view - defaults to OFF (primary view)
  const [showRoleGrouped, setShowRoleGrouped] = useState(false);

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

  // Get the latest action entry for role-grouped display
  const latestActionEntry = reversedEntries.find(e => e.kind === "action");
  const latestRoleGrouped = latestActionEntry?.kind === "action"
    ? latestActionEntry.recommendations?.role_grouped
    : null;

  // Determine which team to show role-grouped for (from latest recommendation)
  const latestForTeam = latestActionEntry?.kind === "action"
    ? latestActionEntry.recommendations?.for_team
    : null;
  const ourTeam = latestForTeam === "blue" ? blueTeam : latestForTeam === "red" ? redTeam : null;

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg uppercase tracking-wide text-gold-bright">
          Draft Insights
        </h2>
        <div className="flex items-center gap-3">
          {/* Role-grouped toggle - only show if we have role_grouped data */}
          {latestRoleGrouped && ourTeam && (
            <button
              onClick={() => setShowRoleGrouped(!showRoleGrouped)}
              className={`
                text-xs px-2 py-1 rounded transition-colors
                ${showRoleGrouped
                  ? "bg-magic/20 text-magic border border-magic/40"
                  : "bg-lol-light text-text-tertiary hover:text-text-secondary"
                }
              `}
            >
              By Role
            </button>
          )}
          {isLive && (
            <span className="text-xs text-magic animate-pulse">● LIVE</span>
          )}
        </div>
      </div>

      {/* Role-Grouped Panel (supplemental view) */}
      {showRoleGrouped && latestRoleGrouped && ourTeam && (
        <div className="mb-4">
          <RoleRecommendationPanel
            roleGrouped={latestRoleGrouped}
            ourTeam={ourTeam}
          />
        </div>
      )}

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

          // Calculate action number using the actual action sequence and type
          const actionNum = calculateActionNumber(entry.action.sequence, isBan);

          // Get recommendations - use the correct array based on action type
          const recs: (PickRecommendation | BanRecommendation)[] = isBan
            ? entry.recommendations?.bans ?? []
            : entry.recommendations?.picks ?? [];
          const top5 = recs.slice(0, 5);
          const hasRecommendations = top5.length > 0;

          // Check if actual champion was recommended
          const actualChampion = entry.action.champion_name;
          const matchedRec = recs.find(r => r.champion_name === actualChampion);

          return (
            <div
              key={`${entry.sessionId}-${entry.action.sequence}`}
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
                    {isBan ? "Ban" : "Pick"} #{actionNum}
                  </span>
                </div>
                {isLatest && isLive && (
                  <span className="text-xs bg-magic/20 text-magic px-2 py-0.5 rounded">
                    LIVE
                  </span>
                )}
              </div>

              {/* What actually happened */}
              <div className="flex items-center gap-2 mb-2 p-2 rounded bg-lol-dark/50">
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
                  {!matchedRec && hasRecommendations && (
                    <span className="ml-2 text-warning text-xs">
                      ✗ Not in top 5
                    </span>
                  )}
                </div>
              </div>

              {/* Top 5 recommendations as horizontal row */}
              {hasRecommendations ? (
                <div>
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
              ) : (
                <div className="text-xs text-text-tertiary italic">
                  No recommendations available (draft complete)
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
