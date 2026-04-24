"""
Lyrics alignment module.

Uses WhisperX to transcribe audio and force-align the transcription
against raw lyric text. Produces a structured JSON file with line-level
timestamps and confidence scores for downstream display.

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
    "confidence": float,
}


def validate_lyrics_json(data: list[dict[str, Any]]) -> bool:
    """Validate a list of line dicts against the lyrics JSON schema.

    Checks that every required field is present with the correct type.

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


def _display_word(word: str) -> str:
    """Normalize aligned word text for display in lyric lines."""
    return " ".join(word.strip().split())


def _join_words(words: list[dict[str, Any]]) -> str:
    """Join aligned words into a single display line."""
    return " ".join(
        cleaned for cleaned in (_display_word(w.get("word", "")) for w in words) if cleaned
    ).strip()


def _line_confidence(words: list[dict[str, Any]]) -> float:
    """Average confidence across aligned words in a line."""
    confidences = [w.get("score", -1.0) for w in words]
    valid_conf = [c for c in confidences if c >= 0]
    return sum(valid_conf) / len(valid_conf) if valid_conf else -1.0


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


def _build_line_dict(line_index: int, line_text: str, matched_words: list[dict[str, Any]]) -> dict[str, Any]:
    """Construct a single line dict from matched words.

    If no words matched, returns a zero-duration placeholder entry with
    confidence -1.0 so the output schema remains stable.
    """
    if matched_words:
        line_start = float(matched_words[0].get("start", 0.0))
        line_end = float(matched_words[-1].get("end", 0.0))
        avg_confidence = _line_confidence(matched_words)
    else:
        line_start = 0.0
        line_end = 0.0
        avg_confidence = -1.0

    return {
        "line_index": line_index,
        "line": line_text,
        "start": round(line_start, 3),
        "end": round(line_end, 3),
        "confidence": round(avg_confidence, 4),
    }


def _should_break_phrase(
    current_words: list[dict[str, Any]],
    next_word: dict[str, Any],
    max_words_per_line: int,
    max_chars_per_line: int,
    phrase_gap_seconds: float,
    punctuation_gap_seconds: float,
) -> bool:
    """Decide whether the next aligned word should start a new lyric line."""
    from config import SHORT_LINE_WORDS

    if not current_words:
        return False

    previous_word = current_words[-1]
    previous_end = float(previous_word.get("end", 0.0))
    next_start = float(next_word.get("start", previous_end))
    gap = next_start - previous_end

    if gap >= phrase_gap_seconds:
        return True

    previous_text = _display_word(previous_word.get("word", ""))
    if previous_text.endswith((".", "!", "?", ",", ";", ":")) and gap >= punctuation_gap_seconds:
        return True

    candidate_words = current_words + [next_word]
    if len(candidate_words) > max_words_per_line:
        return True

    candidate_text = _join_words(candidate_words)
    if len(candidate_text) > max_chars_per_line and len(current_words) > SHORT_LINE_WORDS:
        return True

    return False


def _merge_short_phrases(
    phrases: list[list[dict[str, Any]]],
    max_words_per_line: int,
    max_chars_per_line: int,
) -> list[list[dict[str, Any]]]:
    """Merge very short adjacent phrases when they still fit comfortably."""
    from config import MERGE_PHRASE_GAP_SECONDS, SHORT_LINE_WORDS

    if not phrases:
        return []

    merged: list[list[dict[str, Any]]] = [phrases[0]]
    for phrase in phrases[1:]:
        previous = merged[-1]
        combined = previous + phrase
        combined_text = _join_words(combined)
        gap = float(phrase[0].get("start", 0.0)) - float(previous[-1].get("end", 0.0))

        if (
            len(previous) <= SHORT_LINE_WORDS
            and gap <= MERGE_PHRASE_GAP_SECONDS
            and len(combined) <= max_words_per_line
            and len(combined_text) <= max_chars_per_line
        ):
            merged[-1] = combined
        else:
            merged.append(phrase)

    return merged


def group_aligned_words_into_lines(all_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn aligned word timings into phrase-based lyric lines.

    The grouping is driven by audible pauses between words first, then by
    readability constraints such as max words and max characters per line.
    """
    from config import (
        MAX_CHARS_PER_LINE,
        MAX_WORDS_PER_LINE,
        PHRASE_GAP_SECONDS,
        PUNCTUATION_GAP_SECONDS,
    )

    cleaned_words = [w for w in all_words if _display_word(w.get("word", ""))]
    if not cleaned_words:
        return []

    phrases: list[list[dict[str, Any]]] = []
    current_phrase: list[dict[str, Any]] = []

    for word in cleaned_words:
        if _should_break_phrase(
            current_phrase,
            word,
            max_words_per_line=MAX_WORDS_PER_LINE,
            max_chars_per_line=MAX_CHARS_PER_LINE,
            phrase_gap_seconds=PHRASE_GAP_SECONDS,
            punctuation_gap_seconds=PUNCTUATION_GAP_SECONDS,
        ):
            phrases.append(current_phrase)
            current_phrase = []
        current_phrase.append(word)

    if current_phrase:
        phrases.append(current_phrase)

    merged_phrases = _merge_short_phrases(
        phrases,
        max_words_per_line=MAX_WORDS_PER_LINE,
        max_chars_per_line=MAX_CHARS_PER_LINE,
    )

    return [
        _build_line_dict(idx, _join_words(words), words)
        for idx, words in enumerate(merged_phrases)
    ]


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

    lyric_lines = [
        ln.strip() for ln in lyrics_text.splitlines() if ln.strip()
    ]
    if lyric_lines:
        logger.info("Parsed %d lyric lines from input text", len(lyric_lines))
    else:
        logger.info("No lyric lines supplied; generating display lines from alignment")

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

    # --- build display lines from the aligned timings ---
    t3 = time.perf_counter()
    line_dicts = group_aligned_words_into_lines(all_words)
    logger.info("Generated %d display lines in %.2fs", len(line_dicts), time.perf_counter() - t3)

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
