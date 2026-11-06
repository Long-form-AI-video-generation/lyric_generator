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
    co_speakers: string[];
  };
  transition: string;
  image_prompt: string | null;
  speaker_name: string | null;
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
  project_id?: string | null;
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
  image_file: File | null;
  image_preview: string;   // object URL for thumbnail display
};

export type SectionRule = {
  id: string;
  sections: string[];
  style: string;
};

export type SongConfigForm = {
  global_style: string;
  speakers: SpeakerConfig[];
  section_rules: SectionRule[];
  generate_ai_backgrounds: boolean;
};

export type UserProfile = {
  id: string;
  email: string;
  role: "admin" | "user";
  status: "active" | "invited" | "revoked";
  credits_remaining: number;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type InviteVerifyResponse = {
  valid: boolean;
  email: string;
};

export type ProjectScene = {
  scene_order: number;
  start_time_ms: number;
  end_time_ms: number;
  prompt: string;
  transition_type: string;
};

export type ProjectExportInfo = {
  id: string;
  resolution: string;
  format: string;
  file_name: string;
  download_url: string;
  created_at: string;
};

export type ProjectItem = {
  id: string;
  title: string;
  status: string;
  styling_config?: Record<string, any>;
  lyrics?: {
    raw_text: string;
    timing_data: LyricLine[];
    source: string;
  } | null;
  scenes?: ProjectScene[];
  latest_export?: ProjectExportInfo | null;
  audio?: {
    id: string;
    file_name: string;
    mime_type: string;
    file_size_bytes: number;
    url: string;
  } | null;
  created_at: string;
  updated_at: string;
};

export type AdminUserItem = {
  id: string;
  email: string;
  role: "admin" | "user";
  status: "active" | "invited" | "revoked";
  credit_allowance: number;
  credits_used: number;
  credits_remaining: number;
  projects_count: number;
  created_at: string;
};

export type AdminInviteItem = {
  id: string;
  email: string;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
  status: "accepted" | "pending" | "expired";
};

