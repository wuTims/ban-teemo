import { MetricBar } from "../shared";
import type { TeamContext } from "../../types";
import { getTeamAbbreviation } from "../../data/teamAbbreviations";

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

function getMatchupDescription(
  advantage: number,
  blueArch: string | null,
  redArch: string | null,
): { text: string; favoredTeam: "blue" | "red" | null } {
  // advantage is a multiplier: >1.0 = blue favored, <1.0 = red favored
  const blueArchLabel = blueArch ?? "comp";
  const redArchLabel = redArch ?? "comp";

  // Same archetype = mirror matchup
  if (blueArch && redArch && blueArch === redArch) {
    return { text: `Mirror ${blueArch} matchup`, favoredTeam: null };
  }

  // Determine advantage level
  if (advantage > 1.1) {
    return { text: `${blueArchLabel} favored vs ${redArchLabel}`, favoredTeam: "blue" };
  } else if (advantage < 0.9) {
    return { text: `${redArchLabel} favored vs ${blueArchLabel}`, favoredTeam: "red" };
  } else if (advantage > 1.01) {
    return { text: `${blueArchLabel} slightly favored vs ${redArchLabel}`, favoredTeam: "blue" };
  } else if (advantage < 0.99) {
    return { text: `${redArchLabel} slightly favored vs ${blueArchLabel}`, favoredTeam: "red" };
  }
  return { text: "Even matchup", favoredTeam: null };
}

export function DraftAnalysis({
  blueTeam,
  redTeam,
  blueData,
  redData,
  matchupAdvantage,
}: DraftAnalysisProps) {
  const matchup = getMatchupDescription(matchupAdvantage, blueData.archetype, redData.archetype);

  return (
    <div className="bg-lol-dark rounded-lg p-3 xs:p-4 border border-gold-dim/30">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright text-center mb-3 xs:mb-4">
        Draft Analysis
      </h3>

      <div className="grid grid-cols-2 gap-3 xs:gap-6">
        {/* Blue Team Column */}
        <div className="space-y-2 xs:space-y-3">
          <div className="text-xs font-semibold text-blue-team uppercase text-center mb-2" title={blueTeam.name}>
            {getTeamAbbreviation(blueTeam.name)}
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
          <div className="text-[10px] xs:text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{blueData.archetype ?? "None"}</span>
          </div>
        </div>

        {/* Red Team Column */}
        <div className="space-y-2 xs:space-y-3">
          <div className="text-xs font-semibold text-red-team uppercase text-center mb-2" title={redTeam.name}>
            {getTeamAbbreviation(redTeam.name)}
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
          <div className="text-[10px] xs:text-xs text-text-secondary">
            Archetype: <span className="text-gold-dim">{redData.archetype ?? "None"}</span>
          </div>
        </div>
      </div>

      {/* Matchup Indicator */}
      <div className="mt-4 pt-3 border-t border-gold-dim/20 text-center">
        <span className="text-xs text-text-secondary">Matchup: </span>
        <span className={`text-xs font-semibold ${
          matchup.favoredTeam === "blue" ? "text-blue-team" :
          matchup.favoredTeam === "red" ? "text-red-team" :
          "text-text-tertiary"
        }`}>
          {matchup.text}
        </span>
      </div>
    </div>
  );
}
