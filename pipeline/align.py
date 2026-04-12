"""
Lyrics alignment module.

Uses WhisperX to transcribe audio and force-align the transcription
against raw lyric text. Produces a structured JSON file with word-level
and line-level timestamps, confidence scores, and speaker placeholders.

Can be used as an importable module or run directly via:
    python -m pipeline.align --audio path --lyrics path --output path
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from thefuzz import fuzz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lyrics loading
# ---------------------------------------------------------------------------

def load_lyrics_text(lyrics_path: str) -> list[str]:
    """Read a plain .txt file of lyrics, one line per line.

    Blank lines and whitespace-only lines are ignored.

    Args:
        lyrics_path: Path to the lyrics text file.

    Returns:
        A list of cleaned, non-empty lyric line strings.

    Raises:
        FileNotFoundError: If *lyrics_path* does not exist.
    """
    path = Path(lyrics_path)
    if not path.exists():
        raise FileNotFoundError(f"Lyrics file not found: {lyrics_path}")
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped:
            lines.append(stripped)
    logger.info("Loaded %d lyric lines from %s", len(lines), lyrics_path)
    return lines


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED_LINE_FIELDS: dict[str, type] = {
    "line_index": int,
    "line": str,
    "start": float,
    "end": float,
    "speaker": str,
    "words": list,
    "confidence": float,
}

_REQUIRED_WORD_FIELDS: dict[str, type] = {
    "word": str,
    "start": float,
    "end": float,
}


def validate_lyrics_json(data: list[dict[str, Any]]) -> bool:
    """Validate a list of line dicts against the lyrics JSON schema.

    Checks that every required field is present with the correct type for
    both line-level and word-level entries.

    Args:
        data: The list of line dictionaries to validate.

    Returns:
        True if the data is valid.

    Raises:
        ValueError: With a descriptive message if any field is missing or
            has the wrong type.
    """
    if not isinstance(data, list):
        raise ValueError("Top-level lyrics JSON must be a list")

    for idx, line_dict in enumerate(data):
        if not isinstance(line_dict, dict):
            raise ValueError(f"Item at index {idx} is not a dict")

        for field, expected_type in _REQUIRED_LINE_FIELDS.items():
            if field not in line_dict:
                raise ValueError(
                    f"Line {idx}: missing required field '{field}'"
                )
            value = line_dict[field]
            # Allow int where float is expected (e.g. 0 instead of 0.0)
            if expected_type is float and isinstance(value, int):
                continue
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Line {idx}: field '{field}' expected "
                    f"{expected_type.__name__}, got {type(value).__name__}"
                )

        for widx, word_dict in enumerate(line_dict["words"]):
            if not isinstance(word_dict, dict):
                raise ValueError(
                    f"Line {idx}, word {widx}: not a dict"
                )
            for field, expected_type in _REQUIRED_WORD_FIELDS.items():
                if field not in word_dict:
                    raise ValueError(
                        f"Line {idx}, word {widx}: missing '{field}'"
                    )
                value = word_dict[field]
                if expected_type is float and isinstance(value, int):
                    continue
                if not isinstance(value, expected_type):
                    raise ValueError(
                        f"Line {idx}, word {widx}: field '{field}' expected "
                        f"{expected_type.__name__}, got {type(value).__name__}"
                    )

    return True


# ---------------------------------------------------------------------------
# Correction report
# ---------------------------------------------------------------------------

def print_correction_report(lyrics_json: list[dict[str, Any]]) -> None:
    """Print a human-readable table highlighting low-confidence lines.

    Lines with confidence below the configured threshold are prefixed with
    a warning marker so the user knows which timestamps to review.

    Args:
        lyrics_json: A validated list of line dicts.
    """
    from config import CONFIDENCE_WARNING_THRESHOLD, MIN_LINE_DURATION

    header = f"{'':3s} {'idx':>4s} | {'start':>8s} | {'end':>8s} | {'conf':>6s} | line"
    separator = "-" * len(header)
    logger.info("\n%s\n%s", header, separator)
    for entry in lyrics_json:
        flag = ""
        if 0 <= entry["confidence"] < CONFIDENCE_WARNING_THRESHOLD:
            flag = ">>>"
        duration = entry["end"] - entry["start"]
        if 0 < duration < MIN_LINE_DURATION:
            flag = flag or "!!!"
        line_str = (
            f"{flag:3s} {entry['line_index']:4d} | "
            f"{entry['start']:8.2f} | {entry['end']:8.2f} | "
            f"{entry['confidence']:6.2f} | {entry['line']}"
        )
        logger.info(line_str)
    logger.info(separator)


# ---------------------------------------------------------------------------
# Fuzzy matching helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy comparison."""
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch == " ").strip()


def _match_words_to_line(
    line: str,
    whisper_words: list[dict[str, Any]],
    start_idx: int,
) -> tuple[list[dict[str, Any]], int]:
    """Greedily match WhisperX words to a single lyric line using fuzzy matching.

    Starting from *start_idx* in the whisper_words list, accumulates words
    until the reconstructed string best matches *line*.  Returns the matched
    word dicts and the new cursor position.

    Args:
        line: The original lyric line to match against.
        whisper_words: The full list of word-level dicts from WhisperX.
        start_idx: Index in *whisper_words* to start matching from.

    Returns:
        A tuple of (matched_words, next_start_idx).
    """
    norm_line = _normalize(line)
    best_score: int = 0
    best_end: int = start_idx
    accumulated = ""

    for i in range(start_idx, len(whisper_words)):
        word_text = whisper_words[i].get("word", "")
        if accumulated:
            accumulated += " " + _normalize(word_text)
        else:
            accumulated = _normalize(word_text)

        score = fuzz.ratio(accumulated, norm_line)
        if score > best_score:
            best_score = score
            best_end = i + 1

        # If we have a near-perfect match or score starts declining
        # significantly after a good match, stop early.
        if best_score >= 95:
            break
        if score < best_score - 20 and best_score > 50:
            break

    matched = whisper_words[start_idx:best_end]
    return matched, best_end


def _build_line_dict(
    line_index: int,
    line_text: str,
    matched_words: list[dict[str, Any]],
    prev_end: float,
    next_start: float,
) -> dict[str, Any]:
    """Construct a single line dict from matched words.

    If no words matched (e.g. instrumental section), estimates start/end
    from surrounding lines and sets confidence to -1.0.

    Args:
        line_index: Zero-based line index.
        line_text: The original lyric line string.
        matched_words: Word-level dicts that were matched to this line.
        prev_end: End time of the previous line (for estimation).
        next_start: Start time of the next line (for estimation).

    Returns:
        A fully-formed line dict conforming to the lyrics JSON schema.
    """
    clean_words: list[dict[str, Any]] = []
    for w in matched_words:
        clean_words.append({
            "word": w.get("word", ""),
            "start": float(w.get("start", 0.0)),
            "end": float(w.get("end", 0.0)),
        })

    if clean_words:
        line_start = clean_words[0]["start"]
        line_end = clean_words[-1]["end"]
        confidences = [
            w.get("score", -1.0) for w in matched_words
        ]
        valid_conf = [c for c in confidences if c >= 0]
        avg_confidence = sum(valid_conf) / len(valid_conf) if valid_conf else -1.0
    else:
        # No words matched — estimate from neighbours
        line_start = prev_end
        line_end = next_start if next_start > prev_end else prev_end + 2.0
        avg_confidence = -1.0

    return {
        "line_index": line_index,
        "line": line_text,
        "start": round(line_start, 3),
        "end": round(line_end, 3),
        "speaker": "unknown",
        "words": clean_words,
        "confidence": round(avg_confidence, 4),
    }


# ---------------------------------------------------------------------------
# Main alignment entry point
# ---------------------------------------------------------------------------

def run_alignment(
    audio_path: str,
    lyrics_text: str,
    output_path: str,
    device: str = "",
) -> list[dict[str, Any]]:
    """Run full WhisperX alignment and produce a lyrics JSON file.

    Loads the WhisperX model, transcribes the audio, runs forced alignment,
    then merges word-level output back into the original lyric lines using
    fuzzy matching.  Validates and saves the result.

    Args:
        audio_path: Path to the WAV audio file.
        lyrics_text: Raw multiline lyrics string (one line per line).
        output_path: Destination path for the output lyrics.json.
        device: ``"cuda"`` or ``"cpu"``.  Auto-detected when empty.

    Returns:
        The validated list of line dicts.

    Raises:
        FileNotFoundError: If *audio_path* does not exist.
        RuntimeError: If WhisperX model loading or alignment fails.
    """
    import torch
    import whisperx

    from config import (
        ALIGNMENT_DEVICE,
        WHISPERX_LANGUAGE,
        WHISPERX_MODEL,
    )

    # --- resolve device ---
    if not device:
        device = ALIGNMENT_DEVICE
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested but unavailable — falling back to cpu")
        device = "cpu"
    logger.info("Using device: %s", device)

    # --- validate audio ---
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # --- parse lyrics lines ---
    lyric_lines = [
        ln.strip() for ln in lyrics_text.splitlines() if ln.strip()
    ]
    logger.info("Parsed %d lyric lines from input text", len(lyric_lines))

    # --- load model & transcribe ---
    t0 = time.perf_counter()
    try:
        model = whisperx.load_model(
            WHISPERX_MODEL, device, language=WHISPERX_LANGUAGE
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load WhisperX model: {exc}") from exc
    logger.info("WhisperX model loaded in %.2fs", time.perf_counter() - t0)

    t1 = time.perf_counter()
    audio = whisperx.load_audio(str(audio_file))
    result = model.transcribe(audio)
    logger.info("Transcription completed in %.2fs", time.perf_counter() - t1)

    # --- forced alignment ---
    t2 = time.perf_counter()
    try:
        align_model, align_meta = whisperx.load_align_model(
            language_code=WHISPERX_LANGUAGE, device=device
        )
        aligned = whisperx.align(
            result["segments"], align_model, align_meta, audio, device
        )
    except Exception as exc:
        raise RuntimeError(f"WhisperX alignment failed: {exc}") from exc
    logger.info("Forced alignment completed in %.2fs", time.perf_counter() - t2)

    # --- collect all word-level entries ---
    all_words: list[dict[str, Any]] = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            all_words.append(w)
    logger.info("WhisperX produced %d word-level entries", len(all_words))

    # --- fuzzy-match words to original lyric lines ---
    t3 = time.perf_counter()
    cursor = 0
    line_dicts: list[dict[str, Any]] = []

    for i, line_text in enumerate(lyric_lines):
        matched, cursor = _match_words_to_line(line_text, all_words, cursor)
        prev_end = line_dicts[-1]["end"] if line_dicts else 0.0
        # Peek at next line's first word for estimation if needed
        next_start = all_words[cursor]["start"] if cursor < len(all_words) else 0.0
        ld = _build_line_dict(i, line_text, matched, prev_end, next_start)
        line_dicts.append(ld)

    logger.info("Line matching completed in %.2fs", time.perf_counter() - t3)

    # --- validate ---
    validate_lyrics_json(line_dicts)
    logger.info("Output validation passed")

    # --- write output ---
    out = Path(output_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(line_dicts, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to write JSON to {output_path}: {exc}") from exc
    logger.info("Wrote lyrics JSON to %s", output_path)

    # --- correction report ---
    print_correction_report(line_dicts)

    return line_dicts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the alignment script."""
    parser = argparse.ArgumentParser(
        description="Align lyrics to audio using WhisperX",
    )
    parser.add_argument(
        "--audio", required=True, help="Path to the WAV audio file"
    )
    parser.add_argument(
        "--lyrics", required=True, help="Path to the raw lyrics .txt file"
    )
    parser.add_argument(
        "--output", required=True, help="Path to write the output lyrics.json"
    )
    parser.add_argument(
        "--device",
        default="",
        choices=["cpu", "cuda", ""],
        help="Force cpu or cuda (auto-detected if omitted)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for running alignment."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args(argv)

    lyrics_path = Path(args.lyrics)
    if not lyrics_path.exists():
        logger.error("Lyrics file not found: %s", args.lyrics)
        sys.exit(1)

    lyrics_text = lyrics_path.read_text(encoding="utf-8")
    run_alignment(args.audio, lyrics_text, args.output, args.device)


if __name__ == "__main__":
    main()
