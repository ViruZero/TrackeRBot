"""Pillow-based banner rendering for the /items shopping list command.

Self-contained module: builds 880x180 RGBA banner images from the artwork
in assets/banners/, with a blocky 8-bit style title overlaid (nearest-neighbor
upscaled bold text). No bot imports.

Templates: the four artwork themes below ship in the repo. Custom URLs are
handled via render_custom_banner().
"""

import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 880, 180
RADIUS = 24
ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'banners'

FONT_CHAIN = [
    'C:/Windows/Fonts/arialbd.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
]

PIXEL_FONT = ASSETS_DIR.parent / 'fonts' / 'PressStart2P.ttf'


def pixel_font(size):
    """Load the pixel font if available, else fall back to the bold font chain."""
    if PIXEL_FONT.is_file():
        return ImageFont.truetype(str(PIXEL_FONT), size)
    return font(size)


def font(size):
    """Load a bold font, falling back gracefully across platforms."""
    for path in FONT_CHAIN:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _cover_crop(img):
    """Resize-cover an image and center-crop it to exactly W x H."""
    img = img.convert('RGBA')
    w, h = img.size
    scale = max(W / w, H / h)
    nw, nh = math.ceil(w * scale), math.ceil(h * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - W) // 2
    top = (nh - H) // 2
    return img.crop((left, top, left + W, top + H))


def _apply_rounded(img):
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=RADIUS, fill=255)
    img = img.copy()
    img.putalpha(mask)
    return img


def _inner_border(img):
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([3, 3, W - 4, H - 4], radius=RADIUS - 3,
                           outline=(255, 255, 255, 80), width=2)
    draw.rounded_rectangle([7, 7, W - 8, H - 8], radius=RADIUS - 7,
                           outline=(0, 0, 0, 90), width=1)


def _pixel_title(img, name, fill, outline, title_dy=0):
    """8-bit style title: render bold text small, nearest-neighbor upscale it."""
    text = name + "'s Shopping List"
    small = Image.new('RGBA', (2000, 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(small)
    base = pixel_font(20 if PIXEL_FONT.is_file() else 17)
    ox, oy = 30, 22
    for dx, dy in [(-3, -3), (-3, 0), (-3, 3), (0, -3), (0, 3), (3, -3), (3, 0), (3, 3), (-3, -1), (3, 1), (-3, 1), (3, -1), (-1, -3), (1, 3), (-1, 3), (1, -3)]:
        d.text((ox + dx, oy + dy), text, font=base, fill=outline)
    d.text((ox, oy), text, font=base, fill=fill)
    bbox = small.getbbox()
    line = small.crop(bbox)
    target_h = 34
    scale = target_h / line.height
    up = line.resize((max(1, round(line.width * scale)), target_h), Image.NEAREST)
    if up.width > W - 24:
        shrink = (W - 24) / up.width
        up = up.resize((max(1, int(up.width * shrink)), max(1, int(up.height * shrink))), Image.NEAREST)
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    canvas.paste(up, ((W - up.width) // 2, (H - up.height) // 2 - title_dy), up)
    img.alpha_composite(canvas)








ART_THEMES = {
    'starry_night': {'file': 'starry_night.jpg', 'fill': (255, 241, 196, 255),
                     'outline': (22, 20, 54, 255), 'label': 'Starry Night'},
    'cozy_cafe': {'file': 'cozy_cafe.jpg', 'fill': (255, 240, 210, 255),
                  'outline': (84, 46, 22, 255), 'label': 'Cozy Cafe'},
    'pastel_cats': {'file': 'pastel_cats.jpg', 'fill': (255, 255, 255, 255),
                    'outline': (80, 46, 80, 255), 'label': 'Pastel Cats'},
    'dog_park': {'file': 'dog_park.jpg', 'fill': (255, 255, 255, 255),
                 'outline': (44, 32, 12, 255), 'label': 'Dog Park', 'title_dy': 34},
}

THEME_LABELS = {key: cfg['label'] for key, cfg in ART_THEMES.items()}
DEFAULT_THEME = 'starry_night'



def render_banner(theme, name, out_path):
    """Render the themed artwork banner for  and save it to ."""
    theme = theme if theme in ART_THEMES else DEFAULT_THEME
    art = ASSETS_DIR / ART_THEMES[theme]['file']
    img = _cover_crop(Image.open(art)) if art.is_file() else Image.new('RGBA', (W, H), (16, 16, 32, 255))
    _inner_border(img)
    cfg = ART_THEMES[theme]
    _pixel_title(img, name, cfg['fill'], cfg['outline'], cfg.get('title_dy', 0))
    img = _apply_rounded(img)
    img.save(out_path)


def render_custom_banner(png_bytes, name, out_path):
    """Cover-crop arbitrary image bytes (https image) and overlay the title."""
    img = _cover_crop(Image.open(BytesIO(png_bytes)))
    region = img.crop((W // 4, H // 4, 3 * W // 4, 3 * H // 4))
    small = region.resize((8, 8)).convert('RGB')
    pixels = list(small.getdata())
    lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels) / 64
    fill = (255, 255, 255, 255) if lum < 128 else (28, 32, 64, 255)
    _inner_border(img)
    _pixel_title(img, name, fill, (15, 15, 20, 255))
    img = _apply_rounded(img)
    img.save(out_path)
