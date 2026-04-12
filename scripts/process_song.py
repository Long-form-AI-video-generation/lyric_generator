"""
End-to-end song processing: convert to WAV, transcribe lyrics, align timestamps.

Takes a single audio or video file and produces all outputs in the same
directory as the input file:
  - audio.wav     (converted audio for alignment)
  - lyrics.txt    (transcribed lyrics)
  - lyrics.json   (aligned lyrics with word-level timestamps)

Usage:
    python scripts/process_song.py songs/song01/mysong.mp4
    python scripts/process_song.py songs/song01/mysong.mp4 --model small --device cuda
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on the Python path so both pipeline and scripts imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)


def process_song(
    input_path: str,
    model_name: str = "base",
    language: str = "en",
    device: str = "cpu",
) -> None:
    """Run the full pipeline on a single audio/video file.

    Steps:
        1. Convert input to WAV (saved as audio.wav in the same directory)
        2. Transcribe audio to lyrics text (saved as lyrics.txt)
        3. Align lyrics against audio (saved as lyrics.json)
        4. Print correction report for low-confidence lines

    All outputs are written to the same directory as the input file.

    Args:
        input_path: Path to the input audio or video file.
        model_name: WhisperX model size (tiny, base, small, medium, large-v2).
        language: Language code for transcription.
        device: "cpu" or "cuda".

    Raises:
        FileNotFoundError: If input_path does not exist.
    """
    from transcribe import convert_to_wav, transcribe
    from pipeline.align import run_alignment

    src = Path(input_path)
    if not src.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    song_dir = src.parent
    wav_path = song_dir / "audio.wav"
    lyrics_path = song_dir / "lyrics.txt"
    json_path = song_dir / "lyrics.json"

    # --- Step 1: Convert to WAV ---
    if src.suffix.lower() == ".wav":
        # If already WAV, just copy/use in place
        wav_path = src
        logger.info("Input is already WAV: %s", wav_path)
    else:
        logger.info("Step 1/3: Converting %s to WAV...", src.name)
        convert_to_wav(str(src), str(wav_path))
        logger.info("Saved WAV to %s", wav_path)

    # --- Step 2: Transcribe to lyrics.txt ---
    logger.info("Step 2/3: Transcribing audio to lyrics...")
    lines = transcribe(str(wav_path), model_name, language, device)

    if not lines:
        logger.error("Transcription produced no lines — is the audio silent or instrumental?")
        sys.exit(1)

    lyrics_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Saved %d lyric lines to %s", len(lines), lyrics_path)

    # --- Step 3: Align lyrics to get timestamps ---
    logger.info("Step 3/3: Running forced alignment...")
    lyrics_text = lyrics_path.read_text(encoding="utf-8")
    run_alignment(
        audio_path=str(wav_path),
        lyrics_text=lyrics_text,
        output_path=str(json_path),
        device=device,
    )

    logger.info("Done! Outputs in %s/", song_dir)
    logger.info("  audio.wav   — converted audio")
    logger.info("  lyrics.txt  — transcribed lyrics")
    logger.info("  lyrics.json — aligned lyrics with timestamps")
    logger.info("")
    logger.info("Review low-confidence lines above, then optionally run:")
    logger.info("  python scripts/correct_timestamps.py %s", json_path)


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Process a song end-to-end: convert, transcribe, and align",
    )
    parser.add_argument(
        "input",
        help="Path to audio or video file (MP4, MP3, WAV, etc.)",
    )
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large-v2"],
        help="WhisperX model size (default: base)",
    )
    parser.add_argument(
        "--language", default="en",
        help="Language code (default: en)",
    )
    parser.add_argument(
        "--device", default="cpu",
        choices=["cpu", "cuda"],
        help="Device to run on (default: cpu)",
    )
    args = parser.parse_args()

    process_song(args.input, args.model, args.language, args.device)


if __name__ == "__main__":
    main()
