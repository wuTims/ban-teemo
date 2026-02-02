// frontend/src/App.tsx
import { useState, useEffect } from "react";
import { ActionLog, DraftBoard, RecommendationPanel, ReplayControls } from "./components/replay";
import { SimulatorSetupModal } from "./components/SimulatorSetupModal";
import { SettingsModal } from "./components/SettingsModal";
import { SimulatorView } from "./components/SimulatorView";
import { DraftCompletePanel } from "./components/DraftCompletePanel";
import { useReplaySession, useSimulatorSession, useSettings } from "./hooks";
import type { SimulatorConfig } from "./types";

type AppMode = "replay" | "simulator";

export default function App() {
  const [mode, setMode] = useState<AppMode>("replay");
  const [showSetup, setShowSetup] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const replay = useReplaySession();
  const simulator = useSimulatorSession();
  const settings = useSettings();

  useEffect(() => {
    if (!settings.llmEnabled) return;
    if (!settings.apiKey) return;
    if (simulator.llmApiKey !== settings.apiKey) {
      simulator.setLlmApiKey(settings.apiKey);
    }
  }, [settings.llmEnabled, settings.apiKey, simulator.llmApiKey, simulator.setLlmApiKey]);

  const handleSaveSettings = (apiKey: string, llmEnabled: boolean) => {
    settings.setApiKey(apiKey);
    settings.setLlmEnabled(llmEnabled);
  };

  const handleStartSimulator = async (config: SimulatorConfig) => {
    await simulator.startSession(config);
    setShowSetup(false);
  };

  return (
    <div className="min-h-screen bg-lol-darkest overflow-x-hidden">
      {/* Header - responsive */}
      <header className="min-h-12 sm:h-14 lg:h-16 bg-lol-dark border-b border-gold-dim/30 flex flex-wrap sm:flex-nowrap items-center px-2 sm:px-4 lg:px-6 py-2 sm:py-0 gap-2 sm:gap-0">
        <div className="flex items-center gap-2 sm:gap-4">
          <h1 className="text-base sm:text-lg lg:text-xl font-bold uppercase tracking-wide text-gold-bright">
            Ban Teemo
          </h1>
          <span className="hidden sm:inline text-xs lg:text-sm text-text-tertiary">LoL Draft Assistant</span>
        </div>

        {/* Mode Toggle */}
        <div className="ml-2 sm:ml-4 lg:ml-8 flex items-center gap-1 sm:gap-2">
          <button
            onClick={() => setMode("replay")}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded text-xs sm:text-sm font-medium transition-colors ${
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
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded text-xs sm:text-sm font-medium transition-colors ${
              mode === "simulator"
                ? "bg-magic text-lol-darkest"
                : "bg-lol-light text-text-secondary hover:bg-lol-hover"
            }`}
          >
            Simulator
          </button>
        </div>

        <div className="ml-auto flex items-center gap-2 sm:gap-4">
          {mode === "replay" && replay.patch && (
            <span className="hidden sm:inline text-xs text-text-tertiary">Patch {replay.patch}</span>
          )}
          {mode === "replay" && replay.status === "playing" && (
            <span className="text-[10px] sm:text-xs text-magic animate-pulse">Live</span>
          )}
          {mode === "replay" && replay.status === "paused" && (
            <span className="text-[10px] sm:text-xs text-gold-bright">Paused</span>
          )}
          {mode === "simulator" && simulator.status === "drafting" && (
            <span className="text-[10px] sm:text-xs text-magic animate-pulse">Drafting</span>
          )}
          <button
            onClick={() => setShowSettings(true)}
            className="p-1.5 sm:p-2 rounded hover:bg-lol-light transition-colors text-text-tertiary hover:text-gold-bright"
            title="Settings"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 sm:h-5 sm:w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-2 sm:p-4 lg:p-6 space-y-3 sm:space-y-4 lg:space-y-6">
        {mode === "replay" ? (
          <>
            <ReplayControls
              status={replay.status}
              onStart={replay.startReplay}
              onStop={replay.stopReplay}
              onPause={replay.pauseReplay}
              onResume={replay.resumeReplay}
              onSeriesChange={replay.resetSession}
              error={replay.error}
              llmEnabled={settings.llmEnabled}
              hasApiKey={settings.hasApiKey}
              apiKey={settings.apiKey}
            />

            <div className="flex flex-row gap-6">
              <div className="flex-1">
                <DraftBoard
                  blueTeam={replay.blueTeam}
                  redTeam={replay.redTeam}
                  draftState={replay.draftState}
                  blueCompWithRoles={replay.blueCompWithRoles}
                  redCompWithRoles={replay.redCompWithRoles}
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
              llmInsights={replay.llmInsights}
              llmTimeouts={replay.llmTimeouts}
              isWaitingForLLM={replay.isWaitingForLLM}
              waitingForActionCount={replay.waitingForActionCount}
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
                  blueCompWithRoles={simulator.blueCompWithRoles}
                  redCompWithRoles={simulator.redCompWithRoles}
                  llmLoading={simulator.llmLoading}
                  llmInsight={simulator.llmInsight}
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
                        draftQuality={simulator.draftQuality}
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
        onSetLlmApiKey={simulator.setLlmApiKey}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        apiKey={settings.apiKey}
        llmEnabled={settings.llmEnabled}
        onSave={handleSaveSettings}
      />
    </div>
  );
}
