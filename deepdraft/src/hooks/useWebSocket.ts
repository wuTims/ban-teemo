/**
 * WebSocket hook for real-time draft updates.
 */

import { useEffect, useRef, useState, useCallback } from "react";

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export function useWebSocket({
  url,
  onMessage,
  reconnectAttempts = 5,
  reconnectInterval = 3000,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setStatus("connected");
      attemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage?.(data);
      } catch {
        console.error("Failed to parse WebSocket message");
      }
    };

    ws.onclose = () => {
      setStatus("disconnected");
      if (attemptsRef.current < reconnectAttempts) {
        attemptsRef.current++;
        setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = () => {
      setStatus("error");
    };

    wsRef.current = ws;
  }, [url, onMessage, reconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { status, connect, disconnect, send };
}
