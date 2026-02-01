// frontend/src/components/ReplayControls/index.tsx
import { useState, useEffect, useMemo } from "react";
import type { SeriesInfo, GameInfo, GamePreview } from "../../types";
import { getTeamLogoUrl, getTeamInitials } from "../../utils/teamLogos";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type SessionStatus = "idle" | "connecting" | "playing" | "paused" | "complete" | "error";

interface ReplayControlsProps {
  status: SessionStatus;
  onStart: (
    seriesId: string,
    gameNumber: number,
    speed?: number,
    delaySeconds?: number,
    llmEnabled?: boolean,
    llmApiKey?: string | null,
    waitForLlm?: boolean,
  ) => void;
  onStop: () => void;
  onPause: () => void;
  onResume: () => void;
  error: string | null;
  llmEnabled?: boolean;
  hasApiKey?: boolean;
  apiKey?: string;
  isWaitingForLLM?: boolean;
  waitingForActionCount?: number | null;
}

function TeamLogo({ teamId, teamName, size = "sm" }: { teamId: string; teamName: string; size?: "sm" | "md" }) {
  const logoUrl = getTeamLogoUrl(teamId);
  const sizeClass = size === "sm" ? "w-6 h-6" : "w-10 h-10";

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={`${teamName} logo`}
        className={`${sizeClass} rounded bg-lol-dark object-contain`}
      />
    );
  }

  return (
    <div className={`${sizeClass} rounded bg-lol-dark flex items-center justify-center`}>
      <span className="font-bold text-xs text-gold-dim">
        {getTeamInitials(teamName)}
      </span>
    </div>
  );
}

export function ReplayControls({
  status,
  onStart,
  onStop,
  onPause,
  onResume,
  error,
  llmEnabled: globalLlmEnabled = false,
  hasApiKey = false,
  apiKey = "",
  isWaitingForLLM = false,
  waitingForActionCount = null,
}: ReplayControlsProps) {
  const [seriesList, setSeriesList] = useState<SeriesInfo[]>([]);
  const [games, setGames] = useState<GameInfo[]>([]);
  const [selectedSeries, setSelectedSeries] = useState<string>("");
  const [selectedGame, setSelectedGame] = useState<number>(1);
  const [speed, setSpeed] = useState<number>(1.0);
  const [gamePreview, setGamePreview] = useState<GamePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [useLlm, setUseLlm] = useState<boolean>(globalLlmEnabled && hasApiKey);

  // Get the currently selected series object
  const currentSeries = seriesList.find(s => s.id === selectedSeries);

  const computeSeriesScore = useMemo(() => {
    return (blueId?: string, redId?: string) => {
      if (!blueId || !redId || games.length === 0) return null;
      let blueWins = 0;
      let redWins = 0;
      for (const game of games) {
        const gameNum = Number(game.game_number);
        if (!Number.isFinite(gameNum) || gameNum > selectedGame) {
          continue;
        }
        if (game.winner_team_id === blueId) {
          blueWins += 1;
        } else if (game.winner_team_id === redId) {
          redWins += 1;
        }
      }
      return { blue: blueWins, red: redWins };
    };
  }, [games, selectedGame]);

  const seriesScorePreview = gamePreview
    ? computeSeriesScore(gamePreview.blue_team.id, gamePreview.red_team.id)
    : null;

  const seriesScoreFallback = currentSeries
    ? computeSeriesScore(currentSeries.blue_team_id, currentSeries.red_team_id)
    : null;

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
    async function fetchGames() {
      if (!selectedSeries) {
        setGames([]);
        setGamePreview(null);
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/series/${selectedSeries}/games`);
        const data = await res.json();
        setGames(data.games || []);
        setSelectedGame(1);
      } catch (err) {
        console.error("Failed to fetch games:", err);
        setGames([]);
      }
    }
    fetchGames();
  }, [selectedSeries]);

  // Fetch game preview when series or game changes
  useEffect(() => {
    async function fetchPreview() {
      if (!selectedSeries || !selectedGame) {
        setGamePreview(null);
        return;
      }
      setLoadingPreview(true);
      try {
        const res = await fetch(`${API_BASE}/api/game/preview/${selectedSeries}/${selectedGame}`);
        if (res.ok) {
          const data = await res.json();
          setGamePreview(data);
        } else {
          setGamePreview(null);
        }
      } catch (err) {
        console.error("Failed to fetch game preview:", err);
        setGamePreview(null);
      } finally {
        setLoadingPreview(false);
      }
    }
    fetchPreview();
  }, [selectedSeries, selectedGame]);

  const handleStart = () => {
    if (!selectedSeries) return;
    const llmApiKey = useLlm && hasApiKey ? apiKey : null;
    // When AI Analysis is enabled, we pass wait_for_llm=true to block replay
    const waitForLlm = useLlm && hasApiKey;
    // Force speed to 1x when AI Analysis is enabled
    const effectiveSpeed = waitForLlm ? 1.0 : speed;
    onStart(selectedSeries, selectedGame, effectiveSpeed, 5.0, useLlm && hasApiKey, llmApiKey, waitForLlm);
  };

  const isConnecting = status === "connecting";
  const isPlaying = status === "playing";
  const isPaused = status === "paused";
  const isActive = isPlaying || isPaused || isConnecting; // Any state with an active session

  return (
    <div className="bg-lol-dark rounded-lg p-4 space-y-4">
      {/* Controls Row */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Series Selector */}
        <div className="flex-1 min-w-[280px]">
          <label className="block text-xs text-text-tertiary uppercase mb-1">
            Series
          </label>
          <select
            value={selectedSeries}
            onChange={(e) => setSelectedSeries(e.target.value)}
            disabled={isActive}
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
            disabled={isActive || games.length === 0}
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
            value={useLlm && hasApiKey ? 1 : speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            disabled={isPlaying || (useLlm && hasApiKey)}
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

        {/* AI Analysis Toggle - only show if API key is configured */}
        {hasApiKey && (
          <div className="pt-5">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
                disabled={isActive}
                className="w-4 h-4 accent-magic"
              />
              <span className={`text-sm ${isActive ? "text-text-tertiary" : "text-text-secondary"}`}>
                AI Analysis
              </span>
            </label>
          </div>
        )}

        {/* Playback Controls */}
        <div className="pt-5 flex gap-2">
          {isConnecting ? (
            <button
              onClick={onStop}
              className="
                px-6 py-2 rounded font-semibold uppercase tracking-wide text-sm
                bg-red-team text-white
                hover:bg-red-team/80 transition-colors
              "
            >
              Connecting...
            </button>
          ) : isPlaying ? (
            <>
              <button
                onClick={onPause}
                className="
                  px-4 py-2 rounded font-semibold uppercase tracking-wide text-sm
                  bg-gold-dim text-lol-darkest
                  hover:bg-gold-bright transition-colors
                "
              >
                Pause
              </button>
              <button
                onClick={onStop}
                className="
                  px-4 py-2 rounded font-semibold uppercase tracking-wide text-sm
                  bg-red-team text-white
                  hover:bg-red-team/80 transition-colors
                "
              >
                Stop
              </button>
            </>
          ) : isPaused ? (
            <>
              <button
                onClick={onResume}
                className="
                  px-4 py-2 rounded font-semibold uppercase tracking-wide text-sm
                  bg-magic text-lol-darkest
                  hover:bg-magic-bright transition-colors
                  shadow-[0_0_15px_rgba(10,200,185,0.3)]
                "
              >
                Resume
              </button>
              <button
                onClick={onStop}
                className="
                  px-4 py-2 rounded font-semibold uppercase tracking-wide text-sm
                  bg-red-team text-white
                  hover:bg-red-team/80 transition-colors
                "
              >
                Stop
              </button>
            </>
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
              Start Replay
            </button>
          )}
        </div>

        {/* AI Waiting Indicator */}
        {isWaitingForLLM && waitingForActionCount && (
          <div className="flex items-center gap-2 text-magic">
            <div className="w-4 h-4 border-2 border-magic border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium">
              Analyzing action {waitingForActionCount}...
            </span>
          </div>
        )}

        {/* Status */}
        {isPaused && (
          <span className="text-sm text-gold-bright font-semibold uppercase">
            ⏸ Paused
          </span>
        )}
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

      {/* Game Preview Panel - Shows when a game is selected but not active */}
      {!isActive && currentSeries && (
        <div className="border-t border-gold-dim/30 pt-4">
          {loadingPreview ? (
            <div className="text-center text-text-tertiary text-sm py-4">
              Loading game info...
            </div>
          ) : gamePreview ? (
            <div className="flex items-center justify-between gap-8">
              {/* Blue Team */}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <TeamLogo teamId={gamePreview.blue_team.id} teamName={gamePreview.blue_team.name} size="md" />
                  <div>
                    <h3 className="font-semibold text-blue-team">{gamePreview.blue_team.name}</h3>
                    <span className="text-xs text-text-tertiary uppercase">Blue Side</span>
                  </div>
                </div>
                <div className="space-y-1">
                  {gamePreview.blue_team.players.map(p => (
                    <div key={p.id} className="flex items-center gap-2 text-sm">
                      <span className="w-8 text-xs text-text-tertiary">{p.role}</span>
                      <span className="text-gold-bright">{p.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* VS Divider */}
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl font-bold text-gold-dim">VS</span>
                {seriesScorePreview && (
                  <div className="text-center">
                    <div className="text-[10px] text-text-tertiary uppercase">Series Score</div>
                    <div className="text-sm font-semibold text-gold-bright">
                      {seriesScorePreview.blue} - {seriesScorePreview.red}
                    </div>
                  </div>
                )}
                {gamePreview.patch && (
                  <span className="text-xs text-text-tertiary">Patch {gamePreview.patch}</span>
                )}
              </div>

              {/* Red Team */}
              <div className="flex-1 text-right">
                <div className="flex items-center justify-end gap-3 mb-3">
                  <div>
                    <h3 className="font-semibold text-red-team">{gamePreview.red_team.name}</h3>
                    <span className="text-xs text-text-tertiary uppercase">Red Side</span>
                  </div>
                  <TeamLogo teamId={gamePreview.red_team.id} teamName={gamePreview.red_team.name} size="md" />
                </div>
                <div className="space-y-1">
                  {gamePreview.red_team.players.map(p => (
                    <div key={p.id} className="flex items-center justify-end gap-2 text-sm">
                      <span className="text-gold-bright">{p.name}</span>
                      <span className="w-8 text-xs text-text-tertiary text-right">{p.role}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Fallback: Show series info with team logos when preview not available */
            <div className="flex items-center justify-center gap-6">
              <div className="flex items-center gap-2">
                <TeamLogo teamId={currentSeries.blue_team_id} teamName={currentSeries.blue_team_name} size="md" />
                <span className="font-semibold text-blue-team">{currentSeries.blue_team_name}</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <span className="text-xl font-bold text-gold-dim">VS</span>
                {seriesScoreFallback && (
                  <div className="text-center">
                    <div className="text-[10px] text-text-tertiary uppercase">Series Score</div>
                    <div className="text-sm font-semibold text-gold-bright">
                      {seriesScoreFallback.blue} - {seriesScoreFallback.red}
                    </div>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-red-team">{currentSeries.red_team_name}</span>
                <TeamLogo teamId={currentSeries.red_team_id} teamName={currentSeries.red_team_name} size="md" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
