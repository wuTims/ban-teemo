// frontend/src/components/simulator/SimulatorBanRow.tsx
// Displays bans in a horizontal row layout for Simulator mode
import { ChampionPortrait } from "../shared";

interface SimulatorBanRowProps {
  blueBans: string[];
  redBans: string[];
}

export function SimulatorBanRow({ blueBans, redBans }: SimulatorBanRowProps) {
  // Show Teemo placeholders only in pristine state (no bans yet)
  const hasBans = blueBans.length > 0 || redBans.length > 0;

  const renderBans = (bans: string[], _side: "blue" | "red") => (
    <div className="flex gap-1 sm:gap-1.5 lg:gap-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <ChampionPortrait
          key={i}
          championName={bans[i]}
          state={bans[i] ? "banned" : "empty"}
          className="w-12 h-12 lg:w-[66px] lg:h-[66px] 2xl:w-[88px] 2xl:h-[88px] shrink-0"
          placeholderChampion={hasBans ? undefined : "Teemo"}
        />
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
