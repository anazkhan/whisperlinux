import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { HistoryEntry } from "../lib/types";

export function History() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setEntries(await api.getHistory());
    setLoading(false);
  }

  async function handleClear() {
    await api.clearHistory();
    setEntries([]);
  }

  useEffect(() => { void load(); }, []);

  if (loading) return <p style={{ color: "#9ca3af" }}>Loading…</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <span style={{ color: "#9ca3af", fontSize: 13 }}>{entries.length} dictation{entries.length !== 1 ? "s" : ""}</span>
        {entries.length > 0 && (
          <button onClick={handleClear} style={clearBtn}>Clear history</button>
        )}
      </div>

      {entries.length === 0 ? (
        <p style={{ color: "#6b7280", fontStyle: "italic" }}>No dictations yet. Use your hotkey to record.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {entries.map((e, i) => (
            <div key={i} style={card}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ color: "#6b7280", fontSize: 12 }}>
                  {new Date(e.timestamp).toLocaleString()}
                </span>
                {e.cleanup_skipped && (
                  <span style={{ color: "#f59e0b", fontSize: 11, fontWeight: 600 }}>
                    cleanup skipped
                  </span>
                )}
              </div>
              <div style={{ marginBottom: 6 }}>
                <span style={label}>Cleaned</span>
                <p style={textBlock}>{e.cleaned_text}</p>
              </div>
              {e.raw_text !== e.cleaned_text && (
                <div>
                  <span style={{ ...label, color: "#6b7280" }}>Raw transcript</span>
                  <p style={{ ...textBlock, color: "#9ca3af" }}>{e.raw_text}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const card: React.CSSProperties = {
  background: "#1f2937",
  border: "1px solid #374151",
  borderRadius: 8,
  padding: 14,
};
const label: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "#10b981",
};
const textBlock: React.CSSProperties = {
  margin: "4px 0 0",
  fontSize: 14,
  color: "#f9fafb",
  lineHeight: 1.5,
};
const clearBtn: React.CSSProperties = {
  background: "transparent",
  border: "1px solid #4b5563",
  color: "#9ca3af",
  borderRadius: 5,
  padding: "4px 10px",
  fontSize: 12,
  cursor: "pointer",
};
