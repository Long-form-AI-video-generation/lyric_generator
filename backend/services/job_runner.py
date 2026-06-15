

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
   
    raw = settings.asset_dirs_raw.strip()
    if not raw:
        return []
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def _speaker_image_map(job_token: str, extra_name_dirs: dict[str, str] | None = None) -> dict[str, list[Path]]:
    
    from backend.services.asset_pipeline import load_background_images

    result: dict[str, list[Path]] = {}

    
    speakers_dir = storage.job_dir(job_token) / "speakers"
    if speakers_dir.is_dir():
        for slug_dir in sorted(speakers_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            name_file = slug_dir / ".artist_name"
            # Recover original name from manifest, fall back to slug
            artist_name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else slug_dir.name
            images = load_background_images([slug_dir])
            if images:
                result.setdefault(artist_name.lower(), []).extend(images)

    
    if extra_name_dirs:
        for name, path_str in extra_name_dirs.items():
            images = load_background_images([Path(path_str)])
            if images:
                result.setdefault(name.lower(), []).extend(images)

    
    raw = settings.speaker_dirs_raw.strip()
    if raw:
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                name, _, path_str = token.partition("=")
                images = load_background_images([Path(path_str.strip())])
                result.setdefault(name.strip().lower(), []).extend(images)
            else:
                result.setdefault("", []).extend(load_background_images([Path(token)]))

    return result


def _public_error(message: str) -> str:
    if settings.hide_internal_errors:
        return "The job failed. Please try again or contact the tool owner."
    return message


def run_transcription_job(job_token: str) -> None:

    try:
        manifest = storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.transcribing,
            progress_pct=10,
            error="",
            debug_log="",
        )
        
        storage.update(job_token, progress_pct=15)
        lyrics = transcribe_audio(Path(manifest.audio_path))
        
        storage.update(job_token, progress_pct=90)
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

    try:
        manifest = storage.update(
            job_token,
            status=JobState.processing,
            phase=JobPhase.transcribing,
            progress_pct=10,
            error="",
            debug_log="",
        )
       
        storage.update(job_token, progress_pct=15)
        lyrics = align_lyrics_text(Path(manifest.audio_path), lyrics_text)
        
        storage.update(job_token, progress_pct=90)
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


def run_art_direction_job(
    job_token: str,
    style_prompt: str,
    openai_api_key: str | None = None,
) -> None:
   
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
            raise RuntimeError("No lyrics.json found ,run transcription or alignment first.")

        lyrics_payload = json.loads(Path(manifest.lyrics_path).read_text(encoding="utf-8"))
        from backend.models.schemas import parse_lyrics_payload

        lyrics = parse_lyrics_payload(lyrics_payload)

        from backend.services.art_director import run_art_direction
        from backend.services.song_config import parse_song_config

        ad_request = storage.read_json(job_token, "art_direction_request.json")
        background_image_b64: str | None = ad_request.get("background_image_b64")
        song_config_yaml: str | None = ad_request.get("song_config_yaml")

        song_config = parse_song_config(song_config_yaml or "")

        effective_key = openai_api_key or settings.openai_api_key or None

        has_ai_backgrounds = song_config.generate_ai_backgrounds and effective_key

        phase_a_end = 60 if has_ai_backgrounds else 95

        def on_llm_progress(chunk_pct: int) -> None:
            mapped = round(10 + chunk_pct / 100 * (phase_a_end - 10))
            storage.update(job_token, progress_pct=mapped)

        artist_names = list(song_config.speakers.keys()) if song_config.speakers else None

        storyboard = run_art_direction(
            lyrics,
            style_prompt,
            background_image_b64=background_image_b64,
            song_config=song_config,
            openai_api_key=effective_key,
            on_progress=on_llm_progress,
            artist_names=artist_names,
        )

        storyboard_dict = storyboard.model_dump(mode="json")

        
        if has_ai_backgrounds:
            try:
                from backend.services.ai_backgrounds import (
                    apply_ai_backgrounds_to_storyboard,
                    generate_ai_backgrounds,
                )

                
                def on_bg_progress(img_pct: int) -> None:
                    mapped = round(60 + img_pct / 100 * 35)
                    storage.update(job_token, progress_pct=mapped)

                job_dir = storage.job_dir(job_token)
                prompt_to_index = generate_ai_backgrounds(
                    job_dir,
                    storyboard_dict.get("lines", []),
                    openai_api_key=effective_key,
                    on_progress=on_bg_progress,
                )
                if prompt_to_index:
                    storyboard_dict = apply_ai_backgrounds_to_storyboard(
                        storyboard_dict, prompt_to_index
                    )
            except Exception as bg_exc:  # noqa: BLE001
                
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

        
        def on_render_progress(renderer_pct: int) -> None:
            mapped = round(35 + renderer_pct / 100 * 60)
            storage.update(job_token, progress_pct=mapped)

        if storyboard_data:
            from backend.models.schemas import Storyboard
            from backend.services.moviepy_renderer import render_storyboard_video

            storyboard = Storyboard.model_validate(storyboard_data)

            job_dir = storage.job_dir(job_token)
            ai_bg_files = sorted(job_dir.glob("bg_ai_*.jpg"))

            job_asset_dirs = []
            if ai_bg_files:
                # AI images live in job_dir — put it first so indices 0-N map to them
                job_asset_dirs.append(job_dir)
            if background_path and background_path.exists():
                job_asset_dirs.append(background_path.parent)
            job_asset_dirs.extend(_asset_dirs())

            render_storyboard_video(
                audio_path=Path(manifest.audio_path),
                asset_dirs=job_asset_dirs,
                speaker_image_map=_speaker_image_map(job_token),
                lyrics=lyrics,
                storyboard=storyboard,
                output_path=output_path,
                resolution=export_settings.resolution,
                fps=export_settings.fps,
                on_progress=on_render_progress,
            )
        else:
            render_lyric_video(
                audio_path=Path(manifest.audio_path),
                background_path=background_path,
                lyrics=lyrics,
                output_path=output_path,
                resolution=export_settings.resolution,
                fps=export_settings.fps,
                on_progress=on_render_progress,
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

