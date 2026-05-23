"""Celery task entry points."""

from __future__ import annotations

from backend.services.job_runner import run_art_direction_job, run_export_job, run_transcription_job
from backend.services.storage import storage
from backend.tasks.celery_app import celery_app


@celery_app.task(name="backend.transcribe_job")
def transcribe_job(job_token: str) -> None:
    run_transcription_job(job_token)


@celery_app.task(name="backend.art_direction_job")
def art_direction_job(job_token: str, style_prompt: str) -> None:
    run_art_direction_job(job_token, style_prompt)


@celery_app.task(name="backend.export_job")
def export_job(job_token: str) -> None:
    run_export_job(job_token)


@celery_app.task(name="backend.cleanup_expired_jobs")
def cleanup_expired_jobs() -> int:
    return storage.cleanup_expired()

