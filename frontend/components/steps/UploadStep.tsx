"use client";

import { CloudUpload, FileAudio2, Music2 } from "lucide-react";
import { useCallback, useState } from "react";
import { uploadAudio } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

const MAX_AUDIO_BYTES = 200 * 1024 * 1024;

async function waveformFromFile(file: File) {
  try {
    const audioContext = new AudioContext();
    const buffer = await audioContext.decodeAudioData(await file.arrayBuffer());
    const data = buffer.getChannelData(0);
    const bars = 72;
    const block = Math.floor(data.length / bars);
    const values = Array.from({ length: bars }, (_, index) => {
      let sum = 0;
      const start = index * block;
      for (let i = 0; i < block; i += 1) sum += Math.abs(data[start + i] || 0);
      return Math.min(1, (sum / Math.max(1, block)) * 6);
    });
    await audioContext.close();
    return { values, duration: buffer.duration };
  } catch {
    return { values: Array.from({ length: 72 }, (_, index) => 0.25 + ((index * 13) % 9) / 14), duration: 0 };
  }
}

export function UploadStep({ onNext }: { onNext: () => void }) {
  const { upload, uploadProgress, setUpload, setUploadProgress, setError } = useAppStore();
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [bars, setBars] = useState<number[]>([]);

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      const extension = file.name.split(".").pop()?.toLowerCase();
      if (!["mp3", "wav"].includes(extension || "")) {
        setError("Please upload an MP3 or WAV audio file.");
        return;
      }
      if (file.size > MAX_AUDIO_BYTES) {
        setError("Audio uploads are limited to 200 MB.");
        return;
      }
      setBusy(true);
      setError("");
      setUploadProgress(0);
      try {
        const local = await waveformFromFile(file);
        setBars(local.values);
        const response = await uploadAudio(file, setUploadProgress);
        setUpload({
          file,
          objectUrl: URL.createObjectURL(file),
          filename: response.filename,
          duration: response.duration_seconds || local.duration,
          jobToken: response.job_token
        });
      } catch (error) {
        setError(error instanceof Error ? error.message : "The audio upload failed.");
      } finally {
        setBusy(false);
      }
    },
    [setError, setUpload, setUploadProgress]
  );

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div
        className={`grid min-h-[200px] place-items-center rounded-xl border border-dashed p-6 transition md:min-h-[360px] md:p-8 ${
          dragging ? "border-primary bg-violet-500/10 shadow-glow" : "border-border bg-surface"
        }`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFile(event.dataTransfer.files?.[0]);
        }}
      >
        <label className="flex w-full max-w-2xl cursor-pointer flex-col items-center gap-5 text-center">
          <input type="file" accept="audio/mpeg,audio/wav,.mp3,.wav" className="hidden" onChange={(event) => handleFile(event.target.files?.[0])} />
          <div className="grid h-12 w-12 place-items-center rounded-xl border border-violet-500/30 bg-violet-500/15 md:h-16 md:w-16">
            <CloudUpload className="h-6 w-6 text-violet-200 md:h-8 md:w-8" aria-hidden />
          </div>
          <div>
            <div className="font-display text-2xl font-black tracking-normal md:text-3xl">Upload audio</div>
            <div className="mt-1 text-sm text-muted md:mt-2">MP3 or WAV, up to 200 MB</div>
          </div>
          <Button variant="secondary" asChild><span>Choose File</span></Button>
        </label>
      </div>

      {busy ? (
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-2 flex items-center justify-between text-sm text-zinc-200">
            <span>Uploading</span>
            <span>{uploadProgress}%</span>
          </div>
          <ProgressBar value={uploadProgress} />
        </div>
      ) : null}

      {upload.file ? (
        <div className="grid gap-4 rounded-xl border border-border bg-surface p-4 md:grid-cols-[auto_1fr_auto] md:items-center">
          <div className="grid h-12 w-12 place-items-center rounded-lg bg-emerald-500/15 text-emerald-200">
            <FileAudio2 className="h-6 w-6" aria-hidden />
          </div>
          <div className="min-w-0">
            <div className="truncate font-semibold">{upload.filename}</div>
            <div className="text-sm text-muted">{formatBytes(upload.file.size)} · {formatDuration(upload.duration)}</div>
            <div className="mt-3 flex h-12 items-center gap-1 overflow-hidden" aria-label="Waveform visualisation">
              {(bars.length ? bars : Array.from({ length: 72 }, () => 0.35)).map((value, index) => (
                <span key={index} className="w-1 flex-1 rounded-full bg-primary/80" style={{ height: `${Math.max(8, value * 44)}px` }} />
              ))}
            </div>
          </div>
          <StatusBanner tone="success">
            <span className="inline-flex items-center gap-2"><Music2 className="h-4 w-4" aria-hidden /> Ready</span>
          </StatusBanner>
        </div>
      ) : null}

      <div className="mt-auto pt-2">
        <Button className="h-12 w-full text-base" disabled={!upload.jobToken || busy} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}

