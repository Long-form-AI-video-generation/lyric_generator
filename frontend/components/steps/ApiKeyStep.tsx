"use client";

import { ChevronLeft, ChevronRight, ExternalLink, Eye, EyeOff, Film, KeyRound } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/store/useAppStore";

export function ApiKeyStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const { openaiApiKey, setOpenaiApiKey, setStep } = useAppStore();
  const [show, setShow] = useState(false);

  const hasKey = openaiApiKey.trim().startsWith("sk-");

  
  function skipToPreview() {
    setStep(5);
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <div className="grid gap-4 lg:flex-1 lg:grid-cols-[1fr_340px]">

        {/* Main card */}
        <div className="flex flex-col gap-6 rounded-xl border border-border bg-surface p-6">
          <div>
            <h2 className="font-display text-xl font-black tracking-normal">OpenAI API Key</h2>
            <p className="mt-1 text-sm text-muted">
              The next step uses AI to design your video's look - fonts, colors, animations, and
              optionally AI-generated background images. Paste your OpenAI key below to get started.
            </p>
          </div>

        
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-zinc-300" htmlFor="openai-api-key">
              API Key{" "}
              <span className="font-normal text-muted">(starts with sk-…)</span>
            </label>
            <div className="relative">
              <input
                id="openai-api-key"
                type={show ? "text" : "password"}
                className="focus-ring w-full rounded-lg border border-border bg-background px-3 py-2.5 pr-11 font-mono text-sm text-text placeholder:text-zinc-600"
                placeholder="sk-..."
                value={openaiApiKey}
                onChange={(e) => setOpenaiApiKey(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShow((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 transition hover:text-zinc-300"
                aria-label={show ? "Hide key" : "Show key"}
              >
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {hasKey ? (
              <p className="text-xs text-green-400">✓ Key looks good</p>
            ) : (
              <p className="text-xs text-muted">
                Don't have a key?{" "}
                <button
                  type="button"
                  onClick={skipToPreview}
                  className="text-violet-400 underline-offset-2 hover:text-violet-300 hover:underline transition"
                >
                  Skip AI features and go straight to preview →
                </button>
              </p>
            )}
          </div>

          
          <div className="rounded-lg border border-border bg-zinc-900/40 p-4 text-xs">
            <p className="mb-2 font-medium text-zinc-300">What your key is used for</p>
            <ul className="flex flex-col gap-1.5 text-muted">
              <li className="flex gap-2">
                <span className="mt-0.5 shrink-0 text-violet-400">▸</span>
                <span>
                  <strong className="text-zinc-400">GPT-4o</strong> : reads your lyrics and style description, then assigns a unique font, color, animation, and effect to every lyric line
                </span>
              </li>
              <li className="flex gap-2">
                <span className="mt-0.5 shrink-0 text-violet-400">▸</span>
                <span>
                  <strong className="text-zinc-400">gpt-image-1</strong> : generates up to 6 unique background images that match the song's theme (only if you enable AI Backgrounds in the next step)
                </span>
              </li>
            </ul>
          </div>

          <a
            href="https://platform.openai.com/api-keys"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-violet-400 transition hover:text-violet-300"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Get your key at platform.openai.com/api-keys
          </a>
        </div>

        {/* Sidebar */}
        <aside className="hidden flex-col gap-4 rounded-xl border border-border bg-surface p-4 text-sm lg:flex">
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 shrink-0 text-violet-400" />
            <h3 className="font-display text-base font-black tracking-normal">Privacy</h3>
          </div>

          <ul className="flex flex-col gap-2 text-xs text-muted">
            <li className="flex gap-2">
              <span className="mt-0.5 shrink-0 text-violet-400">▸</span>
              Your key is never saved to disk , it only lives in this browser tab and is cleared when you start over
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 shrink-0 text-violet-400">▸</span>
              It is sent over HTTPS to your own server, which uses it to call OpenAI on your behalf
            </li>
            
          </ul>

          <hr className="border-border" />

          
          <div className="rounded-lg border border-dashed border-border bg-zinc-900/30 p-3">
            <p className="mb-2 text-xs font-medium text-zinc-400">No API key? No problem.</p>
            <p className="mb-3 text-xs text-muted">
              Skip AI art direction entirely and go straight to the preview. Your video will render
              with clean default styling. you can always come back and add a key later.
            </p>
            <button
              type="button"
              onClick={skipToPreview}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-700 hover:text-white"
            >
              <Film className="h-3.5 w-3.5" />
              Skip to Preview
            </button>
          </div>
        </aside>
      </div>

      {/* Nav */}
      <div className="mt-auto flex gap-3">
        <Button variant="secondary" className="h-12 px-5" onClick={onBack}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Back
        </Button>
        <Button
          className="h-12 flex-1 text-base"
          onClick={onNext}
        >
          Continue to AI Art Direction
          <ChevronRight className="h-4 w-4" aria-hidden />
        </Button>
      </div>
    </div>
  );
}
