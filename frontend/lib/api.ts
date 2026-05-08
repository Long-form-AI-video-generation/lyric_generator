import axios from "axios";
import type { ExportResolution, JobStatus, LyricsFile, Preset, UploadResponse } from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : "Request failed.";
    throw new Error(detail);
  }
  return payload as T;
}

export async function fetchPresets(): Promise<Preset[]> {
  const response = await fetch(`${API_BASE}/api/presets`, { cache: "no-store" });
  const payload = await readJson<{ presets: Preset[] }>(response);
  return payload.presets;
}

export async function uploadAudio(file: File, onProgress?: (pct: number) => void): Promise<UploadResponse> {
  const form = new FormData();
  form.append("audio", file);
  const response = await axios.post<UploadResponse>(`${API_BASE}/api/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress(event) {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    }
  });
  return response.data;
}

export async function startTranscription(jobToken: string) {
  const response = await fetch(`${API_BASE}/api/transcribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_token: jobToken })
  });
  return readJson<{ job_token: string; status: "queued" }>(response);
}

export async function getJobStatus(jobToken: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE}/api/status/${jobToken}`, { cache: "no-store" });
  return readJson<JobStatus>(response);
}

export async function getLyrics(jobToken: string): Promise<LyricsFile> {
  const response = await fetch(`${API_BASE}/api/lyrics/${jobToken}`, { cache: "no-store" });
  return readJson<LyricsFile>(response);
}

export async function startExport(params: {
  jobToken: string;
  lyrics: LyricsFile;
  presetId?: string;
  background?: File;
  resolution: ExportResolution;
  fps: 30 | 60;
}) {
  const form = new FormData();
  form.append("job_token", params.jobToken);
  form.append("lyrics", JSON.stringify(params.lyrics));
  form.append("resolution", params.resolution);
  form.append("fps", String(params.fps));
  if (params.presetId) {
    form.append("preset_id", params.presetId);
  }
  if (params.background) {
    form.append("background", params.background);
  }
  const response = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    body: form
  });
  return readJson<{ job_token: string; status: "queued" }>(response);
}

export function downloadUrl(pathOrToken: string) {
  if (pathOrToken.startsWith("/")) {
    return `${API_BASE}${pathOrToken}`;
  }
  return `${API_BASE}/api/download/${pathOrToken}`;
}

export function assetUrl(path: string) {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

