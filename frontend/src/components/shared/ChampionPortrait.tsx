// frontend/src/components/shared/ChampionPortrait.tsx
import { getCachedChampionIconUrl } from "../../utils";
import type { Team } from "../../types";

type PortraitState = "empty" | "picking" | "picked" | "banned";

interface ChampionPortraitProps {
  championName?: string | null;
  state?: PortraitState;
  team?: Team | null;
  className?: string;
  imageClassName?: string;
}

export function ChampionPortrait({
  championName,
  state = "empty",
  team = null,
  className = "",
  imageClassName = "",
}: ChampionPortraitProps) {
  // bg-lol-dark provides a dark placeholder matching icon colors to reduce flash
  const baseClasses = "relative rounded-sm overflow-hidden bg-lol-dark";

  // State-specific styles
  const stateClasses: Record<PortraitState, string> = {
    empty: "border-2 border-gold-dim bg-lol-darkest",
    picking: "border-2 border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)] animate-[magic-pulse_2s_ease-in-out_infinite]",
    picked: team === "blue"
      ? "border-2 border-blue-team"
      : "border-2 border-red-team",
    banned: "border-2 border-red-team grayscale opacity-60",
  };

  if (state === "empty" || !championName) {
    return (
      <div className={`${baseClasses} ${stateClasses.empty} ${className}`}>
        <div className="w-full h-full flex items-center justify-center">
          <span className="text-gold-dim text-lg">?</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${baseClasses} ${stateClasses[state]} ${className}`}>
      <img
        src={getCachedChampionIconUrl(championName)}
        alt={championName}
        loading="eager"
        decoding="sync"
        className={`w-full h-full object-cover ${imageClassName}`}
      />
      {state === "banned" && (
        <div className="absolute inset-0 flex items-center justify-center bg-lol-darkest/40">
          <span className="text-red-team text-2xl font-bold">✕</span>
        </div>
      )}
    </div>
  );
}
