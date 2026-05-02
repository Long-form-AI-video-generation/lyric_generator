from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.schemas import ExportSettings, LyricsFile, parse_lyrics_payload


def test_lyrics_file_accepts_spec_schema() -> None:
    lyrics = LyricsFile.model_validate(
        {
            "title": "Song Title",
            "duration_seconds": 214,
            "lines": [
                {"id": 1, "text": "First line", "start": 4.2, "end": 7.8},
                {"id": 2, "text": "Second line", "start": 8.1, "end": 11.4},
            ],
        }
    )

    assert lyrics.title == "Song Title"
    assert lyrics.lines[0].start == 4.2


def test_parse_lyrics_payload_accepts_legacy_alignment_array() -> None:
    lyrics = parse_lyrics_payload(
        [
            {
                "line_index": 0,
                "line": "If there was an apocalypse",
                "start": 7.313,
                "end": 9.654,
                "confidence": 0.7664,
            },
            {
                "line_index": 1,
                "line": "I'd want your lips on mine",
                "start": 10.374,
                "end": 12.395,
                "confidence": 0.6997,
            },
        ]
    )

    assert lyrics.title == "Untitled Song"
    assert lyrics.duration_seconds == 12.395
    assert lyrics.lines[0].id == 1
    assert lyrics.lines[0].text == "If there was an apocalypse"


def test_lyrics_file_rejects_bad_time_range() -> None:
    with pytest.raises(ValidationError, match="end must be greater than start"):
        LyricsFile.model_validate(
            {
                "lines": [
                    {"id": 1, "text": "Broken line", "start": 4.2, "end": 4.2},
                ],
            }
        )


def test_export_settings_are_limited_to_supported_values() -> None:
    assert ExportSettings(resolution="1080p", fps=30).fps == 30

    with pytest.raises(ValidationError, match="resolution must be one of"):
        ExportSettings(resolution="4k", fps=30)

    with pytest.raises(ValidationError, match="fps must be one of"):
        ExportSettings(resolution="720p", fps=24)
