/**
 * TypeScript types aligned with backend WebSocket protocol.
 * See: docs/plans/2026-01-23-draft-simulation-service-design.md
 */

// === Enums ===
export type Team = "blue" | "red";
export type ActionType = "ban" | "pick";
export type DraftPhase =
  | "BAN_PHASE_1"
  | "PICK_PHASE_1"
  | "BAN_PHASE_2"
  | "PICK_PHASE_2"
  | "COMPLETE";
export type ReplayStatus = "pending" | "playing" | "paused" | "complete";

// === Core Models ===
export interface Player {
  id: string;
  name: string;
  role: "TOP" | "JNG" | "MID" | "ADC" | "SUP";
}

export interface TeamContext {
  id: string;
  name: string;
  side: Team;
  players: Player[];
}

export interface DraftAction {
  sequence: number;
  action_type: ActionType;
  team_side: Team;
  champion_id: string;
  champion_name: string;
}

export interface DraftState {
  phase: DraftPhase;
  next_team: Team | null;
  next_action: ActionType | null;
  blue_bans: string[];
  red_bans: string[];
  blue_picks: string[];
  red_picks: string[];
  action_count: number;
}

// === Recommendations ===
export type RecommendationFlag = "SURPRISE_PICK" | "LOW_CONFIDENCE" | null;

export interface PickRecommendation {
  champion_name: string;
  confidence: number;
  flag: RecommendationFlag;
  reasons: string[];
}

export interface BanRecommendation {
  champion_name: string;
  priority: number;
  target_player: string | null;
  reasons: string[];
}

export interface Recommendations {
  for_team: Team;
  picks: PickRecommendation[];
  bans: BanRecommendation[];
}

// === WebSocket Messages ===
export interface SessionStartMessage {
  type: "session_start";
  session_id: string;
  blue_team: TeamContext;
  red_team: TeamContext;
  total_actions: number;
  patch: string | null;
}

export interface DraftActionMessage {
  type: "draft_action";
  action: DraftAction;
  draft_state: DraftState;
  recommendations: Recommendations;
}

export interface DraftCompleteMessage {
  type: "draft_complete";
  draft_state: DraftState;
  blue_comp: string[];
  red_comp: string[];
}

export type WebSocketMessage =
  | SessionStartMessage
  | DraftActionMessage
  | DraftCompleteMessage;

// === API Types ===
export interface SeriesInfo {
  id: string;
  match_date: string;
  format: string;
  blue_team_id: string;
  blue_team_name: string;
  red_team_id: string;
  red_team_name: string;
}

export interface GameInfo {
  id: string;
  game_number: number;
  patch_version: string | null;
  winner_team_id: string | null;
}

export interface PlayerPreview {
  id: string;
  name: string;
  role: string;
}

export interface TeamPreview {
  id: string;
  name: string;
  side: Team;
  players: PlayerPreview[];
}

export interface GamePreview {
  game_id: string;
  series_id: string;
  game_number: number;
  patch: string | null;
  blue_team: TeamPreview;
  red_team: TeamPreview;
}

export interface StartReplayRequest {
  series_id: string;
  game_number: number;
  speed?: number;
  delay_seconds?: number;
}

export interface StartReplayResponse {
  session_id: string;
  total_actions: number;
  blue_team: string;
  red_team: string;
  patch: string | null;
  websocket_url: string;
}
