import { useEffect, useRef, useState } from "react";
import type { StatusEvent } from "./types";

const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/status`;

export function useStatus() {
  const [event, setEvent] = useState<StatusEvent>({ state: "idle", detail: null, entry: null });
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    function connect() {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;

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
        // Reconnect after 2s on unexpected close.
        setTimeout(connect, 2000);
      };
    }

    connect();
    return () => ws.current?.close();
  }, []);

  return event;
}
