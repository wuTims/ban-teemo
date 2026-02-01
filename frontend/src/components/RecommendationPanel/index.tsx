// frontend/src/components/RecommendationPanel/index.tsx
import { InsightsLog } from "../InsightsLog";
import type { InsightEntry, TeamContext, LLMInsight } from "../../types";

interface RecommendationPanelProps {
  recommendationHistory: InsightEntry[];
  isLive: boolean;
  blueTeam?: TeamContext | null;
  redTeam?: TeamContext | null;
  llmInsights?: Map<number, LLMInsight>;
  llmTimeouts?: Set<number>;
  isWaitingForLLM?: boolean;
  waitingForActionCount?: number | null;
}

export function RecommendationPanel({
  recommendationHistory,
  isLive,
  blueTeam,
  redTeam,
  llmInsights,
  llmTimeouts,
  isWaitingForLLM,
  waitingForActionCount,
}: RecommendationPanelProps) {
  return (
    <InsightsLog
      entries={recommendationHistory}
      isLive={isLive}
      blueTeam={blueTeam}
      redTeam={redTeam}
      llmInsights={llmInsights}
      llmTimeouts={llmTimeouts}
      isWaitingForLLM={isWaitingForLLM}
      waitingForActionCount={waitingForActionCount}
    />
  );
}
