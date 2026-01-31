// deepdraft/src/components/RecommendationPanel/index.tsx
import { InsightsLog } from "../InsightsLog";
import type { InsightEntry, TeamContext } from "../../types";

interface RecommendationPanelProps {
  recommendationHistory: InsightEntry[];
  isLive: boolean;
  blueTeam?: TeamContext | null;
  redTeam?: TeamContext | null;
}

export function RecommendationPanel({
  recommendationHistory,
  isLive,
  blueTeam,
  redTeam,
}: RecommendationPanelProps) {
  return (
    <InsightsLog
      entries={recommendationHistory}
      isLive={isLive}
      blueTeam={blueTeam}
      redTeam={redTeam}
    />
  );
}
