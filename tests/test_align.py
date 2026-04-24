"""
Unit tests for the lyrics alignment pipeline.

Tests cover validation, lyrics loading, the correction report, and
error handling for missing audio files.  WhisperX calls are mocked
where a real model or audio file would be required.
"""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pipeline.align import (
    group_aligned_words_into_lines,
    load_lyrics_text,
    print_correction_report,
    run_alignment,
    validate_lyrics_json,
)
from scripts.transcribe import split_transcribed_lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_line(
    line_index: int = 0,
    line: str = "hello world",
    start: float = 1.0,
    end: float = 2.0,
) -> dict[str, Any]:
    """Return a minimal valid line dict for testing."""
    return {
        "line_index": line_index,
        "line": line,
        "start": start,
        "end": end,
        "confidence": 0.92,
    }


# ---------------------------------------------------------------------------
# validate_lyrics_json
# ---------------------------------------------------------------------------

class TestValidateLyricsJson:
    """Tests for the validate_lyrics_json function."""

    def test_validate_lyrics_json_valid(self) -> None:
        """A correctly formed list of dicts passes validation."""
        data = [_make_valid_line(0), _make_valid_line(1, line="foo bar")]
        assert validate_lyrics_json(data) is True

    def test_validate_lyrics_json_missing_field(self) -> None:
        """A dict missing the 'start' field raises ValueError."""
        entry = _make_valid_line()
        del entry["start"]
        with pytest.raises(ValueError, match="missing required field 'start'"):
            validate_lyrics_json([entry])

    def test_validate_lyrics_json_wrong_type(self) -> None:
        """A dict where line_index is a string raises ValueError."""
        entry = _make_valid_line()
        entry["line_index"] = "zero"
        with pytest.raises(ValueError, match="expected int, got str"):
            validate_lyrics_json([entry])

    def test_validate_lyrics_json_not_a_list(self) -> None:
        """Passing a dict instead of a list raises ValueError."""
        with pytest.raises(ValueError, match="must be a list"):
            validate_lyrics_json({})  # type: ignore[arg-type]


class TestSplitTranscribedLines:
    """Tests for turning long WhisperX segments into lyric-sized lines."""

    def test_split_transcribed_lines_chunks_long_text(self) -> None:
        """Long segments are split into short display-friendly lines."""
        segments = [
            {
                "text": (
                    "If there was an apocalypse I'd want your lips on mine "
                    "Just between you and me I think you look so fine"
                )
            }
        ]

        result = split_transcribed_lines(segments, max_words_per_line=6)

        assert result == [
            "If there was an apocalypse I'd",
            "want your lips on mine Just",
            "between you and me I think",
            "you look so fine",
        ]


class TestGroupAlignedWordsIntoLines:
    """Tests for phrase grouping based on aligned word timings."""

    def test_group_aligned_words_into_lines_breaks_on_pause(self) -> None:
        """A large pause between words starts a new display line."""
        words = [
            {"word": "So", "start": 1.0, "end": 1.2, "score": 0.95},
            {"word": "baby", "start": 1.2, "end": 1.6, "score": 0.94},
            {"word": "come", "start": 2.3, "end": 2.7, "score": 0.93},
            {"word": "closer", "start": 2.7, "end": 3.1, "score": 0.92},
        ]

        result = group_aligned_words_into_lines(words)

        assert [entry["line"] for entry in result] == ["So baby", "come closer"]
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 1.6
        assert result[1]["start"] == 2.3
        assert result[1]["end"] == 3.1


# ---------------------------------------------------------------------------
# load_lyrics_text
# ---------------------------------------------------------------------------

class TestLoadLyricsText:
    """Tests for the load_lyrics_text function."""

    def test_load_lyrics_text_ignores_blank_lines(self, tmp_path: Path) -> None:
        """Blank and whitespace-only lines are stripped from output."""
        lyrics_file = tmp_path / "lyrics.txt"
        lyrics_file.write_text(
            "Line one\n\n   \nLine two\n\nLine three\n",
            encoding="utf-8",
        )
        result = load_lyrics_text(str(lyrics_file))
        assert result == ["Line one", "Line two", "Line three"]

    def test_load_lyrics_text_file_not_found(self) -> None:
        """A missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_lyrics_text("/nonexistent/path/lyrics.txt")


# ---------------------------------------------------------------------------
# print_correction_report
# ---------------------------------------------------------------------------

class TestPrintCorrectionReport:
    """Tests for the print_correction_report function."""

    def test_print_correction_report_runs(self) -> None:
        """The report function executes without error on valid data."""
        high_conf = _make_valid_line(0)
        high_conf["confidence"] = 0.95
        low_conf = _make_valid_line(1)
        low_conf["confidence"] = 0.50
        # Should not raise
        print_correction_report([high_conf, low_conf])


# ---------------------------------------------------------------------------
# run_alignment — error case
# ---------------------------------------------------------------------------

class TestRunAlignment:
    """Tests for the run_alignment function."""

    def test_run_alignment_missing_audio(self) -> None:
        """Calling run_alignment with a nonexistent audio path raises FileNotFoundError."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_whisperx = MagicMock()

        with patch.dict("sys.modules", {"torch": mock_torch, "whisperx": mock_whisperx}):
            with pytest.raises(FileNotFoundError, match="Audio file not found"):
                run_alignment(
                    audio_path="/nonexistent/audio.wav",
                    lyrics_text="Some lyrics\nAnother line\n",
                    output_path="/tmp/out.json",
                    device="cpu",
                )

    def test_run_alignment_end_to_end_mocked(
        self,
        tmp_path: Path,
    ) -> None:
        """Full alignment pipeline runs with mocked WhisperX and produces valid JSON."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_whisperx = MagicMock()

        # Create a fake audio file so the path check passes
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        # Mock WhisperX model and transcription
        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_model.transcribe.return_value = {
            "segments": [
                {"text": "hello world goodbye moon"}
            ]
        }

        # Mock alignment output with word-level data
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = {
            "segments": [
                {
                    "words": [
                        {"word": "hello", "start": 1.0, "end": 1.3, "score": 0.95},
                        {"word": "world", "start": 1.3, "end": 1.7, "score": 0.90},
                        {"word": "goodbye", "start": 2.3, "end": 2.7, "score": 0.88},
                        {"word": "moon", "start": 2.7, "end": 3.1, "score": 0.92},
                    ]
                }
            ]
        }

        output_path = tmp_path / "lyrics.json"
        lyrics_text = "hello world goodbye moon\n"

        with patch.dict("sys.modules", {"torch": mock_torch, "whisperx": mock_whisperx}):
            result = run_alignment(
                audio_path=str(audio_file),
                lyrics_text=lyrics_text,
                output_path=str(output_path),
                device="cpu",
            )

        assert len(result) == 2
        assert result[0]["line"] == "hello world"
        assert result[1]["line"] == "goodbye moon"
        assert result[0]["line_index"] == 0
        assert result[1]["line_index"] == 1
        assert output_path.exists()

        # Verify the saved file is valid JSON matching the schema
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert validate_lyrics_json(saved) is True
