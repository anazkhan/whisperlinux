import type { Config, Device, HistoryEntry, ModelOption } from "./types";

const BASE = "/api";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getConfig: () => req<Config>("/config"),
  updateConfig: (body: Partial<Config & { gemini_api_key: string }>) =>
    req<Config>("/config", { method: "PUT", body: JSON.stringify(body) }),
  getDevices: () => req<Device[]>("/devices"),
  getModels: () => req<ModelOption[]>("/models"),
  getHistory: () => req<HistoryEntry[]>("/history"),
  clearHistory: () => req<void>("/history", { method: "DELETE" }),
  startDictation: () => req<void>("/dictate/start", { method: "POST" }),
  stopDictation: () => req<void>("/dictate/stop", { method: "POST" }),
};
