// frontend/src/hooks/useReplaySession.ts
import { useState, useCallback, useEffect, useRef } from "react";
import type {
  TeamContext,
  DraftState,
  Recommendations,
  WebSocketMessage,
  DraftAction,
  InsightEntry,
  ReplayActionLogEntry,
  LLMInsight,
  FinalizedPick,
} from "../types";

type SessionStatus = "idle" | "connecting" | "playing" | "paused" | "complete" | "error";

interface ReplaySessionState {
  status: SessionStatus;
  sessionId: string | null;
  seriesId: string | null;
  gameNumber: number | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
  recommendations: Recommendations | null;
  lastAction: DraftAction | null;
  actionHistory: ReplayActionLogEntry[];
  recommendationHistory: InsightEntry[];
  llmInsights: Map<number, LLMInsight>;
  llmTimeouts: Set<number>;  // Action counts that timed out
  isWaitingForLLM: boolean;
  waitingForActionCount: number | null;
  totalActions: number;
  patch: string | null;
  seriesScoreBefore: { blue: number; red: number } | null;
  seriesScoreAfter: { blue: number; red: number } | null;
  winnerSide: "blue" | "red" | null;
  error: string | null;
  // Finalized role assignments at draft end
  blueCompWithRoles: FinalizedPick[] | null;
  redCompWithRoles: FinalizedPick[] | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace("http", "ws");

export function useReplaySession() {
  const [state, setState] = useState<ReplaySessionState>({
    status: "idle",
    sessionId: null,
    seriesId: null,
    gameNumber: null,
    blueTeam: null,
    redTeam: null,
    draftState: null,
    recommendations: null,
    lastAction: null,
    actionHistory: [],
    recommendationHistory: [],
    llmInsights: new Map(),
    llmTimeouts: new Set(),
    isWaitingForLLM: false,
    waitingForActionCount: null,
    totalActions: 0,
    patch: null,
    seriesScoreBefore: null,
    seriesScoreAfter: null,
    winnerSide: null,
    error: null,
    blueCompWithRoles: null,
    redCompWithRoles: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const pendingReplayInfoRef = useRef<{ seriesId: string; gameNumber: number } | null>(null);

  const startReplay = useCallback(async (
    seriesId: string,
    gameNumber: number,
    speed: number = 1.0,
    delaySeconds: number = 5.0,
    llmEnabled: boolean = false,
    llmApiKey: string | null = null,
    waitForLlm: boolean = false,
  ) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    pendingReplayInfoRef.current = { seriesId, gameNumber };
    setState(prev => {
      const isNewSeries = prev.seriesId !== seriesId;
      if (isNewSeries) {
        return {
          status: "connecting",
          sessionId: null,
          seriesId,
          gameNumber: null,
          blueTeam: null,
          redTeam: null,
          draftState: null,
          recommendations: null,
          lastAction: null,
          actionHistory: [],
          recommendationHistory: [],
          llmInsights: new Map(),
          llmTimeouts: new Set(),
          isWaitingForLLM: false,
          waitingForActionCount: null,
          totalActions: 0,
          patch: null,
          seriesScoreBefore: null,
          seriesScoreAfter: null,
          winnerSide: null,
          error: null,
          blueCompWithRoles: null,
          redCompWithRoles: null,
        };
      }

      // Different game in same series - still need full reset
      return {
        ...prev,
        status: "connecting",
        seriesId,
        gameNumber: null,
        blueTeam: null,
        redTeam: null,
        draftState: null,
        recommendations: null,
        lastAction: null,
        actionHistory: [],
        recommendationHistory: [],
        llmInsights: new Map(),
        llmTimeouts: new Set(),
        isWaitingForLLM: false,
        waitingForActionCount: null,
        totalActions: 0,
        patch: null,
        seriesScoreBefore: null,
        seriesScoreAfter: null,
        winnerSide: null,
        error: null,
        blueCompWithRoles: null,
        redCompWithRoles: null,
      };
    });

    try {
      // Start replay session via REST
      const response = await fetch(`${API_BASE}/api/replay/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          series_id: seriesId,
          game_number: gameNumber,
          speed,
          delay_seconds: delaySeconds,
          llm_enabled: llmEnabled,
          llm_api_key: llmApiKey,
          wait_for_llm: waitForLlm,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start replay: ${response.statusText}`);
      }

      const data = await response.json();
      const { websocket_url } = data;

      // Connect WebSocket
      const ws = new WebSocket(`${WS_BASE}${websocket_url}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg: WebSocketMessage = JSON.parse(event.data);

        switch (msg.type) {
          case "session_start":
            setState(prev => {
              const pendingInfo = pendingReplayInfoRef.current;
              const seriesScoreBefore = msg.series_score_before ?? null;
              const seriesScoreAfter = msg.series_score_after ?? null;
              const winnerSide = msg.winner_side ?? null;
              const labelParts = [];
              if (pendingInfo) {
                labelParts.push(`Series ${pendingInfo.seriesId}`);
                labelParts.push(`Game ${pendingInfo.gameNumber}`);
              } else {
                labelParts.push("New Replay");
              }
              labelParts.push(`${msg.blue_team.name} vs ${msg.red_team.name}`);
              if (msg.patch) {
                labelParts.push(`Patch ${msg.patch}`);
              }

              const marker = {
                kind: "marker" as const,
                sessionId: msg.session_id,
                label: `${labelParts.join(" · ")} · Start`,
                timestamp: Date.now(),
                winnerSide,
                score: seriesScoreBefore,
              };

              return {
                ...prev,
                status: "playing",
                sessionId: msg.session_id,
                seriesId: msg.series_id,
                gameNumber: msg.game_number,
                blueTeam: msg.blue_team,
                redTeam: msg.red_team,
                totalActions: msg.total_actions,
                patch: msg.patch,
                seriesScoreBefore,
                seriesScoreAfter,
                winnerSide,
                draftState: null,
                recommendations: null,
                lastAction: null,
                actionHistory: [...prev.actionHistory, marker],
                recommendationHistory: [...prev.recommendationHistory, marker],
              };
            });
            break;

          case "draft_action":
            setState(prev => ({
              ...prev,
              draftState: msg.draft_state,
              recommendations: msg.recommendations,
              lastAction: msg.action,
              actionHistory: [
                ...prev.actionHistory,
                {
                  kind: "action",
                  sessionId: prev.sessionId ?? "unknown",
                  action: msg.action,
                },
              ],
              recommendationHistory: [...prev.recommendationHistory, {
                kind: "action",
                sessionId: prev.sessionId ?? "unknown",
                action: msg.action,
                recommendations: msg.recommendations,
              }],
            }));
            break;

          case "draft_complete":
            setState(prev => ({
              ...prev,
              status: "complete",
              draftState: msg.draft_state,
              blueCompWithRoles: msg.blue_comp_with_roles ?? null,
              redCompWithRoles: msg.red_comp_with_roles ?? null,
              actionHistory: [
                ...prev.actionHistory,
                {
                  kind: "marker",
                  sessionId: prev.sessionId ?? "unknown",
                  label: `Game ${prev.gameNumber ?? "?"} · End`,
                  timestamp: Date.now(),
                  winnerSide: prev.winnerSide,
                  score: prev.seriesScoreAfter ?? prev.seriesScoreBefore,
                },
              ],
              recommendationHistory: [
                ...prev.recommendationHistory,
                {
                  kind: "marker",
                  sessionId: prev.sessionId ?? "unknown",
                  label: `Game ${prev.gameNumber ?? "?"} · End`,
                  timestamp: Date.now(),
                  winnerSide: prev.winnerSide,
                  score: prev.seriesScoreAfter ?? prev.seriesScoreBefore,
                },
              ],
            }));
            break;

          case "enhanced_recommendations":
            setState(prev => {
              const newInsights = new Map(prev.llmInsights);
              newInsights.set(msg.action_count, {
                actionCount: msg.action_count,
                forTeam: msg.for_team,
                draftAnalysis: msg.draft_analysis,
                reranked: msg.reranked,
                additionalSuggestions: msg.additional_suggestions,
                receivedAt: Date.now(),
              });
              return {
                ...prev,
                llmInsights: newInsights,
                isWaitingForLLM: false,
                waitingForActionCount: null,
              };
            });
            break;

          case "waiting_for_llm":
            setState(prev => ({
              ...prev,
              isWaitingForLLM: true,
              waitingForActionCount: msg.action_count,
            }));
            break;

          case "llm_timeout":
            setState(prev => {
              const newTimeouts = new Set(prev.llmTimeouts);
              newTimeouts.add(msg.action_count);
              return {
                ...prev,
                llmTimeouts: newTimeouts,
                isWaitingForLLM: false,
                waitingForActionCount: null,
              };
            });
            break;

          case "paused":
            setState(prev => ({ ...prev, status: "paused" }));
            break;

          case "resumed":
            setState(prev => ({ ...prev, status: "playing" }));
            break;
        }
      };

      ws.onerror = () => {
        setState(prev => ({
          ...prev,
          status: "error",
          error: "WebSocket connection failed"
        }));
      };

      ws.onclose = () => {
        wsRef.current = null;
      };

    } catch (err) {
      setState(prev => ({
        ...prev,
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  const stopReplay = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    // Only update status - preserve board state so user can still see it
    setState(prev => ({
      ...prev,
      status: "idle",
      sessionId: null,
      isWaitingForLLM: false,
      waitingForActionCount: null,
    }));
  }, []);

  // Full reset - clears all state including board data (for series changes)
  const resetSession = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setState({
      status: "idle",
      sessionId: null,
      seriesId: null,
      gameNumber: null,
      blueTeam: null,
      redTeam: null,
      draftState: null,
      recommendations: null,
      lastAction: null,
      actionHistory: [],
      recommendationHistory: [],
      llmInsights: new Map(),
      llmTimeouts: new Set(),
      isWaitingForLLM: false,
      waitingForActionCount: null,
      totalActions: 0,
      patch: null,
      seriesScoreBefore: null,
      seriesScoreAfter: null,
      winnerSide: null,
      error: null,
      blueCompWithRoles: null,
      redCompWithRoles: null,
    });
  }, []);

  const pauseReplay = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "pause" }));
    }
  }, []);

  const resumeReplay = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "resume" }));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    startReplay,
    stopReplay,
    pauseReplay,
    resumeReplay,
    resetSession,
  };
}
