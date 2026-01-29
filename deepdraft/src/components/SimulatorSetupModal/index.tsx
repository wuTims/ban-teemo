// deepdraft/src/components/SimulatorSetupModal/index.tsx
import { useState, useEffect } from "react";
import type { SimulatorConfig, TeamListItem, Team, DraftMode } from "../../types";

interface SimulatorSetupModalProps {
  isOpen: boolean;
  onStart: (config: SimulatorConfig) => void;
  onClose: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function SimulatorSetupModal({ isOpen, onStart, onClose }: SimulatorSetupModalProps) {
  const [teams, setTeams] = useState<TeamListItem[]>([]);
  const [blueTeamId, setBlueTeamId] = useState("");
  const [redTeamId, setRedTeamId] = useState("");
  const [coachingSide, setCoachingSide] = useState<Team>("blue");
  const [seriesLength, setSeriesLength] = useState<1 | 3 | 5>(1);
  const [draftMode, setDraftMode] = useState<DraftMode>("normal");
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFetchError(null);
      fetch(`${API_BASE}/api/simulator/teams`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed to fetch teams");
          return res.json();
        })
        .then((data) => setTeams(data.teams || []))
        .catch((err) => setFetchError(err.message));
    }
  }, [isOpen]);

  const handleStart = () => {
    if (!blueTeamId || !redTeamId) return;
    setLoading(true);
    onStart({
      blueTeamId,
      redTeamId,
      coachingSide,
      seriesLength,
      draftMode,
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-lol-dark rounded-lg p-6 w-full max-w-lg border border-gold-dim/30 shadow-lg">
        <h2 className="text-2xl font-bold text-gold-bright mb-6 text-center uppercase tracking-wide">
          Start Draft Simulator
        </h2>

        {fetchError && (
          <div className="mb-4 p-3 bg-danger/20 border border-danger/50 rounded text-danger text-sm">
            {fetchError}
          </div>
        )}

        {/* Team Selection */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Blue Side</label>
            <select
              value={blueTeamId}
              onChange={(e) => setBlueTeamId(e.target.value)}
              className="w-full px-3 py-2 bg-lol-light border border-gold-dim/30 rounded text-text-primary focus:outline-none focus:border-magic"
            >
              <option value="">Select Team</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id} disabled={t.id === redTeamId}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Red Side</label>
            <select
              value={redTeamId}
              onChange={(e) => setRedTeamId(e.target.value)}
              className="w-full px-3 py-2 bg-lol-light border border-gold-dim/30 rounded text-text-primary focus:outline-none focus:border-magic"
            >
              <option value="">Select Team</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id} disabled={t.id === blueTeamId}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Coaching Side */}
        <div className="mb-6">
          <label className="block text-sm text-text-secondary mb-2">You are coaching:</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={coachingSide === "blue"}
                onChange={() => setCoachingSide("blue")}
                className="accent-magic w-4 h-4"
              />
              <span className="text-blue-team font-medium">Blue Side</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={coachingSide === "red"}
                onChange={() => setCoachingSide("red")}
                className="accent-magic w-4 h-4"
              />
              <span className="text-red-team font-medium">Red Side</span>
            </label>
          </div>
        </div>

        {/* Series Format */}
        <div className="mb-6">
          <label className="block text-sm text-text-secondary mb-2">Series Format:</label>
          <div className="flex gap-4">
            {([1, 3, 5] as const).map((len) => (
              <label key={len} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  checked={seriesLength === len}
                  onChange={() => setSeriesLength(len)}
                  className="accent-magic w-4 h-4"
                />
                <span className="text-text-primary">Bo{len}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Draft Mode */}
        <div className="mb-8">
          <label className="block text-sm text-text-secondary mb-2">Draft Mode:</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={draftMode === "normal"}
                onChange={() => setDraftMode("normal")}
                className="accent-magic w-4 h-4"
              />
              <span className="text-text-primary">Normal</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                checked={draftMode === "fearless"}
                onChange={() => setDraftMode("fearless")}
                className="accent-magic w-4 h-4"
              />
              <div>
                <span className="text-text-primary">Fearless</span>
                <span className="text-xs text-text-tertiary ml-1">(no repeats)</span>
              </div>
            </label>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-lol-light border border-gold-dim/30 rounded text-text-secondary hover:bg-lol-hover transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={!blueTeamId || !redTeamId || loading}
            className="flex-1 px-4 py-2 bg-magic text-lol-darkest rounded font-semibold hover:bg-magic-bright disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Starting..." : "Start Draft"}
          </button>
        </div>
      </div>
    </div>
  );
}
