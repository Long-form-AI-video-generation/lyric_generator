
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.models.schemas import SongConfig


_EXAMPLE_CONFIG = """\
global_style: "dark cinematic, high contrast"

speakers:
  artist:
    font: Bebas
    text_color: "#F0E6D3"
    animation: fade-in
    font_size_pct: 7.0
    position_y_pct: 55

section_overrides:
  - sections: [chorus]
    style: "bright, energetic, use zoom-in animation"
  - sections: [bridge]
    style: "intimate, soft glow, typewriter effect"

generate_ai_backgrounds: false
"""


def parse_song_config(yaml_text: str) -> SongConfig:
   
    text = yaml_text.strip()
    if not text:
        return SongConfig()

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is not installed — run: pip install PyYAML"
        ) from exc

    try:
        data: Any = yaml.safe_load(text)
    except Exception as exc:  # yaml.YAMLError
        raise ValueError(f"Invalid YAML in song config: {exc}") from exc

    if data is None:
        return SongConfig()

    if not isinstance(data, dict):
        raise ValueError(
            "Song config must be a YAML mapping (key: value pairs), "
            "not a list or bare scalar."
        )

    try:
        return SongConfig.model_validate(data)
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        raise ValueError(f"Song config validation failed — {issues}") from exc


def example_config_yaml() -> str:
    """Return a commented YAML template the frontend can pre-fill."""
    return _EXAMPLE_CONFIG
