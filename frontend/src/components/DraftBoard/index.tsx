// frontend/src/components/DraftBoard/index.tsx
import { TeamPanel, BanTrack, PhaseIndicator } from "../draft";
import type { TeamContext, DraftState, Team, ActionType, FinalizedPick } from "../../types";

interface DraftBoardProps {
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
  blueCompWithRoles?: FinalizedPick[] | null;
  redCompWithRoles?: FinalizedPick[] | null;
}

// Calculate which pick slot is active (0-4 index)
function getCurrentPickIndex(
  picks: string[],
  nextTeam: Team | null,
  nextAction: ActionType | null,
  side: Team
): number | undefined {
  if (nextAction !== "pick" || nextTeam !== side) return undefined;
  return picks.length; // Next empty slot
}

export function DraftBoard({ blueTeam, redTeam, draftState, blueCompWithRoles, redCompWithRoles }: DraftBoardProps) {
  const phase = draftState?.phase ?? "BAN_PHASE_1";
  const nextTeam = draftState?.next_team ?? null;
  const nextAction = draftState?.next_action ?? null;
  const blueBans = draftState?.blue_bans ?? [];
  const redBans = draftState?.red_bans ?? [];
  const bluePicks = draftState?.blue_picks ?? [];
  const redPicks = draftState?.red_picks ?? [];

  return (
    <div className="bg-lol-dark rounded-lg p-6">
      {/* Phase Indicator - Top Center */}
      <div className="flex justify-center mb-6">
        <PhaseIndicator
          currentPhase={phase}
          nextTeam={nextTeam}
          nextAction={nextAction}
        />
      </div>

      {/* Main Draft Grid */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-6 items-start">
        {/* Blue Team Panel - Left */}
        <TeamPanel
          team={blueTeam}
          picks={bluePicks}
          side="blue"
          isActive={nextTeam === "blue" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(bluePicks, nextTeam, nextAction, "blue")}
          picksWithRoles={blueCompWithRoles ?? undefined}
        />

        {/* Center: Ban Track */}
        <div className="flex flex-col items-center pt-8">
          <BanTrack
            blueBans={blueBans}
            redBans={redBans}
            currentBanTeam={nextAction === "ban" ? nextTeam : null}
            currentBanIndex={
              nextAction === "ban" && nextTeam
                ? (nextTeam === "blue" ? blueBans.length : redBans.length)
                : undefined
            }
          />

          {/* Action Counter */}
          <div className="mt-6 text-center">
            <div className="text-3xl font-bold text-gold-bright">
              {draftState?.action_count ?? 0}
            </div>
            <div className="text-xs text-text-tertiary uppercase">
              / 20 actions
            </div>
          </div>
        </div>

        {/* Red Team Panel - Right */}
        <TeamPanel
          team={redTeam}
          picks={redPicks}
          side="red"
          isActive={nextTeam === "red" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(redPicks, nextTeam, nextAction, "red")}
          picksWithRoles={redCompWithRoles ?? undefined}
        />
      </div>
    </div>
  );
}
