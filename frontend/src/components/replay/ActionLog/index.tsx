import { useEffect, useRef } from "react";
import { ChampionPortrait } from "../../shared";
import type { DraftAction, ReplayActionLogEntry, TeamContext } from "../../../types";

interface ActionLogProps {
  actions: ReplayActionLogEntry[];
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
    <div className="w-full 2xl:w-72 bg-lol-dark rounded-lg border border-gold-dim/30 flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gold-dim/30">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gold-bright">
          Draft Log
        </h2>
      </div>

      {/* Action list */}
      <div className="relative flex-1">
        <div
          ref={scrollRef}
          className="overflow-y-auto p-3 space-y-2 max-h-[400px] 2xl:max-h-[750px] scrollbar-thin"
        >
        {actions.length === 0 ? (
          <p className="text-text-tertiary text-sm text-center py-4">
            Waiting for draft to begin...
          </p>
        ) : (
          actions.map((entry, index) => {
            if (entry.kind === "marker") {
              const markerBorder = entry.winnerSide === "blue"
                ? "border-blue-team/60"
                : entry.winnerSide === "red"
                  ? "border-red-team/60"
                  : "border-gold-dim/20";
              return (
                <div
                  key={`${entry.sessionId}-marker-${entry.timestamp}-${index}`}
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

            return (
              <ActionEntry
                key={`${entry.sessionId}-${entry.action.sequence}`}
                action={entry.action}
                teamName={getTeamName(entry.action.team_side)}
              />
            );
          })
        )}
        </div>
        {/* Fade gradient hint at bottom when content overflows */}
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-lol-dark to-transparent" />
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
        className="w-11 h-11 lg:w-[88px] lg:h-[88px] 2xl:w-[104px] 2xl:h-[104px] shrink-0"
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
