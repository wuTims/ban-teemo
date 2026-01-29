// deepdraft/src/hooks/useSimulatorSession.ts
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
  teamEvaluation: TeamEvaluation | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesStatus: SeriesStatus | null;
  fearlessBlocked: FearlessBlocked;
  error: string | null;
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
  teamEvaluation: null,
  isOurTurn: false,
  isEnemyThinking: false,
  gameNumber: 1,
  seriesStatus: null,
  fearlessBlocked: {},
  error: null,
};

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useSimulatorSession() {
  const [state, setState] = useState<SimulatorState>(initialState);

  // Track pending timers and abort controllers for cleanup
  const pendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  // Keep sessionId ref in sync
  useEffect(() => {
    sessionIdRef.current = state.sessionId;
  }, [state.sessionId]);

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
        return { ...s, recommendations: data.recommendations };
      });
    } catch (err) {
      console.error("Failed to fetch recommendations:", err);
    }
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
        };
      });

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
  }, []);

  const startSession = useCallback(async (config: SimulatorConfig) => {
    cancelPendingOperations();
    setState({ ...initialState, status: "setup" });

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
        status: "drafting",
        sessionId: data.session_id,
        blueTeam: data.blue_team,
        redTeam: data.red_team,
        coachingSide: config.coachingSide,
        draftMode: config.draftMode,
        draftState: data.draft_state,
        recommendations: null, // Fetch separately
        teamEvaluation: null,
        isOurTurn: data.is_our_turn,
        gameNumber: data.game_number,
      });

      // Fetch recommendations if it's our turn
      if (data.is_our_turn) {
        fetchRecommendations(data.session_id, actionCount);
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(data.session_id);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [cancelPendingOperations, triggerEnemyAction, fetchRecommendations]);

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
          teamEvaluation: data.evaluation ?? null,
          isOurTurn: data.is_our_turn,
        };
      });

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
  }, [state.sessionId, state.isOurTurn, triggerEnemyAction, fetchRecommendations]);

  const recordWinner = useCallback(async (winner: "blue" | "red") => {
    if (!state.sessionId) return;

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
      }));
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId]);

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
        teamEvaluation: null,
        isOurTurn,
      }));

      if (isOurTurn) {
        fetchRecommendations(currentSessionId, actionCount);
      } else {
        pendingTimerRef.current = setTimeout(() => {
          triggerEnemyAction(currentSessionId);
        }, 500);
      }
    } catch (err) {
      setState((s) => ({ ...s, error: String(err) }));
    }
  }, [state.sessionId, state.coachingSide, triggerEnemyAction, fetchRecommendations]);

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
  };
}
