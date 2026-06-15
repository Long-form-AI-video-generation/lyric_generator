

from __future__ import annotations

import base64
import io
from pathlib import Path

_SOLO_SYSTEM = (
    "You are a music video art director. "
    "Given a photo of an artist, generate a cinematic, high-quality image of that "
    "same artist styled to match the visual brief. Preserve their face and likeness exactly. "
    "The result should look like a professional music video still frame."
)

_DUO_SYSTEM = (
    "You are a music video art director. "
    "Given photos of two artists, generate a single cinematic image showing both artists "
    "together, styled to match the visual brief. Preserve both faces and likenesses exactly. "
    "The result should look like a professional music video collaboration still frame."
)


def _read_image_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _first_photo(slug_dir: Path) -> Path | None:
   
    for f in sorted(slug_dir.iterdir()):
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and not f.name.startswith(".") and not f.name.startswith("generated_"):
            return f
    return None


def _save_image_response(item, out_path: Path) -> bool:
    
    if item.b64_json:
        out_path.write_bytes(base64.b64decode(item.b64_json))
        return True
    if item.url:
        import urllib.request
        with urllib.request.urlopen(item.url, timeout=60) as resp:  # noqa: S310
            out_path.write_bytes(resp.read())
        return True
    return False


def generate_solo_image(
    slug_dir: Path,
    style_prompt: str,
    artist_name: str,
    openai_api_key: str,
    model: str = "gpt-image-1",
    size: str = "1024x1024",
) -> Path | None:
    
    import openai

    photo = _first_photo(slug_dir)
    if not photo:
        return None

    out_path = slug_dir / "generated_solo.jpg"

    client = openai.OpenAI(api_key=openai_api_key)

    prompt = (
        f"Artist: {artist_name}. "
        f"Visual style: {style_prompt}. "
        "Generate a cinematic music video still of this exact artist in this visual style. "
        "Preserve their face and likeness perfectly."
    )

    try:
        with open(photo, "rb") as img_file:
            response = client.images.edit(
                model=model,
                image=img_file,
                prompt=prompt,
                size=size,
                n=1,
            )
        if _save_image_response(response.data[0], out_path):
            return out_path
    except Exception as exc:  # noqa: BLE001
        print(f"[artist_image_gen] Solo generation failed for {artist_name}: {exc}")

    return None


def generate_duo_image(
    slug_dir_a: Path,
    slug_dir_b: Path,
    artist_name_a: str,
    artist_name_b: str,
    style_prompt: str,
    openai_api_key: str,
    out_dir: Path,
    slug_a: str,
    slug_b: str,
    model: str = "gpt-image-1",
    size: str = "1536x1024",
) -> Path | None:
    
    import openai
    from PIL import Image

    photo_a = _first_photo(slug_dir_a)
    photo_b = _first_photo(slug_dir_b)
    if not photo_a or not photo_b:
        return None

    # Stable slug ordering so duo_{a}_{b} == duo_{b}_{a}
    key_a, key_b = sorted([slug_a, slug_b])
    out_path = out_dir / f"duo_{key_a}_{key_b}.jpg"

    client = openai.OpenAI(api_key=openai_api_key)

    # Side-by-side composite passed as the reference image
    img_a = Image.open(photo_a).convert("RGBA")
    img_b = Image.open(photo_b).convert("RGBA")

    target_h = 512
    def _resize(img: Image.Image) -> Image.Image:
        ratio = target_h / img.height
        return img.resize((int(img.width * ratio), target_h), Image.LANCZOS)

    img_a = _resize(img_a)
    img_b = _resize(img_b)

    combined = Image.new("RGBA", (img_a.width + img_b.width, target_h))
    combined.paste(img_a, (0, 0))
    combined.paste(img_b, (img_a.width, 0))

    buf = io.BytesIO()
    combined.save(buf, format="PNG")
    buf.seek(0)

    prompt = (
        f"Artists: {artist_name_a} and {artist_name_b}. "
        f"Visual style: {style_prompt}. "
        "Generate a cinematic music video collaboration still showing both artists together "
        "in this visual style. Preserve both faces and likenesses perfectly."
    )

    try:
        response = client.images.edit(
            model=model,
            image=("reference.png", buf, "image/png"),
            prompt=prompt,
            size=size,
            n=1,
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        if _save_image_response(response.data[0], out_path):
            return out_path
    except Exception as exc:  # noqa: BLE001
        print(f"[artist_image_gen] Duo generation failed for {artist_name_a}+{artist_name_b}: {exc}")

    return None


def generate_artist_images(
    job_dir: Path,
    style_prompt: str,
    openai_api_key: str,
    pairs: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    
    speakers_dir = job_dir / "speakers"
    if not speakers_dir.is_dir():
        return {}

    # Build slug → (name, dir) map
    slug_map: dict[str, tuple[str, Path]] = {}
    for slug_dir in sorted(speakers_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        name_file = slug_dir / ".artist_name"
        artist_name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else slug_dir.name
        slug_map[slug_dir.name] = (artist_name, slug_dir)

    # Name → slug reverse map
    name_to_slug = {name.lower(): slug for slug, (name, _) in slug_map.items()}

    results: dict[str, str] = {}

    # Solo images
    for slug, (artist_name, slug_dir) in slug_map.items():
        out = generate_solo_image(slug_dir, style_prompt, artist_name, openai_api_key)
        if out:
            results[f"solo:{artist_name.lower()}"] = str(out.relative_to(job_dir))
            print(f"[artist_image_gen] Solo done: {artist_name}")

    # Duo images
    if pairs:
        for name_a, name_b in pairs:
            slug_a = name_to_slug.get(name_a.lower())
            slug_b = name_to_slug.get(name_b.lower())
            if not slug_a or not slug_b:
                continue
            _, dir_a = slug_map[slug_a]
            _, dir_b = slug_map[slug_b]
            out = generate_duo_image(
                dir_a, dir_b,
                name_a, name_b,
                style_prompt,
                openai_api_key,
                speakers_dir,
                slug_a, slug_b,
            )
            if out:
                key_a, key_b = sorted([name_a.lower(), name_b.lower()])
                results[f"duo:{key_a}:{key_b}"] = str(out.relative_to(job_dir))
                print(f"[artist_image_gen] Duo done: {name_a}+{name_b}")

    return results
