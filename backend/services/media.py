"""Media validation, filename sanitisation, and ffprobe helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Protocol

from backend.core.errors import ValidationAppError


class AsyncUpload(Protocol):
    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...


AUDIO_EXTENSIONS = {".mp3", ".wav"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sanitize_filename(filename: str | None, fallback: str = "upload") -> str:
    """Return a filesystem-safe basename without trusting user paths."""

    raw = Path(filename or fallback).name.strip() or fallback
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    stem = re.sub(r"-{2,}", "-", stem).strip(".-")
    return stem[:180] or fallback


def sniff_audio_type(header: bytes, filename: str | None = None) -> str:
    """Validate MP3/WAV by magic bytes and return the canonical extension."""

    suffix = Path(filename or "").suffix.lower()
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        if suffix and suffix != ".wav":
            raise ValidationAppError("The file content is WAV, but the extension is not .wav.")
        return ".wav"
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0):
        if suffix and suffix != ".mp3":
            raise ValidationAppError("The file content is MP3, but the extension is not .mp3.")
        return ".mp3"
    raise ValidationAppError("Please upload an MP3 or WAV audio file.")


def sniff_image_type(header: bytes, filename: str | None = None) -> str:
    """Validate JPG/PNG/WebP by magic bytes and return the canonical extension."""

    suffix = Path(filename or "").suffix.lower()
    if header.startswith(b"\xff\xd8\xff"):
        if suffix and suffix not in {".jpg", ".jpeg"}:
            raise ValidationAppError("The file content is JPEG, but the extension is not .jpg.")
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        if suffix and suffix != ".png":
            raise ValidationAppError("The file content is PNG, but the extension is not .png.")
        return ".png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        if suffix and suffix != ".webp":
            raise ValidationAppError("The file content is WebP, but the extension is not .webp.")
        return ".webp"
    raise ValidationAppError("Please upload a JPG, PNG, or WebP background image.")


async def save_validated_upload(
    upload: AsyncUpload,
    destination: Path,
    *,
    max_bytes: int,
    kind: str,
) -> tuple[Path, int]:
    """Stream an upload to disk while enforcing size and magic-byte validation."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    first_chunk = await upload.read(1024 * 1024)
    if not first_chunk:
        raise ValidationAppError("The uploaded file is empty.")

    if kind == "audio":
        extension = sniff_audio_type(first_chunk[:32], upload.filename)
    elif kind == "image":
        extension = sniff_image_type(first_chunk[:32], upload.filename)
    else:
        raise ValueError(f"Unsupported upload kind: {kind}")

    final_path = destination.with_suffix(extension)
    written = len(first_chunk)
    if written > max_bytes:
        raise ValidationAppError("The uploaded file is too large.")

    with final_path.open("wb") as handle:
        handle.write(first_chunk)
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                final_path.unlink(missing_ok=True)
                raise ValidationAppError("The uploaded file is too large.")
            handle.write(chunk)

    return final_path, written


def probe_audio_duration(path: Path) -> float:
    """Return the audio duration in seconds using ffprobe."""

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is not installed on this system.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValidationAppError(
            "The audio file could not be inspected. Please try another MP3 or WAV file.",
            debug=exc.stderr,
        ) from exc

    payload = json.loads(completed.stdout or "{}")
    duration = float(payload.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise ValidationAppError("The uploaded audio has no detectable duration.")
    return round(duration, 3)

