"use client";

import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Sparkles, SkipForward } from "lucide-react";
import { useState } from "react";
import { getStoryboard, startArtDirection } from "@/lib/api";
import { pollJobStatus } from "@/lib/jobs";
import type { StoryboardLine } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

const STYLE_PRESETS = [
  "Dark cinematic, deep shadows, dramatic text",
  "Neon glitch, cyberpunk, chromatic aberration",
  "Warm acoustic, soft blur, earthy tones",
  "Abstract minimal, clean typography, monochrome",
  "Lo-fi aesthetic, VHS grain, muted palette",
  "High-energy pop, bold colors, zoom animations",
];

const ANIMATION_COLORS: Record<string, string> = {
  "fade-in":         "bg-zinc-700 text-zinc-200",
  typewriter:        "bg-violet-900/60 text-violet-200",
  glitch:            "bg-red-900/50 text-red-300",
  "slide-from-left": "bg-blue-900/50 text-blue-300",
  "slide-from-right":"bg-blue-900/50 text-blue-300",
  "zoom-in":         "bg-amber-900/50 text-amber-300",
  pop:               "bg-green-900/50 text-green-300",
};

function AnimationBadge({ animation }: { animation: string }) {
  const cls = ANIMATION_COLORS[animation] ?? "bg-zinc-700 text-zinc-200";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {animation}
    </span>
  );
}

function StoryboardPreview({ lines }: { lines: StoryboardLine[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? lines : lines.slice(0, 5);

  return (
    <div className="rounded-xl border border-border bg-background overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted">
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">Animation</th>
            <th className="px-3 py-2 font-medium">Font</th>
            <th className="px-3 py-2 font-medium">Color</th>
            <th className="px-3 py-2 font-medium hidden sm:table-cell">Filter</th>
            <th className="px-3 py-2 font-medium hidden md:table-cell">Transition</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((line) => (
            <tr key={line.line_id} className="border-b border-border/50 hover:bg-surface/50">
              <td className="px-3 py-2 text-muted">{line.line_id}</td>
              <td className="px-3 py-2">
                <AnimationBadge animation={line.animation} />
              </td>
              <td className="px-3 py-2 text-zinc-300">{line.font}</td>
              <td className="px-3 py-2">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-3 w-3 rounded-full border border-white/20"
                    style={{ background: line.text_color }}
                  />
                  <span className="font-mono text-xs text-zinc-400">{line.text_color}</span>
                </span>
              </td>
              <td className="px-3 py-2 text-zinc-400 hidden sm:table-cell">{line.background.filter}</td>
              <td className="px-3 py-2 text-zinc-400 hidden md:table-cell">{line.transition}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {lines.length > 5 && (
        <button
          className="w-full py-2 text-center text-xs text-muted hover:text-text transition"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Show less" : `Show ${lines.length - 5} more lines…`}
        </button>
      )}
    </div>
  );
}


async function imageUrlToB64(url: string): Promise<string | undefined> {
  try {
    return await new Promise<string>((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        const MAX_W = 640;
        const MAX_H = 360;
        const scale = Math.min(MAX_W / img.width, MAX_H / img.height, 1);
        const canvas = document.createElement("canvas");
        canvas.width  = Math.round(img.width  * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
       
        resolve(canvas.toDataURL("image/jpeg", 0.75).split(",")[1]);
      };
      img.onerror = reject;
      img.src = url;
    });
  } catch {
    return undefined; 
  }
}

export function ArtDirectStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const { upload, background, storyboard, stylePrompt, setStoryboard, setStylePrompt, setError } = useAppStore();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [localError, setLocalError] = useState("");

  async function generate() {
    if (!stylePrompt.trim()) {
      setLocalError("Enter a style description first.");
      return;
    }
    setBusy(true);
    setProgress(0);
    setLocalError("");
    setStoryboard(null);
    try {
      const bgB64 = background?.previewUrl
        ? await imageUrlToB64(background.previewUrl)
        : undefined;
      await startArtDirection(upload.jobToken, stylePrompt.trim(), bgB64);
      const jobStatus = await pollJobStatus(upload.jobToken, {
        timeoutMs: 3 * 60 * 1000,
        timeoutMessage: "Art direction is taking longer than expected. Please try again.",
        onProgress: setProgress,
      });
      if (jobStatus.status === "failed") {
        throw new Error(jobStatus.error || "Art direction job failed. Check that OPENAI_API_KEY is set and lyrics have been transcribed.");
      }
      const sb = await getStoryboard(upload.jobToken);
      setStoryboard(sb);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Art direction failed.";
      setLocalError(msg);
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  function skip() {
    setStoryboard(null);
    onNext();
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      {localError ? <StatusBanner tone="error">{localError}</StatusBanner> : null}

      <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_380px]">

       
        <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4">
          <div>
            <h2 className="font-display text-xl font-black tracking-normal">AI Art Direction</h2>
            <p className="mt-1 text-sm text-muted">
              Describe the visual style and the AI will design fonts, colors, animations, and
              background effects for every lyric line.
            </p>
          </div>

          <textarea
            className="focus-ring min-h-[96px] w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-muted"
            placeholder="e.g. dark cinematic, neon accents, lo-fi glitch aesthetic"
            value={stylePrompt}
            onChange={(e) => setStylePrompt(e.target.value)}
            disabled={busy}
          />

          <div className="flex flex-wrap gap-2">
            {STYLE_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                disabled={busy}
                onClick={() => setStylePrompt(preset)}
                className={`rounded-full border px-3 py-1 text-xs transition ${
                  stylePrompt === preset
                    ? "border-primary bg-primary/20 text-text"
                    : "border-border text-muted hover:border-zinc-500 hover:text-text"
                }`}
              >
                {preset.split(",")[0]}
              </button>
            ))}
          </div>

          {busy && (
            <div className="grid gap-2 rounded-lg border border-border bg-background p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Generating storyboard…
                </span>
                <span>{progress}%</span>
              </div>
              <ProgressBar value={progress} />
            </div>
          )}

          {storyboard && !busy && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-green-400">
                  ✓ Storyboard ready — {storyboard.lines.length} lines directed
                </p>
                <button
                  onClick={generate}
                  className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-text transition"
                >
                  <RefreshCw className="h-3 w-3" />
                  Re-generate
                </button>
              </div>
              <StoryboardPreview lines={storyboard.lines} />
            </div>
          )}
        </div>

     
        <aside className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 text-sm">
          <h3 className="font-display text-base font-black tracking-normal">What this does</h3>
          <ul className="flex flex-col gap-2 text-muted">
            <li className="flex gap-2"><span className="mt-0.5 text-violet-400">▸</span> Sends your lyrics to GPT-4o with your style brief</li>
            <li className="flex gap-2"><span className="mt-0.5 text-violet-400">▸</span> Gets back a per-line storyboard: font, color, position, animation, background filter</li>
            <li className="flex gap-2"><span className="mt-0.5 text-violet-400">▸</span> Export then uses MoviePy to composite each line with its own look</li>
          </ul>
          <hr className="border-border" />
          <p className="text-muted">
            <span className="text-zinc-300 font-medium">Tip:</span> Try re-generating with the same
            prompt to get different creative variations — the LLM introduces variety each run.
          </p>
          <hr className="border-border" />
          <button
            onClick={skip}
            disabled={busy}
            className="mt-auto inline-flex items-center gap-1.5 text-xs text-muted hover:text-text transition disabled:opacity-50"
          >
            <SkipForward className="h-3.5 w-3.5" />
            Skip — use plain render instead
          </button>
        </aside>
      </div>

      <div className="mt-auto flex gap-3">
        <Button variant="secondary" className="h-12 px-5" onClick={onBack} disabled={busy}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Back
        </Button>
        <Button
          className="h-12 flex-1 text-base"
          onClick={storyboard ? onNext : generate}
          disabled={busy || !stylePrompt.trim()}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : storyboard ? (
            <>
              Next
              <ChevronRight className="h-4 w-4" aria-hidden />
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" aria-hidden />
              Generate
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
