// frontend/src/components/draft/BanRow.tsx
import { BAN_ICON_SIZE_CLASS, ChampionPortrait } from "../shared";

interface BanRowProps {
  blueBans: string[];
  redBans: string[];
}

export function BanRow({ blueBans, redBans }: BanRowProps) {
  const renderBans = (bans: string[], side: "blue" | "red") => (
    <div className="flex gap-1 sm:gap-1.5 lg:gap-2">
      {[0, 1, 2, 3, 4].map((i) => (
        bans[i] ? (
          <ChampionPortrait
            key={i}
            championName={bans[i]}
            state="banned"
            className={`${BAN_ICON_SIZE_CLASS} shrink-0`}
          />
        ) : (
          <div
            key={i}
            className={`${BAN_ICON_SIZE_CLASS} shrink-0 rounded-sm overflow-hidden border-2 ${
              side === "blue" ? "border-blue-team/30" : "border-red-team/30"
            } bg-lol-light flex items-center justify-center`}
          >
            <span className="text-text-tertiary text-[10px] lg:text-xs">-</span>
          </div>
        )
      ))}
    </div>
  );

  return (
    <div className="flex flex-col sm:flex-row justify-center items-center gap-2 sm:gap-4 lg:gap-8 py-2 lg:py-3 bg-lol-dark/50 rounded">
      <div className="flex items-center gap-1.5 sm:gap-2">
        <span className="text-[10px] sm:text-xs text-blue-team uppercase font-medium whitespace-nowrap">Blue</span>
        {renderBans(blueBans, "blue")}
      </div>
      <div className="hidden sm:block w-px h-8 bg-gold-dim/30" />
      <div className="flex items-center gap-1.5 sm:gap-2">
        {renderBans(redBans, "red")}
        <span className="text-[10px] sm:text-xs text-red-team uppercase font-medium whitespace-nowrap">Red</span>
      </div>
    </div>
  );
}
