"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { AiBackground, LyricsFile, LyricLine, Storyboard, StoryboardLine } from "@/lib/types";
import type { SpeakerImage } from "@/lib/api";

type LyricCanvasProps = {
  lyrics: LyricsFile | null;
  backgroundUrl: string | null;
  isCustomBackground?: boolean;
  audioRef: RefObject<HTMLAudioElement>;
  currentTime: number;
  playing: boolean;
  storyboard?: Storyboard | null;
  aiBackgrounds?: AiBackground[];
  speakerImages?: SpeakerImage[];
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


function genreWarpProfile(stylePrompt: string): { amp: number; freq: number; speed: number } {
  const s = stylePrompt.toLowerCase();
  if (/metal|hardcore|death|thrash|grind/.test(s))
    return { amp: 0.055, freq: 7, speed: 6 };
  if (/rock|punk|grunge|alternative|alt-rock/.test(s))
    return { amp: 0.038, freq: 5, speed: 4 };
  if (/electronic|edm|dubstep|drum.?and.?bass|dnb|techno|industrial/.test(s))
    return { amp: 0.032, freq: 9, speed: 8 };
  if (/hip.?hop|trap|rap|drill/.test(s))
    return { amp: 0.022, freq: 4, speed: 3 };
  if (/jazz|blues|soul|r.?b/.test(s))
    return { amp: 0.014, freq: 2, speed: 1.5 };
  if (/pop|dance|disco|funk/.test(s))
    return { amp: 0.018, freq: 3, speed: 2.5 };
  if (/classical|orchestral|ambient|acoustic/.test(s))
    return { amp: 0.008, freq: 1.5, speed: 1 };
  // default — gentle pulse
  return { amp: 0.018, freq: 3, speed: 2 };
}


function drawWarpedSpeaker(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  width: number,
  height: number,
  opacity: number,
  cssFilter: string,
  time: number,
  profile: { amp: number; freq: number; speed: number },
) {
  const slices = Math.ceil(height / 3); // ~3px rows
  const rowH = height / slices;
  const maxShift = width * profile.amp;

  ctx.globalAlpha = opacity;
  ctx.filter = cssFilter !== "none" ? cssFilter : "none";

  for (let i = 0; i < slices; i++) {
    const y = i * rowH;
    
    const shift =
      Math.sin(i / slices * Math.PI * profile.freq + time * profile.speed) * maxShift +
      Math.sin(i / slices * Math.PI * profile.freq * 2.3 + time * profile.speed * 1.7) * maxShift * 0.3;

    const scale = Math.max(width / img.width, height / img.height);
    const dw = img.width  * scale;
    const dh = img.height * scale;
    const dx = (width  - dw) / 2;
    const dy = (height - dh) / 2;

    ctx.save();
    ctx.beginPath();
    ctx.rect(0, y, width, rowH + 1); 
    ctx.clip();
    ctx.drawImage(img, dx + shift, dy, dw, dh);
    ctx.restore();
  }

  ctx.filter = "none";
}

function drawSpeakerImage(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  width: number,
  height: number,
  opacity: number,
  distortion: string,
  bgFilter: string,
  time: number,
  stylePrompt: string,
) {
  const scale = Math.max(width / img.width, height / img.height);
  const dw = img.width  * scale;
  const dh = img.height * scale;
  const dx = (width  - dw) / 2;
  const dy = (height - dh) / 2;

  
  const cssFilter = BG_FILTERS[bgFilter] ?? "none";
  const warpProfile = genreWarpProfile(stylePrompt);

  ctx.save();

  if (distortion === "chromatic_aberration") {
    const shift = Math.round(width * 0.012 + Math.sin(time * warpProfile.speed) * width * (0.005 + warpProfile.amp * 0.3));
    
    ctx.globalAlpha = opacity;
    ctx.filter = cssFilter !== "none" ? `${cssFilter} saturate(2)` : "saturate(2)";
    ctx.globalCompositeOperation = "source-over";
    ctx.drawImage(img, dx - shift, dy, dw, dh);
    
    ctx.globalAlpha = opacity * 0.7;
    ctx.globalCompositeOperation = "screen";
    ctx.filter = cssFilter !== "none" ? `${cssFilter} hue-rotate(180deg) saturate(2)` : "hue-rotate(180deg) saturate(2)";
    ctx.drawImage(img, dx + shift, dy, dw, dh);
    
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = opacity * 0.6;
    ctx.filter = cssFilter !== "none" ? cssFilter : "none";
    ctx.drawImage(img, dx, dy, dw, dh);

  } else if (distortion === "pixel_sort") {
    const slices = 12;
    const sliceW = Math.ceil(width / slices);
    const amp = height * 0.07;
    ctx.globalAlpha = opacity;
    ctx.filter = cssFilter !== "none" ? cssFilter : "none";
    for (let i = 0; i < slices; i++) {
      const sx = i * sliceW;
      
      const offsetY = Math.sin((i / slices) * Math.PI * 3 + time * warpProfile.speed * 0.5) * amp * (i % 3 === 0 ? 1.5 : 0.5);
      ctx.save();
      ctx.beginPath();
      ctx.rect(sx, 0, sliceW, height);
      ctx.clip();
      ctx.drawImage(img, dx, dy + offsetY, dw, dh);
      ctx.restore();
    }

  } else if (distortion === "datamosh") {
   
    ctx.globalAlpha = opacity;
    ctx.filter = cssFilter !== "none" ? `${cssFilter} blur(2px) brightness(1.15)` : "blur(2px) brightness(1.15)";
    ctx.drawImage(img, dx, dy, dw, dh);
    ctx.filter = "none";
    
    const seed = Math.floor(time * warpProfile.speed * 0.5) % 9;
    const blockW = Math.ceil(width  * 0.12);
    const blockH = Math.ceil(height * 0.10);
    for (let bi = 0; bi < 6; bi++) {
      const bx = ((seed * 37 + bi * 19) % 9) / 9 * (width  - blockW);
      const by = ((seed * 17 + bi * 31) % 9) / 9 * (height - blockH);
      const offX = Math.sin(time + bi) * width  * 0.04;
      const offY = Math.cos(time + bi) * height * 0.03;
      ctx.save();
      ctx.beginPath();
      ctx.rect(bx, by, blockW, blockH);
      ctx.clip();
      ctx.globalAlpha = opacity * 0.55;
      ctx.drawImage(img, dx + offX, dy + offY, dw, dh);
      ctx.restore();
    }

  } else {
    
    const profile = genreWarpProfile(stylePrompt);
    drawWarpedSpeaker(ctx, img, width, height, opacity, cssFilter, time, profile);
  }

  ctx.restore();
}


function drawCoSpeakerComposite(
  ctx: CanvasRenderingContext2D,
  images: HTMLImageElement[],
  width: number,
  height: number,
  opacity: number,
  cssFilter: string,
  time: number,
  stylePrompt: string,
) {
  if (images.length === 0) return;
  if (images.length === 1) {
    const profile = genreWarpProfile(stylePrompt);
    ctx.save();
    drawWarpedSpeaker(ctx, images[0], width, height, opacity, cssFilter, time, profile);
    ctx.restore();
    return;
  }

  const profile = genreWarpProfile(stylePrompt);
  const n = Math.min(images.length, 4);

  ctx.save();

  if (n === 2) {
    
    const splitX = width / 2;
    const feather = width * 0.08;

    for (let i = 0; i < 2; i++) {
      const img = images[i];
      const scale = Math.max(width / img.width, height / img.height);
      const dw = img.width * scale;
      const dh = img.height * scale;
      const dx = (width - dw) / 2;
      const dy = (height - dh) / 2;

      
      const slices = Math.ceil(height / 3);
      const rowH = height / slices;
      const maxShift = width * profile.amp;

      ctx.globalAlpha = opacity;
      ctx.filter = cssFilter !== "none" ? cssFilter : "none";

      for (let s = 0; s < slices; s++) {
        const y = s * rowH;
        const shift =
          Math.sin(s / slices * Math.PI * profile.freq + time * profile.speed + i * Math.PI) * maxShift * 0.6;

        
        ctx.save();
        const grad = ctx.createLinearGradient(splitX - feather, 0, splitX + feather, 0);
        if (i === 0) {
          grad.addColorStop(0, "rgba(0,0,0,1)");
          grad.addColorStop(1, "rgba(0,0,0,0)");
        } else {
          grad.addColorStop(0, "rgba(0,0,0,0)");
          grad.addColorStop(1, "rgba(0,0,0,1)");
        }

        
        ctx.beginPath();
        if (i === 0) {
          ctx.rect(0, y, splitX + feather, rowH + 1);
        } else {
          ctx.rect(splitX - feather, y, width - (splitX - feather), rowH + 1);
        }
        ctx.clip();
        ctx.drawImage(img, dx + shift, dy, dw, dh);

        
        ctx.globalCompositeOperation = "destination-out";
        ctx.fillStyle = grad;
        ctx.fillRect(splitX - feather, y, feather * 2, rowH + 1);
        ctx.restore();
      }
    }

    
    ctx.globalAlpha = opacity * 0.6;
    ctx.filter = "none";
    ctx.globalCompositeOperation = "screen";
    const seam = ctx.createLinearGradient(splitX - 2, 0, splitX + 2, 0);
    seam.addColorStop(0, "rgba(255,255,255,0)");
    seam.addColorStop(0.5, "rgba(255,255,255,0.8)");
    seam.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = seam;
    ctx.fillRect(splitX - 2, 0, 4, height);

  } else {
   
    const cols = n <= 2 ? 2 : 2;
    const rows = Math.ceil(n / cols);
    const tileW = width  / cols;
    const tileH = height / rows;

    for (let i = 0; i < n; i++) {
      const img = images[i];
      const col = i % cols;
      const row = Math.floor(i / cols);
      const tx = col * tileW;
      const ty = row * tileH;

      const scale = Math.max(tileW / img.width, tileH / img.height);
      const dw = img.width  * scale;
      const dh = img.height * scale;
      const ddx = tx + (tileW - dw) / 2;
      const ddy = ty + (tileH - dh) / 2;

      const slices = Math.ceil(tileH / 3);
      const rowH2 = tileH / slices;
      const maxShift = tileW * profile.amp;

      ctx.globalAlpha = opacity;
      ctx.filter = cssFilter !== "none" ? cssFilter : "none";

      for (let s = 0; s < slices; s++) {
        const y2 = ty + s * rowH2;
        const shift =
          Math.sin(s / slices * Math.PI * profile.freq + time * profile.speed + i * 1.3) * maxShift;
        ctx.save();
        ctx.beginPath();
        ctx.rect(tx, y2, tileW, rowH2 + 1);
        ctx.clip();
        ctx.drawImage(img, ddx + shift, ddy, dw, dh);
        ctx.restore();
      }
    }

    
    ctx.globalAlpha = opacity * 0.4;
    ctx.filter = "none";
    ctx.globalCompositeOperation = "screen";
    ctx.strokeStyle = "rgba(255,255,255,0.5)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(tileW, 0); ctx.lineTo(tileW, height);
    if (rows > 1) { ctx.moveTo(0, tileH); ctx.lineTo(width, tileH); }
    ctx.stroke();
  }

  ctx.globalCompositeOperation = "source-over";
  ctx.filter = "none";
  ctx.restore();
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
  speakerImages = [],
}: LyricCanvasProps) {
  const canvasRef         = useRef<HTMLCanvasElement | null>(null);
  const imageRef          = useRef<HTMLImageElement | null>(null);              // preset/upload bg
  const aiImagesRef       = useRef<Map<number, HTMLImageElement>>(new Map());  // index → ai image
  const lastAiBgIdxRef    = useRef<number>(0);                                 // last-seen ai bg index
  const speakerImagesRef  = useRef<Map<string, HTMLImageElement>>(new Map()); // artist name / duo key → image

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

  
  useEffect(() => {
    const map = new Map<string, HTMLImageElement>();
    const cleanup: Array<() => void> = [];

    const loadImg = (key: string, src: string) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => { map.set(key, img); };
      img.src = src;
      cleanup.push(() => { img.onload = null; });
    };

    for (const sp of speakerImages) {
      // Solo: prefer AI-generated image if available
      loadImg(sp.name.toLowerCase(), sp.generated_url ?? sp.url);

      // Duo images keyed by duo_key stem
      if (sp.duo_generated_urls) {
        for (const [duoKey, duoUrl] of Object.entries(sp.duo_generated_urls)) {
          if (!map.has(duoKey)) {
            loadImg(duoKey, duoUrl);
          }
        }
      }
    }

    speakerImagesRef.current = map;
    return () => cleanup.forEach(fn => fn());
  }, [speakerImages]);

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

     
      if (direction) {
        const opacity = direction.background.speaker_opacity ?? 0;
        const cssFilter = BG_FILTERS[direction.background.filter ?? "none"] ?? "none";
        const coSpeakers = direction.background.co_speakers ?? [];

        if (coSpeakers.length >= 2 && opacity > 0) {
          
          const sortedNames = [...coSpeakers].sort();
          const duoKey = `duo_${sortedNames.map(n => n.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")).join("_")}`;
          const duoImg = speakerImagesRef.current.get(duoKey);

          if (duoImg) {
            
            ctx.save();
            ctx.globalAlpha = opacity;
            ctx.filter = cssFilter !== "none" ? cssFilter : "none";
            const sc = Math.max(width / duoImg.width, height / duoImg.height);
            const dw = duoImg.width * sc, dh = duoImg.height * sc;
            ctx.drawImage(duoImg, (width - dw) / 2, (height - dh) / 2, dw, dh);
            ctx.filter = "none";
            ctx.restore();
          } else {
            
            const imgs = coSpeakers
              .map(n => speakerImagesRef.current.get(n.toLowerCase()))
              .filter((img): img is HTMLImageElement => !!img);
            if (imgs.length >= 2) {
              drawCoSpeakerComposite(ctx, imgs, width, height, opacity, cssFilter, time, storyboard?.style_prompt ?? "");
            } else if (imgs.length === 1) {
              drawSpeakerImage(ctx, imgs[0], width, height, opacity,
                direction.background.speaker_distortion ?? "none",
                direction.background.filter ?? "none", time,
                storyboard?.style_prompt ?? "");
            }
          }
        } else if (direction.speaker_name && opacity > 0) {
          
          const speakerImg = speakerImagesRef.current.get(direction.speaker_name.toLowerCase());
          if (speakerImg) {
            drawSpeakerImage(ctx, speakerImg, width, height, opacity,
              direction.background.speaker_distortion ?? "none",
              direction.background.filter ?? "none", time,
              storyboard?.style_prompt ?? "");
          }
        }
      }

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
  }, [audioRef, currentTime, lyrics, playing, backgroundUrl, isCustomBackground, aiBackgrounds, speakerImages]);

  return (
    <canvas
      ref={canvasRef}
      className="aspect-video w-full rounded-lg border border-border bg-black"
      aria-label="Lyric video preview"
    />
  );
}
