"use client";

import { AlignLeft, ChevronLeft, Loader2, Wand2 } from "lucide-react";
import { useState } from "react";
import { getLyrics, startAlignment, startTranscription } from "@/lib/api";
import { pollJobStatus } from "@/lib/jobs";
import { LyricEditor } from "@/components/LyricEditor";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

async function pollJob(jobToken: string, onProgress: (pct: number) => void) {
  const status = await pollJobStatus(jobToken, {
    timeoutMs: 30 * 60 * 1000,
    timeoutMessage: "Operation is taking longer than expected.",
    onProgress,
  });
  if (status.status === "failed") throw new Error(status.error || "Operation failed.");
  return getLyrics(jobToken);
}

export function LyricsStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const { upload, lyrics, setLyrics, resetLyrics, setError } = useAppStore();
  const [generateBusy, setGenerateBusy] = useState(false);
  const [generateProgress, setGenerateProgress] = useState(0);
  const [alignBusy, setAlignBusy] = useState(false);
  const [alignProgress, setAlignProgress] = useState(0);
  const [lyricsText, setLyricsText] = useState("");
  const [alignError, setAlignError] = useState("");

  const busy = generateBusy || alignBusy;

  async function generateLyrics() {
    if (!upload.jobToken) return;
    setGenerateBusy(true);
    setGenerateProgress(3);
    setError("");
    try {
      await startTranscription(upload.jobToken);
      const result = await pollJob(upload.jobToken, setGenerateProgress);
      setLyrics(result, true);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Transcription failed.");
    } finally {
      setGenerateBusy(false);
    }
  }

  async function alignLyrics() {
    if (!upload.jobToken || !lyricsText.trim()) return;
    setAlignError("");
    setAlignBusy(true);
    setAlignProgress(3);
    setError("");
    try {
      await startAlignment(upload.jobToken, lyricsText.trim());
      const result = await pollJob(upload.jobToken, setAlignProgress);
      setLyrics(result, true);
    } catch (error) {
      setAlignError(error instanceof Error ? error.message : "Alignment failed.");
    } finally {
      setAlignBusy(false);
    }
  }

  if (!lyrics) {
    return (
      <div className="flex flex-1 flex-col gap-5">
        <div className="grid flex-1 gap-4 lg:grid-cols-2">
          {/* Auto-generate card */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-6">
            <div>
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-lg bg-violet-500/15 text-violet-100">
                <Wand2 className="h-6 w-6" aria-hidden />
              </div>
              <h2 className="font-display text-2xl font-black tracking-normal">Auto-generate</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
                Whisper runs on the backend and detects lyrics with timestamps from the audio.
              </p>
            </div>
            <div className="mt-8 grid gap-4">
              {generateBusy ? (
                <div className="grid gap-2">
                  <div className="flex items-center justify-between text-sm text-zinc-200">
                    <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Processing</span>
                    <span>{generateProgress}%</span>
                  </div>
                  <ProgressBar value={generateProgress} />
                  <div className="text-xs text-muted">Estimated time depends on the server model and device.</div>
                </div>
              ) : null}
              <Button className="h-12 w-full" disabled={busy} onClick={generateLyrics}>
                <Wand2 className="h-4 w-4" aria-hidden />
                Generate Lyrics
              </Button>
            </div>
          </div>

          {/* Paste lyrics card */}
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-6">
            <div className="flex flex-1 flex-col">
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-lg bg-emerald-500/15 text-emerald-100">
                <AlignLeft className="h-6 w-6" aria-hidden />
              </div>
              <h2 className="font-display text-2xl font-black tracking-normal">Paste Lyrics</h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                Paste the lyrics text below one line per lyric line.
              </p>
              <textarea
                className="mt-4 flex-1 min-h-[160px] w-full resize-none rounded-lg border border-border bg-background p-3 text-sm leading-6 text-zinc-200 placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
                placeholder={"Verse 1 line one\nVerse 1 line two\nChorus line..."}
                value={lyricsText}
                onChange={(e) => setLyricsText(e.target.value)}
                disabled={busy}
                spellCheck={false}
              />
            </div>
            <div className="mt-4 grid gap-3">
              {alignError ? <StatusBanner tone="error">{alignError}</StatusBanner> : null}
              {alignBusy ? (
                <div className="grid gap-2">
                  <div className="flex items-center justify-between text-sm text-zinc-200">
                    <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Aligning</span>
                    <span>{alignProgress}%</span>
                  </div>
                  <ProgressBar value={alignProgress} />
                </div>
              ) : null}
              <Button
                className="h-12 w-full"
                variant="secondary"
                disabled={busy || !lyricsText.trim()}
                onClick={alignLyrics}
              >
                <AlignLeft className="h-4 w-4" aria-hidden />
                Align to Audio
              </Button>
            </div>
          </div>
        </div>
        <div className="mt-auto flex gap-3">
          <Button variant="secondary" className="h-12 px-5" onClick={onBack}>
            <ChevronLeft className="h-4 w-4" aria-hidden />
            Back
          </Button>
          <Button className="h-12 flex-1 text-base" disabled>
            Next
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.8fr)]">
        <div className="min-h-0 rounded-xl border border-border bg-surface p-4">
          <LyricEditor
            lyrics={lyrics}
            onChange={(next) => setLyrics(next)}
            onReset={resetLyrics}
            onUploadLyrics={(next) => setLyrics(next, true)}
          />
        </div>
      </div>
      <div className="mt-auto flex gap-3">
        <Button variant="secondary" className="h-12 px-5" onClick={onBack}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Back
        </Button>
        <Button className="h-12 flex-1 text-base" disabled={!lyrics.lines.length} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}
