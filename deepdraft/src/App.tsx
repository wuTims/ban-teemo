// deepdraft/src/App.tsx
import { ActionLog } from "./components/ActionLog";
import { DraftBoard } from "./components/DraftBoard";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { ReplayControls } from "./components/ReplayControls";
import { useReplaySession } from "./hooks";

export default function App() {
  const {
    status,
    blueTeam,
    redTeam,
    draftState,
    recommendations,
    actionHistory,
    patch,
    error,
    startReplay,
    stopReplay,
  } = useReplaySession();

  return (
    <div className="min-h-screen bg-lol-darkest">
      {/* Header */}
      <header className="h-16 bg-lol-dark border-b border-gold-dim/30 flex items-center px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold uppercase tracking-wide text-gold-bright">
            DeepDraft
          </h1>
          <span className="text-sm text-text-tertiary">
            LoL Draft Assistant
          </span>
        </div>

        <div className="ml-auto flex items-center gap-4">
          {patch && (
            <span className="text-xs text-text-tertiary">
              Patch {patch}
            </span>
          )}
          {status === "playing" && (
            <span className="text-xs text-magic animate-pulse">
              ● Live
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {/* Replay Controls */}
        <ReplayControls
          status={status}
          onStart={startReplay}
          onStop={stopReplay}
          error={error}
        />

        {/* Draft Board + Action Log */}
        <div className="flex flex-row gap-6">
          <div className="flex-1">
            <DraftBoard
              blueTeam={blueTeam}
              redTeam={redTeam}
              draftState={draftState}
            />
          </div>

          {status !== "idle" && (
            <ActionLog
              actions={actionHistory}
              blueTeam={blueTeam}
              redTeam={redTeam}
            />
          )}
        </div>

        {/* Recommendations Panel */}
        <RecommendationPanel
          recommendations={recommendations}
          nextAction={draftState?.next_action ?? null}
        />
      </main>
    </div>
  );
}
