"""
Transcribe audio or video to a plain text lyrics file using WhisperX.

Accepts WAV, MP3, MP4, or any ffmpeg-supported format. If the input is
not a WAV file, it is automatically converted to WAV first via ffmpeg.

Usage:
    python scripts/transcribe.py input.mp4 -o songs/song01/lyrics.txt
    python scripts/transcribe.py input.mp4 -o songs/song01/lyrics.txt --model small
"""

import argparse
import logging
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)
_PUNCTUATION_BOUNDARY = re.compile(r"(?<=[.!?;,])\s+")


def convert_to_wav(input_path: str, output_path: str) -> None:
    """Convert any audio/video file to WAV using ffmpeg.

    Args:
        input_path: Path to the source audio or video file.
        output_path: Path to write the converted WAV file.

    Raises:
        RuntimeError: If ffmpeg is not installed or the conversion fails.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vn",              # strip video
        "-acodec", "pcm_s16le",
        "-ar", "16000",     # 16kHz mono — what WhisperX expects
        "-ac", "1",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found. Install it: sudo apt install ffmpeg"
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg conversion failed: {exc.stderr}")
    logger.info("Converted %s to WAV at %s", input_path, output_path)


def transcribe(
    audio_path: str,
    model_name: str = "base",
    language: str = "en",
    device: str = "cpu",
) -> list[str]:
    """Transcribe an audio file to a list of text lines using WhisperX.

    Args:
        audio_path: Path to a WAV audio file.
        model_name: WhisperX model size (tiny, base, small, medium, large-v2).
        language: Language code for transcription.
        device: "cpu" or "cuda".

    Returns:
        A list of transcribed text lines.

    Raises:
        FileNotFoundError: If audio_path does not exist.
        RuntimeError: If model loading or transcription fails.
    """
    import torch
    import whisperx

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested but unavailable — falling back to cpu")
        device = "cpu"

    t0 = time.perf_counter()
    try:
        model = whisperx.load_model(model_name, device, language=language)
    except Exception as exc:
        raise RuntimeError(f"Failed to load WhisperX model: {exc}") from exc
    logger.info("Model loaded in %.2fs", time.perf_counter() - t0)

    t1 = time.perf_counter()
    audio = whisperx.load_audio(str(path))
    result = model.transcribe(audio)
    logger.info("Transcription completed in %.2fs", time.perf_counter() - t1)

    lines = split_transcribed_lines(result.get("segments", []))

    logger.info("Transcribed %d lines", len(lines))
    return lines


def split_transcribed_lines(
    segments: list[dict[str, object]],
    max_words_per_line: int = 8,
) -> list[str]:
    """Split WhisperX segments into display-friendly lyric lines.

    WhisperX often returns long segments that are awkward to show as lyric
    subtitles. This helper first honors punctuation when present, then falls
    back to compact fixed-size word chunks to keep lines readable.
    """
    lines: list[str] = []

    for segment in segments:
        raw_text = str(segment.get("text", "")).strip()
        if not raw_text:
            continue

        pieces = _PUNCTUATION_BOUNDARY.split(raw_text)
        for piece in pieces:
            text = piece.strip()
            if not text:
                continue

            words = text.split()
            if len(words) <= max_words_per_line:
                lines.append(text)
                continue

            for idx in range(0, len(words), max_words_per_line):
                chunk = " ".join(words[idx:idx + max_words_per_line]).strip()
                if chunk:
                    lines.append(chunk)

    return lines


def run(
    input_path: str,
    output_path: str,
    model_name: str = "base",
    language: str = "en",
    device: str = "cpu",
) -> list[str]:
    """Full pipeline: convert input to WAV if needed, transcribe, save lyrics.

    Args:
        input_path: Path to the input audio or video file.
        output_path: Path to write the output lyrics text file.
        model_name: WhisperX model size.
        language: Language code.
        device: "cpu" or "cuda".

    Returns:
        The list of transcribed lyric lines.
    """
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Convert to WAV if not already
    if src.suffix.lower() == ".wav":
        wav_path = str(src)
        tmp_wav = None
    else:
        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_wav.close()
        wav_path = tmp_wav.name
        logger.info("Converting %s to WAV...", input_path)
        convert_to_wav(input_path, wav_path)

    try:
        lines = transcribe(wav_path, model_name, language, device)
    finally:
        # Clean up temp WAV if we created one
        if tmp_wav is not None:
            Path(tmp_wav.name).unlink(missing_ok=True)

    # Write output
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Saved %d lines to %s", len(lines), output_path)

    return lines


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video to a lyrics text file using WhisperX",
    )
    parser.add_argument(
        "input", help="Path to audio or video file (WAV, MP3, MP4, etc.)"
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Path to write the output lyrics.txt"
    )
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large-v2"],
        help="WhisperX model size (default: base)",
    )
    parser.add_argument(
        "--language", default="en", help="Language code (default: en)"
    )
    parser.add_argument(
        "--device", default="cpu", choices=["cpu", "cuda"],
        help="Device to run on (default: cpu)",
    )
    args = parser.parse_args()

    run(args.input, args.output, args.model, args.language, args.device)


if __name__ == "__main__":
    main()
