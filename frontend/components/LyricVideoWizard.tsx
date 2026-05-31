"use client";

import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { UploadStep } from "@/components/steps/UploadStep";
import { LyricsStep } from "@/components/steps/LyricsStep";
import { BackgroundStep } from "@/components/steps/BackgroundStep";
import { ApiKeyStep } from "@/components/steps/ApiKeyStep";
import { ArtDirectStep } from "@/components/steps/ArtDirectStep";
import { PreviewStep } from "@/components/steps/PreviewStep";
import { Button } from "@/components/ui/Button";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

const steps = ["Upload", "Lyrics", "Background", "API Key", "Art Direction", "Preview"];

export function LyricVideoWizard() {
  const { step, setStep, reset, upload, lyrics, background, error } = useAppStore();

  const canContinue =
    (step === 0 && Boolean(upload.jobToken)) ||
    (step === 1 && Boolean(lyrics?.lines.length)) ||
    (step === 2 && Boolean(background)) ||
    step === 3 || 
    step === 4;

  function next() {
    if (step < 5 && canContinue) setStep((step + 1) as 0 | 1 | 2 | 3 | 4 | 5);
  }

  function back() {
    if (step > 0) setStep((step - 1) as 0 | 1 | 2 | 3 | 4 | 5);
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
        <div className="grid min-h-16 grid-cols-[1fr_auto] items-center gap-4 px-4 md:grid-cols-[1fr_2fr_1fr] md:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg border border-violet-500/40 bg-violet-500/15 font-display text-sm font-black text-white">
              LV
            </div>
            <div className="font-display text-lg font-black tracking-normal">LyricVid</div>
          </div>
          <nav aria-label="Wizard progress" className="hidden items-center gap-2 md:flex">
            {steps.map((label, index) => (
              <div key={label} className="flex flex-1 items-center gap-2">
                <div className={`h-2 flex-1 rounded-full ${index <= step ? "bg-primary" : "bg-zinc-800"}`} />
                <span className={`text-xs font-medium ${index === step ? "text-text" : "text-muted"}`}>{label}</span>
              </div>
            ))}
          </nav>
          <div className="flex justify-end">
            <Button variant="ghost" onClick={reset}>
              <RotateCcw className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">Start Over</span>
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-6 md:hidden">
          {steps.map((label, index) => (
            <button
              key={label}
              className={`h-1 ${index <= step ? "bg-primary" : "bg-zinc-800"}`}
              aria-label={label}
              onClick={() => index < step && setStep(index as 0 | 1 | 2 | 3 | 4 | 5)}
            />
          ))}
        </div>
      </header>

      <main className="mx-auto flex min-h-[calc(100vh-65px)] max-w-7xl flex-col px-4 py-5 md:px-6">
        {error ? <div className="mb-4"><StatusBanner tone="error">{error}</StatusBanner></div> : null}
        <AnimatePresence mode="wait">
          <motion.section
            key={step}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.18 }}
            className="flex flex-1 flex-col"
          >
            {step === 0 ? <UploadStep onNext={next} /> : null}
            {step === 1 ? <LyricsStep onNext={next} onBack={back} /> : null}
            {step === 2 ? <BackgroundStep onNext={next} onBack={back} /> : null}
            {step === 3 ? <ApiKeyStep onNext={next} onBack={back} /> : null}
            {step === 4 ? <ArtDirectStep onNext={next} onBack={back} /> : null}
            {step === 5 ? <PreviewStep onBack={back} /> : null}
          </motion.section>
        </AnimatePresence>
      </main>
    </div>
  );
}

