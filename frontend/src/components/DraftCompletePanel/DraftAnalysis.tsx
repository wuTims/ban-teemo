import { MetricBar } from "../shared";
import type { TeamContext } from "../../types";

interface DraftAnalysisProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  blueData: {
    synergy_score: number;
    composition_score: number;
    archetype: string | null;
  };
  redData: {
    synergy_score: number;
    composition_score: number;
    archetype: string | null;
  };
  matchupAdvantage: number;
}

function getSynergyExplanation(score: number): string {
  if (score >= 0.6) return "Good champion synergies";
  if (score >= 0.4) return "Average synergies";
  return "Poor champion synergies";
}

function getCompositionExplanation(score: number, archetype: string | null): string {
  if (score >= 0.6) return `Strong ${archetype ?? "team"} identity`;
  if (score >= 0.4) return "Balanced composition";
  return "Lacks clear identity";
}

export function DraftAnalysis({
  blueTeam,
  redTeam,
  blueData,
  redData,
  matchupAdvantage,
}: DraftAnalysisProps) {
  const favoredTeam = matchupAdvantage > 0 ? "blue" : matchupAdvantage < 0 ? "red" : null;
  const favoredName = favoredTeam === "blue" ? blueTeam.name : favoredTeam === "red" ? redTeam.name : null;
  const advantageAbs = Math.abs(matchupAdvantage);

  return (
    <div className="bg-lol-dark rounded-lg p-4 border border-gold-dim/30">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright text-center mb-4">
        Draft Analysis
      </h3>

      <div className="grid grid-cols-2 gap-6">
        {/* Blue Team Column */}
        <div className="space-y-3">
          <div className="text-xs font-semibold text-blue-team uppercase text-center mb-2">
            {blueTeam.name}
          </div>
          <MetricBar
            label="Synergy"
            value={blueData.synergy_score}
            explanation={getSynergyExplanation(blueData.synergy_score)}
          />
          <MetricBar
            label="Composition"
            value={blueData.composition_score}
            explanation={getCompositionExplanation(blueData.composition_score, blueData.archetype)}
          />
          <div className="text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{blueData.archetype ?? "None"}</span>
          </div>
        </div>

        {/* Red Team Column */}
        <div className="space-y-3">
          <div className="text-xs font-semibold text-red-team uppercase text-center mb-2">
            {redTeam.name}
          </div>
          <MetricBar
            label="Synergy"
            value={redData.synergy_score}
            explanation={getSynergyExplanation(redData.synergy_score)}
          />
          <MetricBar
            label="Composition"
            value={redData.composition_score}
            explanation={getCompositionExplanation(redData.composition_score, redData.archetype)}
          />
          <div className="text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{redData.archetype ?? "None"}</span>
          </div>
        </div>
      </div>

      {/* Matchup Indicator */}
      <div className="mt-4 pt-3 border-t border-gold-dim/20 text-center">
        <span className="text-xs text-text-secondary">Matchup: </span>
        {favoredTeam ? (
          <span className={`text-xs font-semibold ${favoredTeam === "blue" ? "text-blue-team" : "text-red-team"}`}>
            {favoredName} favored ({advantageAbs > 0 ? "+" : ""}{(matchupAdvantage * 100).toFixed(0)}%)
          </span>
        ) : (
          <span className="text-xs text-text-tertiary">Even matchup</span>
        )}
      </div>
    </div>
  );
}
