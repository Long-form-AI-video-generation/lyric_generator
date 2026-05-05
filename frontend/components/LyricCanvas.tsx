"use client";

import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { LyricsFile, LyricLine } from "@/lib/types";

type LyricCanvasProps = {
  lyrics: LyricsFile | null;
  backgroundUrl: string | null;
  isCustomBackground?: boolean;
  audioRef: RefObject<HTMLAudioElement>;
  currentTime: number;
  playing: boolean;
};

function activeLineAt(lines: LyricLine[], time: number): { line: LyricLine; end: number } | null {
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const next = lines[index + 1];
    const end = next ? Math.min(line.end, next.start) : line.end;
    if (time >= line.start && time < end) {
      return { line, end };
    }
  }
  return null;
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const words = text.split(/\s+/);
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

export function LyricCanvas({ lyrics, backgroundUrl, isCustomBackground = false, audioRef, currentTime, playing }: LyricCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!backgroundUrl) {
      imageRef.current = null;
      return;
    }
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.src = backgroundUrl;
    image.onload = () => {
      imageRef.current = image;
    };
    return () => {
      image.onload = null;
    };
  }, [backgroundUrl]);

  useEffect(() => {
    let frame = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      const width = canvas.width;
      const height = canvas.height;
      const image = imageRef.current;

      ctx.clearRect(0, 0, width, height);
      if (image) {
        const scale = Math.max(width / image.width, height / image.height);
        const drawWidth = image.width * scale;
        const drawHeight = image.height * scale;
        const x = (width - drawWidth) / 2;
        const y = (height - drawHeight) / 2;
        if (isCustomBackground) {
          // Extend draw area so blur doesn't bleed transparent edges in from outside
          const pad = 24;
          ctx.filter = "blur(2px) brightness(0.75)";
          ctx.drawImage(image, x - pad, y - pad, drawWidth + pad * 2, drawHeight + pad * 2);
          ctx.filter = "none";
        } else {
          ctx.drawImage(image, x, y, drawWidth, drawHeight);
        }
      } else {
        const gradient = ctx.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, "#101827");
        gradient.addColorStop(1, "#020203");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
      }

      ctx.fillStyle = isCustomBackground ? "rgba(0,0,0,0.35)" : "rgba(0,0,0,0.18)";
      ctx.fillRect(0, 0, width, height);

      const time = audioRef.current?.currentTime ?? currentTime;
      const active = lyrics ? activeLineAt(lyrics.lines, time) : null;
      if (active) {
        const fadeIn = 0.2;
        const fadeOut = 0.3;
        const inAlpha = Math.min(1, Math.max(0, (time - active.line.start) / fadeIn));
        const outAlpha = Math.min(1, Math.max(0, (active.end - time) / fadeOut));
        const alpha = Math.min(inAlpha, outAlpha);
        const fontSize = Math.round(height * 0.052);
        ctx.font = `800 ${fontSize}px Montserrat, Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.shadowColor = "rgba(0,0,0,0.7)";
        ctx.shadowBlur = 16;
        ctx.shadowOffsetY = 4;
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        const wrapped = wrapText(ctx, active.line.text, width * 0.84);
        const lineHeight = fontSize * 1.18;
        const startY = height / 2 - ((wrapped.length - 1) * lineHeight) / 2;
        wrapped.forEach((line, index) => {
          ctx.fillText(line, width / 2, startY + index * lineHeight);
        });
        ctx.shadowColor = "transparent";
      }

      if (playing) {
        frame = requestAnimationFrame(draw);
      }
    };

    draw();
    return () => cancelAnimationFrame(frame);
  }, [audioRef, currentTime, lyrics, playing, backgroundUrl]);

  return (
    <canvas
      ref={canvasRef}
      width={1280}
      height={720}
      className="aspect-video w-full rounded-lg border border-border bg-black"
      aria-label="Lyric video preview"
    />
  );
}
