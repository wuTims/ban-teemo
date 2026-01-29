// deepdraft/src/components/RecommendationPanel/index.tsx
import { InsightsLog } from "../InsightsLog";
import type { InsightEntry } from "../../types";

interface RecommendationPanelProps {
  recommendationHistory: InsightEntry[];
  isLive: boolean;
}

export function RecommendationPanel({
  recommendationHistory,
  isLive,
}: RecommendationPanelProps) {
  return (
    <InsightsLog
      entries={recommendationHistory}
      isLive={isLive}
    />
  );
}
