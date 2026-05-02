"""Synchronous job implementations used by Celery and local background tasks."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from backend.core.config import settings
from backend.models.schemas import ExportSettings, JobPhase, JobState, LyricsFile
from backend.services.ffmpeg_service import RenderError, render_lyric_video
from backend.services.presets import preset_service
from backend.services.storage import storage
from backend.services.whisper_service import transcribe_audio


def _public_error(message: str) -> str:
    if settings.hide_internal_errors:
        return "The job failed. Please try again or contact the tool owner."
    return message


def run_transcription_job(job_token: str) -> None:
    """Transcribe a previously uploaded audio file and persist lyrics JSON."""

    try:
        manifest = storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.transcribing,
            progress_pct=10,
            error="",
            debug_log="",
        )
        lyrics = transcribe_audio(Path(manifest.audio_path))
        lyrics_path = storage.write_json(
            job_token,
            "lyrics.json",
            lyrics.model_dump(mode="json"),
        )
        storage.update(
            job_token,
            status=JobState.complete,
            phase=JobPhase.transcribing,
            progress_pct=100,
            lyrics_path=str(lyrics_path),
            error="",
            debug_log="",
        )
    except Exception as exc:
        storage.update(
            job_token,
            status=JobState.failed,
            phase=JobPhase.transcribing,
            progress_pct=100,
            error=_public_error(str(exc)),
            debug_log=str(exc),
        )


def run_export_job(job_token: str) -> None:
    """Render an MP4 from a stored export request."""

    try:
        storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.rendering,
            progress_pct=15,
            error="",
            debug_log="",
        )
        manifest = storage.read_manifest(job_token)
        request = storage.read_json(job_token, "export_request.json")
        lyrics = LyricsFile.model_validate(request["lyrics"])
        export_settings = ExportSettings.model_validate(request["settings"])

        if request.get("preset_id"):
            background_path = preset_service.resolve_full_path(request["preset_id"])
        else:
            background_path = Path(request["background_path"])

        storage.update(job_token, progress_pct=35)
        title = lyrics.title or Path(manifest.safe_filename).stem or "song"
        safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in title).strip("-") or "song"
        output_path = storage.job_dir(job_token) / f"{safe_title}-lyrics.mp4"
        render_lyric_video(
            audio_path=Path(manifest.audio_path),
            background_path=background_path,
            lyrics=lyrics,
            output_path=output_path,
            resolution=export_settings.resolution,
            fps=export_settings.fps,
        )
        storage.update(
            job_token,
            status=JobState.complete,
            phase=JobPhase.rendering,
            progress_pct=100,
            result_path=str(output_path),
            error="",
            debug_log="",
        )
    except RenderError as exc:
        storage.update(
            job_token,
            status=JobState.failed,
            phase=JobPhase.rendering,
            progress_pct=100,
            error=_public_error(str(exc)),
            debug_log=exc.stderr or str(exc),
        )
    except (ValidationError, json.JSONDecodeError, KeyError, ValueError) as exc:
        storage.update(
            job_token,
            status=JobState.failed,
            phase=JobPhase.rendering,
            progress_pct=100,
            error="The export request is invalid.",
            debug_log=str(exc),
        )
    except Exception as exc:
        storage.update(
            job_token,
            status=JobState.failed,
            phase=JobPhase.rendering,
            progress_pct=100,
            error=_public_error(str(exc)),
            debug_log=str(exc),
        )

