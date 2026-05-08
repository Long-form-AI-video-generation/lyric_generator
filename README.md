# LyricVid

LyricVid is an internal browser tool for creating synced lyric videos from an MP3 or WAV file. The refactored system follows the product specification in `requirememts.md`: a Next.js wizard for upload/edit/preview/export, a FastAPI backend for transient jobs, optional Celery + Redis workers, Whisper transcription, FFmpeg MP4 rendering, and no database-backed persistence.

## What Is Included

- `frontend/` - Next.js 14 App Router, TypeScript, Tailwind, Zustand, Framer Motion, Lucide icons.
- `backend/` - FastAPI API, Pydantic v2 schemas, upload validation by magic bytes, transient filesystem job storage, preset generation, Whisper boundary, ASS subtitle generation, FFmpeg rendering.
- `docker-compose.yml` - frontend, backend, Celery worker, and Redis.

## Local Development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

By default `USE_CELERY=false`, so transcription and export jobs run as FastAPI background tasks for local development. For production-like async workers, set `USE_CELERY=true` and run Redis plus:

```bash
celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO
```

## Docker

```bash
docker compose up --build
```

The compose stack exposes:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Redis: internal service only

Whisper model weights are cached in the `whisper-cache` Docker volume. For a GPU server, set `WHISPER_DEVICE=cuda` and use an appropriate CUDA-enabled Python base image for `backend/Dockerfile`.

## API Summary

- `POST /api/upload` - upload MP3/WAV, returns a `job_token`.
- `POST /api/transcribe` - queue Whisper transcription for an uploaded job.
- `GET /api/status/{job_token}` - poll transcription/render progress.
- `GET /api/lyrics/{job_token}` - fetch generated lyrics JSON.
- `POST /api/export` - queue MP4 rendering with final lyrics and background.
- `GET /api/download/{job_token}` - stream the rendered MP4 and delete the job.
- `GET /api/presets` - list built-in background presets.

## Data Retention

There is no database, no accounts, and no analytics. Uploaded files and render outputs live under `LYRICVID_TEMP_ROOT` only. Jobs are deleted after download or when the TTL cleanup removes stale directories.

## Verification

Lightweight tests avoid loading Whisper:

```bash
pytest backend/tests/
```

The Whisper path is intentionally isolated in `backend/services/whisper_service.py`; run that portion on a machine with enough CPU/GPU capacity and preloaded model weights.
