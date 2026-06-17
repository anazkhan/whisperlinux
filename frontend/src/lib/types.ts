export type ModelSize = "tiny" | "base" | "small" | "medium" | "large";

export interface Config {
  hotkey: string;
  mic_device: string | null;
  stt_model: ModelSize;
  stt_device: string;
  language: string | null;
  gemini_model: string;
  gemini_api_key_set: boolean;
}

export interface Device {
  id: string;
  name: string;
  is_default: boolean;
}

export interface ModelOption {
  id: ModelSize;
  label: string;
  approx_size_mb: number;
}

export interface HistoryEntry {
  timestamp: string;
  raw_text: string;
  cleaned_text: string;
  cleanup_skipped: boolean;
}

export interface StatusEvent {
  state: "idle" | "recording" | "transcribing" | "cleaning_up" | "injecting" | "done" | "error";
  detail: string | null;
  entry: HistoryEntry | null;
}
