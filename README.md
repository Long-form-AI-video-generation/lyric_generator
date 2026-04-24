# Lyric Video Pipeline

Automated lyrics-to-audio alignment pipeline built on WhisperX. Transcribes audio, force-aligns the vocals, groups aligned words into display-friendly lyric lines based on timing pauses, and produces a structured JSON file that downstream video rendering tools can consume.

## Installation

1. **Install system dependencies** (ffmpeg is required by WhisperX):

   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg

   # macOS
   brew install ffmpeg
   ```

2. **Create a virtual environment and install Python packages:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Copy the environment file and add your HuggingFace token** (needed for WhisperX model downloads):

   ```bash
   cp .env.example .env
   # Edit .env and set HF_TOKEN
   ```

## Preparing a Song Folder

Create a directory under `songs/` for each track:

```
songs/
  track01/
    audio.wav      # WAV audio file
    lyrics.txt     # Raw lyrics, one line per line
```

The lyrics file should contain one lyric line per text line. Blank lines are ignored.

## Running Alignment

```bash
python -m pipeline.align \
  --audio songs/track01/audio.wav \
  --lyrics songs/track01/lyrics.txt \
  --output songs/track01/lyrics.json
```

Optional: pass `--device cuda` to use GPU acceleration.

This produces a `lyrics.json` file with one timestamped lyric line per entry and prints a correction report highlighting low-confidence lines.

## Correcting Timestamps

Use the interactive correction helper to manually fix timestamps:

```bash
python scripts/correct_timestamps.py songs/track01/lyrics.json
```

For each line you can press ENTER to keep the current timestamps, or type `start,end` (e.g. `32.4,34.8`) to override.

## Running Tests

```bash
pytest tests/
```

## Lyric Visualizer

There is also a lightweight frontend preview app under `visualizer/` for reviewing a song against the generated `lyrics.json`.

Start it locally with:

```bash
python -m visualizer.server
```

Then open `http://127.0.0.1:8000` in your browser and upload:

- the audio file you want to preview
- the generated `lyrics.json`

The app will play the song, highlight the active lyric line, and show each line exactly as stored in the uploaded JSON.

## Lyrics JSON Schema

The output JSON is an array of line objects:

| Field        | Type          | Description                                                             |
|-------------|---------------|-------------------------------------------------------------------------|
| `line_index` | `int`         | Zero-based sequential index                                             |
| `line`       | `str`         | The full reconstructed lyric line                                       |
| `start`      | `float`       | Start time in seconds from beginning of audio                           |
| `end`        | `float`       | End time in seconds from beginning of audio                             |
| `confidence` | `float`       | Average of word-level confidence scores (0.0-1.0), or `-1.0` if unavailable |

Example:

```json
[
  {
    "line_index": 0,
    "line": "I keep waiting for the signal",
    "start": 32.4,
    "end": 34.8,
    "confidence": 0.94
  }
]
```

`lyrics.json` is phrase-based: line breaks are driven primarily by timing gaps in the aligned vocals, with readability limits as a fallback. `process_song.py` also rewrites `lyrics.txt` from those final phrase lines so both outputs stay in sync.

## Note on WhisperX Accuracy

WhisperX is optimized for spoken language and may produce less accurate transcriptions for sung vocals, especially with:

- Heavy vocal effects (reverb, autotune, distortion)
- Overlapping vocals or harmonies
- Rapid or mumbled delivery
- Non-English words mixed into English lyrics

The pipeline uses fuzzy matching (`thefuzz`) to align WhisperX output back to your original lyrics, which compensates for minor transcription differences. Lines with confidence below 0.75 are flagged in the correction report for manual review. Use `scripts/correct_timestamps.py` to fix any misaligned timestamps.
