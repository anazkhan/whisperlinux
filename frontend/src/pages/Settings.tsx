import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Config, Device, ModelOption } from "../lib/types";

export function Settings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Promise.all([api.getConfig(), api.getDevices(), api.getModels()]).then(
      ([cfg, devs, mods]) => {
        setConfig(cfg);
        setDevices(devs);
        setModels(mods);
      }
    );
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateConfig({
        hotkey: config.hotkey,
        mic_device: config.mic_device ?? undefined,
        stt_model: config.stt_model,
        stt_device: config.stt_device,
        language: config.language ?? undefined,
        gemini_model: config.gemini_model,
        ...(apiKey ? { gemini_api_key: apiKey } : {}),
      });
      setConfig(updated);
      setApiKey("");
      setSaved(true);
      if (savedTimer.current) clearTimeout(savedTimer.current);
      savedTimer.current = setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!config) return <p style={{ color: "#9ca3af" }}>Loading…</p>;

  return (
    <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* API Key */}
      <section>
        <h2 style={sectionTitle}>Gemini API Key</h2>
        <p style={hint}>
          {config.gemini_api_key_set
            ? "A key is saved. Paste a new one below to replace it."
            : "No key saved. Paste your Google Gemini API key to enable text cleanup."}
        </p>
        <input
          type="password"
          placeholder={config.gemini_api_key_set ? "Replace existing key…" : "Paste your API key…"}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={inputStyle}
        />
      </section>

      {/* Hotkey */}
      <section>
        <h2 style={sectionTitle}>Global Hotkey</h2>
        <p style={hint}>
          Format: <code style={code}>&lt;ctrl&gt;+&lt;alt&gt;+space</code>. On Wayland, bind{" "}
          <code style={code}>whisperlinux-toggle</code> in your DE keyboard settings instead.
        </p>
        <input
          type="text"
          value={config.hotkey}
          onChange={(e) => setConfig({ ...config, hotkey: e.target.value })}
          style={inputStyle}
        />
      </section>

      {/* Microphone */}
      <section>
        <h2 style={sectionTitle}>Microphone</h2>
        <select
          value={config.mic_device ?? ""}
          onChange={(e) => setConfig({ ...config, mic_device: e.target.value || null })}
          style={inputStyle}
        >
          <option value="">System default</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} {d.is_default ? "(default)" : ""}
            </option>
          ))}
        </select>
      </section>

      {/* STT Model */}
      <section>
        <h2 style={sectionTitle}>Speech-to-Text Model</h2>
        <select
          value={config.stt_model}
          onChange={(e) => setConfig({ ...config, stt_model: e.target.value as Config["stt_model"] })}
          style={inputStyle}
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </section>

      {/* STT Device */}
      <section>
        <h2 style={sectionTitle}>STT Compute Device</h2>
        <select
          value={config.stt_device}
          onChange={(e) => setConfig({ ...config, stt_device: e.target.value })}
          style={inputStyle}
        >
          <option value="auto">Auto (GPU if available, else CPU)</option>
          <option value="cpu">CPU (int8)</option>
          <option value="cuda">GPU / CUDA (float16)</option>
        </select>
      </section>

      {/* Language */}
      <section>
        <h2 style={sectionTitle}>Language</h2>
        <input
          type="text"
          placeholder="Auto-detect (leave blank)"
          value={config.language ?? ""}
          onChange={(e) => setConfig({ ...config, language: e.target.value || null })}
          style={inputStyle}
        />
        <p style={hint}>ISO 639-1 code, e.g. <code style={code}>en</code>, <code style={code}>fr</code>. Leave blank for auto-detect.</p>
      </section>

      {error && <p style={{ color: "#ef4444", margin: 0 }}>{error}</p>}

      <button type="submit" disabled={saving} style={btnStyle}>
        {saving ? "Saving…" : saved ? "Saved!" : "Save settings"}
      </button>
    </form>
  );
}

const sectionTitle: React.CSSProperties = { fontSize: 14, fontWeight: 600, margin: "0 0 6px", color: "#e5e7eb" };
const hint: React.CSSProperties = { fontSize: 12, color: "#9ca3af", margin: "0 0 8px" };
const code: React.CSSProperties = { background: "#1f2937", padding: "1px 5px", borderRadius: 4, fontFamily: "monospace" };
const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "#1f2937",
  border: "1px solid #374151",
  borderRadius: 6,
  padding: "8px 10px",
  color: "#f9fafb",
  fontSize: 14,
  boxSizing: "border-box",
};
const btnStyle: React.CSSProperties = {
  padding: "10px 20px",
  background: "#3b82f6",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  alignSelf: "flex-start",
};
