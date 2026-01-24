// deepdraft/src/components/ReplayControls/index.tsx
import { useState, useEffect } from "react";
import type { SeriesInfo, GameInfo } from "../../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type SessionStatus = "idle" | "connecting" | "playing" | "complete" | "error";

interface ReplayControlsProps {
  status: SessionStatus;
  onStart: (seriesId: string, gameNumber: number, speed?: number) => void;
  onStop: () => void;
  error: string | null;
}

export function ReplayControls({
  status,
  onStart,
  onStop,
  error,
}: ReplayControlsProps) {
  const [seriesList, setSeriesList] = useState<SeriesInfo[]>([]);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [selectedSeries, setSelectedSeries] = useState<string>("");
  const [selectedGame, setSelectedGame] = useState<number>(1);
  const [speed, setSpeed] = useState<number>(1.0);

  // Fetch series list on mount
  useEffect(() => {
    async function fetchSeries() {
      try {
        const res = await fetch(`${API_BASE}/api/series?limit=20`);
        const data = await res.json();
        setSeriesList(data.series || []);
      } catch (err) {
        console.error("Failed to fetch series:", err);
      }
    }
    fetchSeries();
  }, []);

  // Fetch games when series changes
  useEffect(() => {
    if (!selectedSeries) {
      setGames([]);
      return;
    }

    async function fetchGames() {
      try {
        const res = await fetch(`${API_BASE}/api/series/${selectedSeries}/games`);
        const data = await res.json();
        setGames(data.games || []);
        setSelectedGame(1);
      } catch (err) {
        console.error("Failed to fetch games:", err);
      }
    }
    fetchGames();
  }, [selectedSeries]);

  const handleStart = () => {
    if (!selectedSeries) return;
    onStart(selectedSeries, selectedGame, speed);
  };

  const isPlaying = status === "playing" || status === "connecting";

  return (
    <div className="bg-lol-dark rounded-lg p-4">
      <div className="flex flex-wrap items-center gap-4">
        {/* Series Selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Series
          </label>
          <select
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            disabled={isPlaying}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            <option value="">Select a series...</option>
            {seriesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.blue_team_name} vs {s.red_team_name} ({s.match_date?.split("T")[0]})
              </option>
            ))}
          </select>
        </div>

        {/* Game Selector */}
        <div className="w-24">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Game
          </label>
          <select
            value={selectedGame}
            onChange={(e) => setSelectedGame(Number(e.target.value))}
            disabled={isPlaying || games.length === 0}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            {games.map((g) => (
              <option key={g.game_number} value={g.game_number}>
                Game {g.game_number}
              </option>
            ))}
          </select>
        </div>

        {/* Speed Selector */}
        <div className="w-24">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Speed
          </label>
          <select
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            disabled={isPlaying}
            className="
              w-full px-3 py-2 rounded bg-lol-light border border-gold-dim
              text-text-primary text-sm
              disabled:opacity-50 disabled:cursor-not-allowed
              focus:outline-none focus:border-magic
            "
          >
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={2}>2x</option>
            <option value={4}>4x</option>
          </select>
        </div>

        {/* Start/Stop Button */}
        <div className="pt-5">
          {isPlaying ? (
            <button
              onClick={onStop}
              className="
                px-6 py-2 rounded font-semibold uppercase tracking-wide text-sm
                bg-red-team text-white
                hover:bg-red-team/80 transition-colors
              "
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={!selectedSeries}
              className="
                px-6 py-2 rounded font-semibold uppercase tracking-wide text-sm
                bg-magic text-lol-darkest
                hover:bg-magic-bright transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                shadow-[0_0_15px_rgba(10,200,185,0.3)]
              "
            >
              {status === "connecting" ? "Connecting..." : "Start Replay"}
            </button>
          )}
        </div>

        {/* Status */}
        {status === "complete" && (
          <span className="text-sm text-success font-semibold uppercase">
            ✓ Complete
          </span>
        )}

        {error && (
          <span className="text-sm text-danger">
            {error}
          </span>
        )}
      </div>
    </div>
  );
}
