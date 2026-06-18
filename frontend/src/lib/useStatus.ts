import { useEffect, useRef, useState } from "react";
import type { StatusEvent } from "./types";

const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/status`;

export function useStatus() {
  const [event, setEvent] = useState<StatusEvent>({ state: "idle", detail: null, entry: null });
  const ws = useRef<WebSocket | null>(null);
  const wsConnected = useRef(false);

  // WebSocket for real-time pipeline events
  useEffect(() => {
    function connect() {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;

      socket.onopen = () => { wsConnected.current = true; };

      socket.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data as string);
          if (data.type === "ping") return;
          setEvent(data as StatusEvent);
        } catch {
          // ignore parse errors
        }
      };

      socket.onclose = () => {
        wsConnected.current = false;
        setTimeout(connect, 2000);
      };
    }

    connect();
    return () => ws.current?.close();
  }, []);

  // Poll /api/status every second as a fallback so the button always reflects reality
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/status");
        const data = await res.json() as { state: string };
        setEvent(prev => {
          // Only override with polled state if we're in a "terminal" state
          // (idle/done/error) — let WebSocket handle the in-progress transitions
          const terminal = ["idle", "done", "error"].includes(prev.state);
          if (data.state === "recording" || terminal) {
            return { ...prev, state: data.state as StatusEvent["state"] };
          }
          return prev;
        });
      } catch {
        // backend unreachable
      }
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return event;
}
