import { useEffect, useRef, useState } from "react";
import type { StatusEvent } from "./types";

const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/status`;

export function useStatus() {
  const [event, setEvent] = useState<StatusEvent>({ state: "idle", detail: null, entry: null });
  const ws = useRef<WebSocket | null>(null);

  // WebSocket — real-time pipeline events
  useEffect(() => {
    function connect() {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;
      socket.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data as string);
          if (data.type === "ping") return;
          setEvent(data as StatusEvent);
        } catch { /* ignore */ }
      };
      socket.onclose = () => setTimeout(connect, 2000);
    }
    connect();
    return () => ws.current?.close();
  }, []);

  // Poll /api/status every 800ms as a reliable fallback for button state
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/status");
        const data = await res.json() as { state: string };
        setEvent(prev => {
          const next = data.state as StatusEvent["state"];
          const prevIsRecording = prev.state === "recording";
          const nextIsRecording = next === "recording";
          // Always sync recording ↔ non-recording (button must appear/disappear).
          if (prevIsRecording !== nextIsRecording) return { ...prev, state: next };
          // Unstick from processing states when backend is idle/done.
          if (["transcribing", "cleaning_up", "injecting"].includes(prev.state) &&
              (next === "idle" || next === "done")) {
            return { ...prev, state: next };
          }
          // Terminal states: always sync.
          if (prev.state === "idle" || prev.state === "done" || prev.state === "error") {
            return { ...prev, state: next };
          }
          return prev;
        });
      } catch { /* backend unreachable */ }
    }, 800);
    return () => clearInterval(id);
  }, []);

  return event;
}
