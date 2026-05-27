
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image


def _filter_none(img: Image.Image) -> Image.Image:
    return img


def _filter_blur(img: Image.Image, radius: int = 8) -> Image.Image:
    from PIL.ImageFilter import GaussianBlur

    return img.filter(GaussianBlur(radius))


def _filter_desaturate(img: Image.Image) -> Image.Image:
    from PIL import ImageEnhance

    return ImageEnhance.Color(img).enhance(0.0)


def _filter_color_shift(img: Image.Image) -> Image.Image:
    
    r, g, b = img.convert("RGB").split()
    choice = random.randint(0, 2)
    if choice == 0:  # cyan
        result = Image.merge("RGB", (r.point(lambda v: int(v * 0.55)), g, b))
    elif choice == 1:  # purple
        result = Image.merge("RGB", (r, g.point(lambda v: int(v * 0.55)), b))
    else:  # amber
        result = Image.merge(
            "RGB",
            (r, g.point(lambda v: int(v * 0.85)), b.point(lambda v: int(v * 0.35))),
        )
    return result


def _filter_glitch(img: Image.Image) -> Image.Image:
   
    w, h = img.size
    arr = list(img.convert("RGB").getdata())
    out_data = arr[:]

    for _ in range(h // 8):
        y = random.randint(0, h - 1)
        shift = random.randint(-w // 10, w // 10)
        row = out_data[y * w : (y + 1) * w]
        if shift > 0:
            row = row[-shift:] + row[:-shift]
        elif shift < 0:
            row = row[-shift:] + row[:-shift]
        out_data[y * w : (y + 1) * w] = row

    out = Image.new("RGB", (w, h))
    out.putdata(out_data)
    return out


def _filter_vhs(img: Image.Image) -> Image.Image:
    
    from PIL import ImageDraw
    from PIL.ImageFilter import GaussianBlur

    img = img.convert("RGB").filter(GaussianBlur(1))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, img.size[1], 4):
        draw.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, 45))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


_BACKGROUND_FILTERS: dict[str, object] = {
    "none": _filter_none,
    "blur": _filter_blur,
    "desaturate": _filter_desaturate,
    "color_shift": _filter_color_shift,
    "glitch": _filter_glitch,
    "vhs": _filter_vhs,
}


def apply_background_filter(img: Image.Image, filter_name: str) -> Image.Image:
   
    fn = _BACKGROUND_FILTERS.get(filter_name, _filter_none)
    return fn(img.convert("RGB"))  # type: ignore[call-arg]

def _distort_none(img: Image.Image) -> Image.Image:
    return img


def _distort_chromatic_aberration(img: Image.Image, shift: int = 6) -> Image.Image:
    
    from PIL import ImageChops

    r, g, b = img.convert("RGB").split()
    r_shifted = ImageChops.offset(r, shift, 0)
    b_shifted = ImageChops.offset(b, -shift, 0)
    return Image.merge("RGB", (r_shifted, g, b_shifted))


def _distort_pixel_sort(img: Image.Image) -> Image.Image:
    
    import numpy as np

    arr = np.array(img.convert("RGB"), dtype=np.uint8)
    h, w = arr.shape[:2]
    lum = arr.mean(axis=2)  # (h, w)

    for x in range(w):
        col_lum = lum[:, x]
        threshold = float(col_lum.mean())
        indices = np.where(col_lum > threshold)[0]
        if len(indices) > 1:
            sorted_idx = indices[np.argsort(col_lum[indices])]
            arr[indices, x, :] = arr[sorted_idx, x, :]

    return Image.fromarray(arr)


def _distort_datamosh(img: Image.Image) -> Image.Image:
   
    import numpy as np

    arr = np.array(img.convert("RGB"), dtype=np.uint8).copy()
    h, w = arr.shape[:2]
    block = 32

    for _ in range(24):
        src_y = random.randint(0, h - block - 1)
        src_x = random.randint(0, w - block - 1)
        dst_y = random.randint(0, h - block - 1)
        dst_x = random.randint(0, w - block - 1)
        arr[dst_y : dst_y + block, dst_x : dst_x + block] = arr[
            src_y : src_y + block, src_x : src_x + block
        ]

    return Image.fromarray(arr)


_SPEAKER_DISTORTIONS: dict[str, object] = {
    "none": _distort_none,
    "chromatic_aberration": _distort_chromatic_aberration,
    "pixel_sort": _distort_pixel_sort,
    "datamosh": _distort_datamosh,
}


def apply_speaker_distortion(img: Image.Image, distortion_name: str) -> Image.Image:
    
    fn = _SPEAKER_DISTORTIONS.get(distortion_name, _distort_none)
    return fn(img.convert("RGB"))  # type: ignore[call-arg]


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def load_background_images(asset_dirs: list[Path]) -> list[Path]:
   
    images: list[Path] = []
    for d in asset_dirs:
        if d.is_dir():
            images.extend(
                p for p in sorted(d.iterdir()) if p.suffix.lower() in _IMAGE_EXTENSIONS
            )
    return images


def load_speaker_images(speaker_dirs: list[Path]) -> list[Path]:
    
    return load_background_images(speaker_dirs)


def prepare_background(
    image_path: Path,
    width: int,
    height: int,
    *,
    filter_name: str = "none",
    dark_overlay_alpha: float = 0.45,
) -> Image.Image:
   
    img = Image.open(image_path).convert("RGB")
    scale = max(width / img.width, height / img.height)
    new_w = int(img.width * scale + 0.5)
    new_h = int(img.height * scale + 0.5)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x0 = (new_w - width) // 2
    y0 = (new_h - height) // 2
    img = img.crop((x0, y0, x0 + width, y0 + height))
    black = Image.new("RGB", (width, height), (0, 0, 0))
    img = Image.blend(img, black, alpha=dark_overlay_alpha)
    return apply_background_filter(img, filter_name)


def composite_speaker(
    bg: Image.Image,
    speaker_path: Path,
    *,
    distortion: str = "none",
    opacity: float = 0.5,
) -> Image.Image:
    
    if opacity <= 0.0:
        return bg

    w, h = bg.size
    speaker = Image.open(speaker_path).convert("RGB")
    # Scale to fill
    scale = max(w / speaker.width, h / speaker.height)
    new_w = int(speaker.width * scale + 0.5)
    new_h = int(speaker.height * scale + 0.5)
    speaker = speaker.resize((new_w, new_h), Image.LANCZOS)
    x0 = (new_w - w) // 2
    y0 = (new_h - h) // 2
    speaker = speaker.crop((x0, y0, x0 + w, y0 + h))
    speaker = apply_speaker_distortion(speaker, distortion)
    return Image.blend(bg.convert("RGB"), speaker, alpha=opacity)
