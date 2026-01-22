import { DraftBoard } from "./components/DraftBoard";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { InsightPanel } from "./components/InsightPanel";

function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-2xl font-bold">DeepDraft</h1>
        <p className="text-gray-400 text-sm">LoL Draft Assistant</p>
      </header>

      <main className="container mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main draft board */}
          <div className="lg:col-span-2">
            <DraftBoard />
          </div>

          {/* Side panels */}
          <div className="space-y-6">
            <RecommendationPanel />
            <InsightPanel />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
