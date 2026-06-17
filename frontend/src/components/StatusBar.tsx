import type { StatusEvent } from "../lib/types";

const STATE_LABELS: Record<StatusEvent["state"], string> = {
  idle: "Idle — ready",
  recording: "Recording...",
  transcribing: "Transcribing...",
  cleaning_up: "Cleaning up with Gemini...",
  injecting: "Typing result...",
  done: "Done",
  error: "Error",
};

const STATE_COLORS: Record<StatusEvent["state"], string> = {
  idle: "#6b7280",
  recording: "#ef4444",
  transcribing: "#f59e0b",
  cleaning_up: "#3b82f6",
  injecting: "#8b5cf6",
  done: "#10b981",
  error: "#ef4444",
};

export function StatusBar({ event }: { event: StatusEvent }) {
  const color = STATE_COLORS[event.state];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0" }}>
      <span
        style={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
          boxShadow: event.state === "recording" ? `0 0 8px ${color}` : undefined,
        }}
      />
      <span style={{ color, fontWeight: 600, fontSize: 14 }}>
        {STATE_LABELS[event.state]}
        {event.detail ? ` — ${event.detail}` : ""}
      </span>
    </div>
  );
}
