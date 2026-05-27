"use client";

import {
  ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Loader2, Music2, Plus, RefreshCw, Sliders, Sparkles, SkipForward,
  Users, X, ImageIcon,
} from "lucide-react";
import { useState } from "react";
import { getStoryboard, startArtDirection } from "@/lib/api";
import { pollJobStatus } from "@/lib/jobs";
import type { SectionRule, SongConfigForm, SpeakerConfig, StoryboardLine } from "@/lib/types";
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

const FONT_OPTIONS = [
  { value: "default",       label: "Auto (let AI choose)" },
  { value: "Impact",        label: "Impact" },
  { value: "Bebas",         label: "Bebas Neue" },
  { value: "Montserrat",    label: "Montserrat" },
  { value: "FuturaBold",    label: "Futura Bold" },
  { value: "AvenirNext",    label: "Avenir Next" },
  { value: "Georgia",       label: "Georgia" },
  { value: "TrajanPro",     label: "Trajan Pro" },
  { value: "Helvetica",     label: "Helvetica" },
  { value: "CourierNew",    label: "Courier New" },
  { value: "SourceCodePro", label: "Source Code Pro" },
];

const ANIMATION_OPTIONS = [
  { value: "fade-in",         label: "Fade In" },
  { value: "zoom-in",         label: "Zoom In" },
  { value: "pop",             label: "Pop" },
  { value: "typewriter",      label: "Typewriter" },
  { value: "slide-from-left", label: "Slide from Left" },
  { value: "slide-from-right",label: "Slide from Right" },
  { value: "glitch",          label: "Glitch" },
];

const COMMON_SECTIONS = ["intro", "verse", "pre-chorus", "chorus", "bridge", "hook", "outro"];

const ANIMATION_COLORS: Record<string, string> = {
  "fade-in":          "bg-zinc-700 text-zinc-200",
  typewriter:         "bg-violet-900/60 text-violet-200",
  glitch:             "bg-red-900/50 text-red-300",
  "slide-from-left":  "bg-blue-900/50 text-blue-300",
  "slide-from-right": "bg-blue-900/50 text-blue-300",
  "zoom-in":          "bg-amber-900/50 text-amber-300",
  pop:                "bg-green-900/50 text-green-300",
};


function formToYaml(form: SongConfigForm): string | undefined {
  const validSpeakers = form.speakers.filter(s => s.name.trim());
  const validRules    = form.section_rules.filter(r => r.sections.length > 0 && r.style.trim());
  const hasContent    = validSpeakers.length > 0 || validRules.length > 0 || form.generate_ai_backgrounds;
  if (!hasContent) return undefined;

  const lines: string[] = [];

  if (validSpeakers.length > 0) {
    lines.push("speakers:");
    for (const sp of validSpeakers) {
      // YAML keys must be safe identifiers
      const key = sp.name.trim().replace(/[^a-zA-Z0-9_]/g, "_");
      lines.push(`  ${key}:`);
      lines.push(`    font: ${sp.font}`);
      lines.push(`    text_color: "${sp.text_color}"`);
      lines.push(`    animation: ${sp.animation}`);
      lines.push(`    font_size_pct: ${sp.font_size_pct}`);
      lines.push(`    position_y_pct: ${sp.position_y_pct}`);
    }
    lines.push("");
  }

  if (validRules.length > 0) {
    lines.push("section_overrides:");
    for (const rule of validRules) {
      lines.push(`  - sections: [${rule.sections.join(", ")}]`);
      lines.push(`    style: ${JSON.stringify(rule.style.trim())}`);
    }
    lines.push("");
  }

  if (form.generate_ai_backgrounds) {
    lines.push("generate_ai_backgrounds: true");
  }

  return lines.join("\n").trim();
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
        checked ? "bg-violet-500" : "bg-zinc-600"
      } disabled:cursor-not-allowed disabled:opacity-50`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] text-muted">{label}</span>
      <select
        className="rounded-lg border border-border bg-zinc-800 px-2 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-violet-500/50"
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function SpeakerCard({
  speaker,
  index,
  onChange,
  onRemove,
  disabled,
}: {
  speaker: SpeakerConfig;
  index: number;
  onChange: (s: SpeakerConfig) => void;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-zinc-900/60 p-3 flex flex-col gap-3">
     
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-muted w-10 shrink-0">Artist {index + 1}</span>
        <input
          className="flex-1 rounded-lg border border-border bg-zinc-800 px-2.5 py-1.5 text-sm text-text placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
          placeholder="e.g. Nicki Minaj, Drake, Featured Artist"
          value={speaker.name}
          onChange={e => onChange({ ...speaker, name: e.target.value })}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          className="text-zinc-600 hover:text-red-400 transition disabled:opacity-40"
          aria-label="Remove artist"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SelectField
          label="Font"
          value={speaker.font}
          onChange={v => onChange({ ...speaker, font: v })}
          options={FONT_OPTIONS}
          disabled={disabled}
        />

        {/* Color picker */}
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted">Text color</span>
          <div className="flex items-center gap-1.5">
            <input
              type="color"
              className="h-8 w-8 cursor-pointer rounded border border-border bg-transparent p-0.5"
              value={speaker.text_color}
              onChange={e => onChange({ ...speaker, text_color: e.target.value })}
              disabled={disabled}
            />
            <span className="font-mono text-xs text-zinc-400">{speaker.text_color}</span>
          </div>
        </div>

        <SelectField
          label="Animation"
          value={speaker.animation}
          onChange={v => onChange({ ...speaker, animation: v })}
          options={ANIMATION_OPTIONS}
          disabled={disabled}
        />

        
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted">Text size — {speaker.font_size_pct}%</span>
          <input
            type="range"
            min={4}
            max={14}
            step={0.5}
            value={speaker.font_size_pct}
            onChange={e => onChange({ ...speaker, font_size_pct: parseFloat(e.target.value) })}
            disabled={disabled}
            className="w-full accent-violet-500"
          />
        </div>
      </div>
    </div>
  );
}

function SectionRuleCard({
  rule,
  index,
  onChange,
  onRemove,
  disabled,
}: {
  rule: SectionRule;
  index: number;
  onChange: (r: SectionRule) => void;
  onRemove: () => void;
  disabled: boolean;
}) {
  function toggleSection(section: string) {
    const next = rule.sections.includes(section)
      ? rule.sections.filter(s => s !== section)
      : [...rule.sections, section];
    onChange({ ...rule, sections: next });
  }

  return (
    <div className="rounded-xl border border-border bg-zinc-900/60 p-3 flex flex-col gap-3">
      
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted">Rule {index + 1} — tap the parts of the song it applies to:</span>
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          className="text-zinc-600 hover:text-red-400 transition disabled:opacity-40"
          aria-label="Remove rule"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

    
      <div className="flex flex-wrap gap-1.5">
        {COMMON_SECTIONS.map(section => {
          const active = rule.sections.includes(section);
          return (
            <button
              key={section}
              type="button"
              disabled={disabled}
              onClick={() => toggleSection(section)}
              className={`rounded-full border px-3 py-0.5 text-xs font-medium capitalize transition ${
                active
                  ? "border-violet-500/60 bg-violet-500/25 text-violet-200"
                  : "border-border bg-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300"
              } disabled:opacity-50`}
            >
              {section}
            </button>
          );
        })}
      </div>

      
      <textarea
        className="w-full resize-none rounded-lg border border-border bg-zinc-800 px-2.5 py-2 text-sm text-text placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
        rows={2}
        placeholder={`How should ${rule.sections.length ? rule.sections.join(" & ") : "these parts"} look? e.g. bright colors, zoom animation, full-energy feel`}
        value={rule.style}
        onChange={e => onChange({ ...rule, style: e.target.value })}
        disabled={disabled}
      />
    </div>
  );
}


function CustomisePanel({
  form,
  onChange,
  disabled,
}: {
  form: SongConfigForm;
  onChange: (f: SongConfigForm) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);

  function addSpeaker() {
    onChange({
      ...form,
      speakers: [
        ...form.speakers,
        {
          id: crypto.randomUUID(),
          name: "",
          font: "default",
          text_color: "#FFFFFF",
          animation: "fade-in",
          font_size_pct: 7,
          position_y_pct: 55,
        },
      ],
    });
  }

  function addRule() {
    onChange({
      ...form,
      section_rules: [
        ...form.section_rules,
        { id: crypto.randomUUID(), sections: [], style: "" },
      ],
    });
  }

  const hasConfig =
    form.speakers.some(s => s.name.trim()) ||
    form.section_rules.some(r => r.sections.length > 0 && r.style.trim()) ||
    form.generate_ai_backgrounds;

  return (
    <div className="rounded-xl border border-border bg-background overflow-hidden">
     
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        disabled={disabled}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-text hover:bg-surface/40 transition disabled:opacity-50"
      >
        <span className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-violet-400" />
          Customise the look
          {hasConfig && !open && (
            <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-normal text-violet-300">
              configured
            </span>
          )}
        </span>
        {open
          ? <ChevronUp className="h-4 w-4 text-muted" />
          : <ChevronDown className="h-4 w-4 text-muted" />}
      </button>

      {open && (
        <div className="border-t border-border divide-y divide-border">

          
          <div className="flex items-start justify-between gap-4 px-4 py-4">
            <div className="flex gap-3">
              <ImageIcon className="mt-0.5 h-4 w-4 shrink-0 text-violet-400" />
              <div>
                <p className="text-sm font-medium">AI-Generated Backgrounds</p>
                <p className="mt-0.5 text-xs text-muted">
                  Create a unique image behind each lyric line using DALL-E 3.
                  Requires an OpenAI API key and uses credits.
                </p>
              </div>
            </div>
            <Toggle
              checked={form.generate_ai_backgrounds}
              onChange={v => onChange({ ...form, generate_ai_backgrounds: v })}
              disabled={disabled}
            />
          </div>

          
          <div className="flex flex-col gap-3 px-4 py-4">
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <Music2 className="mt-0.5 h-4 w-4 shrink-0 text-violet-400" />
                <div>
                  <p className="text-sm font-medium">Section Styles</p>
                  <p className="mt-0.5 text-xs text-muted">
                    Make the chorus, bridge, or any part look different from the rest.
                  </p>
                </div>
              </div>
              <button
                type="button"
                disabled={disabled}
                onClick={addRule}
                className="inline-flex items-center gap-1 rounded-lg border border-dashed border-border px-2.5 py-1 text-xs text-muted transition hover:border-zinc-500 hover:text-text disabled:opacity-50"
              >
                <Plus className="h-3 w-3" />
                Add rule
              </button>
            </div>

            {form.section_rules.length === 0 && (
              <p className="text-xs italic text-zinc-600">
                No rules yet — add one to make specific parts stand out.
              </p>
            )}

            {form.section_rules.map((rule, i) => (
              <SectionRuleCard
                key={rule.id}
                rule={rule}
                index={i}
                disabled={disabled}
                onChange={updated =>
                  onChange({
                    ...form,
                    section_rules: form.section_rules.map((r, j) => j === i ? updated : r),
                  })
                }
                onRemove={() =>
                  onChange({ ...form, section_rules: form.section_rules.filter((_, j) => j !== i) })
                }
              />
            ))}
          </div>

          
          <div className="flex flex-col gap-3 px-4 py-4">
            <div className="flex items-start justify-between">
              <div className="flex gap-3">
                <Users className="mt-0.5 h-4 w-4 shrink-0 text-violet-400" />
                <div>
                  <p className="text-sm font-medium">Artist Styles</p>
                  <p className="mt-0.5 text-xs text-muted">
                    Give each artist their own font, color, and animation. Perfect for features and duets.
                  </p>
                </div>
              </div>
              <button
                type="button"
                disabled={disabled}
                onClick={addSpeaker}
                className="inline-flex items-center gap-1 rounded-lg border border-dashed border-border px-2.5 py-1 text-xs text-muted transition hover:border-zinc-500 hover:text-text disabled:opacity-50"
              >
                <Plus className="h-3 w-3" />
                Add artist
              </button>
            </div>

            {form.speakers.length === 0 && (
              <p className="text-xs italic text-zinc-600">
                No artists added — great for solo tracks.
              </p>
            )}

            {form.speakers.map((sp, i) => (
              <SpeakerCard
                key={sp.id}
                speaker={sp}
                index={i}
                disabled={disabled}
                onChange={updated =>
                  onChange({
                    ...form,
                    speakers: form.speakers.map((s, j) => j === i ? updated : s),
                  })
                }
                onRemove={() =>
                  onChange({ ...form, speakers: form.speakers.filter((_, j) => j !== i) })
                }
              />
            ))}
          </div>

        </div>
      )}
    </div>
  );
}

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
          {visible.map(line => (
            <tr key={line.line_id} className="border-b border-border/50 hover:bg-surface/50">
              <td className="px-3 py-2 text-muted">{line.line_id}</td>
              <td className="px-3 py-2"><AnimationBadge animation={line.animation} /></td>
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
          onClick={() => setExpanded(v => !v)}
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
        const MAX_W = 640, MAX_H = 360;
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
  const {
    upload, background, storyboard, stylePrompt, songConfig, openaiApiKey,
    setStoryboard, setStylePrompt, setSongConfig, setError,
  } = useAppStore();

  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phaseLabel, setPhaseLabel] = useState("");
  const [localError, setLocalError] = useState("");

  async function generate() {
    if (!stylePrompt.trim()) {
      setLocalError("Enter a style description first.");
      return;
    }
    setBusy(true);
    setProgress(0);
    setPhaseLabel("");
    setLocalError("");
    setStoryboard(null);
    try {
      const bgB64 = background?.previewUrl
        ? await imageUrlToB64(background.previewUrl)
        : undefined;

      await startArtDirection(
        upload.jobToken,
        stylePrompt.trim(),
        bgB64,
        formToYaml(songConfig),
        openaiApiKey || undefined,
      );

      const jobStatus = await pollJobStatus(upload.jobToken, {
        timeoutMs: 15 * 60 * 1000,
        timeoutMessage: "Art direction is taking longer than expected (AI backgrounds can take several minutes). Please try again.",
        onProgress: (pct) => {
          setProgress(pct);
          if (pct < 15)        setPhaseLabel("Starting up…");
          else if (pct < 60)   setPhaseLabel("Designing storyboard with GPT-4o…");
          else if (pct < 95)   setPhaseLabel("Generating AI background images…");
          else                 setPhaseLabel("Finishing up…");
        },
      });

      if (jobStatus.status === "failed") {
        throw new Error(
          jobStatus.error ||
          "Art direction failed. Check that OPENAI_API_KEY is set and lyrics have been transcribed.",
        );
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

  const noKey = !openaiApiKey.trim();

  return (
    <div className="flex flex-1 flex-col gap-5">
      {noKey && !busy && !storyboard && (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
          <p className="text-amber-200">
            <strong className="text-amber-100">No API key entered.</strong>{" "}
            Go back to add your OpenAI key, or skip straight to the preview with default styling.
          </p>
          <button
            type="button"
            onClick={skip}
            className="shrink-0 rounded-lg border border-amber-500/40 bg-amber-500/20 px-3 py-1.5 text-xs font-medium text-amber-200 transition hover:bg-amber-500/30 hover:text-white"
          >
            Skip to Preview →
          </button>
        </div>
      )}
      {localError ? <StatusBanner tone="error">{localError}</StatusBanner> : null}

      <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_360px]">

       
        <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4">
          <div>
            <h2 className="font-display text-xl font-black tracking-normal">AI Art Direction</h2>
            <p className="mt-1 text-sm text-muted">
              Describe your vibe and the AI designs every lyric line - fonts, colors, animations, and effects.
            </p>
          </div>

        
          <textarea
            className="focus-ring min-h-[96px] w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-muted"
            placeholder="e.g. dark cinematic, neon accents, lo-fi glitch aesthetic"
            value={stylePrompt}
            onChange={e => setStylePrompt(e.target.value)}
            disabled={busy}
          />

         
          <div className="flex flex-wrap gap-2">
            {STYLE_PRESETS.map(preset => (
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

         
          <CustomisePanel form={songConfig} onChange={setSongConfig} disabled={busy} />

          
          {busy && (
            <div className="grid gap-2 rounded-lg border border-border bg-background p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  {phaseLabel || "Generating storyboard…"}
                </span>
                <span>{progress}%</span>
              </div>
              <ProgressBar value={progress} />
            </div>
          )}

          {/* Result */}
          {storyboard && !busy && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-green-400">
                  ✓ Storyboard ready, {storyboard.lines.length} lines directed
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
            <li className="flex gap-2">
              <span className="mt-0.5 text-violet-400">▸</span>
              Sends your lyrics to GPT-4o with your style description
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-violet-400">▸</span>
              Returns a per-line plan: font, color, animation, and background effect for every line
            </li>
            <li className="flex gap-2">
              <span className="mt-0.5 text-violet-400">▸</span>
              Export composites it all into your video automatically
            </li>
          </ul>
          <hr className="border-border" />
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium text-zinc-400">Tips</p>
            <ul className="flex flex-col gap-1.5 text-xs text-muted">
              <li className="flex gap-1.5">
                <span className="text-violet-400 shrink-0">▸</span>
                Re-generate with the same style to get fresh variations , the AI is creative each run
              </li>
              <li className="flex gap-1.5">
                <span className="text-violet-400 shrink-0">▸</span>
                Use <strong className="text-zinc-400">Section Styles</strong> to make the chorus pop differently from your verses
              </li>
              <li className="flex gap-1.5">
                <span className="text-violet-400 shrink-0">▸</span>
                <strong className="text-zinc-400">Artist Styles</strong> are great for features , each artist gets their own signature look
              </li>
            </ul>
          </div>
          <hr className="border-border" />
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-zinc-400">Don't want AI styling?</p>
            <button
              onClick={skip}
              disabled={busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <SkipForward className="h-3.5 w-3.5" />
              Skip - go straight to preview
            </button>
          </div>
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
            <>Next <ChevronRight className="h-4 w-4" aria-hidden /></>
          ) : (
            <><Sparkles className="h-4 w-4" aria-hidden /> Generate</>
          )}
        </Button>
      </div>
    </div>
  );
}
