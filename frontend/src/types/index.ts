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
  sequence: number | string;  // Backend sends string due to DB conversion, but represents a number
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
  suggested_role?: string | null;
  flag: RecommendationFlag;
  reasons: string[];
  // Score breakdown fields
  score?: number;
  base_score?: number | null;
  synergy_multiplier?: number | null;
  components?: Record<string, number>; // Raw scores for debugging
  weighted_components?: Record<string, number>; // Weighted for display (same scale as bans)
  // Proficiency tracking
  proficiency_source?: string | null;
  proficiency_player?: string | null;
}

export interface BanRecommendation {
  champion_name: string;
  priority: number;
  target_player: string | null;
  reasons: string[];
  // Score breakdown fields
  components?: Record<string, number>;
}

export interface Recommendations {
  for_team: Team;
  picks: PickRecommendation[];
  bans: BanRecommendation[];
  role_grouped?: RoleGroupedRecommendations;
}

// === WebSocket Messages ===
export interface SessionStartMessage {
  type: "session_start";
  session_id: string;
  series_id: string;
  game_number: number;
  blue_team: TeamContext;
  red_team: TeamContext;
  total_actions: number;
  patch: string | null;
  series_score_before?: { blue: number; red: number } | null;
  series_score_after?: { blue: number; red: number } | null;
  winner_team_id?: string | null;
  winner_side?: Team | null;
}

export interface DraftActionMessage {
  type: "draft_action";
  action: DraftAction;
  draft_state: DraftState;
  recommendations: Recommendations;
}

// Finalized pick with resolved role assignment
export interface FinalizedPick {
  champion: string;
  role: "top" | "jungle" | "mid" | "bot" | "support";
}

export interface DraftCompleteMessage {
  type: "draft_complete";
  draft_state: DraftState;
  blue_comp: string[];
  red_comp: string[];
  blue_comp_with_roles?: FinalizedPick[];
  red_comp_with_roles?: FinalizedPick[];
  // Backend sends draft_quality as nested object with blue/red keys
  draft_quality?: {
    blue?: DraftQuality | null;
    red?: DraftQuality | null;
  } | null;
}

// LLM-enhanced recommendation types
export interface RerankedRecommendation {
  champion_name: string;
  original_rank: number;
  new_rank: number;
  confidence: number;
  reasoning: string;
  strategic_factors: string[];
}

export interface AdditionalSuggestion {
  champion_name: string;
  reasoning: string;
  confidence: number;
  role: string;
  for_player?: string;
}

export interface EnhancedRecommendationsMessage {
  type: "enhanced_recommendations";
  action_count: number;
  for_team: Team;
  draft_analysis: string;
  reranked: RerankedRecommendation[];
  additional_suggestions: AdditionalSuggestion[];
}

export interface WaitingForLLMMessage {
  type: "waiting_for_llm";
  action_count: number;
}

export interface LLMTimeoutMessage {
  type: "llm_timeout";
  action_count: number;
}

export interface PausedMessage {
  type: "paused";
}

export interface ResumedMessage {
  type: "resumed";
}

export type WebSocketMessage =
  | SessionStartMessage
  | DraftActionMessage
  | DraftCompleteMessage
  | EnhancedRecommendationsMessage
  | WaitingForLLMMessage
  | LLMTimeoutMessage
  | PausedMessage
  | ResumedMessage;

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
  components?: Record<string, number>;
}

export interface ScoreComponents {
  meta?: number;
  tournament_priority?: number;
  tournament_performance?: number;
  proficiency?: number;
  matchup?: number;
  counter?: number;
  matchup_counter?: number;
  archetype?: number;
  synergy?: number;
  role_flex?: number;
  blind_safety?: number;
  presence_bonus?: number;
  [key: string]: number | undefined; // Allow additional dynamic components
}

export interface SimulatorPickRecommendation {
  champion_name: string;
  score: number;
  base_score: number;
  synergy_multiplier: number;
  confidence: number; // 0.65-1.0 numeric confidence
  suggested_role: string;
  components: ScoreComponents; // Raw scores for debugging
  weighted_components?: ScoreComponents; // Weighted for display (same scale as bans)
  flag: RecommendationFlag;
  reasons: string[];
}

// Union type: backend returns ban recs OR pick recs depending on phase
export type SimulatorRecommendation = SimulatorBanRecommendation | SimulatorPickRecommendation;

export interface SynergyPair {
  champions: [string, string];
  score: number;
}

export interface ChampionMeta {
  champion: string;
  priority: number;
  tier: string;
}

export interface TeamDraftEvaluation {
  archetype: string | null;
  synergy_score: number;
  composition_score: number;
  meta_strength: number;
  champion_meta: ChampionMeta[];
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
  // Optional: included when draft is complete
  blue_comp_with_roles?: FinalizedPick[];
  red_comp_with_roles?: FinalizedPick[];
}

// Fearless blocked entry with team and game metadata for tooltips
export interface FearlessBlockedEntry {
  team: "blue" | "red";
  game: number;
}

// Map of champion name -> blocking metadata
export type FearlessBlocked = Record<string, FearlessBlockedEntry>;

// === Draft Quality Types ===

export interface DraftQualityDraft {
  picks: string[];
  archetype: string | null;
  composition_score: number;
  synergy_score: number;
  meta_strength: number;
  champion_meta: ChampionMeta[];
  vs_enemy_advantage: number;
  vs_enemy_description: string;
}

export interface DraftQualityComparison {
  score_delta: number;
  advantage_delta: number;
  archetype_insight: string;
  picks_matched: number;
  picks_tracked: number;
}

export interface DraftQuality {
  actual_draft: DraftQualityDraft;
  recommended_draft: DraftQualityDraft;
  comparison: DraftQualityComparison;
}

export interface CompleteGameResponse {
  series_status: SeriesStatus;
  fearless_blocked: FearlessBlocked;
  next_game_ready: boolean;
  blue_comp_with_roles?: FinalizedPick[];
  red_comp_with_roles?: FinalizedPick[];
  draft_quality?: DraftQuality | null;
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

export interface RoleGroupedRecommendations {
  view_type?: "supplemental";
  description?: string;
  by_role: {
    [role: string]: SimulatorPickRecommendation[];
  };
}

export interface RecommendationsResponse {
  for_action_count: number;
  phase: DraftPhase;
  recommendations: SimulatorRecommendation[];
  role_grouped?: RoleGroupedRecommendations;
}

export interface EvaluationResponse {
  for_action_count: number;
  our_evaluation: TeamDraftEvaluation | null;
  enemy_evaluation: TeamDraftEvaluation | null;
  matchup_advantage: number;
  matchup_description: string;
}

// === Replay Insights ===
export interface ReplayLogMarker {
  kind: "marker";
  sessionId: string;
  label: string;
  timestamp: number;
  winnerSide?: Team | null;
  score?: { blue: number; red: number } | null;
}

export interface InsightActionEntry {
  kind: "action";
  sessionId: string;
  action: DraftAction;
  recommendations: Recommendations | null;
}

export type InsightEntry = InsightActionEntry | ReplayLogMarker;

export interface ActionLogEntry {
  kind: "action";
  sessionId: string;
  action: DraftAction;
}

export type ReplayActionLogEntry = ActionLogEntry | ReplayLogMarker;

// LLM Insights stored by action count
export interface LLMInsight {
  actionCount: number;
  forTeam: Team;
  draftAnalysis: string;
  reranked: RerankedRecommendation[];
  additionalSuggestions: AdditionalSuggestion[];
  receivedAt: number;
}

// LLM Insights API response for simulator polling
export interface LLMInsightsResponse {
  status: "ready" | "stale" | "complete" | "error";
  action_count?: number;
  for_team?: Team;
  draft_analysis?: string;
  reranked?: RerankedRecommendation[];
  additional_suggestions?: AdditionalSuggestion[];
  message?: string;
}
