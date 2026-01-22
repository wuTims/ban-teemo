/**
 * DraftBoard - Main draft visualization component.
 * Shows the 10-slot draft grid with bans and picks.
 */

import { getChampionIconUrl } from "../../utils";

// Sample champions to demonstrate icon loading
const SAMPLE_CHAMPIONS = [
  "Jinx",
  "K'Sante",
  "Wukong",      // Tests MonkeyKing mapping
  "Lee Sin",     // Tests space removal
  "Kai'Sa",      // Tests apostrophe
  "Aurelion Sol",
  "Bel'Veth",
  "Cho'Gath",
  "Nunu & Willump",
  "Dr. Mundo",
];

export function DraftBoard() {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Draft Board</h2>

      {/* Demo: Champion icons from Data Dragon CDN */}
      <div className="mb-6">
        <p className="text-gray-400 text-sm mb-3">
          Champion icons (via Riot Data Dragon CDN):
        </p>
        <div className="grid grid-cols-5 gap-3">
          {SAMPLE_CHAMPIONS.map((name) => (
            <div key={name} className="flex flex-col items-center">
              <img
                src={getChampionIconUrl(name)}
                alt={name}
                className="w-16 h-16 rounded border-2 border-gray-700 hover:border-blue-500 transition-colors"
                loading="lazy"
              />
              <span className="text-xs text-gray-400 mt-1 text-center truncate w-full">
                {name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* TODO: Implement full draft grid */}
      <div className="border-t border-gray-700 pt-4">
        <p className="text-gray-500 text-sm">Full draft UI coming soon...</p>
      </div>
    </div>
  );
}
