import { useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { useStatus } from "./lib/useStatus";
import { History } from "./pages/History";
import { Settings } from "./pages/Settings";
import { api } from "./lib/api";

type Tab = "settings" | "history";

export function App() {
  const [tab, setTab] = useState<Tab>("settings");
  const status = useStatus();

  const isRecording = status.state === "recording";
  const isBusy = ["transcribing", "cleaning_up", "injecting"].includes(status.state);

  return (
    <div style={shell}>
      <header style={header}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22 }}>🎙</span>
          <span style={{ fontWeight: 700, fontSize: 18, color: "#f9fafb" }}>WhisperLinux</span>
        </div>

        {isRecording ? (
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={pulsingDot} />
            <span style={{ color: "#ef4444", fontWeight: 600, fontSize: 14 }}>Recording…</span>
            <button
              onClick={() => api.stopDictation()}
              style={doneBtn}
              title="Done — process speech"
            >
              ✓ Done
            </button>
          </div>
        ) : (
          <button
            onClick={() => api.startDictation()}
            disabled={isBusy}
            style={{ ...recordBtn, opacity: isBusy ? 0.5 : 1, cursor: isBusy ? "default" : "pointer" }}
          >
            {isBusy ? "Processing…" : "● Record"}
          </button>
        )}
      </header>

      <div style={{ padding: "8px 24px 0" }}>
        <StatusBar event={status} />
      </div>

      <nav style={nav}>
        {(["settings", "history"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={tabBtn(t === tab)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <main style={main}>
        {tab === "settings" ? <Settings /> : <History />}
      </main>
    </div>
  );
}

const shell: React.CSSProperties = {
  minHeight: "100vh",
  background: "#111827",
  color: "#f9fafb",
  fontFamily: "system-ui, sans-serif",
  display: "flex",
  flexDirection: "column",
};
const header: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "16px 24px",
  borderBottom: "1px solid #1f2937",
};
const nav: React.CSSProperties = {
  display: "flex",
  gap: 4,
  padding: "0 24px",
  borderBottom: "1px solid #1f2937",
};
const main: React.CSSProperties = {
  flex: 1,
  padding: "24px",
  maxWidth: 680,
  width: "100%",
  margin: "0 auto",
};
const recordBtn: React.CSSProperties = {
  border: "none",
  background: "#3b82f6",
  color: "#fff",
  borderRadius: 6,
  padding: "8px 18px",
  fontWeight: 600,
  fontSize: 14,
};
const doneBtn: React.CSSProperties = {
  border: "none",
  background: "#10b981",
  color: "#fff",
  borderRadius: 6,
  padding: "8px 20px",
  fontWeight: 700,
  fontSize: 15,
  cursor: "pointer",
};
const pulsingDot: React.CSSProperties = {
  width: 12,
  height: 12,
  borderRadius: "50%",
  background: "#ef4444",
  animation: "pulse 1s infinite",
};
const tabBtn = (active: boolean): React.CSSProperties => ({
  background: "none",
  border: "none",
  padding: "10px 16px",
  fontSize: 14,
  cursor: "pointer",
  color: active ? "#f9fafb" : "#6b7280",
  borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
  fontWeight: active ? 600 : 400,
});
