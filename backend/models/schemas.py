"""Pydantic models shared by the API, workers, and services."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.core.config import FPS_VALUES, RESOLUTIONS


class JobPhase(str, Enum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    art_directing = "art_directing"
    rendering = "rendering"


class JobState(str, Enum):
    queued = "queued"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class LyricLine(BaseModel):
    id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1, max_length=500)
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "LyricLine":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class LyricsFile(BaseModel):
    title: str = Field(default="Untitled Song", min_length=1, max_length=180)
    duration_seconds: float | None = Field(default=None, ge=0)
    lines: list[LyricLine] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_line_order(self) -> "LyricsFile":
        seen_ids: set[int] = set()
        previous_start = -1.0
        for index, line in enumerate(self.lines):
            if line.id in seen_ids:
                raise ValueError(f"lines.{index}.id duplicates {line.id}")
            seen_ids.add(line.id)
            if line.start < previous_start:
                raise ValueError("lines must be sorted by start time")
            previous_start = line.start
        return self


class FieldIssue(BaseModel):
    field: str
    message: str


class ValidationIssues(BaseModel):
    message: str = "Invalid lyrics JSON."
    errors: list[FieldIssue]


class UploadResponse(BaseModel):
    job_token: str
    filename: str
    duration_seconds: float


class TranscribeRequest(BaseModel):
    job_token: str


class AlignRequest(BaseModel):
    job_token: str
    lyrics_text: str = Field(..., min_length=1, max_length=50_000)


class QueueResponse(BaseModel):
    job_token: str
    status: Literal["queued", "processing", "complete"] = "queued"


class StatusResponse(BaseModel):
    job_token: str
    status: JobState
    phase: JobPhase | None = None
    progress_pct: int = Field(default=0, ge=0, le=100)
    result_url: str | None = None
    error: str | None = None
    debug_log: str | None = None


class Preset(BaseModel):
    id: str
    label: str
    thumbnail_url: str


class PresetList(BaseModel):
    presets: list[Preset]


class ExportSettings(BaseModel):
    resolution: str = "1080p"
    fps: int = 30

    @model_validator(mode="after")
    def validate_export_settings(self) -> "ExportSettings":
        if self.resolution not in RESOLUTIONS:
            allowed = ", ".join(sorted(RESOLUTIONS))
            raise ValueError(f"resolution must be one of: {allowed}")
        if self.fps not in FPS_VALUES:
            allowed = ", ".join(str(value) for value in sorted(FPS_VALUES))
            raise ValueError(f"fps must be one of: {allowed}")
        return self


class JobManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_token: str
    original_filename: str
    safe_filename: str
    audio_path: str
    duration_seconds: float = 0
    status: JobState = JobState.queued
    phase: JobPhase | None = None
    progress_pct: int = 0
    result_path: str | None = None
    lyrics_path: str | None = None
    error: str | None = None
    debug_log: str | None = None
    created_at: float
    updated_at: float


# ---------------------------------------------------------------------------
# Storyboard schemas (Phase A / art direction)
# ---------------------------------------------------------------------------

class AnimationStyle(str, Enum):
    fade_in = "fade-in"
    typewriter = "typewriter"
    glitch = "glitch"
    slide_from_left = "slide-from-left"
    slide_from_right = "slide-from-right"
    zoom_in = "zoom-in"
    pop = "pop"


class TextPosition(BaseModel):
    x_pct: float = Field(50.0, ge=0, le=100, description="Horizontal centre as % of frame width")
    y_pct: float = Field(50.0, ge=0, le=100, description="Vertical centre as % of frame height")


class BackgroundTreatment(BaseModel):
    image_index: int = Field(0, ge=0, description="Which image from the asset pool to use (cycled)")
    filter: str = Field("none", description="One of: none, blur, desaturate, color_shift, glitch, vhs")
    speaker_distortion: str = Field(
        "none",
        description="One of: none, chromatic_aberration, pixel_sort, datamosh",
    )
    speaker_opacity: float = Field(0.0, ge=0.0, le=1.0)


class LineDirection(BaseModel):
    """Per-lyric-line visual directions produced by the art direction pass."""

    line_id: int
    font: str = Field("default", description="Font name from the supported set")
    text_color: str = Field("#FFFFFF", description="Hex colour for the lyric text")
    font_size_pct: float = Field(
        5.2, ge=1.0, le=20.0,
        description="Font size as a percentage of the frame height",
    )
    position: TextPosition = Field(default_factory=TextPosition)
    animation: AnimationStyle = AnimationStyle.fade_in
    background: BackgroundTreatment = Field(default_factory=BackgroundTreatment)
    transition: str = Field("cut", description="One of: cut, fade, slide")
    image_prompt: str | None = Field(
        None,
        description="Optional Stable Diffusion / FLUX prompt for AI-generated background",
    )


class Storyboard(BaseModel):
    """Full art direction storyboard for one song."""

    title: str
    style_prompt: str
    lines: list[LineDirection]
    created_at: float = Field(default_factory=time.time)


class ArtDirectRequest(BaseModel):
    job_token: str
    style_prompt: str = Field(..., min_length=1, max_length=2000)
    ai_image_generation: bool = Field(
        False,
        description="When True, image_prompt fields are sent to a diffusion API",
    )
    background_image_b64: str | None = Field(
        None,
        description="Base64-encoded JPEG thumbnail of the chosen background (no data: prefix). "
                    "Passed to the vision model so it can choose contrasting text colors.",
    )


def validation_issues(exc: ValidationError) -> ValidationIssues:
    """Convert Pydantic's nested errors into frontend-friendly field issues."""

    errors: list[FieldIssue] = []
    for issue in exc.errors():
        location = ".".join(str(part) for part in issue["loc"])
        errors.append(FieldIssue(field=location, message=issue["msg"]))
    return ValidationIssues(errors=errors)


def _as_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _coerce_legacy_lyrics(payload: Any) -> dict[str, Any]:
    """Accept the legacy alignment array and convert it to the product schema."""

    data = {"lines": payload} if isinstance(payload, list) else _as_mapping(payload, "lyrics")
    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list):
        return data

    lines: list[dict[str, Any]] = []
    for index, raw_line in enumerate(raw_lines):
        item = _as_mapping(raw_line, f"lines.{index}")
        text = item.get("text", item.get("line"))
        line_id = item.get("id")
        if line_id is None and isinstance(item.get("line_index"), int):
            line_id = int(item["line_index"]) + 1
        lines.append(
            {
                "id": line_id or index + 1,
                "text": text,
                "start": item.get("start"),
                "end": item.get("end"),
            }
        )

    duration = data.get("duration_seconds")
    if duration is None and lines:
        duration = max(float(line["end"] or 0) for line in lines)

    return {
        "title": data.get("title") or "Untitled Song",
        "duration_seconds": duration,
        "lines": lines,
    }


def parse_lyrics_payload(payload: Any) -> LyricsFile:
    """Validate a lyrics payload, accepting both current and legacy schemas."""

    return LyricsFile.model_validate(_coerce_legacy_lyrics(payload))
