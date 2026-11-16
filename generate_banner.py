#!/usr/bin/env python3
"""Generate a 16-bit cozy farming RPG pixel-art banner via the Gemini image API.

Reads GEMINI_API_KEY from the project .env file (parsed manually), calls the
Gemini image generation REST API, and saves the result as a PNG in
assets/banners/.
"""

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-image:generateContent"
)
PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "banners"
# Sources at or below this size are treated as pixel art and upscaled with NEAREST.
PIXEL_ART_MAX_DIM = 512


def load_api_key(env_path):
    """Parse GEMINI_API_KEY out of a .env file without extra dependencies."""
    candidates = [env_path, Path.cwd() / ".env"]
    for path in candidates:
        if path.is_file():
            env_path = path
            break
    else:
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
        if key.strip() != "GEMINI_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        if not value:
            raise RuntimeError(f"GEMINI_API_KEY is empty in {env_path}")
        return value

    raise RuntimeError(f"GEMINI_API_KEY not found in {env_path}")


def build_prompt(user_prompt):
    return (
        f"{user_prompt}. "
        "16-bit cozy farming RPG pixel art style, wide 4:1 banner composition, "
        "absolutely no text, no letters, no words, no typography, no watermarks."
    )


def generate_image(api_key, prompt):
    """Call the Gemini image API and return the raw image bytes."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"network request to Gemini API failed: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Gemini API request failed (HTTP {resp.status_code}): {resp.text}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError("Gemini API returned invalid JSON") from exc

    for candidate in data.get("candidates", []):
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                try:
                    return base64.b64decode(inline["data"])
                except Exception as exc:
                    raise RuntimeError(f"failed to decode base64 image data: {exc}") from exc

    snippet = json.dumps(data)[:500]
    raise RuntimeError(f"no inline image data found in Gemini API response: {snippet}")


def process_image(image_bytes, width, height):
    """Center-crop to the target aspect ratio and resize to (width, height)."""
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

    if max(img.size) <= PIXEL_ART_MAX_DIM:
        resample = Image.Resampling.NEAREST
    else:
        resample = Image.Resampling.LANCZOS
    img = img.resize((width, height), resample)

    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    return img


def main():
    parser = argparse.ArgumentParser(
        description="Generate a 16-bit cozy farming RPG pixel-art banner with Gemini."
    )
    parser.add_argument("prompt", help="description of the banner scene to generate")
    parser.add_argument(
        "--out",
        default="banner.png",
        help="output filename, saved into assets/banners/ (default: banner.png)",
    )
    parser.add_argument("--width", type=int, default=2048, help="output width (default: 2048)")
    parser.add_argument("--height", type=int, default=512, help="output height (default: 512)")
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
        api_key = load_api_key(ENV_PATH)
        prompt = build_prompt(args.prompt)
        image_bytes = generate_image(api_key, prompt)
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
