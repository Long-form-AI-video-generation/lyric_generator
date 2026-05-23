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
from backend.services.whisper_service import align_lyrics_text, transcribe_audio


def _asset_dirs() -> list[Path]:
    """Return the configured background-image directories (may be empty)."""
    raw = settings.asset_dirs_raw.strip()
    if not raw:
        return []
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def _speaker_dirs() -> list[Path]:
    """Return the configured speaker-photo directories (may be empty)."""
    raw = settings.speaker_dirs_raw.strip()
    if not raw:
        return []
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


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


def run_alignment_job(job_token: str, lyrics_text: str) -> None:
    """Align user-provided lyrics text to audio timing and persist lyrics JSON."""

    try:
        manifest = storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.transcribing,
            progress_pct=10,
            error="",
            debug_log="",
        )
        lyrics = align_lyrics_text(Path(manifest.audio_path), lyrics_text)
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


def run_art_direction_job(job_token: str, style_prompt: str) -> None:

    try:
        storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.art_directing,
            progress_pct=10,
            error="",
            debug_log="",
        )
        manifest = storage.read_manifest(job_token)
        if not manifest.lyrics_path:
            raise RuntimeError("No lyrics.json found — run transcription or alignment first.")

        lyrics_payload = json.loads(Path(manifest.lyrics_path).read_text(encoding="utf-8"))
        from backend.models.schemas import parse_lyrics_payload

        lyrics = parse_lyrics_payload(lyrics_payload)

        from backend.services.art_director import run_art_direction
        from backend.services.song_config import parse_song_config

        ad_request = storage.read_json(job_token, "art_direction_request.json")
        background_image_b64: str | None = ad_request.get("background_image_b64")
        song_config_yaml: str | None = ad_request.get("song_config_yaml")

        song_config = parse_song_config(song_config_yaml or "")

        storyboard = run_art_direction(
            lyrics,
            style_prompt,
            background_image_b64=background_image_b64,
            song_config=song_config,
        )

        storyboard_dict = storyboard.model_dump(mode="json")

        # Phase A+: generate AI backgrounds if the song config requests it
        if song_config.generate_ai_backgrounds and settings.openai_api_key:
            try:
                from backend.services.ai_backgrounds import (
                    apply_ai_backgrounds_to_storyboard,
                    generate_ai_backgrounds,
                )

                job_dir = storage.job_dir(job_token)
                prompt_to_index = generate_ai_backgrounds(
                    job_dir,
                    storyboard_dict.get("lines", []),
                    openai_api_key=settings.openai_api_key,
                )
                if prompt_to_index:
                    storyboard_dict = apply_ai_backgrounds_to_storyboard(
                        storyboard_dict, prompt_to_index
                    )
            except Exception as bg_exc:  # noqa: BLE001
                # Non-fatal — log but let the job succeed without AI images
                print(f"[job_runner] AI background generation failed: {bg_exc}")

        storage.write_json(
            job_token,
            "storyboard.json",
            storyboard_dict,
        )
        storage.update(
            job_token,
            status=JobState.complete,
            phase=JobPhase.art_directing,
            progress_pct=100,
            error="",
            debug_log="",
        )
    except Exception as exc:
        storage.update(
            job_token,
            status=JobState.failed,
            phase=JobPhase.art_directing,
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

        storyboard_data = None
        try:
            storyboard_data = storage.read_json(job_token, "storyboard.json")
        except Exception:
            pass

        if storyboard_data:
            from backend.models.schemas import Storyboard
            from backend.services.moviepy_renderer import render_storyboard_video

            storyboard = Storyboard.model_validate(storyboard_data)
            # Seed the asset pool with the job's own background image / preset
            job_asset_dirs = _asset_dirs()
            if background_path and background_path.exists():
                job_asset_dirs = [background_path.parent] + job_asset_dirs
            render_storyboard_video(
                audio_path=Path(manifest.audio_path),
                asset_dirs=job_asset_dirs,
                speaker_dirs=_speaker_dirs(),
                lyrics=lyrics,
                storyboard=storyboard,
                output_path=output_path,
                resolution=export_settings.resolution,
                fps=export_settings.fps,
            )
        else:
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

