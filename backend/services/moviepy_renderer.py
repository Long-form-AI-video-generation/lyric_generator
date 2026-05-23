from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.core.config import RESOLUTIONS
from backend.models.schemas import AnimationStyle, LineDirection, LyricsFile, Storyboard
from backend.services.asset_pipeline import (
    composite_speaker,
    load_background_images,
    load_speaker_images,
    prepare_background,
)


_FONT_PATHS: dict[str, list[str]] = {
    "Impact": [
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    ],
    "Montserrat": [
        "/Library/Fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
    ],
    "Bebas": [
        "/Library/Fonts/BebasNeue-Regular.ttf",
        "/usr/share/fonts/truetype/bebas-neue/BebasNeue-Regular.ttf",
    ],
    "CourierNew": [
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/cour.ttf",
    ],
    "Georgia": [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/georgia.ttf",
    ],
    "FuturaBold": [
        "/Library/Fonts/Futura.ttc",
        "/usr/share/fonts/truetype/futura/Futura-Bold.ttf",
    ],
    "TrajanPro": [
        "/Library/Fonts/Trajan Pro 3 Regular.ttf",
        "/usr/share/fonts/truetype/trajan/TrajanPro-Regular.ttf",
    ],
}

_FONT_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _FONT_PATHS.get(name, []) + _FONT_FALLBACKS
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r, g, b, alpha



def _word_wrap(text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        try:
            tw = font.getbbox(candidate)[2] - font.getbbox(candidate)[0]
        except AttributeError:
            tw = font.getsize(candidate)[0]
        if tw <= max_w or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def _make_text_frame(
    bg: Image.Image,
    text: str,
    direction: LineDirection,
    width: int,
    height: int,
    alpha_t: float,
    *,
    typewriter_chars: int | None = None,
) -> Image.Image:
    
    font_size = max(18, int(height * direction.font_size_pct / 100))
    font = _load_font(direction.font, font_size)
    display_text = text[:typewriter_chars] if typewriter_chars is not None else text
    color = _hex_to_rgba(direction.text_color, int(255 * alpha_t))
    shadow = (0, 0, 0, int(200 * alpha_t))

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    wrapped = _word_wrap(display_text, font, int(width * 0.84))
    line_h = int(font_size * 1.3)
    total_h = len(wrapped) * line_h

    cx = width * direction.position.x_pct / 100
    cy = height * direction.position.y_pct / 100
    y = int(cy - total_h / 2)

    for line_str in wrapped:
        try:
            tw = font.getbbox(line_str)[2] - font.getbbox(line_str)[0]
        except AttributeError:
            tw = font.getsize(line_str)[0]
        x = int(cx - tw / 2)
        draw.text((x + 3, y + 3), line_str, font=font, fill=shadow)
        draw.text((x, y), line_str, font=font, fill=color)
        y += line_h

    return Image.alpha_composite(bg.convert("RGBA"), canvas).convert("RGB")


def _anim_fade_in(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    return [_make_text_frame(bg, text, d, w, h, (i + 1) / n) for i in range(n)]


def _anim_typewriter(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    total = max(1, len(text))
    return [
        _make_text_frame(bg, text, d, w, h, 1.0, typewriter_chars=max(1, int(total * (i + 1) / n)))
        for i in range(n)
    ]


def _anim_glitch(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    import random
    from PIL import ImageChops

    frames = []
    for i in range(n):
        alpha = (i + 1) / n
        frame = _make_text_frame(bg, text, d, w, h, alpha)
        if i < n // 3:
            r, g, b = frame.split()
            shift = random.randint(2, 9)
            frame = Image.merge("RGB", (ImageChops.offset(r, shift, 0), g, ImageChops.offset(b, -shift, 0)))
        frames.append(frame)
    return frames


def _anim_slide_from_left(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    full = _make_text_frame(bg, text, d, w, h, 1.0)
    frames = []
    for i in range(n):
        t = (i + 1) / n
        offset = int((1 - t) * -w)
        frame = Image.new("RGB", (w, h), (0, 0, 0))
        frame.paste(full, (offset, 0))
        frames.append(frame)
    return frames


def _anim_slide_from_right(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    full = _make_text_frame(bg, text, d, w, h, 1.0)
    frames = []
    for i in range(n):
        t = (i + 1) / n
        offset = int((1 - t) * w)
        frame = Image.new("RGB", (w, h), (0, 0, 0))
        frame.paste(full, (offset, 0))
        frames.append(frame)
    return frames


def _anim_zoom_in(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    full = _make_text_frame(bg, text, d, w, h, 1.0)
    frames = []
    for i in range(n):
        scale = 0.5 + 0.5 * (i + 1) / n
        nw, nh = int(w * scale), int(h * scale)
        zoomed = full.resize((nw, nh), Image.LANCZOS)
        frame = Image.new("RGB", (w, h), (0, 0, 0))
        frame.paste(zoomed, ((w - nw) // 2, (h - nh) // 2))
        frames.append(frame)
    return frames


def _anim_pop(
    bg: Image.Image, text: str, d: LineDirection, w: int, h: int, n: int
) -> list[Image.Image]:
    full = _make_text_frame(bg, text, d, w, h, 1.0)
    frames = []
    for i in range(n):
        # Overshoot: scale peaks at ~1.15× then settles to 1.0
        scale = 1.0 + 0.15 * math.sin((i + 1) / n * math.pi)
        nw, nh = int(w * scale), int(h * scale)
        scaled = full.resize((nw, nh), Image.LANCZOS)
        frame = Image.new("RGB", (w, h), (0, 0, 0))
        frame.paste(scaled, ((w - nw) // 2, (h - nh) // 2))
        frames.append(frame)
    return frames


_ANIM_BUILDERS = {
    AnimationStyle.fade_in: _anim_fade_in,
    AnimationStyle.typewriter: _anim_typewriter,
    AnimationStyle.glitch: _anim_glitch,
    AnimationStyle.slide_from_left: _anim_slide_from_left,
    AnimationStyle.slide_from_right: _anim_slide_from_right,
    AnimationStyle.zoom_in: _anim_zoom_in,
    AnimationStyle.pop: _anim_pop,
}

def _default_direction(line_id: int) -> LineDirection:
    from backend.models.schemas import BackgroundTreatment, TextPosition

    return LineDirection(
        line_id=line_id,
        font="default",
        text_color="#FFFFFF",
        font_size_pct=5.2,
        position=TextPosition(x_pct=50, y_pct=50),
        animation=AnimationStyle.fade_in,
        background=BackgroundTreatment(),
        transition="cut",
    )

def render_storyboard_video(
    *,
    audio_path: Path,
    asset_dirs: list[Path],
    speaker_dirs: list[Path] | None = None,
    lyrics: LyricsFile,
    storyboard: Storyboard,
    output_path: Path,
    resolution: str = "1080p",
    fps: int = 30,
) -> Path:
   
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    if resolution not in RESOLUTIONS:
        raise ValueError(f"Unsupported resolution: {resolution!r}")

    width, height = RESOLUTIONS[resolution]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    background_images = load_background_images(asset_dirs)
    speaker_images = load_speaker_images(speaker_dirs or [])
    fallback_bg = Image.new("RGB", (width, height), (0, 0, 0))

    direction_map: dict[int, LineDirection] = {d.line_id: d for d in storyboard.lines}
    frame_dur = 1.0 / fps
    # Number of frames devoted to the entrance animation per lyric line
    ANIM_FRAME_COUNT = max(4, round(0.25 * fps))

    clips = []

    if lyrics.lines[0].start > 0.01:
        clips.append(ImageClip(fallback_bg).with_duration(lyrics.lines[0].start))

    for i, line in enumerate(lyrics.lines):
        next_line = lyrics.lines[i + 1] if i + 1 < len(lyrics.lines) else None
        display_end = min(line.end, next_line.start) if next_line else line.end
        display_dur = max(0.0, display_end - line.start)
        if display_dur < frame_dur:
            continue

        direction = direction_map.get(line.id) or _default_direction(line.id)

        if background_images:
            img_idx = direction.background.image_index % len(background_images)
            bg = prepare_background(
                background_images[img_idx],
                width,
                height,
                filter_name=direction.background.filter,
            )
        else:
            bg = fallback_bg.copy()

        # Optionally composite a speaker photo on top
        if speaker_images and direction.background.speaker_opacity > 0:
            sp_idx = direction.background.image_index % len(speaker_images)
            bg = composite_speaker(
                bg,
                speaker_images[sp_idx],
                distortion=direction.background.speaker_distortion,
                opacity=direction.background.speaker_opacity,
            )
        anim_frames_count = min(ANIM_FRAME_COUNT, max(1, int(display_dur * fps) - 1))
        builder = _ANIM_BUILDERS.get(direction.animation, _anim_fade_in)
        anim_frames = builder(bg, line.text, direction, width, height, anim_frames_count)

        anim_clips = [ImageClip(f).with_duration(frame_dur) for f in anim_frames]
        if anim_clips:
            clips.append(concatenate_videoclips(anim_clips))

        hold_dur = max(0.0, display_dur - anim_frames_count * frame_dur)
        if hold_dur > 0.01:
            hold_frame = _make_text_frame(bg, line.text, direction, width, height, 1.0)
            clips.append(ImageClip(hold_frame).with_duration(hold_dur))

        if next_line and display_end < next_line.start - frame_dur:
            gap = next_line.start - display_end
            clips.append(ImageClip(bg).with_duration(gap))

    duration = lyrics.duration_seconds or (max(ln.end for ln in lyrics.lines) + 2.0)
    last_end = lyrics.lines[-1].end
    if last_end < duration - 0.1:
        clips.append(ImageClip(fallback_bg).with_duration(duration - last_end))

    if not clips:
        raise RuntimeError("No video clips were generated — the lyrics list may be empty.")

    video = concatenate_videoclips(clips, method="compose")

    audio = AudioFileClip(str(audio_path))
    final_dur = min(audio.duration, video.duration)
    video = video.with_audio(audio.subclipped(0, final_dur))

    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("MoviePy finished but produced an empty or missing output file.")

    return output_path
