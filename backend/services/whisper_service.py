"""Whisper transcription boundary.

This module deliberately imports Whisper libraries only inside the execution
path, so the API and tests remain light on machines that cannot run the model.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.config import settings
from backend.models.schemas import LyricLine, LyricsFile
from backend.services.media import probe_audio_duration, sanitize_filename


def _title_from_filename(path: Path) -> str:
    return sanitize_filename(path.stem, "Untitled Song").replace("-", " ").strip().title()


def transcribe_with_openai_whisper(audio_path: Path) -> LyricsFile:
    """Transcribe audio with openai-whisper and return segment-level lyrics."""

    import torch
    import whisper

    device = settings.whisper_device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model = whisper.load_model(settings.whisper_model, device=device)
    result = model.transcribe(
        str(audio_path),
        language=settings.whisper_language,
        word_timestamps=True,
        verbose=False,
    )
    duration = probe_audio_duration(audio_path)
    lines: list[LyricLine] = []
    for index, segment in enumerate(result.get("segments", []), start=1):
        text = str(segment.get("text", "")).strip()
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start + 0.1))
        if text and end > start:
            lines.append(LyricLine(id=index, text=text, start=round(start, 3), end=round(end, 3)))

    if not lines:
        raise RuntimeError("Whisper did not detect any lyric segments.")

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=duration,
        lines=lines,
    )


def transcribe_with_faster_whisper(audio_path: Path) -> LyricsFile:
    """Transcribe audio with faster-whisper and return segment-level lyrics."""

    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type="float16" if settings.whisper_device == "cuda" else "int8",
    )
    segments, info = model.transcribe(
        str(audio_path),
        language=settings.whisper_language,
        vad_filter=True,
    )
    duration = float(getattr(info, "duration", 0) or probe_audio_duration(audio_path))
    lines: list[LyricLine] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip()
        if text and segment.end > segment.start:
            lines.append(
                LyricLine(
                    id=index,
                    text=text,
                    start=round(float(segment.start), 3),
                    end=round(float(segment.end), 3),
                )
            )

    if not lines:
        raise RuntimeError("Whisper did not detect any lyric segments.")

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=round(duration, 3),
        lines=lines,
    )


def transcribe_audio(audio_path: Path) -> LyricsFile:
    """Run the configured Whisper backend."""

    if settings.whisper_backend == "faster-whisper":
        return transcribe_with_faster_whisper(audio_path)
    return transcribe_with_openai_whisper(audio_path)

