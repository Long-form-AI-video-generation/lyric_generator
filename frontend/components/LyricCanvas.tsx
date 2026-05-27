"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { AiBackground, LyricsFile, LyricLine, Storyboard, StoryboardLine } from "@/lib/types";

type LyricCanvasProps = {
  lyrics: LyricsFile | null;
  backgroundUrl: string | null;
  isCustomBackground?: boolean;
  audioRef: RefObject<HTMLAudioElement>;
  currentTime: number;
  playing: boolean;
  storyboard?: Storyboard | null;
  aiBackgrounds?: AiBackground[];
};

const FONT_MAP: Record<string, string> = {
  Impact:        "Impact, Haettenschweiler, sans-serif",
  Montserrat:    "Montserrat, Inter, sans-serif",
  Bebas:         '"Bebas Neue", Impact, sans-serif',
  CourierNew:    '"Courier New", Courier, monospace',
  Georgia:       "Georgia, serif",
  Helvetica:     "Helvetica, Arial, sans-serif",
  AvenirNext:    '"Avenir Next", Avenir, sans-serif',
  FuturaBold:    "Futura, Trebuchet MS, sans-serif",
  TrajanPro:     '"Trajan Pro", Georgia, serif',
  SourceCodePro: '"Source Code Pro", "Courier New", monospace',
  default:       "Montserrat, Inter, sans-serif",
};


const BG_FILTERS: Record<string, string> = {
  none:         "none",
  blur:         "blur(6px) brightness(0.85)",
  desaturate:   "grayscale(90%) brightness(0.9)",
  color_shift:  "hue-rotate(120deg) saturate(1.4)",
  glitch:       "saturate(2) contrast(1.2)",
  vhs:          "contrast(1.1) brightness(0.9) sepia(0.3)",
};

function cssFont(name: string, sizePx: number, weight = 800) {
  const stack = FONT_MAP[name] ?? FONT_MAP.default;
  return `${weight} ${sizePx}px ${stack}`;
}

function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `${r},${g},${b}`;
}

function activeLineAt(lines: LyricLine[], time: number): { line: LyricLine; end: number } | null {
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const next = lines[i + 1];
    const end  = next ? Math.min(line.end, next.start) : line.end;
    if (time >= line.start && time < end) return { line, end };
  }
  return null;
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words: string[] = text.split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width <= maxWidth || !current) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines.slice(0, 3);
}

const FADE_IN_S  = 0.22;
const FADE_OUT_S = 0.28;

type AnimState = { alpha: number; xOffset: number; scale: number; chars: number | null };

function computeAnimState(
  animation: string,
  time: number,
  lineStart: number,
  lineEnd: number,
  width: number,
  totalChars: number,
): AnimState {
  const elapsed   = time - lineStart;
  const remaining = lineEnd - time;
  const dur       = Math.max(0.01, lineEnd - lineStart);

  const inAlpha  = Math.min(1, Math.max(0, elapsed   / FADE_IN_S));
  const outAlpha = Math.min(1, Math.max(0, remaining / FADE_OUT_S));
  const alpha    = Math.min(inAlpha, outAlpha);

  const animDur = Math.max(0.15, dur * 0.25);
  const t       = Math.min(1, elapsed / animDur);

  switch (animation) {
    case "typewriter":
      return { alpha: 1, xOffset: 0, scale: 1, chars: Math.max(1, Math.floor(totalChars * t)) };
    case "slide-from-left":
      return { alpha, xOffset: (1 - t) * -width * 0.6, scale: 1, chars: null };
    case "slide-from-right":
      return { alpha, xOffset: (1 - t) *  width * 0.6, scale: 1, chars: null };
    case "zoom-in":
      return { alpha, xOffset: 0, scale: 0.5 + 0.5 * t, chars: null };
    case "pop": {
      const scale = t >= 1 ? 1 : 1 + 0.15 * Math.sin(t * Math.PI);
      return { alpha, xOffset: 0, scale, chars: null };
    }
    default: // fade-in, glitch
      return { alpha, xOffset: 0, scale: 1, chars: null };
  }
}

function drawBackground(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement | null,
  width: number,
  height: number,
  filter: string,
  isCustom: boolean,
) {
  if (!image) {
    const grad = ctx.createLinearGradient(0, 0, width, height);
    grad.addColorStop(0, "#101827");
    grad.addColorStop(1, "#020203");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);
    return;
  }

  const scale = Math.max(width / image.width, height / image.height);
  const dw = image.width  * scale;
  const dh = image.height * scale;
  const dx = (width  - dw) / 2;
  const dy = (height - dh) / 2;

  const cssFilter = BG_FILTERS[filter] ?? "none";
  const baseFilter = isCustom ? "blur(2px) brightness(0.75)" : "none";
  ctx.filter = baseFilter !== "none" || cssFilter !== "none"
    ? [baseFilter, cssFilter].filter(f => f !== "none").join(" ") || "none"
    : "none";

  const pad = isCustom ? 24 : 0;
  ctx.drawImage(image, dx - pad, dy - pad, dw + pad * 2, dh + pad * 2);
  ctx.filter = "none";
}

function drawLine(
  ctx: CanvasRenderingContext2D,
  text: string,
  direction: StoryboardLine | null,
  animState: AnimState,
  width: number,
  height: number,
) {
  const fontSizePct = Math.max(5.5, direction?.font_size_pct ?? 5.5);
  const fontSize    = Math.round(height * fontSizePct / 100);
  const fontName    = direction?.font      ?? "default";
  const colorHex    = direction?.text_color ?? "#FFFFFF";
  const xPct        = 50; 
  const yPct        = direction?.position.y_pct ?? 50;

  const displayText = animState.chars !== null ? text.slice(0, animState.chars) : text;
  const rgb         = hexToRgb(colorHex);

  ctx.save();

  const cx = width  * xPct / 100 + animState.xOffset;
  const cy = height * yPct / 100;

  if (animState.scale !== 1) {
    ctx.translate(cx, cy);
    ctx.scale(animState.scale, animState.scale);
    ctx.translate(-cx, -cy);
  }

  ctx.font         = cssFont(fontName, fontSize);
  ctx.textAlign    = "center";
  ctx.textBaseline = "middle";

  const wrapped    = wrapText(ctx, displayText, width * 0.84);
  const lineHeight = fontSize * 1.22;
  const totalH     = (wrapped.length - 1) * lineHeight;
  const startY     = cy - totalH / 2;

  if (direction?.animation === "glitch" && animState.alpha > 0.5) {
    const shift = Math.round(fontSize * 0.08);
    ctx.globalAlpha = animState.alpha * 0.5;
    ctx.fillStyle   = "rgba(255,0,80,0.6)";
    wrapped.forEach((ln, i) => ctx.fillText(ln, cx + shift, startY + i * lineHeight));
    ctx.fillStyle   = "rgba(0,200,255,0.6)";
    wrapped.forEach((ln, i) => ctx.fillText(ln, cx - shift, startY + i * lineHeight));
  }

  ctx.shadowColor   = "rgba(0,0,0,0.8)";
  ctx.shadowBlur    = Math.round(fontSize * 0.4);
  ctx.shadowOffsetY = Math.round(fontSize * 0.06);
  ctx.globalAlpha   = animState.alpha;
  ctx.fillStyle     = `rgba(${rgb},${animState.alpha})`;
  wrapped.forEach((ln, i) => ctx.fillText(ln, cx, startY + i * lineHeight));

  ctx.restore();
}

export function LyricCanvas({
  lyrics,
  backgroundUrl,
  isCustomBackground = false,
  audioRef,
  currentTime,
  playing,
  storyboard,
  aiBackgrounds = [],
}: LyricCanvasProps) {
  const canvasRef      = useRef<HTMLCanvasElement | null>(null);
  const imageRef       = useRef<HTMLImageElement | null>(null);              // preset/upload bg
  const aiImagesRef    = useRef<Map<number, HTMLImageElement>>(new Map());  // index → ai image
  const lastAiBgIdxRef = useRef<number>(0);                                 // last-seen ai bg index

  // Build direction lookup
  const directionMap = useRef<Map<number, StoryboardLine>>(new Map());
  useEffect(() => {
    directionMap.current = new Map(storyboard?.lines.map((d) => [d.line_id, d]) ?? []);
  }, [storyboard]);

  // Resize canvas buffer to match CSS display size × DPR
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        const dpr = window.devicePixelRatio || 1;
        canvas.width  = Math.round(width  * dpr);
        canvas.height = Math.round(height * dpr);
        const ctx = canvas.getContext("2d");
        if (ctx) ctx.scale(dpr, dpr);
      }
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  
  useEffect(() => {
    if (!backgroundUrl) { imageRef.current = null; return; }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = backgroundUrl;
    img.onload = () => { imageRef.current = img; };
    return () => { img.onload = null; };
  }, [backgroundUrl]);

  
  useEffect(() => {
    if (!aiBackgrounds.length) { aiImagesRef.current = new Map(); return; }
    const map = new Map<number, HTMLImageElement>();
    for (const bg of aiBackgrounds) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => { map.set(bg.index, img); };
      img.src = bg.url;
    }
    aiImagesRef.current = map;
    return () => {
      for (const bg of aiBackgrounds) {
        const img = map.get(bg.index);
        if (img) img.onload = null;
      }
    };
  }, [aiBackgrounds]);

  // Render loop
  useEffect(() => {
    let frame = 0;

    const draw = () => {
      const canvas = canvasRef.current;
      const ctx    = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      const dpr    = window.devicePixelRatio || 1;
      const width  = canvas.width  / dpr;
      const height = canvas.height / dpr;

      ctx.clearRect(0, 0, width, height);

      // Pick background image: AI bg by image_index if available, else preset/upload
      const time      = audioRef.current?.currentTime ?? currentTime;
      const active    = lyrics ? activeLineAt(lyrics.lines, time) : null;
      const direction = active ? (directionMap.current.get(active.line.id) ?? null) : null;

      let bgImage: HTMLImageElement | null = null;
      let bgFilter = "none";
      const aiMap = aiImagesRef.current;

      if (aiMap.size > 0) {
        
        if (direction) {
          const rawIdx = direction.background.image_index;
          const indices = Array.from(aiMap.keys()).sort((a, b) => a - b);
          const idx = indices[rawIdx % indices.length];
          lastAiBgIdxRef.current = idx;
          bgFilter = direction.background.filter;
        }
        bgImage = aiMap.get(lastAiBgIdxRef.current) ?? aiMap.values().next().value ?? null;
      } else {
        bgImage = imageRef.current;
      }

      drawBackground(ctx, bgImage, width, height, bgFilter, aiMap.size === 0 && isCustomBackground);

      // Dark overlay
      ctx.fillStyle = "rgba(0,0,0,0.22)";
      ctx.fillRect(0, 0, width, height);

      
      if (active) {
        const animState = computeAnimState(
          direction?.animation ?? "fade-in",
          time, active.line.start, active.end,
          width, active.line.text.length,
        );
        drawLine(ctx, active.line.text, direction, animState, width, height);
      }

      if (playing) frame = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(frame);
  }, [audioRef, currentTime, lyrics, playing, backgroundUrl, isCustomBackground, aiBackgrounds]);

  return (
    <canvas
      ref={canvasRef}
      className="aspect-video w-full rounded-lg border border-border bg-black"
      aria-label="Lyric video preview"
    />
  );
}
