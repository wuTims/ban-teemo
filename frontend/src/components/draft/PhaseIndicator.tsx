// frontend/src/components/draft/PhaseIndicator.tsx
import type { DraftPhase, Team, ActionType } from "../../types";

interface PhaseIndicatorProps {
  currentPhase: DraftPhase;
  nextTeam: Team | null;
  nextAction: ActionType | null;
}

const PHASES: Array<{ id: DraftPhase; label: string }> = [
  { id: "BAN_PHASE_1", label: "Ban 1" },
  { id: "PICK_PHASE_1", label: "Pick 1" },
  { id: "BAN_PHASE_2", label: "Ban 2" },
  { id: "PICK_PHASE_2", label: "Pick 2" },
];

export function PhaseIndicator({
  currentPhase,
  nextTeam,
  nextAction,
}: PhaseIndicatorProps) {
  const currentIndex = PHASES.findIndex(p => p.id === currentPhase);
  const isComplete = currentPhase === "COMPLETE";

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Phase Pills */}
      <div className="flex items-center gap-2">
        {PHASES.map((phase, i) => {
          const isActive = phase.id === currentPhase;
          const isPast = currentIndex > i || isComplete;

          return (
            <div
              key={phase.id}
              className={`
                px-3 py-1.5 rounded text-xs uppercase tracking-widest font-semibold
                transition-all duration-300
                ${isActive
                  ? "bg-magic text-lol-darkest shadow-[0_0_20px_rgba(10,200,185,0.4)]"
                  : isPast
                    ? "bg-gold-dark text-gold-dim"
                    : "bg-lol-light text-text-tertiary"
                }
              `}
            >
              {phase.label}
            </div>
          );
        })}
      </div>

      {/* Current Action Indicator */}
      {!isComplete && nextTeam && nextAction && (
        <div className="flex items-center gap-2 text-sm">
          <span className={`
            font-semibold uppercase
            ${nextTeam === "blue" ? "text-blue-team" : "text-red-team"}
          `}>
            {nextTeam}
          </span>
          <span className="text-text-secondary">
            {nextAction === "ban" ? "banning" : "picking"}
          </span>
        </div>
      )}

      {isComplete && (
        <div className="text-sm text-success font-semibold uppercase tracking-wide">
          Draft Complete
        </div>
      )}
    </div>
  );
}
