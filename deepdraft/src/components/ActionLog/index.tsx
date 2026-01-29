import { useEffect, useRef } from "react";
import { CHAMPION_ICON_SIZE_CLASS, ChampionPortrait } from "../shared";
import type { DraftAction, TeamContext } from "../../types";

interface ActionLogProps {
  actions: DraftAction[];
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
}

export function ActionLog({ actions, blueTeam, redTeam }: ActionLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new actions arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [actions.length]);

  const getTeamName = (side: "blue" | "red"): string => {
    if (side === "blue") return blueTeam?.name ?? "Blue Team";
    return redTeam?.name ?? "Red Team";
  };

  return (
    <div className="w-72 bg-lol-dark rounded-lg border border-gold-dim/30 flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gold-dim/30">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gold-bright">
          Draft Log
        </h2>
      </div>

      {/* Action list */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-2 max-h-[500px]"
      >
        {actions.length === 0 ? (
          <p className="text-text-tertiary text-sm text-center py-4">
            Waiting for draft to begin...
          </p>
        ) : (
          actions.map((action) => (
            <ActionEntry
              key={action.sequence}
              action={action}
              teamName={getTeamName(action.team_side)}
            />
          ))
        )}
      </div>
    </div>
  );
}

interface ActionEntryProps {
  action: DraftAction;
  teamName: string;
}

function ActionEntry({ action, teamName }: ActionEntryProps) {
  const isBan = action.action_type === "ban";
  const teamColorClass = action.team_side === "blue" ? "text-blue-team" : "text-red-team";

  return (
    <div className="flex items-center gap-3 p-2 rounded bg-lol-darkest/50">
      <ChampionPortrait
        championName={action.champion_name}
        state={isBan ? "banned" : "picked"}
        team={action.team_side}
        className={`${CHAMPION_ICON_SIZE_CLASS} shrink-0`}
      />
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${teamColorClass}`}>
          {teamName}
        </p>
        <p className="text-xs text-text-tertiary">
          {isBan ? "banned" : "picked"}{" "}
          <span className="text-text-secondary">{action.champion_name}</span>
        </p>
      </div>
    </div>
  );
}
