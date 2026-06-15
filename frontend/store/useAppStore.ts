"use client";

import { create } from "zustand";
import type { BackgroundSelection, JobStatus, LyricsFile, Preset, SongConfigForm, Storyboard } from "@/lib/types";

type WizardStep = 0 | 1 | 2 | 3 | 4 | 5;

type UploadState = {
  file: File | null;
  objectUrl: string | null;
  filename: string;
  duration: number;
  jobToken: string;
};

export const emptySpeaker = () => ({
  id: crypto.randomUUID(),
  name: "",
  font: "default",
  text_color: "#FFFFFF",
  animation: "fade-in",
  font_size_pct: 7,
  position_y_pct: 55,
  image_file: null as File | null,
  image_preview: "",
});

const defaultSongConfig: SongConfigForm = {
  global_style: "",
  speakers: [],
  section_rules: [],
  generate_ai_backgrounds: false,
};

type AppState = {
  step: WizardStep;
  upload: UploadState;
  uploadProgress: number;
  lyrics: LyricsFile | null;
  originalLyrics: LyricsFile | null;
  presets: Preset[];
  background: BackgroundSelection | null;
  storyboard: Storyboard | null;
  stylePrompt: string;
  songConfig: SongConfigForm;
  openaiApiKey: string;
  exportStatus: JobStatus | null;
  error: string;
  setStep: (step: WizardStep) => void;
  reset: () => void;
  setUploadProgress: (value: number) => void;
  setUpload: (payload: UploadState) => void;
  setLyrics: (lyrics: LyricsFile, makeOriginal?: boolean) => void;
  resetLyrics: () => void;
  setPresets: (presets: Preset[]) => void;
  setBackground: (background: BackgroundSelection) => void;
  setStoryboard: (storyboard: Storyboard | null) => void;
  setStylePrompt: (prompt: string) => void;
  setSongConfig: (config: SongConfigForm) => void;
  setOpenaiApiKey: (key: string) => void;
  setExportStatus: (status: JobStatus | null) => void;
  setError: (message: string) => void;
};

const emptyUpload: UploadState = {
  file: null,
  objectUrl: null,
  filename: "",
  duration: 0,
  jobToken: ""
};

export const useAppStore = create<AppState>((set, get) => ({
  step: 0,
  upload: emptyUpload,
  uploadProgress: 0,
  lyrics: null,
  originalLyrics: null,
  presets: [],
  background: null,
  storyboard: null,
  stylePrompt: "",
  songConfig: defaultSongConfig,
  openaiApiKey: "",
  exportStatus: null,
  error: "",
  setStep: (step) => set({ step, error: "" }),
  reset: () => {
    const { upload, background } = get();
    if (upload.objectUrl) URL.revokeObjectURL(upload.objectUrl);
    if (background?.type === "upload") URL.revokeObjectURL(background.previewUrl);
    set({
      step: 0,
      upload: emptyUpload,
      uploadProgress: 0,
      lyrics: null,
      originalLyrics: null,
      background: null,
      storyboard: null,
      stylePrompt: "",
      songConfig: { ...defaultSongConfig },
      exportStatus: null,
      error: ""
    });
  },
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  setUpload: (payload) => set({ upload: payload, uploadProgress: 100, error: "" }),
  setLyrics: (lyrics, makeOriginal = false) =>
    set((state) => ({
      lyrics,
      originalLyrics: makeOriginal ? structuredClone(lyrics) : state.originalLyrics,
      error: ""
    })),
  resetLyrics: () => {
    const original = get().originalLyrics;
    if (original) set({ lyrics: structuredClone(original), error: "" });
  },
  setPresets: (presets) => set({ presets }),
  setBackground: (background) => set({ background, error: "" }),
  setStoryboard: (storyboard) => set({ storyboard }),
  setStylePrompt: (stylePrompt) => set({ stylePrompt }),
  setSongConfig: (songConfig) => set({ songConfig }),
  setOpenaiApiKey: (openaiApiKey) => set({ openaiApiKey }),
  setExportStatus: (exportStatus) => set({ exportStatus }),
  setError: (error) => set({ error })
}));
