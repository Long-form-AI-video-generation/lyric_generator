
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
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


_REFUSAL_PHRASES = (
    "i'm sorry",
    "i am sorry",
    "i can't assist",
    "i cannot assist",
    "i can't help",
    "i cannot help",
    "i'm unable",
    "i am unable",
    "unable to assist",
    "unable to help",
    "i apologize",
    "i won't",
    "i will not",
    "as an ai",
    "as a language model",
    "violates my",
    "against my",
    "i must decline",
)

_REFUSAL_USER_MSG = (
    "OpenAI declined to process this content. "
    "This can happen with certain lyrics due to content moderation. "
    "Try clicking Generate again — the model is sometimes inconsistent. "
    "If it keeps failing, try a different style description or rephrase your lyrics."
)


def _is_refusal(text: str) -> bool:
    
    lowered = text.lower()
    
    if lowered.lstrip().startswith("{"):
        return False
    return any(phrase in lowered for phrase in _REFUSAL_PHRASES)

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
      "speaker_name": "<artist name exactly as provided in the lyrics, or null if unknown/both>",
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
        "speaker_opacity": <0.0–1.0>,
        "co_speakers": ["<artist name>", ...]
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
- speaker_name: each input line is prefixed with [Speaker: Name] when known — \
copy that name exactly into speaker_name. For lines sung by multiple artists or \
with no speaker label, use null. When per-speaker styles are configured, apply \
that speaker's font/color/animation/position_y_pct to their lines.
- co_speakers: when a line is sung by multiple artists together (chorus, hook, \
duet bridge), list ALL their names in co_speakers even though speaker_name is null. \
Only include artists that have photos available (listed in the artist roster). \
For solo lines or lines with no known artists, set co_speakers to [].
- Artist photos and distortion: when artist photos are available, you MUST decide \
the best distortion for each artist based on their genre, energy, and the song's mood. \
Use chromatic_aberration for high-energy/glitch aesthetics, pixel_sort for \
electronic/intense sections, datamosh for chaotic/climactic moments, and none for \
clean/emotional moments. Set speaker_opacity between 0.3–0.7 for solo lines.
- For co_speakers lines (multiple artists), set speaker_opacity to 0.6 so the \
composite of their photos fills the background dramatically.
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
    openai_api_key: str | None = None,
) -> str:
    import httpx
    import openai

    api_key = openai_api_key or settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "No OpenAI API key available. "
            "Please enter your key on the API Key page"
        )

    proxy_url = settings.openai_proxy_url or None
    http_client = httpx.Client(proxy=proxy_url, timeout=60.0) if proxy_url else None
    client = openai.OpenAI(api_key=api_key, http_client=http_client)

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
    try:
        for attempt in range(1, 4):
            response = client.chat.completions.create(
                model=settings.art_direction_model_openai,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content},
                ],
                max_tokens=4096,
            )
            choice = response.choices[0]
            content = (choice.message.content or "").strip()

            refusal = getattr(choice.message, "refusal", None)
            _LOG.info(
                "OpenAI %s attempt %d/3: finish_reason=%r content_len=%d refusal=%r",
                attempt_label, attempt, choice.finish_reason, len(content), refusal,
            )

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

            if content:
                if _is_refusal(content):
                    _LOG.warning(
                        "OpenAI %s attempt %d/3: soft refusal detected — retrying. "
                        "Content preview: %r",
                        attempt_label, attempt, content[:120],
                    )
                    last_err = RuntimeError(_REFUSAL_USER_MSG)
                    time.sleep(1.0)
                    continue
                return content

            last_err = RuntimeError(
                f"OpenAI empty response on attempt {attempt}/3 "
                f"(finish_reason={finish_reason!r})"
            )
    finally:
        if http_client:
            http_client.close()

    if last_err and _REFUSAL_USER_MSG in str(last_err):
        raise RuntimeError(_REFUSAL_USER_MSG) from last_err

    raise RuntimeError(
        "OpenAI returned empty responses on all 3 attempts for this lyric chunk. "
        "Please try again — if it keeps failing, switch to a different style prompt."
    ) from last_err


def _call_anthropic(
    lyrics_text: str,
    background_image_b64: str | None = None,
) -> str:
    import anthropic  

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

   
    if _is_refusal(raw):
        raise RuntimeError(_REFUSAL_USER_MSG)

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
                f"  \"{name}\": font={style.font}, color={style.text_color}, "
                f"animation={style.animation}, font_size_pct={style.font_size_pct}, "
                f"position_y_pct={style.position_y_pct}"
                + (f", has_photo=true" if style.image_dir else "")
            )
        parts.append(
            "Per-speaker styles — MUST apply these exactly when speaker_name matches "
            "(match case-insensitively):\n" + "\n".join(rows)
        )

    if song_config.section_overrides:
        rows2: list[str] = []
        for override in song_config.section_overrides:
            rows2.append(f"  [{', '.join(override.sections)}]: {override.style}")
        parts.append("Section style overrides:\n" + "\n".join(rows2))

    if song_config.generate_ai_backgrounds:
        parts.append(
            "AI background generation is enabled, populate image_prompt for every "
            "line with a concise Stable Diffusion / FLUX prompt for that line's mood."
        )

    return "\n\n".join(parts)


def run_art_direction(
    lyrics: LyricsFile,
    style_prompt: str,
    *,
    background_image_b64: str | None = None,
    song_config: SongConfig | None = None,
    openai_api_key: str | None = None,
    on_progress: Callable[[int], None] | None = None,
    artist_names: list[str] | None = None,
) -> Storyboard:
    

    config_context = _build_song_config_context(song_config)
    provider = settings.llm_provider.lower()

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
            f"[{ln.id}] ({ln.start:.2f}s–{ln.end:.2f}s)"
            + (f" [Speaker: {ln.speaker}]" if ln.speaker else "")
            + f"  {ln.text}"
            for ln in chunk
        )

        chunk_header = (
            f"Chunk {chunk_idx + 1} of {n_chunks} — direct ONLY these {len(chunk)} lines.\n"
            if n_chunks > 1
            else ""
        )

        artist_roster = ""
        if artist_names:
            roster_list = ", ".join(artist_names)
            artist_roster = (
                f"\nArtist roster (these artists have photos available): {roster_list}\n"
                f"Use this roster to populate co_speakers on lines sung together, "
                f"and to decide distortion style per artist.\n"
            )

        user_message = (
            f"Song title: {lyrics.title}\n"
            f"Style brief: {style_prompt}\n"
            + (f"\n{config_context}\n" if config_context else "")
            + artist_roster
            + f"\n{chunk_header}"
            + f"Lyrics:\n{lyrics_block}"
        )

        
        bg = background_image_b64 if chunk_idx == 0 else None

        label = f"chunk {chunk_idx + 1}/{n_chunks}"
        if provider == "anthropic":
            raw = _call_anthropic(user_message, bg)
        else:
            raw = _call_openai(user_message, bg, attempt_label=label, openai_api_key=openai_api_key)

        chunk_lines_result = _parse_chunk(raw, chunk)
        all_raw_lines.extend(chunk_lines_result)
        _LOG.info("Chunk %d/%d: got %d directions", chunk_idx + 1, n_chunks, len(chunk_lines_result))
        if on_progress:
            on_progress(round((chunk_idx + 1) / n_chunks * 100))

    return _build_storyboard(
        {"title": lyrics.title, "lines": all_raw_lines},
        lyrics,
        style_prompt,
        song_config=song_config,
    )


# ---------------------------------------------------------------------------
# Storyboard builder
# ---------------------------------------------------------------------------

def _build_storyboard(
    payload: dict[str, Any],
    lyrics: LyricsFile,
    style_prompt: str,
    *,
    song_config: "SongConfig | None" = None,
) -> Storyboard:
    valid_ids = {ln.id for ln in lyrics.lines}
    lyrics_by_id: dict[int, LyricLine] = {ln.id: ln for ln in lyrics.lines}

   
    speaker_styles: dict[str, Any] = {}
    if song_config and song_config.speakers:
        for name, style in song_config.speakers.items():
            speaker_styles[name.lower()] = style

   
    known_artists: dict[str, str] = {}
    if song_config and song_config.speakers:
        for name in song_config.speakers:
            known_artists[name.lower()] = name

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

        
        llm_speaker = item.get("speaker_name") or None
        source_line = lyrics_by_id.get(line_id)
        resolved_speaker = llm_speaker or (source_line.speaker if source_line else None)

        
        font       = item.get("font", "default")
        text_color = item.get("text_color", "#FFFFFF")
        font_size  = max(5.0, float(item.get("font_size_pct", 6.5)))
        pos_x      = float(pos.get("x_pct", 50))
        pos_y      = float(pos.get("y_pct", 50))

       
        if resolved_speaker:
            sp_style = speaker_styles.get(resolved_speaker.lower())
            if sp_style:
                if sp_style.font and sp_style.font != "default":
                    font = sp_style.font
                if sp_style.text_color:
                    text_color = sp_style.text_color
                try:
                    animation = AnimationStyle(sp_style.animation)
                except ValueError:
                    pass
                font_size = float(sp_style.font_size_pct)
                pos_y     = float(sp_style.position_y_pct)

        
        speaker_opacity = float(bg.get("speaker_opacity", 0.0))
        if resolved_speaker and speaker_styles.get(resolved_speaker.lower()) and speaker_opacity == 0.0:
            speaker_opacity = 0.5

        
        raw_co = bg.get("co_speakers") or []
        co_speakers: list[str] = []
        if isinstance(raw_co, list):
            for name in raw_co:
                if isinstance(name, str) and name.strip():
                    canonical = known_artists.get(name.strip().lower())
                    if canonical:
                        co_speakers.append(canonical)

        
        if not co_speakers and resolved_speaker is None and len(known_artists) >= 2:
            co_speakers = list(known_artists.values())

        
        if co_speakers and speaker_opacity == 0.0:
            speaker_opacity = 0.6

        parsed_lines.append(
            LineDirection(
                line_id=line_id,
                speaker_name=resolved_speaker,
                font=font,
                text_color=text_color,
                font_size_pct=font_size,
                position=TextPosition(x_pct=pos_x, y_pct=pos_y),
                animation=animation,
                background=BackgroundTreatment(
                    image_index=int(bg.get("image_index", 0)),
                    filter=bg.get("filter", "none"),
                    speaker_distortion=bg.get("speaker_distortion", "none"),
                    speaker_opacity=speaker_opacity,
                    co_speakers=co_speakers,
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
