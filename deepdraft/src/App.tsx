// deepdraft/src/App.tsx
import { useState } from "react";
import { ActionLog } from "./components/ActionLog";
import { DraftBoard } from "./components/DraftBoard";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ReplayControls } from "./components/ReplayControls";
import { SimulatorSetupModal } from "./components/SimulatorSetupModal";
import { SimulatorView } from "./components/SimulatorView";
import { DraftCompletePanel } from "./components/DraftCompletePanel";
import { useReplaySession, useSimulatorSession } from "./hooks";
import type { SimulatorConfig } from "./types";

type AppMode = "replay" | "simulator";

export default function App() {
  const [mode, setMode] = useState<AppMode>("replay");
  const [showSetup, setShowSetup] = useState(false);

  const replay = useReplaySession();
  const simulator = useSimulatorSession();

  const handleStartSimulator = async (config: SimulatorConfig) => {
    await simulator.startSession(config);
    setShowSetup(false);
  };

  return (
    <div className="min-h-screen bg-lol-darkest">
      {/* Header */}
      <header className="h-16 bg-lol-dark border-b border-gold-dim/30 flex items-center px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            DeepDraft
          </h1>
          <span className="text-sm text-text-tertiary">LoL Draft Assistant</span>
        </div>

        {/* Mode Toggle */}
        <div className="ml-8 flex items-center gap-2">
          <button
            onClick={() => setMode("replay")}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              mode === "replay"
                ? "bg-magic text-lol-darkest"
                : "bg-lol-light text-text-secondary hover:bg-lol-hover"
            }`}
          >
            Replay
          </button>
          <button
            onClick={() => {
              setMode("simulator");
              if (simulator.status === "setup") setShowSetup(true);
            }}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              mode === "simulator"
                ? "bg-magic text-lol-darkest"
                : "bg-lol-light text-text-secondary hover:bg-lol-hover"
            }`}
          >
            Simulator
          </button>
        </div>

        <div className="ml-auto flex items-center gap-4">
          {mode === "replay" && replay.patch && (
            <span className="text-xs text-text-tertiary">Patch {replay.patch}</span>
          )}
          {mode === "replay" && replay.status === "playing" && (
            <span className="text-xs text-magic animate-pulse">Live</span>
          )}
          {mode === "simulator" && simulator.status === "drafting" && (
            <span className="text-xs text-magic animate-pulse">Drafting</span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {mode === "replay" ? (
          <>
            <ReplayControls
              status={replay.status}
              onStart={replay.startReplay}
              onStop={replay.stopReplay}
              error={replay.error}
            />

            <div className="flex flex-row gap-6">
              <div className="flex-1">
                <DraftBoard
                  blueTeam={replay.blueTeam}
                  redTeam={replay.redTeam}
                  draftState={replay.draftState}
                />
              </div>

              {replay.status !== "idle" && (
                <ActionLog
                  actions={replay.actionHistory}
                  blueTeam={replay.blueTeam}
                  redTeam={replay.redTeam}
                />
              )}
            </div>

            <RecommendationPanel
              recommendationHistory={replay.recommendationHistory}
              isLive={replay.status === "playing"}
              blueTeam={replay.blueTeam}
              redTeam={replay.redTeam}
            />
          </>
        ) : (
          <>
            {simulator.status === "setup" && (
              <div className="text-center py-12">
                <p className="text-text-secondary mb-4">
                  Practice drafting against an AI opponent based on real pro team data.
                </p>
                <button
                  onClick={() => setShowSetup(true)}
                  className="px-6 py-3 bg-magic text-lol-darkest rounded-lg font-semibold hover:bg-magic-bright transition-colors"
                >
                  Start New Draft
                </button>
              </div>
            )}

            {/* Show drafting view OR game complete with panel */}
            {(simulator.status === "drafting" || simulator.status === "game_complete") &&
              simulator.blueTeam && simulator.redTeam && simulator.draftState && (
              <>
                <SimulatorView
                  blueTeam={simulator.blueTeam}
                  redTeam={simulator.redTeam}
                  coachingSide={simulator.coachingSide!}
                  draftState={simulator.draftState}
                  recommendations={simulator.recommendations}
                  isOurTurn={simulator.isOurTurn}
                  isEnemyThinking={simulator.isEnemyThinking}
                  gameNumber={simulator.gameNumber}
                  seriesScore={simulator.seriesStatus ? [simulator.seriesStatus.blue_wins, simulator.seriesStatus.red_wins] : [0, 0]}
                  fearlessBlocked={simulator.fearlessBlocked}
                  draftMode={simulator.draftMode}
                  onChampionSelect={simulator.submitAction}
                />

                {/* Draft Complete Panel - shown when game is complete */}
                {simulator.status === "game_complete" && (
                  <div className="mt-4">
                    {!simulator.seriesStatus?.games_played ||
                     simulator.seriesStatus.games_played < simulator.gameNumber ? (
                      <DraftCompletePanel
                        blueTeam={simulator.blueTeam}
                        redTeam={simulator.redTeam}
                        evaluation={simulator.teamEvaluation}
                        onSelectWinner={simulator.recordWinner}
                        isRecordingWinner={simulator.isRecordingWinner}
                      />
                    ) : (
                      /* Winner recorded, show continue button */
                      <div className="bg-lol-dark rounded-lg p-6 text-center">
                        <div className="text-lg text-text-primary mb-4">
                          <span className="text-blue-team">{simulator.blueTeam.name}</span>
                          <span className="mx-4 text-gold-bright font-bold">
                            {simulator.seriesStatus?.blue_wins} - {simulator.seriesStatus?.red_wins}
                          </span>
                          <span className="text-red-team">{simulator.redTeam.name}</span>
                        </div>
                        <button
                          onClick={() => simulator.nextGame()}
                          className="px-6 py-3 bg-magic text-lol-darkest rounded-lg font-semibold hover:bg-magic-bright transition-colors"
                        >
                          Continue to Game {simulator.gameNumber + 1}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {simulator.status === "series_complete" && (
              <div className="text-center py-12 space-y-6">
                <h2 className="text-2xl font-bold text-gold-bright uppercase tracking-wide">
                  Series Complete!
                </h2>
                <div className="text-xl text-text-primary">
                  <span className="text-blue-team">{simulator.blueTeam?.name}</span>
                  <span className="mx-4 text-gold-bright font-bold">
                    {simulator.seriesStatus?.blue_wins} - {simulator.seriesStatus?.red_wins}
                  </span>
                  <span className="text-red-team">{simulator.redTeam?.name}</span>
                </div>
                <button
                  onClick={simulator.endSession}
                  className="px-6 py-2 bg-magic text-lol-darkest rounded font-semibold hover:bg-magic-bright transition-colors"
                >
                  New Session
                </button>
              </div>
            )}

            {simulator.error && (
              <div className="bg-danger/20 border border-danger/50 rounded-lg p-4 text-center text-danger">
                {simulator.error}
              </div>
            )}
          </>
        )}
      </main>

      {/* Simulator Setup Modal */}
      <SimulatorSetupModal
        isOpen={showSetup}
        onStart={handleStartSimulator}
        onClose={() => setShowSetup(false)}
      />
    </div>
  );
}
