# Art Standards (canonical decisions)

- Style: 16-bit cozy farming RPG / 8-bit pixel art, Stardew Valley vibe — chunky pixels, warm palettes.
- Banner sizes: **880x180** and **880x220** (4:1). Generate large, then crop/resize to exact 4:1.
- Pixelation pipeline (in `scripts/generate_banner.py`, `process_image`):
  1. Center-crop source to 4:1 target aspect ratio.
  2. Downsample to 1/4 resolution (`width//4 x height//4` = 220x55 for 880x220) with `Resampling.BOX`.
  3. Quantize to 40 colors (`Quantize.MEDIANCUT`, `Dither.NONE`) for a limited flat palette.
  4. Convert to RGB, then upscale to full size (880x220) with `Resampling.NEAREST` for sharp blocky pixels.
- Resampling: `Image.Resampling.NEAREST` for final upscale — never smooth/LANCZOS upscaling of pixel sources.
- Prompt wrapper (`build_prompt`): prepends `"authentic 16-bit SNES pixel art sprite background, Stardew Valley style, hard pixel edges, dithering, flat pixel shading, no smooth gradients, no anti-aliasing, no text."` to every prompt, plus a trailing `"absolutely no text, no letters, no words, no typography, no watermarks."`
- Paths: templates/assets in `assets/banners/`; pixel title font `assets/fonts/PressStart2P.ttf`.
- Banner TEMPLATES are **text-free** (`/items` templates especially) — the developer agent overlays dynamic titles with PressStart2P.ttf. Artist never renders text.
- Workflow: artist generates text-free PNG template → developer loads with NEAREST, overlays title, deploys via deploy.py.
- Image API: Cloudflare Workers AI `@cf/black-forest-labs/flux-1-schnell` via `scripts/generate_banner.py`
  (was `generate_banner.py` at project root; moved to `scripts/`). Reads
  `CLOUDFLARE_WORKERS_AI_API_TOKEN` and `CLOUDFLARE_WORKERS_AI_BASE_URL` from
  `os.environ` first, then falls back to `TrackerBot/.env`. Endpoint strips a
  trailing `/v1` from the base URL to avoid path duplication.
- Gemini `gemini-2.5-flash-image` (GEMINI_API_KEY) is retired; as of
  2026-11-16 its free tier was quota-exhausted (~15h retry).
- Generated banner assets (text-free templates, 880x220, pixel-art pipeline, saved to `assets/banners/`):
  - `spring_morning_banner.png` — pastel sunrise, cherry blossoms, white cottage w/ red roof
  - `summer_harvest_banner.png` — golden fields, sunflowers, red barn, bright blue sky
  - `winter_dawn_banner.png` — snow-covered fields, evergreens, pale dawn sky, warm lantern glow
