
from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from backend.core.config import RESOLUTIONS
from backend.models.schemas import LyricsFile

FADE_IN_S = 0.2
FADE_OUT_S = 0.3


class RenderError(RuntimeError):
   

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def _load_font(font_size: int):
    
    from PIL import ImageFont

    candidates = [
        # macOS
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def _text_width(font, text: str) -> int:
    try:
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]
    except AttributeError:
        w, _ = font.getsize(text) 
        return w


def _word_wrap(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(font, candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def _prepare_background(background_path: Path, width: int, height: int):
    
    from PIL import Image

    img = Image.open(background_path).convert("RGB")
    scale = max(width / img.width, height / img.height)
    new_w, new_h = int(img.width * scale + 0.5), int(img.height * scale + 0.5)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x0, y0 = (new_w - width) // 2, (new_h - height) // 2
    img = img.crop((x0, y0, x0 + width, y0 + height))
    overlay = Image.new("RGB", (width, height), (0, 0, 0))
    return Image.blend(img, overlay, alpha=0.45)


def _make_text_overlay(text: str, font, font_size: int, width: int, height: int):
    
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    line_height = int(font_size * 1.28)
    lines = _word_wrap(text, font, int(width * 0.84))
    total_h = len(lines) * line_height
    y = (height - total_h) // 2

    for line in lines:
        tw = _text_width(font, line)
        x = (width - tw) // 2
        draw.text((x + 3, y + 4), line, font=font, fill=(0, 0, 0, 220))  # shadow
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    return canvas


def _composite(bg_rgba, text_overlay, alpha_f: float):
    
    from PIL import Image

    if alpha_f >= 0.999:
        return Image.alpha_composite(bg_rgba, text_overlay).convert("RGB")

    r, g, b, a = text_overlay.split()
    a = a.point(lambda v: int(v * alpha_f))
    scaled = Image.merge("RGBA", (r, g, b, a))
    return Image.alpha_composite(bg_rgba, scaled).convert("RGB")


def render_lyric_video(
    *,
    audio_path: Path,
    background_path: Path,
    lyrics: LyricsFile,
    output_path: Path,
    resolution: str = "1080p",
    fps: int = 30,
    on_progress: Callable[[int], None] | None = None,
) -> Path:
    

    if resolution not in RESOLUTIONS:
        raise ValueError(f"Unsupported resolution: {resolution}")
    width, height = RESOLUTIONS[resolution]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    duration = lyrics.duration_seconds or (max(ln.end for ln in lyrics.lines) + 2.0)
    font_size = max(36, int(height * 0.052))
    font = _load_font(font_size)
    bg = _prepare_background(background_path, width, height)
    bg_rgba = bg.convert("RGBA")

    frame_dur = 1.0 / fps
    fi_frames = round(FADE_IN_S * fps)   
    fo_frames = round(FADE_OUT_S * fps)  
    lines = lyrics.lines

    with tempfile.TemporaryDirectory() as tmpdir:
        
        bg_path = os.path.join(tmpdir, "bg.png")
        bg.save(bg_path, "PNG")

        concat_lines: list[str] = []

        def add(img_path: str, dur: float) -> None:
            safe = img_path.replace("\\", "/")
            concat_lines.append(f"file '{safe}'")
            concat_lines.append(f"duration {dur:.6f}")

        def add_bg(dur: float) -> None:
            add(bg_path, dur)

       
        if lines[0].start > 0.01:
            add_bg(lines[0].start)

        n_lines = len(lines)
        for i, line in enumerate(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            display_end = min(line.end, next_line.start) if next_line else line.end
            display_dur = max(0.0, display_end - line.start)

            
            max_fade_frames = max(0, int(display_dur * fps) - 1)
            fi = min(fi_frames, max_fade_frames // 2)
            fo = min(fo_frames, max_fade_frames - fi)
            full_dur = display_dur - (fi + fo) * frame_dur

            
            text_overlay = _make_text_overlay(line.text, font, font_size, width, height)

            
            for k in range(1, fi + 1):
                alpha = k / fi
                frame = _composite(bg_rgba, text_overlay, alpha)
                p = os.path.join(tmpdir, f"f{i:04d}_fi{k:03d}.png")
                frame.save(p, "PNG")
                add(p, frame_dur)

            
            if full_dur > 0:
                p = os.path.join(tmpdir, f"f{i:04d}_full.png")
                _composite(bg_rgba, text_overlay, 1.0).save(p, "PNG")
                add(p, max(full_dur, frame_dur))

            
            for k in range(fo, 0, -1):
                alpha = k / fo
                frame = _composite(bg_rgba, text_overlay, alpha)
                p = os.path.join(tmpdir, f"f{i:04d}_fo{k:03d}.png")
                frame.save(p, "PNG")
                add(p, frame_dur)

            
            if next_line and display_end < next_line.start - 0.01:
                add_bg(next_line.start - display_end)

            
            if on_progress:
                on_progress(round((i + 1) / n_lines * 65))

        
        last_end = lines[-1].end
        if last_end < duration - 0.1:
            add_bg(duration - last_end)

        
        if concat_lines:
            last_file = concat_lines[-2]  
            concat_lines.append(last_file)

        concat_path = os.path.join(tmpdir, "concat.txt")
        Path(concat_path).write_text("\n".join(concat_lines) + "\n")

        command = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_path,
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]

       
        if on_progress:
            on_progress(70)

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RenderError("FFmpeg is not installed.", "") from exc
        except subprocess.CalledProcessError as exc:
            raise RenderError("FFmpeg failed to render the video.", exc.stderr) from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RenderError("FFmpeg finished but did not produce a video.", "")

    return output_path
