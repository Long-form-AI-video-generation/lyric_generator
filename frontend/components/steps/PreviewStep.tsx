"use client";

import { ChevronLeft, Download, FileWarning, Film, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { downloadUrl, getAiBackgrounds, startExport } from "@/lib/api";
import { pollJobStatus } from "@/lib/jobs";
import type { AiBackground, ExportResolution } from "@/lib/types";
import { AudioPlayer } from "@/components/AudioPlayer";
import { LyricCanvas } from "@/components/LyricCanvas";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

async function pollExport(jobToken: string, onProgress: (pct: number) => void) {
  return pollJobStatus(jobToken, {
    timeoutMs: 10 * 60 * 1000,
    timeoutMessage: "Export is taking longer than expected. Please retry the render.",
    onProgress
  });
}

export function PreviewStep({ onBack }: { onBack: () => void }) {
  const { upload, lyrics, background, storyboard, exportStatus, setExportStatus, setError } = useAppStore();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [resolution, setResolution] = useState<ExportResolution>("1080p");
  const [fps, setFps] = useState<30 | 60>(30);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [renderLabel, setRenderLabel] = useState("Rendering…");
  const [aiBackgrounds, setAiBackgrounds] = useState<AiBackground[]>([]);

  
  useEffect(() => {
    if (!upload.jobToken) return;
    getAiBackgrounds(upload.jobToken)
      .then(setAiBackgrounds)
      .catch(() => setAiBackgrounds([]));
  }, [upload.jobToken, storyboard]);

  const ready = Boolean(upload.objectUrl && lyrics?.lines.length && background);
  const resultUrl = exportStatus?.result_url ? downloadUrl(exportStatus.result_url) : null;

  async function exportMp4() {
    if (!ready || !lyrics || !background) {
      setError("Add at least one lyric line and select a background before exporting.");
      return;
    }
    const invalid = lyrics.lines.find((line) => !line.text.trim() || line.end <= line.start);
    if (invalid) {
      setError(`Line ${invalid.id} needs valid text, start, and end times.`);
      return;
    }
    setBusy(true);
    setProgress(0);
    setRenderLabel("Preparing…");
    setExportStatus(null);
    setError("");
    try {
      await startExport({
        jobToken: upload.jobToken,
        lyrics,
        presetId: background.type === "preset" ? background.presetId : undefined,
        background: background.type === "upload" ? background.file : undefined,
        resolution,
        fps
      });
      const status = await pollExport(upload.jobToken, (pct) => {
        setProgress(pct);
        if (pct < 36)       setRenderLabel("Preparing…");
        else if (pct < 70)  setRenderLabel("Building frames…");
        else if (pct < 95)  setRenderLabel("Encoding video…");
        else                setRenderLabel("Finishing up…");
      });
      setExportStatus(status);
      if (status.status === "failed") setError(status.error || "Export failed.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || !lyrics || !background || !upload.objectUrl) {
    return (
      <div className="grid flex-1 place-items-center">
        <StatusBanner tone="error">
          <span className="inline-flex items-center gap-2"><FileWarning className="h-4 w-4" aria-hidden /> The preview needs audio, lyrics, and a background.</span>
        </StatusBanner>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">

        <div className="grid gap-3">
          <LyricCanvas lyrics={lyrics} backgroundUrl={background.previewUrl} isCustomBackground={background.type === "upload"} audioRef={audioRef} currentTime={currentTime} playing={playing} storyboard={storyboard} aiBackgrounds={aiBackgrounds} />
          <AudioPlayer src={upload.objectUrl} audioRef={audioRef} onTimeChange={setCurrentTime} onPlayingChange={setPlaying} />
        </div>

        <aside className="rounded-xl border border-border bg-surface p-4">
          <h2 className="mb-4 font-display text-xl font-black tracking-normal">Export</h2>
          <div className="grid gap-4">
            <label className="grid gap-2 text-sm font-medium text-zinc-200">
              Resolution
              <select className="focus-ring h-10 rounded-lg border border-border bg-background px-3 text-text" value={resolution} onChange={(event) => setResolution(event.target.value as ExportResolution)}>
                <option value="1080p">1080p</option>
                <option value="720p">720p</option>
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium text-zinc-200">
              FPS
              <select className="focus-ring h-10 rounded-lg border border-border bg-background px-3 text-text" value={fps} onChange={(event) => setFps(Number(event.target.value) as 30 | 60)}>
                <option value={30}>30</option>
                <option value={60}>60</option>
              </select>
            </label>
            {busy ? (
              <div className="grid gap-2 rounded-lg border border-border bg-background p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {renderLabel}</span>
                  <span>{progress}%</span>
                </div>
                <ProgressBar value={progress} />
              </div>
            ) : null}
            {resultUrl ? (
              <Button asChild variant="success" className="h-12 w-full text-base">
                <a href={resultUrl}>
                  <Download className="h-4 w-4" aria-hidden />
                  Download Ready
                </a>
              </Button>
            ) : (
              <Button className="h-12 w-full bg-gradient-to-r from-violet-600 to-violet-500 text-base hover:from-violet-500 hover:to-violet-400" disabled={busy} onClick={exportMp4}>
                <Film className="h-4 w-4" aria-hidden />
                Export MP4
              </Button>
            )}
            {/* {exportStatus?.status === "failed" && exportStatus.debug_log ? (
              <details className="rounded-lg border border-border bg-background p-3 text-sm text-zinc-300">
                <summary className="cursor-pointer text-zinc-100">Debug</summary>
                <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{exportStatus.debug_log}</pre>
              </details>
            ) : null} */}
          </div>
        </aside>
      </div>
      <div className="mt-auto">
        <Button variant="secondary" className="h-12 px-5" onClick={onBack}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Back
        </Button>
      </div>
    </div>
  );
}
