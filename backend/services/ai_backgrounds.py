
from __future__ import annotations

import base64
import time
from collections.abc import Callable
from pathlib import Path

MAX_UNIQUE_IMAGES = 6


def generate_ai_backgrounds(
    job_dir: Path,
    storyboard_lines: list[dict],
    *,
    openai_api_key: str,
    model: str = "gpt-image-1",
    size: str = "1536x1024",   
    on_progress: Callable[[int], None] | None = None,
) -> dict[str, int]:
    
    import openai 
    seen: dict[str, int] = {}
    for line in storyboard_lines:
        prompt = (line.get("image_prompt") or "").strip()
        if prompt and prompt not in seen:
            if len(seen) < MAX_UNIQUE_IMAGES:
                seen[prompt] = len(seen)
            else:
                
                seen[prompt] = len(seen) % MAX_UNIQUE_IMAGES

    if not seen:
        return {}

    
    to_generate = {p: i for p, i in seen.items() if i < MAX_UNIQUE_IMAGES}

    client = openai.OpenAI(api_key=openai_api_key)
    prompt_to_index: dict[str, int] = {}

    
    job_dir.mkdir(parents=True, exist_ok=True)

    total = len(to_generate)
    for pos, (prompt, idx) in enumerate(to_generate.items(), 1):
        out_path = job_dir / f"bg_ai_{idx:03d}.jpg"

        if out_path.exists():
            prompt_to_index[prompt] = idx
            if on_progress:
                on_progress(round(pos / total * 100))
            continue

        print(f"[ai_backgrounds] Generating image {pos}/{total}: {prompt[:60]}…")
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,  
                n=1,
            )
            item = response.data[0]

           
            if item.b64_json:
                job_dir.mkdir(parents=True, exist_ok=True)  # re-check before write
                out_path.write_bytes(base64.b64decode(item.b64_json))
                prompt_to_index[prompt] = idx
            elif item.url:
                import urllib.request
                with urllib.request.urlopen(item.url, timeout=60) as resp:  # noqa: S310
                    job_dir.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(resp.read())
                prompt_to_index[prompt] = idx
            else:
                print(f"[ai_backgrounds] No image data for prompt '{prompt[:60]}…'")

        except Exception as exc:  # noqa: BLE001
            print(f"[ai_backgrounds] Failed for prompt '{prompt[:60]}…': {exc}")

        if on_progress:
            on_progress(round(pos / total * 100))

        time.sleep(0.5)  

   
    full_map: dict[str, int] = {}
    for prompt, idx in seen.items():
        resolved = idx % MAX_UNIQUE_IMAGES
        if resolved in {v for v in prompt_to_index.values()}:
            full_map[prompt] = resolved

    return full_map


def apply_ai_backgrounds_to_storyboard(
    storyboard_dict: dict,
    prompt_to_index: dict[str, int],
    ai_base_index: int = 0,
) -> dict:
    
    import copy

    sb = copy.deepcopy(storyboard_dict)
    for line in sb.get("lines", []):
        prompt = (line.get("image_prompt") or "").strip()
        if prompt and prompt in prompt_to_index:
            line["background"] = line.get("background") or {}
            line["background"]["image_index"] = ai_base_index + prompt_to_index[prompt]
    return sb
