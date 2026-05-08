from __future__ import annotations

from backend.models.schemas import LyricsFile
from backend.services.ass_generator import ass_timestamp, escape_ass_text, generate_ass


def test_ass_timestamp_uses_centiseconds() -> None:
    assert ass_timestamp(65.432) == "0:01:05.43"


def test_escape_ass_text_handles_override_chars() -> None:
    assert escape_ass_text(r"a {b}\c") == r"a \{b\}\\c"


def test_generate_ass_contains_centered_fade_dialogue() -> None:
    lyrics = LyricsFile.model_validate(
        {
            "title": "Test",
            "lines": [{"id": 1, "text": "Hello world", "start": 1.0, "end": 2.5}],
        }
    )
    ass = generate_ass(lyrics, 1920, 1080)

    assert "PlayResX: 1920" in ass
    assert r"\fad(200,300)" in ass
    assert "Dialogue: 0,0:00:01.00,0:00:02.50" in ass

