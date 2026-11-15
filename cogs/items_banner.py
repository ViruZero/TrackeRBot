"""Pillow-based banner rendering for the /items shopping list command.

Self-contained module: builds themed 880x180 banner images with gradients,
decorative shapes, and outlined title text. No bot imports, no external assets.
"""

import math

from PIL import Image, ImageDraw, ImageFont

W, H = 880, 180


def _vertical_gradient(top_rgb, bottom_rgb):
    "Build an 880x180 RGB image by lerping rows between two colors."
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        r = math.floor(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = math.floor(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = math.floor(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _outline_text(draw, xy, text, font, fill, outline, width=3):
    "Draw text with an 8-direction outline stroke, then the center fill."
    x, y = xy
    for dx in (-width, 0, width):
        for dy in (-width, 0, width):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline, anchor='mm')
    draw.text((x, y), text, font=font, fill=fill, anchor='mm')


def _heart(draw, cx, cy, size, fill):
    "Draw a heart from two ellipses (lobes) and one polygon (point)."
    half = size / 2
    draw.ellipse([cx - size, cy - half, cx, cy + half * 0.6], fill=fill)
    draw.ellipse([cx, cy - half, cx + size, cy + half * 0.6], fill=fill)
    draw.polygon([(cx - size + 1, cy), (cx + size - 1, cy), (cx, cy + size)], fill=fill)


def _crescent(draw_on, cx, cy, r, moon, background):
    "Draw a full circle, then carve a crescent with a background-colored offset circle."
    draw_on.ellipse([cx - r, cy - r, cx + r, cy + r], fill=moon)
    offset = r * 0.45
    draw_on.ellipse([cx - r + offset, cy - r, cx + r + offset, cy + r], fill=background)


def _star(draw, cx, cy, r, fill):
    "Draw a 4-point sparkle: a cross polygon plus a small center dot."
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


def font(size):
    "Load a bold font, falling back gracefully across platforms."
    try:
        return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', size)
    except OSError:
        try:
            return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', size)
        except OSError:
            return ImageFont.load_default()


def _pokeball(img, draw):
    "Pokeball Red: red gradient, black band, dark top panel with tiny status dots."
    line_y = int(H * 0.62)
    draw.rectangle([0, line_y - 6, W, line_y + 6], fill=(17, 17, 17))
    draw.rounded_rectangle([40, 8, W - 40, 54], radius=12, fill=(31, 41, 55))
    cluster = [
        (70, 31, (74, 222, 128)),
        (95, 31, (253, 224, 71)),
        (120, 31, (250, 204, 21)),
    ]
    for cx, cy, color in cluster:
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=color)


def _strawberry(img, draw):
    "Strawberry Pop: pink gradient, white polka dots, scattered white hearts."
    for row, y in enumerate(range(20, H, 44)):
        offset = 22 if row % 2 else 0
        for x in range(20 + offset, W, 44):
            draw.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 255, 255))
    hearts = [
        (80, 130, 10), (200, 40, 8), (330, 140, 9), (470, 30, 8),
        (610, 135, 10), (760, 45, 9), (830, 140, 7),
    ]
    for cx, cy, size in hearts:
        _heart(draw, cx, cy, size, (255, 255, 255))


def _mint(img, draw):
    "Minty Pixel: mint gradient, checkerboard squares, sparkles and dark green hearts."
    for row, y in enumerate(range(0, H, 60)):
        for col, x in enumerate(range(0, W, 60)):
            if (row + col) % 2 == 0:
                draw.rectangle([x, y, x + 60, y + 60], fill=(63, 174, 120))
    stars = [
        (90, 40, 10), (250, 140, 8), (420, 35, 9), (600, 145, 10), (790, 45, 8),
    ]
    for cx, cy, r in stars:
        _star(draw, cx, cy, r, (255, 255, 255))
    hearts = [
        (160, 120, 8), (340, 60, 7), (520, 130, 8), (700, 60, 7),
    ]
    for cx, cy, size in hearts:
        _heart(draw, cx, cy, size, (14, 92, 55))


def _moon(img, draw):
    "Moonlit Gold: deep navy gradient, gold stars, two crescents, tiny gold dots."
    stars = [
        (60, 30, 6), (180, 140, 5), (260, 50, 8), (350, 120, 4), (430, 30, 6),
        (520, 150, 5), (610, 40, 7), (700, 150, 4), (820, 60, 6),
        (300, 90, 3), (660, 100, 3),
    ]
    for cx, cy, r in stars:
        _star(draw, cx, cy, r, (255, 217, 138))
    _crescent(draw, 120, 60, 26, (245, 199, 107), (29, 36, 69))
    _crescent(draw, 740, 120, 18, (245, 199, 107), (16, 23, 54))
    dots = [
        (150, 110), (230, 80), (390, 70), (480, 110),
        (580, 80), (770, 40), (840, 130), (90, 150),
    ]
    for cx, cy in dots:
        draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 217, 138))


def _hearts(img, draw):
    "Cozy Hearts: peach gradient, alternating heart rows along top and bottom."
    colors = [(248, 113, 113), (236, 72, 153)]
    for i, x in enumerate(range(30, W, 60)):
        _heart(draw, x, 28, 12, colors[i % 2])
        _heart(draw, x, H - 28, 12, colors[(i + 1) % 2])


THEMES = {
    'pokeball': _pokeball,
    'strawberry': _strawberry,
    'mint': _mint,
    'moon': _moon,
    'hearts': _hearts,
}

THEME_GRADIENTS = {
    'pokeball': ((210, 56, 56), (122, 13, 13)),
    'strawberry': ((255, 179, 200), (255, 92, 138)),
    'mint': ((200, 247, 220), (84, 201, 143)),
    'moon': ((35, 44, 78), (11, 16, 36)),
    'hearts': ((255, 243, 230), (255, 201, 179)),
}

THEME_TEXT_COLORS = {
    'pokeball': ((255, 255, 255), (17, 17, 17)),
    'strawberry': ((255, 255, 255), (138, 16, 50)),
    'mint': ((5, 59, 34), (234, 255, 243)),
    'moon': ((255, 233, 176), (58, 42, 8)),
    'hearts': ((127, 29, 29), (255, 255, 255)),
}

THEME_LABELS = {
    'pokeball': 'Pokeball Red',
    'strawberry': 'Strawberry Pop',
    'mint': 'Minty Pixel',
    'moon': 'Moonlit Gold',
    'hearts': 'Cozy Hearts',
}


def render_banner(theme, name, out_path):
    "Render the themed banner for `name` and save it to `out_path`."
    theme = theme if theme in THEMES else 'pokeball'
    top_rgb, bottom_rgb = THEME_GRADIENTS[theme]
    img = _vertical_gradient(top_rgb, bottom_rgb)
    draw = ImageDraw.Draw(img)
    THEMES[theme](img, draw)
    fill, outline = THEME_TEXT_COLORS[theme]
    _outline_text(draw, (W // 2, H // 2 + 10), name + "'s Shopping List", font(64), fill, outline)
    img.save(out_path)
