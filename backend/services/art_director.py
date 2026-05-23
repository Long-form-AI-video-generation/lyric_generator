
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from backend.core.config import settings
from backend.models.schemas import (
    AnimationStyle,
    BackgroundTreatment,
    LineDirection,
    LyricLine,
    LyricsFile,
    SongConfig,
    Storyboard,
    TextPosition,
)

_LOG = logging.getLogger(__name__)


_CHUNK_SIZE = 20

_SYSTEM_PROMPT = """\
You are an art director for a lyric video production company.
Given a batch of song lyrics, a style description, and (optionally) the actual \
background image the lyrics will appear over, you create a detailed visual \
storyboard — one entry per lyric line.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown fences, \
no commentary, no extra keys outside the schema below.

Required JSON schema:
{
  "lines": [
    {
      "line_id": <integer matching the supplied id>,
      "font": "<one of: Impact, AvenirNext, Bebas, Montserrat, CourierNew, \
Georgia, Helvetica, SourceCodePro, TrajanPro, FuturaBold>",
      "text_color": "<CSS hex — must contrast clearly against the background>",
      "font_size_pct": <float 5.0–12.0>,
      "position": { "x_pct": <0–100>, "y_pct": <20–80> },
      "animation": "<one of: fade-in, typewriter, glitch, slide-from-left, \
slide-from-right, zoom-in, pop>",
      "background": {
        "image_index": <integer>,
        "filter": "<one of: none, blur, desaturate, color_shift, glitch, vhs>",
        "speaker_distortion": "<one of: none, chromatic_aberration, pixel_sort, datamosh>",
        "speaker_opacity": <0.0–1.0>
      },
      "transition": "<one of: cut, fade, slide>",
      "image_prompt": "<Stable Diffusion prompt or null>"
    }
  ]
}

Creative rules:
- If a background image is provided, inspect its dominant colors and brightness \
carefully, then choose text colors that are clearly READABLE against it.
- Vary fonts, colors, positions, and animations to match the emotional arc.
- Glitch/distortion effects are for intense moments only.
- y_pct must stay between 20–80.  font_size_pct must be at least 5.0.
- Every line_id must exactly match one from the input.
- image_prompt: choose ONLY 5–8 distinct prompts for the ENTIRE song that \
represent its main visual themes (e.g. setting, mood, key imagery). \
Reuse the SAME prompt string across many lines — the filters, distortions, \
animations, and transitions will create visual variety without needing a \
new image for every line. Do NOT write a unique prompt for every line.
"""

def _call_openai(
    lyrics_text: str,
    background_image_b64: str | None = None,
    *,
    attempt_label: str = "",
) -> str:
    import openai  # type: ignore[import-untyped]

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            "Set it in your .env file."
        )

    client = openai.OpenAI(api_key=api_key)

    if background_image_b64:
        user_content: Any = [
            {
                "type": "text",
                "text": (
                    "The image below is the background the lyrics will appear over. "
                    "Examine its colors and brightness, then pick text colors that are "
                    "clearly readable against it.\n\n" + lyrics_text
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{background_image_b64}",
                    "detail": "low",
                },
            },
        ]
    else:
        user_content = lyrics_text

    last_err: Exception | None = None
    for attempt in range(1, 4):
        response = client.chat.completions.create(
            model=settings.art_direction_model_openai,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            max_tokens=4096,  # safe cap — each chunk is ≤20 lines (~2 k tokens max)
        )
        choice = response.choices[0]
        content = (choice.message.content or "").strip()

        # Log the outcome so the server console shows useful diagnostics
        refusal = getattr(choice.message, "refusal", None)
        _LOG.info(
            "OpenAI %s attempt %d/3: finish_reason=%r content_len=%d refusal=%r",
            attempt_label, attempt, choice.finish_reason, len(content), refusal,
        )

        if content:
            return content

        if refusal:
            raise RuntimeError(
                f"OpenAI refused to generate the storyboard: {refusal}. "
                "Try rephrasing your style description."
            )

        finish_reason = choice.finish_reason or "unknown"
        if finish_reason == "length":
            raise RuntimeError(
                "OpenAI cut the storyboard short. "
                "This should not happen with chunked lyrics — please report this."
            )
        if finish_reason == "content_filter":
            raise RuntimeError(
                "OpenAI filtered the response. Try a different style description."
            )

        last_err = RuntimeError(
            f"OpenAI empty response on attempt {attempt}/3 "
            f"(finish_reason={finish_reason!r})"
        )

    raise RuntimeError(
        "OpenAI returned empty responses on all 3 attempts for this lyric chunk. "
        "Please try again — if it keeps failing, switch to a different style prompt."
    ) from last_err


def _call_anthropic(
    lyrics_text: str,
    background_image_b64: str | None = None,
) -> str:
    import anthropic  # type: ignore[import-untyped]

    api_key = settings.anthropic_api_key
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in your .env file."
        )

    client = anthropic.Anthropic(api_key=api_key)

    if background_image_b64:
        user_content: Any = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": background_image_b64,
                },
            },
            {
                "type": "text",
                "text": (
                    "The image above is the background the lyrics will appear over. "
                    "Use its colors to pick readable text colors.\n\n" + lyrics_text
                ),
            },
        ]
    else:
        user_content = lyrics_text

    response = client.messages.create(
        model=settings.art_direction_model_anthropic,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    content = response.content[0].text.strip() if response.content else ""
    if not content:
        stop_reason = getattr(response, "stop_reason", "unknown")
        raise RuntimeError(
            f"Anthropic returned an empty response (stop_reason={stop_reason!r}). "
            + (
                "The output was truncated — this should not happen with chunked lyrics."
                if stop_reason == "max_tokens"
                else "Please try again."
            )
        )
    return content


def _parse_chunk(raw: str, chunk_lines: list[LyricLine]) -> list[dict[str, Any]]:
    """Strip markdown fences, fix trailing commas, and parse the JSON.

    Returns the ``lines`` list from the parsed payload.
    """
   
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        body = parts[1]
        if body.startswith("json"):
            body = body[4:]
        raw = body.rsplit("```", 1)[0].strip()

   
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    if not raw.strip():
        ids = [ln.id for ln in chunk_lines]
        raise RuntimeError(
            f"The model returned an empty response for lines {ids}. "
            "Please try regenerating."
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json  # type: ignore[import-untyped]
            repaired = repair_json(raw)
            if not repaired or repaired in ("null", '""', "{}"):
                raise ValueError("repair produced empty/trivial output")
            payload = json.loads(repaired)
        except Exception as exc:
            preview = raw[:300].replace("\n", " ")
            raise RuntimeError(
                f"Could not parse the model's JSON response: {exc}. "
                f"Raw preview: {preview!r}"
            ) from exc

    lines = payload.get("lines", [])
    if not isinstance(lines, list):
        raise RuntimeError(
            "The model returned a 'lines' field that is not a list. "
            "Please try regenerating."
        )
    return lines


def _build_song_config_context(song_config: SongConfig | None) -> str:
    if not song_config:
        return ""

    parts: list[str] = []

    if song_config.global_style:
        parts.append(f"Global style override: {song_config.global_style}")

    if song_config.speakers:
        rows: list[str] = []
        for name, style in song_config.speakers.items():
            rows.append(
                f"  {name}: font={style.font}, color={style.text_color}, "
                f"animation={style.animation}, font_size_pct={style.font_size_pct}, "
                f"position_y_pct={style.position_y_pct}"
            )
        parts.append("Per-speaker styles:\n" + "\n".join(rows))

    if song_config.section_overrides:
        rows2: list[str] = []
        for override in song_config.section_overrides:
            rows2.append(f"  [{', '.join(override.sections)}]: {override.style}")
        parts.append("Section style overrides:\n" + "\n".join(rows2))

    if song_config.generate_ai_backgrounds:
        parts.append(
            "AI background generation is enabled — populate image_prompt for every "
            "line with a concise Stable Diffusion / FLUX prompt for that line's mood."
        )

    return "\n\n".join(parts)


def run_art_direction(
    lyrics: LyricsFile,
    style_prompt: str,
    *,
    background_image_b64: str | None = None,
    song_config: SongConfig | None = None,
) -> Storyboard:
    """Generate a storyboard by calling the LLM in chunks of _CHUNK_SIZE lines."""

    config_context = _build_song_config_context(song_config)
    provider = settings.llm_provider.lower()

    # Split lyrics into chunks
    lines = lyrics.lines
    chunks: list[list[LyricLine]] = [
        lines[i : i + _CHUNK_SIZE] for i in range(0, len(lines), _CHUNK_SIZE)
    ]
    n_chunks = len(chunks)
    _LOG.info(
        "Art direction: %d lines split into %d chunk(s) of ≤%d (provider=%s model=%s)",
        len(lines), n_chunks, _CHUNK_SIZE,
        provider,
        settings.art_direction_model_anthropic if provider == "anthropic"
        else settings.art_direction_model_openai,
    )

    all_raw_lines: list[dict[str, Any]] = []

    for chunk_idx, chunk in enumerate(chunks):
        lyrics_block = "\n".join(
            f"[{ln.id}] ({ln.start:.2f}s–{ln.end:.2f}s)  {ln.text}"
            for ln in chunk
        )

        chunk_header = (
            f"Chunk {chunk_idx + 1} of {n_chunks} — direct ONLY these {len(chunk)} lines.\n"
            if n_chunks > 1
            else ""
        )

        user_message = (
            f"Song title: {lyrics.title}\n"
            f"Style brief: {style_prompt}\n"
            + (f"\n{config_context}\n" if config_context else "")
            + f"\n{chunk_header}"
            + f"Lyrics:\n{lyrics_block}"
        )

        # Send the background image only with the first chunk (colour reference)
        bg = background_image_b64 if chunk_idx == 0 else None

        label = f"chunk {chunk_idx + 1}/{n_chunks}"
        if provider == "anthropic":
            raw = _call_anthropic(user_message, bg)
        else:
            raw = _call_openai(user_message, bg, attempt_label=label)

        chunk_lines_result = _parse_chunk(raw, chunk)
        all_raw_lines.extend(chunk_lines_result)
        _LOG.info("Chunk %d/%d: got %d directions", chunk_idx + 1, n_chunks, len(chunk_lines_result))

    return _build_storyboard(
        {"title": lyrics.title, "lines": all_raw_lines},
        lyrics,
        style_prompt,
    )


# ---------------------------------------------------------------------------
# Storyboard builder
# ---------------------------------------------------------------------------

def _build_storyboard(
    payload: dict[str, Any],
    lyrics: LyricsFile,
    style_prompt: str,
) -> Storyboard:
    valid_ids = {ln.id for ln in lyrics.lines}
    parsed_lines: list[LineDirection] = []

    for item in payload.get("lines", []):
        try:
            line_id = int(item.get("line_id", 0))
        except (TypeError, ValueError):
            continue
        if line_id not in valid_ids:
            continue

        pos = item.get("position") or {}
        bg  = item.get("background") or {}

        anim_raw = item.get("animation", "fade-in")
        try:
            animation = AnimationStyle(anim_raw)
        except ValueError:
            animation = AnimationStyle.fade_in

        parsed_lines.append(
            LineDirection(
                line_id=line_id,
                font=item.get("font", "default"),
                text_color=item.get("text_color", "#FFFFFF"),
                font_size_pct=max(5.0, float(item.get("font_size_pct", 6.5))),
                position=TextPosition(
                    x_pct=float(pos.get("x_pct", 50)),
                    y_pct=float(pos.get("y_pct", 50)),
                ),
                animation=animation,
                background=BackgroundTreatment(
                    image_index=int(bg.get("image_index", 0)),
                    filter=bg.get("filter", "none"),
                    speaker_distortion=bg.get("speaker_distortion", "none"),
                    speaker_opacity=float(bg.get("speaker_opacity", 0.0)),
                ),
                transition=item.get("transition", "cut"),
                image_prompt=item.get("image_prompt") or None,
            )
        )

    return Storyboard(
        title=payload.get("title", lyrics.title),
        style_prompt=style_prompt,
        lines=parsed_lines,
        created_at=time.time(),
    )
