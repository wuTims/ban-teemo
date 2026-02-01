// frontend/src/hooks/useSimulatorSession.ts
import { useState, useCallback, useRef, useEffect } from "react";
import type {
  SimulatorConfig,
  TeamContext,
  DraftState,
  DraftMode,
  SimulatorRecommendation,
  SeriesStatus,
  TeamEvaluation,
  SimulatorStartResponse,
  SimulatorActionResponse,
  CompleteGameResponse,
  NextGameResponse,
  FearlessBlocked,
  RecommendationsResponse,
  RoleGroupedRecommendations,
  FinalizedPick,
  LLMInsightsResponse,
} from "../types";

type SimulatorStatus = "setup" | "drafting" | "game_complete" | "series_complete";

interface SimulatorState {
  status: SimulatorStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  coachingSide: "blue" | "red" | null;
  draftMode: DraftMode;
  draftState: DraftState | null;
  recommendations: SimulatorRecommendation[] | null;
  roleGroupedRecommendations: RoleGroupedRecommendations | null;
  teamEvaluation: TeamEvaluation | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  isRecordingWinner: boolean;
  gameNumber: number;
  seriesStatus: SeriesStatus | null;
  fearlessBlocked: FearlessBlocked;
  error: string | null;
  // Finalized role assignments at draft end
  blueCompWithRoles: FinalizedPick[] | null;
  redCompWithRoles: FinalizedPick[] | null;

  // LLM insights
  llmLoading: boolean;
  llmInsight: LLMInsightsResponse | null;
  llmApiKey: string | null;
}

const initialState: SimulatorState = {
  status: "setup",
  sessionId: null,
  blueTeam: null,
  redTeam: null,
  coachingSide: null,
  draftMode: "normal",
  draftState: null,
  recommendations: null,
  roleGroupedRecommendations: null,
  teamEvaluation: null,
  isOurTurn: false,
  isEnemyThinking: false,
  isRecordingWinner: false,
  gameNumber: 1,
  seriesStatus: null,
  fearlessBlocked: {},
  error: null,
  blueCompWithRoles: null,
  redCompWithRoles: null,
  llmLoading: false,
  llmInsight: null,
  llmApiKey: null,
};

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useSimulatorSession() {
  const [state, setState] = useState<SimulatorState>(initialState);

  // Track pending timers and abort controllers for cleanup
  const pendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const llmApiKeyRef = useRef<string | null>(null);

  // Keep sessionId ref in sync
  useEffect(() => {
    sessionIdRef.current = state.sessionId;
  }, [state.sessionId]);

  // Keep llmApiKey ref in sync
  useEffect(() => {
    llmApiKeyRef.current = state.llmApiKey;
  }, [state.llmApiKey]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pendingTimerRef.current) {
        clearTimeout(pendingTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const cancelPendingOperations = useCallback(() => {
    if (pendingTimerRef.current) {
      clearTimeout(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const fetchRecommendations = useCallback(async (sessionId: string, expectedActionCount: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${sessionId}/recommendations`);
      if (!res.ok) return;

      const data: RecommendationsResponse = await res.json();

      // Discard stale recommendations
      if (data.for_action_count !== expectedActionCount) {
        console.debug(`Discarding stale recommendations: got ${data.for_action_count}, expected ${expectedActionCount}`);
        return;
      }

      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        if (s.draftState?.action_count !== expectedActionCount) return s;
        return {
          ...s,
          recommendations: data.recommendations,
          roleGroupedRecommendations: data.role_grouped ?? null,
        };
      });
    } catch (err) {
      console.error("Failed to fetch recommendations:", err);
    }
  }, []);

  const fetchLlmInsights = useCallback(async (
    sessionId: string,
    actionCount: number,
    apiKey: string
  ) => {
    setState((s) => ({ ...s, llmLoading: true, llmInsight: null }));

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${sessionId}/insights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, action_count: actionCount }),
      });

      if (!res.ok) {
        throw new Error("Failed to fetch insights");
      }

      const data: LLMInsightsResponse = await res.json();

      // Only update if still relevant (action count matches)
      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        if (s.draftState?.action_count !== actionCount) {
          // Stale response, ignore
          return { ...s, llmLoading: false };
        }
        return { ...s, llmLoading: false, llmInsight: data };
      });
    } catch (err) {
      setState((s) => ({
        ...s,
        llmLoading: false,
        llmInsight: { status: "error", message: String(err) },
      }));
    }
  }, []);

  const setLlmApiKey = useCallback((apiKey: string | null) => {
    setState((s) => ({ ...s, llmApiKey: apiKey }));
  }, []);

  // fetchEvaluation is available via GET /evaluation endpoint if needed for explicit refetch
  // Currently unused as we use eager fetch via ?include_evaluation=true query param

  const triggerEnemyAction = useCallback(async (sessionId: string) => {
    if (sessionIdRef.current !== sessionId) return;

    setState((s) => ({ ...s, isEnemyThinking: true }));

    abortControllerRef.current = new AbortController();

    try {
      // Use query params for eager fetch when it will be our turn
      const url = `${API_BASE}/api/simulator/sessions/${sessionId}/actions/enemy?include_recommendations=true&include_evaluation=true`;
      const res = await fetch(url, {
        method: "POST",
        signal: abortControllerRef.current.signal,
      });

      if (sessionIdRef.current !== sessionId) return;
      if (!res.ok) throw new Error("Failed to get enemy action");

      const data: SimulatorActionResponse = await res.json();
      const isComplete = data.draft_state.phase === "COMPLETE";

      setState((s) => {
        if (s.sessionId !== sessionId) return s;

        // STALENESS GUARD: Reject if incoming action_count is not newer than current
        const currentCount = s.draftState?.action_count ?? 0;
        const incomingCount = data.draft_state.action_count;
        if (incomingCount <= currentCount) {
          console.debug(`Discarding stale action response: got ${incomingCount}, have ${currentCount}`);
          return { ...s, isEnemyThinking: false };
        }

        return {
          ...s,
          status: isComplete ? "game_complete" : "drafting",
          draftState: data.draft_state,
          // Use eager-fetched data if available, otherwise null
          recommendations: data.recommendations ?? null,
          teamEvaluation: data.evaluation ?? null,
          isOurTurn: data.is_our_turn,
          isEnemyThinking: false,
          // Store finalized role assignments when draft completes
          blueCompWithRoles: data.blue_comp_with_roles ?? null,
          redCompWithRoles: data.red_comp_with_roles ?? null,
        };
      });

      // Fetch LLM insights if API key is set and it's our turn
      const currentApiKey = llmApiKeyRef.current;
      if (currentApiKey && data.is_our_turn && !isComplete) {
        fetchLlmInsights(sessionId, data.draft_state.action_count, currentApiKey);
      }

      // If still enemy's turn, continue
      if (!data.is_our_turn && !isComplete && sessionIdRef.current === sessionId) {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(sessionId);
        }, 1000);
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setState((s) => {
        if (s.sessionId !== sessionId) return s;
        return { ...s, error: String(err), isEnemyThinking: false };
      });
    }
  }, [fetchLlmInsights]);

  const startSession = useCallback(async (config: SimulatorConfig) => {
    cancelPendingOperations();

    // Preserve llmApiKey across session start - it's set before startSession is called
    const preservedApiKey = llmApiKeyRef.current;
    setState({ ...initialState, status: "setup", llmApiKey: preservedApiKey });

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blue_team_id: config.blueTeamId,
          red_team_id: config.redTeamId,
          coaching_side: config.coachingSide,
          series_length: config.seriesLength,
          draft_mode: config.draftMode,
        }),
      });

      if (!res.ok) throw new Error("Failed to start session");

      const data: SimulatorStartResponse = await res.json();
      const actionCount = data.draft_state.action_count;

      setState({
        ...initialState,
        llmApiKey: preservedApiKey,  // Preserve API key
        status: "drafting",
        sessionId: data.session_id,
        blueTeam: data.blue_team,
        redTeam: data.red_team,
        coachingSide: config.coachingSide,
        draftMode: config.draftMode,
        draftState: data.draft_state,
        recommendations: null, // Fetch separately
        roleGroupedRecommendations: null, // Fetch separately
        teamEvaluation: null,
        isOurTurn: data.is_our_turn,
        gameNumber: data.game_number,
      });

      // Fetch recommendations if it's our turn
      if (data.is_our_turn) {
        fetchRecommendations(data.session_id, actionCount);
        // Also fetch LLM insights if API key is set
        if (preservedApiKey) {
          fetchLlmInsights(data.session_id, actionCount, preservedApiKey);
        }
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(data.session_id);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [cancelPendingOperations, triggerEnemyAction, fetchRecommendations, fetchLlmInsights]);

  const submitAction = useCallback(async (champion: string) => {
    const currentSessionId = state.sessionId;
    if (!currentSessionId || !state.isOurTurn) return;

    try {
      // Include evaluation for composition feedback after our pick
      const url = `${API_BASE}/api/simulator/sessions/${currentSessionId}/actions?include_evaluation=true`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ champion }),
      });

      if (!res.ok) throw new Error("Failed to submit action");

      const data: SimulatorActionResponse = await res.json();
      const isComplete = data.draft_state.phase === "COMPLETE";
      const incomingCount = data.draft_state.action_count;

      setState((s) => {
        // STALENESS GUARD: Reject if incoming action_count is not newer
        const currentCount = s.draftState?.action_count ?? 0;
        if (incomingCount <= currentCount) {
          console.debug(`Discarding stale submitAction response: got ${incomingCount}, have ${currentCount}`);
          return s;
        }

        return {
          ...s,
          status: isComplete ? "game_complete" : "drafting",
          draftState: data.draft_state,
          // Clear recommendations - will be refetched if still our turn (double-pick)
          recommendations: null,
          roleGroupedRecommendations: null,
          teamEvaluation: data.evaluation ?? null,
          isOurTurn: data.is_our_turn,
          // Store finalized role assignments when draft completes
          blueCompWithRoles: data.blue_comp_with_roles ?? null,
          redCompWithRoles: data.red_comp_with_roles ?? null,
        };
      });

      // Fetch LLM insights if API key is set
      const currentApiKey = llmApiKeyRef.current;
      if (currentApiKey && !isComplete) {
        fetchLlmInsights(currentSessionId, incomingCount, currentApiKey);
      }

      // Handle next action based on turn
      if (isComplete) {
        // Draft complete, nothing to do
      } else if (data.is_our_turn) {
        // Double-pick window: still our turn, fetch fresh recommendations
        fetchRecommendations(currentSessionId, incomingCount);
      } else {
        // Enemy's turn
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(currentSessionId);
        }, 1000);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.isOurTurn, triggerEnemyAction, fetchRecommendations, fetchLlmInsights]);

  const recordWinner = useCallback(async (winner: "blue" | "red") => {
    if (!state.sessionId || state.isRecordingWinner) return;

    setState((s) => ({ ...s, isRecordingWinner: true }));

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${state.sessionId}/games/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ winner }),
      });

      if (!res.ok) throw new Error("Failed to record winner");

      const data: CompleteGameResponse = await res.json();

      setState((s) => ({
        ...s,
        status: data.series_status.series_complete ? "series_complete" : "game_complete",
        seriesStatus: data.series_status,
        fearlessBlocked: data.fearless_blocked,
        isRecordingWinner: false,
      }));
    } catch (err) {
      setState((s) => ({ ...s, error: String(err), isRecordingWinner: false }));
    }
  }, [state.sessionId, state.isRecordingWinner]);

  const nextGame = useCallback(async () => {
    const currentSessionId = state.sessionId;
    const currentCoachingSide = state.coachingSide;
    if (!currentSessionId) return;

    try {
      const res = await fetch(`${API_BASE}/api/simulator/sessions/${currentSessionId}/games/next`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Failed to start next game");

      const data: NextGameResponse = await res.json();
      const isOurTurn = data.draft_state.next_team === currentCoachingSide;
      const actionCount = data.draft_state.action_count;

      setState((s) => ({
        ...s,
        status: "drafting",
        draftState: data.draft_state,
        gameNumber: data.game_number,
        fearlessBlocked: data.fearless_blocked,
        recommendations: null,
        roleGroupedRecommendations: null,
        teamEvaluation: null,
        isOurTurn,
        blueCompWithRoles: null,
        redCompWithRoles: null,
      }));

      if (isOurTurn) {
        fetchRecommendations(currentSessionId, actionCount);
        // Also fetch LLM insights if API key is set
        const currentApiKey = llmApiKeyRef.current;
        if (currentApiKey) {
          fetchLlmInsights(currentSessionId, actionCount, currentApiKey);
        }
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(currentSessionId);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.coachingSide, triggerEnemyAction, fetchRecommendations, fetchLlmInsights]);

  const endSession = useCallback(async () => {
    cancelPendingOperations();

    const currentSessionId = state.sessionId;
    if (currentSessionId) {
      fetch(`${API_BASE}/api/simulator/sessions/${currentSessionId}`, { method: "DELETE" }).catch(() => {});
    }

    setState(initialState);
  }, [state.sessionId, cancelPendingOperations]);

  return {
    ...state,
    startSession,
    submitAction,
    recordWinner,
    nextGame,
    endSession,
    setLlmApiKey,
  };
}
