"""
Configuration constants for the lyric video pipeline.

Centralizes paths, model settings, and threshold values used across
the alignment and correction tools.
"""

from pathlib import Path

BASE_DIR: Path = Path(__file__).parent
SONGS_DIR: Path = BASE_DIR / "songs"
CACHE_DIR: Path = BASE_DIR / "cache"
OUTPUT_DIR: Path = BASE_DIR / "output"

WHISPERX_MODEL: str = "base"  # can be tiny, base, small, medium, large-v2
WHISPERX_LANGUAGE: str = "en"
ALIGNMENT_DEVICE: str = "cpu"  # override to "cuda" if GPU available
CONFIDENCE_WARNING_THRESHOLD: float = 0.75
MIN_LINE_DURATION: float = 0.5  # seconds — warn if a line is shorter than this
