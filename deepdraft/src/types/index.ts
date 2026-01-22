/**
 * Shared TypeScript types for DeepDraft.
 */

export type Team = "blue" | "red";
export type DraftPhase = "ban" | "pick";

export interface Champion {
  id: string;
  name: string;
  imageUrl?: string;
}

export interface DraftAction {
  phase: DraftPhase;
  team: Team;
  champion: Champion | null;
  position: number;
}

export interface DraftState {
  actions: DraftAction[];
  currentAction: number;
  blueTeam: string;
  redTeam: string;
}

export interface Recommendation {
  champion: Champion;
  confidence: number;
  reasoning: string;
  tags: string[];
}

export interface InsightMessage {
  type: "recommendation" | "analysis" | "warning";
  content: string;
  timestamp: number;
}
