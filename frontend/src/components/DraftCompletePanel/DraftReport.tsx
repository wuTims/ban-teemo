import type { DraftQuality, TeamContext } from "../../types";
import { getTeamAbbreviation } from "../../data/teamAbbreviations";

interface DraftReportCardProps {
  teamName: string;
  teamSide: "blue" | "red";
  quality: DraftQuality;
}

function getPicksMatchedLabel(matched: number, total: number): string {
  if (matched === total) return "Strongly aligned";
  if (matched >= total * 0.6) return "Good alignment";
  if (matched >= total * 0.4) return "Partial alignment";
  return "Independent approach";
}

function getDeltaLabel(delta: number): string {
  if (delta > 0.02) return "Engine would've scored higher";
  if (delta < -0.02) return "Outperformed engine";
  return "Similar outcome";
}

function DraftReportCard({ teamName, teamSide, quality }: DraftReportCardProps) {
  const { comparison } = quality;
  const picksMatched = comparison.picks_matched;
  const picksTotal = comparison.picks_tracked;
  const scoreDelta = comparison.score_delta;

  const deltaColor = scoreDelta > 0.02 ? "text-danger" : scoreDelta < -0.02 ? "text-success" : "text-text-tertiary";
  const abbreviatedName = getTeamAbbreviation(teamName);

  return (
    <div className={`bg-lol-light rounded-lg p-2 xs:p-3 border ${teamSide === "blue" ? "border-blue-team/30" : "border-red-team/30"}`}>
      <h4 className={`text-xs font-semibold uppercase text-center mb-2 xs:mb-3 ${teamSide === "blue" ? "text-blue-team" : "text-red-team"}`} title={teamName}>
        {abbreviatedName}'s Report
      </h4>

      {/* Picks in Top 5 */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-text-tertiary uppercase">Picks in Top 5</span>
          <span className="text-xs font-mono text-text-primary">{picksMatched}/{picksTotal}</span>
        </div>
        <div className="flex gap-1">
          {Array.from({ length: picksTotal }).map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i < picksMatched ? "bg-magic" : "bg-lol-dark"}`}
            />
          ))}
        </div>
        <p className="text-[10px] text-text-tertiary mt-1">{getPicksMatchedLabel(picksMatched, picksTotal)}</p>
      </div>

      {/* Score Delta */}
      <div className="mb-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-text-tertiary uppercase">vs Engine</span>
          <span className={`text-xs font-mono ${deltaColor}`}>
            {scoreDelta >= 0 ? "+" : ""}{(scoreDelta * 100).toFixed(1)}%
          </span>
        </div>
        <p className="text-[10px] text-text-tertiary mt-1">{getDeltaLabel(scoreDelta)}</p>
      </div>

      {/* Archetype Insight */}
      <div className="pt-2 border-t border-gold-dim/20">
        <p className="text-[10px] text-text-secondary italic leading-relaxed">
          "{comparison.archetype_insight}"
        </p>
      </div>
    </div>
  );
}

interface DraftReportProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  blueDraftQuality?: DraftQuality | null;
  redDraftQuality?: DraftQuality | null;
}

export function DraftReport({ blueTeam, redTeam, blueDraftQuality, redDraftQuality }: DraftReportProps) {
  const hasBlue = !!blueDraftQuality;
  const hasRed = !!redDraftQuality;

  if (!hasBlue && !hasRed) return null;

  return (
    <div className="bg-lol-dark rounded-lg p-3 xs:p-4 border border-gold-dim/30">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright text-center mb-3 xs:mb-4">
        Draft Report
      </h3>

      <div className={`grid gap-3 xs:gap-4 ${hasBlue && hasRed ? "grid-cols-1 xs:grid-cols-2" : "grid-cols-1 max-w-sm mx-auto"}`}>
        {hasBlue && (
          <DraftReportCard teamName={blueTeam.name} teamSide="blue" quality={blueDraftQuality} />
        )}
        {hasRed && (
          <DraftReportCard teamName={redTeam.name} teamSide="red" quality={redDraftQuality} />
        )}
      </div>
    </div>
  );
}
