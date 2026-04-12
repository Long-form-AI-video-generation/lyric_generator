"""
Interactive CLI tool for manually correcting lyrics JSON timestamps.

Walks through each line in a lyrics.json file and lets the user accept
or override the start/end timestamps.  Saves corrections back to the
same file when finished.

Usage:
    python scripts/correct_timestamps.py songs/track01/lyrics.json
"""

import argparse
import json
import os
import sys
from typing import Any


def load_lyrics_json(path: str) -> list[dict[str, Any]]:
    """Load and return a lyrics JSON list from *path*.

    Args:
        path: Path to the lyrics.json file.

    Returns:
        The parsed list of line dicts.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_lyrics_json(path: str, data: list[dict[str, Any]]) -> None:
    """Write *data* back to *path* as formatted JSON.

    Args:
        path: Destination file path.
        data: The list of line dicts to persist.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_correction(path: str) -> None:
    """Run the interactive correction loop for the given lyrics JSON file.

    For each line, displays the current timestamps and text, then prompts
    the user to keep or update the start/end values.

    Args:
        path: Path to the lyrics.json file to correct.
    """
    if not os.path.exists(path):
        print(f"Error: file not found: {path}")
        sys.exit(1)

    data = load_lyrics_json(path)
    print(f"\nLoaded {len(data)} lines from {path}\n")
    print("For each line, press ENTER to keep current timestamps,")
    print("or type new start,end (e.g. 32.4,34.8) to override.\n")
    print("-" * 70)

    changed = 0
    for entry in data:
        idx = entry["line_index"]
        start = entry["start"]
        end = entry["end"]
        line = entry["line"]
        conf = entry["confidence"]

        flag = ""
        if 0 <= conf < 0.75:
            flag = " [LOW CONFIDENCE]"

        print(f"\n  [{idx:3d}] {line}")
        print(f"        start={start:.3f}  end={end:.3f}  conf={conf:.2f}{flag}")

        user_input = input("        New start,end or ENTER to keep: ").strip()

        if not user_input:
            continue

        parts = user_input.split(",")
        if len(parts) != 2:
            print("        Invalid format — skipping (expected: start,end)")
            continue

        try:
            new_start = float(parts[0].strip())
            new_end = float(parts[1].strip())
        except ValueError:
            print("        Could not parse as floats — skipping")
            continue

        entry["start"] = round(new_start, 3)
        entry["end"] = round(new_end, 3)
        changed += 1
        print(f"        Updated to start={new_start:.3f}, end={new_end:.3f}")

    print(f"\n{'-' * 70}")
    print(f"Corrected {changed} line(s).")

    if changed > 0:
        save_lyrics_json(path, data)
        print(f"Saved to {path}")
    else:
        print("No changes made.")


def main() -> None:
    """Parse arguments and run the correction tool."""
    parser = argparse.ArgumentParser(
        description="Interactively correct timestamps in a lyrics JSON file",
    )
    parser.add_argument(
        "lyrics_json",
        help="Path to the lyrics.json file to correct",
    )
    args = parser.parse_args()
    run_correction(args.lyrics_json)


if __name__ == "__main__":
    main()
