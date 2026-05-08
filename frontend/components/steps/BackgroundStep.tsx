"use client";

import { Check, ChevronLeft, ImagePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { assetUrl, fetchPresets } from "@/lib/api";
import type { Preset } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { StatusBanner } from "@/components/ui/StatusBanner";
import { useAppStore } from "@/store/useAppStore";

const MAX_BACKGROUND_BYTES = 20 * 1024 * 1024;

const fallbackPresets: Preset[] = [
  { id: "dark-gradient", label: "Dark Gradient", thumbnail_url: "/presets/dark-gradient.png" },
  { id: "starfield", label: "Starfield", thumbnail_url: "/presets/starfield.png" },
  { id: "abstract-violet", label: "Abstract Violet", thumbnail_url: "/presets/abstract-violet.png" },
  { id: "cinematic-grain", label: "Cinematic", thumbnail_url: "/presets/cinematic-grain.png" },
  { id: "deep-ocean", label: "Deep Ocean", thumbnail_url: "/presets/deep-ocean.png" },
  { id: "neon-city", label: "Neon City", thumbnail_url: "/presets/neon-city.png" }
];

function fallbackClass(id: string) {
  const classes: Record<string, string> = {
    "dark-gradient": "bg-[linear-gradient(160deg,#111827,#020203)]",
    starfield: "bg-[radial-gradient(circle_at_30%_20%,#f5f5f5_1px,transparent_2px),linear-gradient(180deg,#070b1d,#010104)]",
    "abstract-violet": "bg-[linear-gradient(135deg,#17112d,#0a0a12_45%,#06352f)]",
    "cinematic-grain": "bg-[linear-gradient(135deg,#171717,#050505)]",
    "deep-ocean": "bg-[linear-gradient(180deg,#063a3f,#030b12)]",
    "neon-city": "bg-[linear-gradient(100deg,#070812,#2f146d_24%,#064e3b_48%,#0f172a_76%,#831843)]"
  };
  return classes[id] || classes["dark-gradient"];
}

export function BackgroundStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const { presets, background, setBackground, setPresets, setError } = useAppStore();
  const [dragging, setDragging] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    fetchPresets()
      .then((items) => setPresets(items.length ? items : fallbackPresets))
      .catch(() => {
        setPresets(fallbackPresets);
        setLoadError("Preset thumbnails will appear after the backend starts.");
      });
  }, [setPresets]);

  function selectUpload(file: File | undefined) {
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!["jpg", "jpeg", "png", "webp"].includes(extension || "")) {
      setError("Please upload a JPG, PNG, or WebP background.");
      return;
    }
    if (file.size > MAX_BACKGROUND_BYTES) {
      setError("Background uploads are limited to 20 MB.");
      return;
    }
    if (background?.type === "upload") URL.revokeObjectURL(background.previewUrl);
    setBackground({ type: "upload", file, previewUrl: URL.createObjectURL(file) });
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      {loadError ? <StatusBanner>{loadError}</StatusBanner> : null}
      <div className="grid flex-1 gap-4 lg:grid-cols-[1.3fr_0.8fr]">
        <div className="rounded-xl border border-border bg-surface p-4">
          <h2 className="mb-4 font-display text-xl font-black tracking-normal">Presets</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {(presets.length ? presets : fallbackPresets).map((preset) => {
              const selected = background?.type === "preset" && background.presetId === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  className={`focus-ring group overflow-hidden rounded-lg border text-left transition ${
                    selected ? "border-primary ring-2 ring-primary" : "border-border hover:border-zinc-500"
                  }`}
                  onClick={() => setBackground({ type: "preset", presetId: preset.id, label: preset.label, previewUrl: assetUrl(preset.thumbnail_url) })}
                >
                  <div
                    className={`relative aspect-video bg-cover bg-center transition group-hover:brightness-110 ${fallbackClass(preset.id)}`}
                    style={{ backgroundImage: `url(${assetUrl(preset.thumbnail_url)})` }}
                  >
                    {selected ? (
                      <span className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full bg-primary text-white">
                        <Check className="h-4 w-4" aria-hidden />
                      </span>
                    ) : null}
                  </div>
                  <div className="px-3 py-2 text-sm font-semibold">{preset.label}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col rounded-xl border border-border bg-surface p-4">
          <h2 className="mb-4 font-display text-xl font-black tracking-normal">Upload</h2>
          <label
            className={`grid min-h-[260px] flex-1 cursor-pointer place-items-center rounded-lg border border-dashed p-6 text-center transition ${
              dragging ? "border-primary bg-violet-500/10 shadow-glow" : "border-border bg-background"
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              selectUpload(event.dataTransfer.files?.[0]);
            }}
          >
            <input type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" className="hidden" onChange={(event) => selectUpload(event.target.files?.[0])} />
            <div className="grid justify-items-center gap-3">
              <ImagePlus className="h-9 w-9 text-violet-200" aria-hidden />
              <div>
                <div className="font-semibold">Custom background</div>
                <div className="mt-1 text-sm text-muted">JPG, PNG, or WebP up to 20 MB</div>
              </div>
            </div>
          </label>
          {background?.type === "upload" ? (
            <div className="mt-4 overflow-hidden rounded-lg border border-border">
              <div
                className="aspect-video w-full bg-cover bg-center"
                style={{ backgroundImage: `url(${background.previewUrl})` }}
                role="img"
                aria-label="Selected custom background"
              />
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-auto flex gap-3">
        <Button variant="secondary" className="h-12 px-5" onClick={onBack}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
          Back
        </Button>
        <Button className="h-12 flex-1 text-base" disabled={!background} onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
}
