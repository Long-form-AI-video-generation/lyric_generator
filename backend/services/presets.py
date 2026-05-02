"""Built-in background presets and deterministic asset generation."""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from backend.core.config import settings
from backend.core.errors import NotFoundError
from backend.models.schemas import Preset


@dataclass(frozen=True)
class PresetDefinition:
    id: str
    label: str
    description: str


PRESETS: tuple[PresetDefinition, ...] = (
    PresetDefinition("dark-gradient", "Dark Gradient", "Deep blue-to-black vertical gradient"),
    PresetDefinition("starfield", "Starfield", "Dark sky with small white star particles"),
    PresetDefinition("abstract-violet", "Abstract Violet", "Blurred violet and indigo colour wash"),
    PresetDefinition("cinematic-grain", "Cinematic", "Solid black with subtle film grain"),
    PresetDefinition("deep-ocean", "Deep Ocean", "Dark teal gradient with soft motion bands"),
    PresetDefinition("neon-city", "Neon City", "Dark background with blurred neon colour streaks"),
)


def _clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def _lerp(a: int, b: int, t: float) -> int:
    return _clamp(a + (b - a) * t)


def _mix(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def _hash_noise(x: int, y: int, seed: int = 0) -> int:
    value = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    value = (value ^ (value >> 13)) * 1274126177
    return (value ^ (value >> 16)) & 0xFF


def _write_png(path: Path, width: int, height: int, pixel_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compressor = zlib.compressobj(level=6)
    chunks: list[bytes] = []
    for y in range(height):
        row = bytearray()
        row.append(0)
        for x in range(width):
            row.extend(pixel_fn(x, y, width, height))
        chunks.append(compressor.compress(bytes(row)))
    chunks.append(compressor.flush())
    raw = b"".join(chunks)

    def chunk(tag: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", checksum)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", raw)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _dark_gradient(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    t = y / max(1, height - 1)
    base = _mix((12, 18, 35), (1, 1, 4), t)
    glow = max(0.0, 1.0 - abs((x / width) - 0.32) * 2.6) * max(0.0, 1.0 - t) * 18
    return (_clamp(base[0] + glow), _clamp(base[1] + glow * 0.45), _clamp(base[2] + glow * 1.1))


def _starfield(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    t = y / max(1, height - 1)
    base = _mix((4, 7, 17), (0, 0, 3), t)
    noise = _hash_noise(x // 2, y // 2, 7)
    if noise > 252:
        brightness = 155 + _hash_noise(x, y, 11) % 90
        return (brightness, brightness, _clamp(brightness + 10))
    return base


def _abstract_violet(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    nx = x / width
    ny = y / height
    color = _mix((12, 10, 25), (5, 6, 15), ny)
    circles = (
        (0.28, 0.38, 0.34, (94, 37, 168)),
        (0.68, 0.34, 0.28, (16, 185, 129)),
        (0.53, 0.70, 0.42, (49, 46, 129)),
    )
    r, g, b = color
    for cx, cy, radius, tint in circles:
        dist = math.sqrt((nx - cx) ** 2 + (ny - cy) ** 2)
        weight = max(0.0, 1.0 - dist / radius) ** 2
        r = _lerp(r, tint[0], weight * 0.45)
        g = _lerp(g, tint[1], weight * 0.35)
        b = _lerp(b, tint[2], weight * 0.50)
    return (r, g, b)


def _cinematic_grain(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    vignette_x = abs((x / width) - 0.5) * 2
    vignette_y = abs((y / height) - 0.5) * 2
    vignette = max(vignette_x, vignette_y)
    grain = _hash_noise(x, y, 19) % 20
    base = 15 - int(vignette * 9) + grain // 4
    return (_clamp(base), _clamp(base), _clamp(base + 1))


def _deep_ocean(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    t = y / max(1, height - 1)
    wave = (math.sin((x / width) * math.tau * 3 + t * 6) + 1) * 0.5
    base = _mix((3, 55, 62), (1, 10, 18), t)
    return (_clamp(base[0] + wave * 6), _clamp(base[1] + wave * 12), _clamp(base[2] + wave * 15))


def _neon_city(x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    t = y / max(1, height - 1)
    r, g, b = _mix((7, 8, 18), (1, 1, 5), t)
    columns = ((0.18, (124, 58, 237)), (0.44, (16, 185, 129)), (0.72, (236, 72, 153)), (0.86, (59, 130, 246)))
    for cx, tint in columns:
        dist = abs((x / width) - cx)
        weight = max(0.0, 1.0 - dist / 0.055) ** 3 * max(0.0, 1.0 - t * 0.72)
        r = _lerp(r, tint[0], weight * 0.7)
        g = _lerp(g, tint[1], weight * 0.7)
        b = _lerp(b, tint[2], weight * 0.7)
    return (r, g, b)


PIXEL_FUNCTIONS = {
    "dark-gradient": _dark_gradient,
    "starfield": _starfield,
    "abstract-violet": _abstract_violet,
    "cinematic-grain": _cinematic_grain,
    "deep-ocean": _deep_ocean,
    "neon-city": _neon_city,
}


class PresetService:
    """Resolve preset metadata and image files."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.preset_root
        self.full_dir = self.root / "full"
        self.thumb_dir = self.root / "thumbs"

    def ensure_assets(self, *, include_full: bool = True) -> None:
        for preset in PRESETS:
            full_path = self.full_path(preset.id)
            thumb_path = self.thumb_path(preset.id)
            pixel_fn = PIXEL_FUNCTIONS[preset.id]
            if include_full and not full_path.exists():
                _write_png(full_path, 1920, 1080, pixel_fn)
            if not thumb_path.exists():
                _write_png(thumb_path, 384, 216, pixel_fn)

    def list_presets(self) -> list[Preset]:
        return [
            Preset(
                id=preset.id,
                label=preset.label,
                thumbnail_url=f"/presets/{preset.id}.png",
            )
            for preset in PRESETS
        ]

    def full_path(self, preset_id: str) -> Path:
        return self.full_dir / f"{preset_id}.png"

    def thumb_path(self, preset_id: str) -> Path:
        return self.thumb_dir / f"{preset_id}.png"

    def resolve_full_path(self, preset_id: str) -> Path:
        if preset_id not in PIXEL_FUNCTIONS:
            raise NotFoundError("Unknown background preset.")
        self.ensure_assets(include_full=False)
        path = self.full_path(preset_id)
        if not path.exists():
            _write_png(path, 1920, 1080, PIXEL_FUNCTIONS[preset_id])
        return path


preset_service = PresetService()
