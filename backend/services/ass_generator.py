"""ASS subtitle generation for karaoke-style lyric burn-in."""

from __future__ import annotations

from pathlib import Path

from backend.models.schemas import LyricsFile


def ass_timestamp(seconds: float) -> str:
    """Format seconds as ASS h:mm:ss.cc timestamp."""

    centiseconds = max(0, int(round(seconds * 100)))
    cs = centiseconds % 100
    total_seconds = centiseconds // 100
    sec = total_seconds % 60
    total_minutes = total_seconds // 60
    minute = total_minutes % 60
    hour = total_minutes // 60
    return f"{hour}:{minute:02d}:{sec:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    """Escape user lyric text for ASS dialogue lines."""

    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def generate_ass(lyrics: LyricsFile, width: int, height: int) -> str:
    """Return an ASS subtitle document for centered lyric lines."""

    font_size = max(32, int(height * 0.05))
    shadow = max(2, int(height * 0.004))
    outline = max(2, int(height * 0.003))
    pos_x = width // 2
    pos_y = height // 2

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Montserrat,"
        f"{font_size},&H00FFFFFF,&H00FFFFFF,&H99000000,&H66000000,"
        f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},5,80,80,80,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for lyric in lyrics.lines:
        start = ass_timestamp(lyric.start)
        end = ass_timestamp(lyric.end)
        text = escape_ass_text(lyric.text)
        override = rf"{{\an5\pos({pos_x},{pos_y})\fad(200,300)}}"
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{override}{text}")

    return "\n".join(lines) + "\n"


def write_ass_file(path: Path, lyrics: LyricsFile, width: int, height: int) -> Path:
    """Write an ASS subtitle file and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_ass(lyrics, width, height), encoding="utf-8")
    return path

