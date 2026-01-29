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

// === Simulator Types ===

export type DraftMode = "normal" | "fearless";

export interface SimulatorConfig {
  blueTeamId: string;
  redTeamId: string;
  coachingSide: Team;
  seriesLength: 1 | 3 | 5;
  draftMode: DraftMode;
}

export interface SeriesStatus {
  blue_wins: number;
  red_wins: number;
  games_played?: number; // Optional: not always present in GET session
  series_complete: boolean;
}

// Simulator-specific recommendation types (different from replay)
export interface SimulatorBanRecommendation {
  champion_name: string;
  priority: number;
  target_player: string | null;
  target_role: string | null;
  reasons: string[];
}

export interface ScoreComponents {
  meta: number;
  proficiency: number;
  matchup: number;
  counter: number;
  synergy: number;
}

export interface SimulatorPickRecommendation {
  champion_name: string;
  score: number;
  base_score: number;
  synergy_multiplier: number;
  confidence: number; // 0.65-1.0 numeric confidence
  suggested_role: string;
  components: ScoreComponents;
  flag: RecommendationFlag;
  reasons: string[];
}

// Union type: backend returns ban recs OR pick recs depending on phase
export type SimulatorRecommendation = SimulatorBanRecommendation | SimulatorPickRecommendation;

export interface SynergyPair {
  champions: [string, string];
  score: number;
}

export interface TeamDraftEvaluation {
  archetype: string | null;
  synergy_score: number;
  composition_score: number;
  strengths: string[];
  weaknesses: string[];
  synergy_pairs: SynergyPair[];
}

export interface TeamEvaluation {
  our_evaluation: TeamDraftEvaluation;
  enemy_evaluation: TeamDraftEvaluation;
  matchup_advantage: number;
  matchup_description: string;
}

export interface SimulatorStartResponse {
  session_id: string;
  game_number: number;
  blue_team: TeamContext;
  red_team: TeamContext;
  draft_state: DraftState;
  is_our_turn: boolean;
}

export interface SimulatorActionResponse {
  action: DraftAction | null;
  draft_state: DraftState;
  is_our_turn: boolean;
  source?: "reference_game" | "fallback_game" | "weighted_random";
  // Optional: included when ?include_recommendations=true
  recommendations?: SimulatorRecommendation[];
  // Optional: included when ?include_evaluation=true
  evaluation?: TeamEvaluation;
}

// Fearless blocked entry with team and game metadata for tooltips
export interface FearlessBlockedEntry {
  team: "blue" | "red";
  game: number;
}

// Map of champion name -> blocking metadata
export type FearlessBlocked = Record<string, FearlessBlockedEntry>;

export interface CompleteGameResponse {
  series_status: SeriesStatus;
  fearless_blocked: FearlessBlocked;
  next_game_ready: boolean;
}

export interface NextGameResponse {
  game_number: number;
  draft_state: DraftState;
  fearless_blocked: FearlessBlocked;
}

export interface TeamListItem {
  id: string;
  name: string;
}

// === Stage 5: New Query Response Types ===

export interface RecommendationsResponse {
  for_action_count: number;
  phase: DraftPhase;
  recommendations: SimulatorRecommendation[];
}

export interface EvaluationResponse {
  for_action_count: number;
  our_evaluation: TeamDraftEvaluation | null;
  enemy_evaluation: TeamDraftEvaluation | null;
  matchup_advantage: number;
  matchup_description: string;
}
