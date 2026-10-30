"""Runtime configuration for the FastAPI backend.

The app intentionally avoids pydantic-settings so the configuration layer
stays light and importable in tests that do not install the full web stack.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = "LyricVid"
    app_env: str = os.getenv("APP_ENV", "development")
    api_prefix: str = "/api"
    
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/lyricvid_db",
    )

    secret_key: str = os.getenv("SECRET_KEY", "insecure-dev-secret-key-change-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days
    invite_token_expire_days: int = int(os.getenv("INVITE_TOKEN_EXPIRE_DAYS", "7"))

    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    email_from: str = os.getenv("EMAIL_FROM", "LyricVid Beta <eyobimpactinglife@gmail.com>")

    # Cloudflare R2 / S3 Storage Settings
    s3_bucket: str = os.getenv("R2_BUCKET", os.getenv("S3_BUCKET", ""))
    s3_endpoint_url: str | None = os.getenv("R2_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", None))
    s3_region: str = os.getenv("R2_REGION", os.getenv("S3_REGION", "auto"))
    aws_access_key_id: str | None = os.getenv("R2_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", None))
    aws_secret_access_key: str | None = os.getenv("R2_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", None))
    s3_presigned_expiry_seconds: int = int(os.getenv("S3_PRESIGNED_EXPIRY_SECONDS", "3600"))
    use_s3_storage: bool = _bool_env(
        "USE_S3_STORAGE",
        bool(os.getenv("R2_BUCKET") or os.getenv("S3_BUCKET")),
    )

    project_root: Path = Path(__file__).resolve().parents[2]
    backend_dir: Path = Path(__file__).resolve().parents[1]
    temp_root: Path = Path(os.getenv("LYRICVID_TEMP_ROOT", "/tmp/lyricvid"))
    preset_root: Path = backend_dir / "presets"

    allowed_origins: tuple[str, ...] = _csv_env(
        "ALLOWED_ORIGINS",
        (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ),
    )

    max_audio_bytes: int = int(os.getenv("MAX_AUDIO_BYTES", str(200 * 1024 * 1024)))
    max_background_bytes: int = int(
        os.getenv("MAX_BACKGROUND_BYTES", str(20 * 1024 * 1024))
    )
    job_ttl_seconds: int = int(os.getenv("JOB_TTL_SECONDS", "600"))
    download_ttl_seconds: int = int(os.getenv("DOWNLOAD_TTL_SECONDS", "300"))
    cleanup_interval_seconds: int = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))

    use_celery: bool = _bool_env("USE_CELERY", False)
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

    whisper_backend: str = os.getenv("WHISPER_BACKEND", "openai-whisper")
    whisper_model: str = os.getenv("WHISPER_MODEL", "large-v3")
    whisper_language: str = os.getenv("WHISPER_LANGUAGE", "en")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")

    hide_internal_errors: bool = _bool_env("HIDE_INTERNAL_ERRORS", False)

    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_proxy_url: str = os.getenv("OPENAI_PROXY_URL", "")
    art_direction_model_openai: str = os.getenv("ART_DIRECTION_MODEL", "gpt-4o")
    art_direction_model_anthropic: str = os.getenv("ART_DIRECTION_MODEL", "claude-sonnet-4-6")
   
    asset_dirs_raw: str = os.getenv("LYRICVID_ASSET_DIRS", "")
    speaker_dirs_raw: str = os.getenv("LYRICVID_SPEAKER_DIRS", "")

RESOLUTIONS: dict[str, tuple[int, int]] = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
}

FPS_VALUES: set[int] = {30, 60}

settings = Settings()
