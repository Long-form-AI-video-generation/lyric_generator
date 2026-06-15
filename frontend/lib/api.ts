import axios from "axios";
import type { AiBackground, ExportResolution, JobStatus, LyricsFile, Preset, Storyboard, UploadResponse } from "@/lib/types";

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

export async function startAlignment(jobToken: string, lyricsText: string) {
  const response = await fetch(`${API_BASE}/api/align`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_token: jobToken, lyrics_text: lyricsText })
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

export async function uploadSpeakerImage(jobToken: string, artistName: string, file: File) {
  const form = new FormData();
  form.append("image", file);
  const response = await fetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(jobToken)}/speaker-image/${encodeURIComponent(artistName)}`,
    { method: "POST", body: form },
  );
  return readJson<{ ok: boolean }>(response);
}

export async function startArtDirection(
  jobToken: string,
  stylePrompt: string,
  backgroundImageB64?: string,
  songConfigYaml?: string,
  openaiApiKey?: string,
) {
  const response = await fetch(`${API_BASE}/api/art-direct`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_token: jobToken,
      style_prompt: stylePrompt,
      background_image_b64: backgroundImageB64 ?? null,
      song_config_yaml: songConfigYaml ?? null,
      openai_api_key: openaiApiKey || null,
    }),
  });
  return readJson<{ job_token: string; status: "queued" }>(response);
}

export async function getStoryboard(jobToken: string): Promise<Storyboard> {
  const response = await fetch(`${API_BASE}/api/storyboard/${jobToken}`, {
    cache: "no-store",
  });
  return readJson<Storyboard>(response);
}

export type SpeakerImage = {
  name: string;
  slug: string;
  url: string;
  generated_url?: string;
  duo_generated_urls?: Record<string, string>;
};

export async function getSpeakerImages(jobToken: string): Promise<SpeakerImage[]> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobToken}/speakers`, { cache: "no-store" });
  const payload = await readJson<{ speakers: SpeakerImage[] }>(response);
  return payload.speakers.map(s => ({
    ...s,
    url: `${API_BASE}${s.url}`,
    ...(s.generated_url ? { generated_url: `${API_BASE}${s.generated_url}` } : {}),
    ...(s.duo_generated_urls
      ? { duo_generated_urls: Object.fromEntries(Object.entries(s.duo_generated_urls).map(([k, v]) => [k, `${API_BASE}${v}`])) }
      : {}),
  }));
}

export async function generateArtistImages(
  jobToken: string,
  stylePrompt: string,
  openaiApiKey: string,
  pairs?: [string, string][],
): Promise<{ ok: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobToken)}/generate-artist-images`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      style_prompt: stylePrompt,
      openai_api_key: openaiApiKey,
      pairs: pairs ?? null,
    }),
  });
  return readJson<{ ok: boolean; message: string }>(response);
}

export async function getAiBackgrounds(jobToken: string): Promise<AiBackground[]> {
  const response = await fetch(`${API_BASE}/api/jobs/${jobToken}/backgrounds`, {
    cache: "no-store",
  });
  const payload = await readJson<{ backgrounds: AiBackground[] }>(response);
  // Rewrite relative URLs to absolute so the canvas can load them cross-origin
  return payload.backgrounds.map(bg => ({
    ...bg,
    url: `${API_BASE}${bg.url}`,
  }));
}

export function assetUrl(path: string) {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

