#!/usr/bin/env python3
"""Generate a 16-bit cozy farming RPG pixel-art banner via Cloudflare Workers AI.

Calls the @cf/black-forest-labs/flux-1-schnell image-generation REST endpoint,
then center-crops to a 4:1 aspect ratio and resizes to (880, 220) with NEAREST
resampling for crisp chunky pixels. Saves as PNG in assets/banners/.

Required .env vars:
  CLOUDFLARE_WORKERS_AI_API_TOKEN   Cloudflare API token with Workers AI access
  CLOUDFLARE_WORKERS_AI_BASE_URL    e.g. https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>
"""

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "banners"
MODEL = "@cf/black-forest-labs/flux-1-schnell"

# Sources at or below this size are treated as pixel art and upscaled with NEAREST.
PIXEL_ART_MAX_DIM = 512


def load_env_var(name):
    """Read a single variable: os.environ first, then fall back to project .env."""
    value = os.environ.get(name)
    if value:
        return value.strip().strip('"').strip("'")

    candidates = [ENV_PATH, Path.cwd() / ".env"]
    env_path = None
    for path in candidates:
        if path.is_file():
            env_path = path
            break
    if env_path is None:
        raise RuntimeError(
            f".env file not found (looked in {candidates[0]} and {candidates[1]})"
        )

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != name:
            continue
        value = value.strip().strip('"').strip("'")
        if not value:
            raise RuntimeError(f"{name} is empty in {env_path}")
        return value

    raise RuntimeError(f"{name} not found in environment or .env")


def build_endpoint(base_url):
    """Build the full Workers AI model endpoint from the base URL.

    Strips trailing slashes and any trailing "/v1" so the model path is never
    duplicated (e.g. .../v1/v1/ai/run/...).
    """
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    return f"{base_url}/ai/run/{MODEL}"


def build_prompt(user_prompt):
    """Prepend the standard pixel-art style wrapper to prompts."""
    return (
        "authentic 16-bit SNES pixel art sprite background, Stardew Valley style, "
        "hard pixel edges, dithering, flat pixel shading, no smooth gradients, "
        "no anti-aliasing, no text. "
        f"{user_prompt}. "
        "absolutely no text, no letters, no words, no typography, no watermarks."
    )


def generate_image(api_token, endpoint, prompt):
    """Call Cloudflare Workers AI FLUX and return raw image bytes."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        # FLUX-1-schnell accepts only 'prompt'; dimensions are handled by
        # center-crop + NEAREST resize in process_image().
    }
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=300)
    except requests.RequestException as exc:
        raise RuntimeError(f"network request to Cloudflare Workers AI failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Cloudflare Workers AI request failed (HTTP {resp.status_code}): {resp.text}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError("Cloudflare Workers AI returned invalid JSON") from exc

    if not data.get("success", False):
        errors = data.get("errors", [])
        raise RuntimeError(f"Cloudflare Workers AI reported failure: {errors}")

    result = data.get("result", {})
    image_data = result.get("image")
    if not image_data:
        snippet = json.dumps(data)[:500]
        raise RuntimeError(
            f"no image data in Cloudflare Workers AI response: {snippet}"
        )

    # Cloudflare may return a data URL or raw base64.
    if isinstance(image_data, str) and image_data.startswith("data:"):
        try:
            _, b64 = image_data.split(",", 1)
        except ValueError as exc:
            raise RuntimeError("failed to parse data URL image") from exc
    else:
        b64 = image_data

    try:
        return base64.b64decode(b64)
    except Exception as exc:
        raise RuntimeError(f"failed to decode base64 image data: {exc}") from exc


def process_image(image_bytes, width, height):
    """Center-crop to target aspect, pixelate, quantize, upscale to (width, height).

    Pixelation pipeline: downsample to 1/4 resolution (BOX), quantize to a
    limited 40-color palette (MEDIANCUT, Dither.NONE), then upscale with NEAREST
    so every pixel is sharp and blocky — matching the existing daily_digest_banner
    chunky 16-bit pixel-art style.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as exc:
        raise RuntimeError(f"failed to open image returned by the API: {exc}") from exc

    src_w, src_h = img.size
    target_aspect = width / height
    src_aspect = src_w / src_h

    if src_aspect > target_aspect:
        new_w = max(1, int(round(src_h * target_aspect)))
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    elif src_aspect < target_aspect:
        new_h = max(1, int(round(src_w / target_aspect)))
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    # Pixelate: shrink to 1/4 resolution, quantize to limited palette, upscale sharp.
    small_w = max(1, width // 4)
    small_h = max(1, height // 4)
    img = img.resize((small_w, small_h), Image.Resampling.BOX)
    img = img.quantize(
        colors=40, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    img = img.convert("RGB")
    img = img.resize((width, height), Image.Resampling.NEAREST)

    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    return img


def main():
    parser = argparse.ArgumentParser(
        description="Generate a 16-bit cozy farming RPG pixel-art banner via Cloudflare FLUX."
    )
    parser.add_argument("prompt", help="description of the banner scene to generate")
    parser.add_argument(
        "--out",
        default="banner.png",
        help="output filename, saved into assets/banners/ (default: banner.png)",
    )
    parser.add_argument(
        "--width", type=int, default=880, help="output width (default: 880)"
    )
    parser.add_argument(
        "--height", type=int, default=220, help="output height (default: 220)"
    )
    args = parser.parse_args()

    if args.width <= 0 or args.height <= 0:
        parser.error("--width and --height must be positive integers")

    out_name = args.out
    if not out_name.lower().endswith(".png"):
        out_name += ".png"
    if Path(out_name).name != out_name:
        parser.error("--out must be a plain filename, not a path")

    out_path = OUTPUT_DIR / out_name

    try:
        api_token = load_env_var("CLOUDFLARE_WORKERS_AI_API_TOKEN")
        base_url = load_env_var("CLOUDFLARE_WORKERS_AI_BASE_URL")
        endpoint = build_endpoint(base_url)
        prompt = build_prompt(args.prompt)
        image_bytes = generate_image(api_token, endpoint, prompt)
        img = process_image(image_bytes, args.width, args.height)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"Error: failed to write {out_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Saved banner to {out_path}")


if __name__ == "__main__":
    main()
