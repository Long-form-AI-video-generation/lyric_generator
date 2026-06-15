

from __future__ import annotations

import re

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.errors import AppError, WorkerUnavailableError
from backend.models.schemas import ArtDirectRequest, JobPhase, JobState, QueueResponse
from backend.services.job_runner import run_art_direction_job
from backend.services.media import sanitize_filename, save_validated_upload
from backend.services.storage import storage

router = APIRouter(tags=["storyboard"])



def _queue_art_direction(
    job_token: str,
    style_prompt: str,
    background_tasks: BackgroundTasks,
    openai_api_key: str | None = None,
) -> None:
    if settings.use_celery:
        try:
            from backend.tasks.celery_tasks import art_direction_job

            art_direction_job.delay(job_token, style_prompt, openai_api_key)
            return
        except Exception as exc:
            raise WorkerUnavailableError(
                "Could not queue the art direction job. Is Redis running?"
            ) from exc
    background_tasks.add_task(run_art_direction_job, job_token, style_prompt, openai_api_key)


def _validate_song_config_yaml(yaml_text: str | None) -> None:
    
    if not yaml_text:
        return
    from backend.services.song_config import parse_song_config
    parse_song_config(yaml_text)  # raises ValueError on bad input


@router.post("/art-direct", response_model=QueueResponse, summary="Run the AI art direction pass")
async def art_direct(
    request: ArtDirectRequest,
    background_tasks: BackgroundTasks,
) -> QueueResponse:
    
    try:
        
        try:
            _validate_song_config_yaml(request.song_config_yaml)
        except ValueError as exc:
            raise AppError(str(exc), status_code=422) from exc

        manifest = storage.read_manifest(request.job_token)

        
        if not manifest.lyrics_path:
            raise AppError(
                "No lyrics found for this job. "
                "Complete transcription or alignment before running art direction.",
                status_code=409,
            )

        
        storage.write_json(
            request.job_token,
            "art_direction_request.json",
            {
                "style_prompt": request.style_prompt,
                "ai_image_generation": request.ai_image_generation,
                "background_image_b64": request.background_image_b64,
                "song_config_yaml": request.song_config_yaml,
            },
        )
        storage.update(
            request.job_token,
            status=JobState.queued,
            phase=JobPhase.art_directing,
            progress_pct=0,
            error="",
            debug_log="",
        )
        _queue_art_direction(
            request.job_token,
            request.style_prompt,
            background_tasks,
            openai_api_key=request.openai_api_key,
        )
        return QueueResponse(job_token=request.job_token)

    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/storyboard/{job_token}", summary="Fetch the storyboard for a job")
async def get_storyboard(job_token: str) -> dict:
    try:
        return storage.read_json(job_token, "storyboard.json")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_token}/backgrounds", summary="List AI-generated background images for a job")
async def list_backgrounds(job_token: str) -> dict:
    """Return URLs for every bg_ai_NNN.jpg file written by the AI background pipeline."""
    try:
        job_dir = storage.job_dir(job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    backgrounds = []
    for f in sorted(job_dir.glob("bg_ai_*.jpg")):
        m = re.match(r"bg_ai_(\d+)\.jpg", f.name)
        if m:
            idx = int(m.group(1))
            backgrounds.append({"index": idx, "url": f"/api/jobs/{job_token}/bg/{idx}"})
    return {"backgrounds": backgrounds}


@router.get("/jobs/{job_token}/speakers", summary="List uploaded speaker images for a job")
async def list_speakers(job_token: str):
    """Return { speakers: [ {name, slug, url, generated_url?, duo_generated_urls?} ] }."""
    try:
        storage.read_manifest(job_token)
        job_dir = storage.job_dir(job_token)
        speakers_dir = job_dir / "speakers"
        result = []
        if speakers_dir.is_dir():
            for slug_dir in sorted(speakers_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                name_file = slug_dir / ".artist_name"
                artist_name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else slug_dir.name
                raw_photos = [
                    f for f in sorted(slug_dir.iterdir())
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                    and not f.name.startswith(".")
                    and not f.name.startswith("generated_")
                ]
                if not raw_photos:
                    continue
                entry: dict = {
                    "name": artist_name,
                    "slug": slug_dir.name,
                    "url": f"/api/jobs/{job_token}/speakers/{slug_dir.name}",
                }
                solo_gen = slug_dir / "generated_solo.jpg"
                if solo_gen.exists():
                    entry["generated_url"] = f"/api/jobs/{job_token}/speakers/{slug_dir.name}/generated"
                result.append(entry)

            # Duo images live directly in speakers_dir as duo_{a}_{b}.jpg
            duo_map: dict[str, str] = {}
            for duo_file in sorted(speakers_dir.glob("duo_*.jpg")):
                duo_map[duo_file.stem] = f"/api/jobs/{job_token}/speakers/duo/{duo_file.stem}"
            if duo_map:
                for entry in result:
                    entry["duo_generated_urls"] = duo_map

        return {"speakers": result}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_token}/speakers/{slug}", summary="Serve the raw uploaded photo for an artist")
async def serve_speaker_image(job_token: str, slug: str):
    try:
        storage.read_manifest(job_token)
        slug_dir = storage.job_dir(job_token) / "speakers" / slug
        images = sorted([
            f for f in slug_dir.iterdir()
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            and not f.name.startswith(".")
            and not f.name.startswith("generated_")
        ])
        if not images:
            raise HTTPException(status_code=404, detail="No image found for this artist.")
        return FileResponse(images[0], media_type="image/jpeg")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_token}/speakers/{slug}/generated", summary="Serve the AI-generated solo image for an artist")
async def serve_generated_speaker_image(job_token: str, slug: str):
    try:
        storage.read_manifest(job_token)
        out = storage.job_dir(job_token) / "speakers" / slug / "generated_solo.jpg"
        if not out.exists():
            raise HTTPException(status_code=404, detail="No generated image for this artist yet.")
        return FileResponse(out, media_type="image/jpeg")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/jobs/{job_token}/speakers/duo/{duo_key}", summary="Serve an AI-generated duo image")
async def serve_generated_duo_image(job_token: str, duo_key: str):
    try:
        storage.read_manifest(job_token)
        # duo_key is the stem e.g. "duo_artist_a_artist_b"
        out = storage.job_dir(job_token) / "speakers" / f"{duo_key}.jpg"
        if not out.exists():
            raise HTTPException(status_code=404, detail="No generated duo image found.")
        return FileResponse(out, media_type="image/jpeg")
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/jobs/{job_token}/speaker-image/{artist_name}", summary="Upload a photo for a named artist")
async def upload_speaker_image(job_token: str, artist_name: str, image: UploadFile = File(...)):
    """Save an artist photo to job_dir/speakers/{slug}/.
    The artist_name is slugified (lowercased, spaces→underscores) for the directory name
    but the original name is stored in a manifest so the renderer can match it.
    """
    try:
        storage.read_manifest(job_token)
        # Slug the artist name for a safe directory name
        slug = re.sub(r"[^a-z0-9]+", "_", artist_name.lower()).strip("_") or "artist"
        safe_filename = sanitize_filename(image.filename, f"{slug}_photo")
        dest = storage.job_dir(job_token) / "speakers" / slug / safe_filename
        await save_validated_upload(
            image,
            dest,
            max_bytes=settings.max_background_bytes,
            kind="image",
        )
        # Write a name manifest so the renderer maps slug → original name
        name_file = storage.job_dir(job_token) / "speakers" / slug / ".artist_name"
        name_file.write_text(artist_name, encoding="utf-8")
        return {"ok": True, "artist": artist_name, "path": str(dest)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


class GenerateArtistImagesRequest(BaseModel):
    style_prompt: str
    openai_api_key: str
    pairs: list[list[str]] | None = None  # e.g. [["Artist A", "Artist B"]]


@router.post("/jobs/{job_token}/generate-artist-images", summary="Generate AI images for each artist using their uploaded photos")
async def generate_artist_images_endpoint(
    job_token: str,
    request: GenerateArtistImagesRequest,
    background_tasks: BackgroundTasks,
):
    
    try:
        storage.read_manifest(job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    from backend.services.artist_image_gen import generate_artist_images

    job_dir = storage.job_dir(job_token)
    pairs = [tuple(p) for p in (request.pairs or []) if len(p) == 2]  # type: ignore[misc]

    background_tasks.add_task(
        generate_artist_images,
        job_dir,
        request.style_prompt,
        request.openai_api_key,
        pairs or None,
    )

    return {"ok": True, "message": "Artist image generation started."}


@router.get("/jobs/{job_token}/bg/{index}", summary="Serve an AI-generated background image")
async def serve_background(job_token: str, index: int):
    try:
        job_dir = storage.job_dir(job_token)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    image_path = job_dir / f"bg_ai_{index:03d}.jpg"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Background image {index} not found.")
    return FileResponse(image_path, media_type="image/jpeg")
