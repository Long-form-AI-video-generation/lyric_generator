"use client";

import { FileJson, Loader2, Wand2 } from "lucide-react";
import { useRef, useState } from "react";
import { getLyrics, startTranscription } from "@/lib/api";
import { pollJobStatus } from "@/lib/jobs";
import { parseLyricsJson } from "@/lib/lyrics";
import { LyricEditor } from "@/components/LyricEditor";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

async function pollTranscription(jobToken: string, onProgress: (pct: number) => void) {
  const status = await pollJobStatus(jobToken, {
    timeoutMs: 30 * 60 * 1000,
    timeoutMessage: "Transcription is taking longer than expected. You can retry or upload a lyrics JSON file.",
    onProgress
  });
  if (status.status === "failed") throw new Error(status.error || "Transcription failed.");
  return getLyrics(jobToken);
}

export function LyricsStep({ onNext }: { onNext: () => void }) {
  const { upload, lyrics, setLyrics, resetLyrics, setError } = useAppStore();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showJson, setShowJson] = useState(true);
  const [manualError, setManualError] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function generateLyrics() {
    if (!upload.jobToken) return;
    setBusy(true);
    setProgress(3);
    setError("");
    try {
      await startTranscription(upload.jobToken);
      const result = await pollTranscription(upload.jobToken, setProgress);
      setLyrics(result, true);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Transcription failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleManualUpload(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const result = parseLyricsJson(parsed);
      setManualError("");
      setLyrics(result, true);
    } catch (error) {
      setManualError(error instanceof Error ? error.message : "Invalid lyrics JSON.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  if (!lyrics) {
    return (
      <div className="flex flex-1 flex-col gap-5">
        <div className="grid flex-1 gap-4 lg:grid-cols-2">
          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-6">
            <div>
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-lg bg-violet-500/15 text-violet-100">
                <Wand2 className="h-6 w-6" aria-hidden />
              </div>
              <h2 className="font-display text-2xl font-black tracking-normal">Auto-generate</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
                Whisper runs on the backend worker and returns editable line timestamps.
              </p>
            </div>
            <div className="mt-8 grid gap-4">
              {busy ? (
                <div className="grid gap-2">
                  <div className="flex items-center justify-between text-sm text-zinc-200">
                    <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Transcribing</span>
                    <span>{progress}%</span>
                  </div>
                  <ProgressBar value={progress} />
                  <div className="text-xs text-muted">Estimated time depends on the server model and device.</div>
                </div>
              ) : null}
              <Button className="h-12 w-full" disabled={busy} onClick={generateLyrics}>
                <Wand2 className="h-4 w-4" aria-hidden />
                Generate Lyrics
              </Button>
            </div>
          </div>

          <div className="flex flex-col justify-between rounded-xl border border-border bg-surface p-6">
            <div>
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-lg bg-emerald-500/15 text-emerald-100">
                <FileJson className="h-6 w-6" aria-hidden />
              </div>
              <h2 className="font-display text-2xl font-black tracking-normal">Upload JSON</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted">
                Use an existing lyrics file with title, duration_seconds, and timed lines.
              </p>
            </div>
            <div className="mt-8 grid gap-4">
              {manualError ? <StatusBanner tone="error">{manualError}</StatusBanner> : null}
              <input ref={inputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => handleManualUpload(event.target.files?.[0])} />
              <Button className="h-12 w-full" variant="secondary" onClick={() => inputRef.current?.click()}>
                <FileJson className="h-4 w-4" aria-hidden />
                Choose JSON
              </Button>
            </div>
          </div>
        </div>
        <div className="mt-auto">
          <Button className="h-12 w-full text-base" disabled>
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
        <div className="min-h-0 rounded-xl border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-lg font-black tracking-normal">JSON</h2>
            <Button variant="ghost" onClick={() => setShowJson((value) => !value)}>{showJson ? "Hide" : "Show"}</Button>
          </div>
          {showJson ? (
            <pre className="max-h-[620px] overflow-auto rounded-lg border border-border bg-background p-4 text-xs leading-5 text-zinc-300">
              {JSON.stringify(lyrics, null, 2)}
            </pre>
          ) : (
            <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted">{lyrics.lines.length} lyric lines loaded</div>
          )}
        </div>
      </div>
      <div className="mt-auto">
        <Button className="h-12 w-full text-base" disabled={!lyrics.lines.length} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}
