

from __future__ import annotations

import json
import re
import time

from backend.core.config import settings
from backend.models.schemas import (
    AnimationStyle,
    BackgroundTreatment,
    LineDirection,
    LyricsFile,
    Storyboard,
    TextPosition,
)

# ---------------------------------------------------------------------------
# Shared system prompt (same for both providers)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an art director for a lyric video production company.
Given a song's lyrics, a style description, and (optionally) the actual \
background image the lyrics will appear over, you create a detailed visual \
storyboard — one entry per lyric line.

IMPORTANT: Respond with ONLY a valid JSON object. No markdown fences, \
no commentary, no extra keys outside the schema below.

Required JSON schema:
{
  "title": "<song title>",
  "lines": [
    {
      "line_id": <integer — must match the id in the supplied lyrics>,
      "font": "<one of: Impact, AvenirNext, Bebas, Montserrat, CourierNew, \
Georgia, Helvetica, SourceCodePro, TrajanPro, FuturaBold>",
      "text_color": "<CSS hex color — MUST contrast clearly against the background>",
      "font_size_pct": <float 5.0–12.0 — size as % of frame height>,
      "position": { "x_pct": <0–100>, "y_pct": <20–80> },
      "animation": "<one of: fade-in, typewriter, glitch, slide-from-left, \
slide-from-right, zoom-in, pop>",
      "background": {
        "image_index": <integer — which background image to use, cycling \
through the asset pool>,
        "filter": "<one of: none, blur, desaturate, color_shift, glitch, vhs>",
        "speaker_distortion": "<one of: none, chromatic_aberration, \
pixel_sort, datamosh>",
        "speaker_opacity": <0.0–1.0>
      },
      "transition": "<one of: cut, fade, slide>",
      "image_prompt": "<short Stable Diffusion / FLUX prompt for an \
AI-generated background, or null>"
    }
  ]
}

Creative rules:
- If a background image is provided, inspect it carefully and choose text \
colors that are READABLE against those specific tones. \
Dark backgrounds need light or vivid text. Light backgrounds need dark text.
- Vary fonts, colors, positions, and animations to match the emotional arc.
- Use glitch/distortion effects sparingly — save them for intense moments.
- Keep y_pct between 20–80 so text is never clipped at the edges.
- font_size_pct must be at least 5.0; prefer 6–9 for most lines.
- Every line_id in the output must exactly match one from the input.
"""

def _call_openai(lyrics_text: str, background_image_b64: str | None = None) -> str:
    """Call the OpenAI Chat Completions API and return the raw response text."""
    import openai

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            "Set it in your environment or .env file."
        )

    client = openai.OpenAI(api_key=api_key)

  
    if background_image_b64:
        user_content = [
            {
                "type": "text",
                "text": (
                    "Here is the background image the lyrics will appear over. "
                    "Examine its dominant colors and brightness carefully, then "
                    "choose text colors that are clearly readable against it.\n\n"
                    + lyrics_text
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{background_image_b64}",
                    "detail": "low",  # low is enough for color / brightness analysis
                },
            },
        ]
    else:
        user_content = lyrics_text

    response = client.chat.completions.create(
        model=settings.art_direction_model_openai,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=16384,
    )
    return response.choices[0].message.content or ""


def _call_anthropic(lyrics_text: str, background_image_b64: str | None = None) -> str:
    
    import anthropic

    api_key = settings.anthropic_api_key
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in your environment or .env file."
        )

    client = anthropic.Anthropic(api_key=api_key)

    if background_image_b64:
        user_content = [
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
                    "Use it to pick contrasting, readable text colors.\n\n"
                    + lyrics_text
                ),
            },
        ]
    else:
        user_content = lyrics_text

    response = client.messages.create(
        model=settings.art_direction_model_anthropic,
        max_tokens=8192,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text.strip()


def run_art_direction(
    lyrics: LyricsFile,
    style_prompt: str,
    *,
    background_image_b64: str | None = None,
) -> Storyboard:
    

    lyrics_block = "\n".join(
        f"[{ln.id}] ({ln.start:.2f}s–{ln.end:.2f}s)  {ln.text}"
        for ln in lyrics.lines
    )
    user_message = (
        f"Song title: {lyrics.title}\n"
        f"Style brief: {style_prompt}\n\n"
        f"Lyrics:\n{lyrics_block}"
    )

    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        raw = _call_anthropic(user_message, background_image_b64)
    else:
        raw = _call_openai(user_message, background_image_b64)

    if raw.startswith("```"):
        parts = raw.split("```", 2)
        body = parts[1]
        if body.startswith("json"):
            body = body[4:]
        raw = body.rsplit("```", 1)[0].strip()

    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json
            payload = json.loads(repair_json(raw))
        except Exception as repair_exc:
            raise RuntimeError(
                f"The LLM returned JSON that could not be parsed even after repair: {repair_exc}"
            ) from repair_exc
    return _build_storyboard(payload, lyrics, style_prompt)

def _build_storyboard(
    payload: dict,
    lyrics: LyricsFile,
    style_prompt: str,
) -> Storyboard:
    valid_ids = {ln.id for ln in lyrics.lines}
    parsed_lines: list[LineDirection] = []

    for item in payload.get("lines", []):
        line_id = int(item.get("line_id", 0))
        if line_id not in valid_ids:
            continue  # skip hallucinated IDs

        pos = item.get("position") or {}
        bg = item.get("background") or {}

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
                font_size_pct=float(item.get("font_size_pct", 5.2)),
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
