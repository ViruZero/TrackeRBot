"""Pillow-based banner rendering for the /items shopping list command.

Self-contained module: builds themed 880x180 RGBA banner images with
multi-stop gradients, layered decorations, a soft dark title pill, and
rounded corners + an inner border frame. No bot imports.

Custom templates: drop a PNG named <theme>.png into assets/banners/ and it
is used as the background for that theme (cover-cropped). Custom URLs are
handled via render_custom_banner().
"""

import math
import random
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


def font(size):
    "Load a bold font, falling back gracefully across platforms."
    for path in FONT_CHAIN:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _gradient(stops):
    """Smooth multi-stop vertical gradient. stops = [(pos, (r,g,b)), ...], pos 0-1."""
    stops = sorted(stops, key=lambda s: s[0])
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        color = None
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                color = tuple(math.floor(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
                break
        if color is None:
            color = stops[-1][1] if t > stops[-1][0] else stops[0][1]
        draw.line([(0, y), (W, y)], fill=color)
    return img.convert('RGBA')


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


def _outline_text(draw, xy, text, fnt, fill, outline, width=4):
    "Drop shadow + 8-direction outline + center fill."
    x, y = xy
    draw.text((x + 3, y + 3), text, font=fnt, fill=(0, 0, 0, 220), anchor='mm')
    for dx in (-width, 0, width):
        for dy in (-width, 0, width):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=fnt, fill=outline, anchor='mm')
    draw.text((x, y), text, font=fnt, fill=fill, anchor='mm')


def _title(img, name):
    """Centered outlined white title."""
    draw = ImageDraw.Draw(img)
    text = name + "'s Shopping List"
    fnt = font(46)
    cx, cy = W // 2, H // 2 + 2
    _outline_text(draw, (cx, cy), text, fnt, (255, 255, 255, 255), (15, 15, 20, 255))


def _heart(draw, cx, cy, size, fill):
    half = size / 2
    draw.ellipse([cx - size, cy - half, cx, cy + half * 0.6], fill=fill)
    draw.ellipse([cx, cy - half, cx + size, cy + half * 0.6], fill=fill)
    draw.polygon([(cx - size + 1, cy), (cx + size - 1, cy), (cx, cy + size)], fill=fill)


def _star(draw, cx, cy, r, fill):
    inner = r * 0.18
    points = [
        (cx, cy - r),
        (cx + inner, cy - inner),
        (cx + r, cy),
        (cx + inner, cy + inner),
        (cx, cy + r),
        (cx - inner, cy + inner),
        (cx - r, cy),
        (cx - inner, cy - inner),
    ]
    draw.polygon(points, fill=fill)
    draw.ellipse([cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12], fill=fill)


def _glowing_crescent(draw, cx, cy, r, carve, moon=(252, 226, 150)):
    for scale, alpha in [(2.1, 26), (1.65, 20), (1.3, 14), (1.05, 10)]:
        rr = int(r * scale)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(250, 214, 130, alpha))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=moon + (255,))
    draw.ellipse([cx - r + int(r * 0.42), cy - r, cx + r + int(r * 0.42), cy + r], fill=carve)
    _star(draw, cx - int(r * 0.35), cy - int(r * 0.28), max(2, r // 4), (255, 255, 255, 230))



def _pokeball(img, draw):
    "Pokeball Red: lens + indicator lights in the pokedex panel, seam band low on the canvas."
    # diagonal shine streaks
    draw.polygon([(60, H), (330, 0), (420, 0), (150, H)], fill=(255, 255, 255, 14))
    draw.polygon([(230, H), (500, 0), (540, 0), (270, H)], fill=(255, 255, 255, 9))
    # pokedex panel
    draw.rounded_rectangle([36, 10, W - 36, 56], radius=14,
                           fill=(22, 30, 44, 255), outline=(255, 255, 255, 28), width=1)
    # corner screws
    for sx in (48, W - 48):
        draw.ellipse([sx - 2, 15, sx + 2, 19], fill=(148, 163, 184, 255))
        draw.ellipse([sx - 2, 49, sx + 2, 53], fill=(148, 163, 184, 255))
    # big lens (left)
    lcx, lcy = 96, 33
    for r, col in [(23, (226, 232, 240)), (18, (100, 116, 139)), (14, (186, 230, 253)),
                   (11, (96, 165, 250)), (7, (37, 99, 235)), (4, (30, 64, 175))]:
        draw.ellipse([lcx - r, lcy - r, lcx + r, lcy + r], fill=col + (255,))
    draw.ellipse([lcx - 8, lcy - 9, lcx + 1, lcy + 0], fill=(255, 255, 255, 200))
    # three indicator lights with glow
    for x, col in [(180, (74, 222, 128)), (218, (253, 224, 71)), (256, (248, 113, 113))]:
        draw.ellipse([x - 10, 22, x + 10, 42], fill=col + (70,))
        draw.ellipse([x - 6, 26, x + 6, 38], fill=col + (255,))
        draw.ellipse([x - 2, 29, x + 2, 33], fill=(255, 255, 255, 220))
    # status label
    draw.text((W - 130, 33), 'POKEDEX', font=font(15), fill=(148, 163, 184, 255), anchor='mm')
    # seam band, kept low so the title sits in open space
    band_y = int(H * 0.85)
    draw.rectangle([0, band_y - 6, W, band_y + 6], fill=(13, 13, 16, 255))
    draw.rectangle([0, band_y - 8, W, band_y - 6], fill=(255, 255, 255, 34))
    draw.rectangle([0, band_y + 6, W, band_y + 8], fill=(255, 255, 255, 44))


def _strawberry(img, draw):
    "Strawberry Pop: gradient berry pink, polka dots, scalloped lace top and bottom."
    dots = [(255, 255, 255, 95), (255, 255, 255, 70)]
    for row, y in enumerate(range(24, H, 46)):
        offset = 24 if row % 2 else 0
        for x in range(28 + offset, W, 46):
            r = 9 if (row + x // 46) % 3 else 12
            draw.ellipse([x - r, y - r, x + r, y + r], fill=dots[row % 2])
    # scalloped lace edges
    for x in range(-14, W + 14, 26):
        draw.pieslice([x, -12, x + 26, 14], 0, 180, fill=(255, 255, 255, 215))
        draw.pieslice([x, H - 14, x + 26, H + 12], 180, 360, fill=(255, 255, 255, 215))
        draw.ellipse([x + 9, 1, x + 15, 7], fill=(255, 226, 232, 255))
        draw.ellipse([x + 9, H - 8, x + 15, H - 2], fill=(255, 226, 232, 255))
    hearts = [(84, 128, 9), (212, 44, 7), (342, 142, 8), (480, 34, 7),
              (618, 138, 9), (764, 46, 8), (836, 142, 6)]
    for cx, cy, size in hearts:
        _heart(draw, cx, cy, size, (255, 255, 255, 225))


def _mint(img, draw):
    "Minty Pixel: mint gradient, soft checker wash, pixel ladder border, sparkles."
    for row, y in enumerate(range(0, H, 44)):
        for col, x in enumerate(range(0, W, 44)):
            if (row + col) % 2 == 0:
                draw.rectangle([x, y, x + 44, y + 44], fill=(255, 255, 255, 26))
    # pixel-ladder border (dark green square dashes)
    col = (14, 92, 55, 170)
    step = 22
    for x in range(18, W - 12, step):
        draw.rectangle([x, 11, x + 8, 19], fill=col)
        draw.rectangle([x, H - 20, x + 8, H - 12], fill=col)
    for y in range(18, H - 12, step):
        draw.rectangle([11, y, 19, y + 8], fill=col)
        draw.rectangle([W - 20, y, W - 12, y + 8], fill=col)
    # corner anchors (bigger pixels)
    for cx, cy in [(18, 18), (W - 18, 18), (18, H - 18), (W - 18, H - 18)]:
        draw.rectangle([cx - 6, cy - 6, cx + 6, cy + 6], fill=(14, 92, 55, 220))
    stars = [(96, 44, 9), (256, 142, 7), (428, 40, 8), (610, 146, 9), (796, 48, 7)]
    for cx, cy, r in stars:
        _star(draw, cx, cy, r, (255, 255, 255, 235))
    hearts = [(166, 124, 8), (348, 64, 7), (528, 132, 8), (706, 64, 7)]
    for cx, cy, size in hearts:
        _heart(draw, cx, cy, size, (14, 92, 55, 230))


def _moon(img, draw):
    "Moonlit Gold: navy multi-stop gradient, seeded starfield, glowing crescent moons."
    rng = random.Random(20261115)
    for _ in range(64):
        x, y = rng.randint(0, W), rng.randint(0, H)
        r = rng.choice([1, 1, 1, 1, 2, 2, 3])
        a = rng.randint(120, 255)
        col = (255, 236, 190, a) if rng.random() < 0.7 else (200, 220, 255, a)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col)
    for _ in range(9):
        x, y = rng.randint(20, W - 20), rng.randint(14, H - 14)
        _star(draw, x, y, rng.choice([3, 4, 5]), (255, 224, 138, 235))
    _glowing_crescent(draw, 118, 56, 24, (30, 36, 62, 255))
    _glowing_crescent(draw, 745, 118, 16, (17, 21, 45, 255))
    # faint gold horizon glint
    draw.rectangle([0, H - 4, W, H], fill=(250, 214, 130, 90))


def _hearts(img, draw):
    "Cozy Hearts: warm peach gradient, scalloped double heart rows, soft center band."
    # soft center band to seat the title
    draw.rounded_rectangle([-20, H // 2 - 25, W + 20, H // 2 + 27], radius=22,
                           fill=(255, 255, 255, 80))
    # tiny dotted texture
    for row, y in enumerate(range(18, H, 36)):
        for x in range(16 + (18 if row % 2 else 0), W, 36):
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 80))
    colors = [(248, 113, 113, 255), (236, 72, 153, 255), (254, 205, 211, 255)]
    for i, x in enumerate(range(28, W, 46)):
        _heart(draw, x, 22, 12, colors[i % 3])
        _heart(draw, x, H - 22, 12, colors[(i + 1) % 3])
        _heart(draw, x + 23, 40, 6, colors[(i + 2) % 3])
        _heart(draw, x + 23, H - 40, 6, colors[(i + 2) % 3])


THEMES = {
    'pokeball': _pokeball,
    'strawberry': _strawberry,
    'mint': _mint,
    'moon': _moon,
    'hearts': _hearts,
}

THEME_GRADIENTS = {
    'pokeball': [(0.0, (244, 108, 86)), (0.40, (198, 58, 50)), (0.78, (146, 26, 26)), (1.0, (104, 13, 13))],
    'strawberry': [(0.0, (255, 214, 224)), (0.45, (255, 150, 180)), (1.0, (255, 92, 138))],
    'mint': [(0.0, (224, 252, 236)), (0.50, (150, 234, 192)), (1.0, (74, 196, 138))],
    'moon': [(0.0, (64, 78, 120)), (0.45, (33, 41, 74)), (1.0, (11, 16, 36))],
    'hearts': [(0.0, (255, 248, 240)), (0.50, (255, 224, 200)), (1.0, (255, 192, 160))],
}

THEME_LABELS = {
    'pokeball': 'Pokeball Red',
    'strawberry': 'Strawberry Pop',
    'mint': 'Minty Pixel',
    'moon': 'Moonlit Gold',
    'hearts': 'Cozy Hearts',
}


def _template_background(theme):
    """Return assets/banners/<theme>.png cover-cropped, or None if absent."""
    path = ASSETS_DIR / f'{theme}.png'
    if not path.is_file():
        return None
    try:
        return _cover_crop(Image.open(path))
    except Exception:
        return None


def render_banner(theme, name, out_path):
    "Render the themed banner for `name` and save it to `out_path`."
    theme = theme if theme in THEMES else 'pokeball'
    template = _template_background(theme)
    if template is not None:
        img = template
    else:
        img = _gradient(THEME_GRADIENTS[theme])
        draw = ImageDraw.Draw(img)
        THEMES[theme](img, draw)
    _inner_border(img)
    _title(img, name)
    img = _apply_rounded(img)
    img.save(out_path)


def render_custom_banner(png_bytes, name, out_path):
    """Cover-crop arbitrary image bytes (https image) and overlay the title."""
    img = _cover_crop(Image.open(BytesIO(png_bytes)))
    _inner_border(img)
    _title(img, name)
    img = _apply_rounded(img)
    img.save(out_path)
