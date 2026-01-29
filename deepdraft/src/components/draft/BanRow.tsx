// deepdraft/src/components/draft/BanRow.tsx
import { ChampionPortrait } from "../shared/ChampionPortrait";

interface BanRowProps {
  blueBans: string[];
  redBans: string[];
}

export function BanRow({ blueBans, redBans }: BanRowProps) {
  const renderBans = (bans: string[], side: "blue" | "red") => (
    <div className="flex gap-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className={`w-10 h-10 rounded border ${
            side === "blue" ? "border-blue-team/30" : "border-red-team/30"
          } bg-lol-light flex items-center justify-center overflow-hidden`}
        >
          {bans[i] ? (
            <ChampionPortrait championName={bans[i]} size="sm" state="banned" />
          ) : (
            <span className="text-text-tertiary text-xs">-</span>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div className="flex justify-center items-center gap-8 py-3 bg-lol-dark/50 rounded">
      <div className="flex items-center gap-2">
        <span className="text-xs text-blue-team uppercase font-medium">Blue Bans</span>
        {renderBans(blueBans, "blue")}
      </div>
      <div className="w-px h-8 bg-gold-dim/30" />
      <div className="flex items-center gap-2">
        {renderBans(redBans, "red")}
        <span className="text-xs text-red-team uppercase font-medium">Red Bans</span>
      </div>
    </div>
  );
}
