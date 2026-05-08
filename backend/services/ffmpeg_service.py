"""FFmpeg orchestration for MP4 rendering."""

from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core.config import RESOLUTIONS
from backend.models.schemas import LyricsFile
from backend.services.ass_generator import write_ass_file


class RenderError(RuntimeError):
    """Raised when FFmpeg fails to render a video."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def _escape_filter_path(path: Path) -> str:
    # FFmpeg filter arguments treat ':' and '\' specially.
    return str(path).replace("\\", "\\\\").replace(":", "\\:")


def render_lyric_video(
    *,
    audio_path: Path,
    background_path: Path,
    lyrics: LyricsFile,
    output_path: Path,
    resolution: str = "1080p",
    fps: int = 30,
) -> Path:
    """Render a lyric video by burning ASS subtitles over a still background."""

    if resolution not in RESOLUTIONS:
        raise ValueError(f"Unsupported resolution: {resolution}")
    width, height = RESOLUTIONS[resolution]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = output_path.with_suffix(".ass")
    write_ass_file(ass_path, lyrics, width, height)

    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,"
        f"ass={_escape_filter_path(ass_path)},format=yuv420p"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-i",
        str(background_path),
        "-i",
        str(audio_path),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RenderError("FFmpeg is not installed.", "") from exc
    except subprocess.CalledProcessError as exc:
        raise RenderError("FFmpeg failed to render the video.", exc.stderr) from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RenderError("FFmpeg finished but did not produce a video.", completed.stderr)

    return output_path

