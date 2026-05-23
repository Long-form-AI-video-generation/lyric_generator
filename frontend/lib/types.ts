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
  phase?: "uploaded" | "transcribing" | "art_directing" | "rendering" | null;
  progress_pct: number;
  result_url?: string | null;
  error?: string | null;
  debug_log?: string | null;
};

export type StoryboardLine = {
  line_id: number;
  font: string;
  text_color: string;
  font_size_pct: number;
  position: { x_pct: number; y_pct: number };
  animation: string;
  background: {
    image_index: number;
    filter: string;
    speaker_distortion: string;
    speaker_opacity: number;
  };
  transition: string;
  image_prompt: string | null;
};

export type Storyboard = {
  title: string;
  style_prompt: string;
  lines: StoryboardLine[];
  created_at: number;
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

export type AiBackground = { index: number; url: string };

export type SpeakerConfig = {
  id: string;
  name: string;
  font: string;
  text_color: string;
  animation: string;
  font_size_pct: number;
  position_y_pct: number;
};

export type SectionRule = {
  id: string;
  sections: string[];
  style: string;
};

export type SongConfigForm = {
  speakers: SpeakerConfig[];
  section_rules: SectionRule[];
  generate_ai_backgrounds: boolean;
};

