"""Filesystem-backed transient job storage.

No database is used. Each job has one directory under the configured temp
root containing uploads, generated lyrics, render outputs, and a manifest.
"""

from __future__ import annotations

import json
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.core.errors import NotFoundError, ValidationAppError
from backend.models.schemas import JobManifest, JobPhase, JobState
from backend.services.media import sanitize_filename


class JobStorage:
    """Small persistence layer for short-lived upload/render jobs."""

    def __init__(self, root: Path | None = None, ttl_seconds: int | None = None) -> None:
        self.root = root or settings.temp_root
        self.ttl_seconds = ttl_seconds or settings.job_ttl_seconds

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def new_token(self) -> str:
        return secrets.token_urlsafe(24)

    def validate_token(self, token: str) -> str:
        if not token or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in token):
            raise ValidationAppError("Invalid job token.")
        return token

    def job_dir(self, token: str) -> Path:
        token = self.validate_token(token)
        return self.root / token

    def manifest_path(self, token: str) -> Path:
        return self.job_dir(token) / "manifest.json"

    def reserve_job(self) -> tuple[str, Path]:
        """Create and return an empty job directory for streaming uploads."""

        self.ensure_root()
        for _ in range(8):
            token = self.new_token()
            job_dir = self.job_dir(token)
            try:
                job_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return token, job_dir
        raise RuntimeError("Could not allocate a unique job token.")

    def create_audio_job(
        self,
        *,
        token: str,
        original_filename: str,
        audio_path: Path,
        duration_seconds: float,
    ) -> JobManifest:
        self.ensure_root()
        job_dir = self.job_dir(token)
        job_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        manifest = JobManifest(
            job_token=token,
            original_filename=original_filename,
            safe_filename=sanitize_filename(original_filename, "song"),
            audio_path=str(audio_path),
            duration_seconds=duration_seconds,
            status=JobState.complete,
            phase=JobPhase.uploaded,
            progress_pct=100,
            created_at=now,
            updated_at=now,
        )
        self.write_manifest(manifest)
        return manifest

    def read_manifest(self, token: str) -> JobManifest:
        path = self.manifest_path(token)
        if not path.exists():
            raise NotFoundError("That job has expired or does not exist.")
        return JobManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def write_manifest(self, manifest: JobManifest) -> None:
        path = self.manifest_path(manifest.job_token)
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest.updated_at = time.time()
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)

    def update(
        self,
        token: str,
        *,
        status: JobState | None = None,
        phase: JobPhase | None = None,
        progress_pct: int | None = None,
        error: str | None = None,
        debug_log: str | None = None,
        result_path: str | None = None,
        lyrics_path: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> JobManifest:
        manifest = self.read_manifest(token)
        if status is not None:
            manifest.status = status
        if phase is not None:
            manifest.phase = phase
        if progress_pct is not None:
            manifest.progress_pct = max(0, min(100, int(progress_pct)))
        if error is not None:
            manifest.error = error
        if debug_log is not None:
            manifest.debug_log = debug_log
        if result_path is not None:
            manifest.result_path = result_path
        if lyrics_path is not None:
            manifest.lyrics_path = lyrics_path
        if extra:
            payload = manifest.model_dump()
            payload.update(extra)
            manifest = JobManifest.model_validate(payload)
        self.write_manifest(manifest)
        return manifest

    def write_json(self, token: str, relative_path: str, payload: Any) -> Path:
        path = self.job_dir(token) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def read_json(self, token: str, relative_path: str) -> Any:
        path = self.job_dir(token) / relative_path
        if not path.exists():
            raise NotFoundError("The requested job file does not exist.")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_job(self, token: str) -> None:
        shutil.rmtree(self.job_dir(token), ignore_errors=True)

    def cleanup_expired(self) -> int:
        self.ensure_root()
        now = time.time()
        removed = 0
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            manifest_path = child / "manifest.json"
            try:
                manifest = JobManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                updated_at = manifest.updated_at
            except Exception:
                updated_at = child.stat().st_mtime
            if now - updated_at > self.ttl_seconds:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        return removed


storage = JobStorage()
