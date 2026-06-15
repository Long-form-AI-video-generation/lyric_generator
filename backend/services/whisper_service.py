
from __future__ import annotations

from pathlib import Path

from backend.core.config import settings
from backend.models.schemas import LyricLine, LyricsFile
from backend.services.media import probe_audio_duration, sanitize_filename


def _title_from_filename(path: Path) -> str:
    return sanitize_filename(path.stem, "Untitled Song").replace("-", " ").strip().title()


def transcribe_with_openai_whisper(audio_path: Path) -> LyricsFile:
   

    import torch
    import whisper

    device = settings.whisper_device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model = whisper.load_model(settings.whisper_model, device=device)
    result = model.transcribe(
        str(audio_path),
        language=settings.whisper_language,
        word_timestamps=True,
        verbose=False,
    )
    duration = probe_audio_duration(audio_path)
    lines: list[LyricLine] = []
    for index, segment in enumerate(result.get("segments", []), start=1):
        text = str(segment.get("text", "")).strip()
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start + 0.1))
        if text and end > start:
            lines.append(LyricLine(id=index, text=text, start=round(start, 3), end=round(end, 3)))

    if not lines:
        raise RuntimeError("Whisper did not detect any lyric segments.")

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=duration,
        lines=lines,
    )


def transcribe_with_faster_whisper(audio_path: Path) -> LyricsFile:
    

    from faster_whisper import WhisperModel

    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type="float16" if settings.whisper_device == "cuda" else "int8",
    )
    segments, info = model.transcribe(
        str(audio_path),
        language=settings.whisper_language,
        vad_filter=True,
    )
    duration = float(getattr(info, "duration", 0) or probe_audio_duration(audio_path))
    lines: list[LyricLine] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip()
        if text and segment.end > segment.start:
            lines.append(
                LyricLine(
                    id=index,
                    text=text,
                    start=round(float(segment.start), 3),
                    end=round(float(segment.end), 3),
                )
            )

    if not lines:
        raise RuntimeError("Whisper did not detect any lyric segments.")

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=round(duration, 3),
        lines=lines,
    )


def transcribe_audio(audio_path: Path) -> LyricsFile:
    
    if settings.whisper_backend == "faster-whisper":
        return transcribe_with_faster_whisper(audio_path)
    return transcribe_with_openai_whisper(audio_path)


def _strip(w: str) -> str:
    return "".join(c for c in w.lower() if c.isalnum())


def _words_to_lines(user_lines: list[str], aligned_words: list[dict], duration: float) -> list[LyricLine]:
    
    lines: list[LyricLine] = []
    word_cursor = 0
    for line_idx, user_line in enumerate(user_lines):
        n_words = len(user_line.split())
        batch = aligned_words[word_cursor : word_cursor + n_words] if n_words else []

        if batch:
            start_t = batch[0]["start"]
            end_t = batch[-1]["end"]
        else:
            prev_end = lines[-1].end if lines else 0.0
            start_t = prev_end
            end_t = min(prev_end + 2.0, duration)

        if lines and start_t <= lines[-1].end:
            start_t = lines[-1].end + 0.01
        if end_t <= start_t:
            end_t = start_t + 0.5

        lines.append(LyricLine(
            id=line_idx + 1,
            text=user_line,
            start=round(start_t, 3),
            end=round(end_t, 3),
        ))
        word_cursor += n_words
    return lines


def _align_with_whisperx(audio_path: Path, user_lines: list[str]) -> LyricsFile:
    
    import whisperx

    device = settings.whisper_device
    try:
        import torch
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
    except ImportError:
        device = "cpu"

    audio = whisperx.load_audio(str(audio_path))
    duration = probe_audio_duration(audio_path)
    lang = settings.whisper_language or "en"

    segments = [{"start": 0.0, "end": float(duration), "text": " ".join(user_lines)}]
    model_a, metadata = whisperx.load_align_model(language_code=lang, device=device)
    result = whisperx.align(segments, model_a, metadata, audio, device, return_char_alignments=False)

    aligned_words = [
        {"start": float(w["start"]), "end": float(w["end"])}
        for seg in result.get("segments", [])
        for w in seg.get("words", [])
        if "start" in w and "end" in w
    ]
    if not aligned_words:
        raise RuntimeError("WhisperX returned no word timestamps.")

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=duration,
        lines=_words_to_lines(user_lines, aligned_words, duration),
    )


def _align_with_whisper_fallback(audio_path: Path, user_lines: list[str]) -> LyricsFile:
    
    import difflib
    import torch
    import whisper

    device = settings.whisper_device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    prompt = " ".join(user_lines)[:224]
    model = whisper.load_model(settings.whisper_model, device=device)
    result = model.transcribe(
        str(audio_path),
        language=settings.whisper_language,
        word_timestamps=True,
        initial_prompt=prompt,
        verbose=False,
    )

    duration = probe_audio_duration(audio_path)

    whisper_words: list[dict] = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            clean = _strip(str(w.get("word", "")))
            start = float(w.get("start", segment.get("start", 0)))
            end = float(w.get("end", segment.get("end", 0)))
            if clean and end >= start:
                whisper_words.append({"clean": clean, "start": start, "end": end})

    if not whisper_words:
        raise RuntimeError("Whisper did not return word-level timestamps.")

   
    user_flat: list[tuple[int, str]] = []
    for line_idx, line in enumerate(user_lines):
        for word in line.split():
            c = _strip(word)
            if c:
                user_flat.append((line_idx, c))

    user_seq = [w for _, w in user_flat]
    whisper_seq = [w["clean"] for w in whisper_words]

    
    matcher = difflib.SequenceMatcher(None, user_seq, whisper_seq, autojunk=False)
    word_to_whisper: dict[int, int] = {}
    for u_start, wh_start, length in matcher.get_matching_blocks():
        for i in range(length):
            word_to_whisper[u_start + i] = wh_start + i

    
    for i in range(len(user_flat)):
        if i not in word_to_whisper:
            prev = next((j for j in range(i - 1, -1, -1) if j in word_to_whisper), None)
            nxt = next((j for j in range(i + 1, len(user_flat)) if j in word_to_whisper), None)
            if prev is not None:
                word_to_whisper[i] = word_to_whisper[prev]
            elif nxt is not None:
                word_to_whisper[i] = word_to_whisper[nxt]

    
    lines: list[LyricLine] = []
    word_offset = 0
    for line_idx, user_line in enumerate(user_lines):
        n_words = len([w for w in user_line.split() if _strip(w)])
        wh_indices = [
            word_to_whisper[i]
            for i in range(word_offset, word_offset + n_words)
            if i in word_to_whisper
        ]

        if wh_indices:
            start_t = whisper_words[min(wh_indices)]["start"]
            end_t = whisper_words[max(wh_indices)]["end"]
        else:
            prev_end = lines[-1].end if lines else 0.0
            start_t, end_t = prev_end, min(prev_end + 2.0, duration)

        if lines and start_t <= lines[-1].end:
            start_t = lines[-1].end + 0.01
        if end_t <= start_t:
            end_t = start_t + 0.5

        lines.append(LyricLine(
            id=line_idx + 1,
            text=user_line,
            start=round(start_t, 3),
            end=round(end_t, 3),
        ))
        word_offset += n_words

    return LyricsFile(
        title=_title_from_filename(audio_path),
        duration_seconds=duration,
        lines=lines,
    )


import re as _re


def _parse_lyrics_with_speakers(raw_text: str) -> tuple[list[str], list[str | None]]:
    
    _HEADER_RE = _re.compile(r"^\[([^\]]+)\]\s*$")
    _BOTH_WORDS = {"both", "all", "&"}

    current_speaker: str | None = None
    lyric_lines: list[str] = []
    speakers: list[str | None] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _HEADER_RE.match(line)
        if m:
            content = m.group(1)
            if ":" in content:
                
                artists_part = content.split(":", 1)[1].strip()
               
                artist_tokens = [
                    a.strip()
                    for a in _re.split(r",|&", artists_part)
                    if a.strip()
                ]
                
                if len(artist_tokens) == 1 and artist_tokens[0].lower() not in _BOTH_WORDS:
                    current_speaker = artist_tokens[0]
                else:
                    
                    current_speaker = None
            else:
                
                current_speaker = None
            continue

        lyric_lines.append(line)
        speakers.append(current_speaker)

    return lyric_lines, speakers


def align_lyrics_text(audio_path: Path, lyrics_text: str) -> LyricsFile:
    
    lyric_lines, speakers = _parse_lyrics_with_speakers(lyrics_text)
    if not lyric_lines:
        raise ValueError("Lyrics text must contain at least one non-empty line.")

    try:
        result = _align_with_whisperx(audio_path, lyric_lines)
    except Exception:
        result = _align_with_whisper_fallback(audio_path, lyric_lines)

    
    for line, spk in zip(result.lines, speakers):
        line.speaker = spk

    return result

