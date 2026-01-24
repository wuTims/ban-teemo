// deepdraft/src/hooks/useReplaySession.ts
import { useState, useCallback, useEffect, useRef } from "react";
import type {
  TeamContext,
  DraftState,
  Recommendations,
  WebSocketMessage,
  DraftAction,
} from "../types";

type SessionStatus = "idle" | "connecting" | "playing" | "complete" | "error";

interface ReplaySessionState {
  status: SessionStatus;
  sessionId: string | null;
  blueTeam: TeamContext | null;
  redTeam: TeamContext | null;
  draftState: DraftState | null;
  recommendations: Recommendations | null;
  lastAction: DraftAction | null;
  totalActions: number;
  patch: string | null;
  error: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace("http", "ws");

export function useReplaySession() {
  const [state, setState] = useState<ReplaySessionState>({
    status: "idle",
    sessionId: null,
    blueTeam: null,
    redTeam: null,
    draftState: null,
    recommendations: null,
    lastAction: null,
    totalActions: 0,
    patch: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);

  const startReplay = useCallback(async (
    seriesId: string,
    gameNumber: number,
    speed: number = 1.0,
    delaySeconds: number = 3.0,
  ) => {
    setState(prev => ({ ...prev, status: "connecting", error: null }));

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
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start replay: ${response.statusText}`);
      }

      const data = await response.json();
      const { session_id, websocket_url } = data;

      // Connect WebSocket
      const ws = new WebSocket(`${WS_BASE}${websocket_url}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg: WebSocketMessage = JSON.parse(event.data);

        switch (msg.type) {
          case "session_start":
            setState(prev => ({
              ...prev,
              status: "playing",
              sessionId: msg.session_id,
              blueTeam: msg.blue_team,
              redTeam: msg.red_team,
              totalActions: msg.total_actions,
              patch: msg.patch,
            }));
            break;

          case "draft_action":
            setState(prev => ({
              ...prev,
              draftState: msg.draft_state,
              recommendations: msg.recommendations,
              lastAction: msg.action,
            }));
            break;

          case "draft_complete":
            setState(prev => ({
              ...prev,
              status: "complete",
              draftState: msg.draft_state,
            }));
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
    setState({
      status: "idle",
      sessionId: null,
      blueTeam: null,
      redTeam: null,
      draftState: null,
      recommendations: null,
      lastAction: null,
      totalActions: 0,
      patch: null,
      error: null,
    });
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
  };
}
