export type LyricLine = {
  id: number;
  text: string;
  start: number;
  end: number;
};

export type LyricsFile = {
  title: string;
  duration_seconds?: number | null;
  lines: LyricLine[];
};

export type Preset = {
  id: string;
  label: string;
  thumbnail_url: string;
};

export type JobStatus = {
  job_token: string;
  status: "queued" | "processing" | "complete" | "failed";
  phase?: "uploaded" | "transcribing" | "rendering" | null;
  progress_pct: number;
  result_url?: string | null;
  error?: string | null;
  debug_log?: string | null;
};

export type UploadResponse = {
  job_token: string;
  filename: string;
  duration_seconds: number;
};

export type BackgroundSelection =
  | {
      type: "preset";
      presetId: string;
      label: string;
      previewUrl: string;
    }
  | {
      type: "upload";
      file: File;
      previewUrl: string;
    };

export type ExportResolution = "1080p" | "720p";

