// frontend/src/components/replay/DraftBoard/index.tsx
import { TeamPanel, PhaseIndicator } from "../../shared";
import { ReplayBanTrack } from "../ReplayBanTrack";
import type { TeamContext, DraftState, Team, ActionType, FinalizedPick } from "../../../types";

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
    <div className="bg-lol-dark rounded-lg p-3 sm:p-4 xl:p-6">
      {/* Phase Indicator - Top Center */}
      <div className="flex justify-center mb-3 sm:mb-4 xl:mb-6">
        <PhaseIndicator
          currentPhase={phase}
          nextTeam={nextTeam}
          nextAction={nextAction}
        />
      </div>

      {/* Main Draft Layout - Vertical on mobile, 3-column grid on desktop */}
      <div className="flex flex-col gap-3 sm:gap-4 xl:grid xl:grid-cols-[1fr_auto_1fr] xl:gap-6 xl:items-start">
        {/* Blue Team Panel */}
        <TeamPanel
          team={blueTeam}
          picks={bluePicks}
          side="blue"
          isActive={nextTeam === "blue" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(bluePicks, nextTeam, nextAction, "blue")}
          picksWithRoles={blueCompWithRoles ?? undefined}
          players={blueTeam?.players}
        />

        {/* Center: Ban Track + Action Counter */}
        <div className="flex flex-col items-center xl:pt-8">
          <ReplayBanTrack
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
          <div className="mt-3 sm:mt-4 xl:mt-6 text-center">
            <div className="text-2xl sm:text-3xl font-bold text-gold-bright">
              {draftState?.action_count ?? 0}
            </div>
            <div className="text-[10px] sm:text-xs text-text-tertiary uppercase">
              / 20 actions
            </div>
          </div>
        </div>

        {/* Red Team Panel */}
        <TeamPanel
          team={redTeam}
          picks={redPicks}
          side="red"
          isActive={nextTeam === "red" && nextAction === "pick"}
          currentPickIndex={getCurrentPickIndex(redPicks, nextTeam, nextAction, "red")}
          picksWithRoles={redCompWithRoles ?? undefined}
          players={redTeam?.players}
        />
      </div>
    </div>
  );
}
