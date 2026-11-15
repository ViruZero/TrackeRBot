import io
import re

import requests
from PIL import Image, ImageDraw, ImageFont

_EMOJI_RE = re.compile("[\U0001F000-\U0010FFFF\u2600-\u27BF\uFE00-\uFE0F\u200D\u2B00-\u2BFF]")


def _strip_emoji(text):
    if text is None:
        return ""
    return _EMOJI_RE.sub("", str(text))


WIDTH = 1100
HEADER_HEIGHT = 132
ROW_HEIGHT = 152
FOOTER_HEIGHT = 56
THUMB_SIZE = 118
THUMB_X = 46
TEXT_X = 200
MAX_TITLE_WIDTH = WIDTH - 240

BG_COLOR = "#1f2124"
ACCENT_COLOR = "#3498db"
DIVIDER_COLOR = "#2b2d31"
PLACEHOLDER_COLOR = "#2b2d31"
TITLE_COLOR = "#ffffff"
LABEL_COLOR = "#b5bac1"
PRICE_COLOR = "#dfe3e8"
STATUS_TEXT_COLOR = "#f0f0f0"
QUESTION_COLOR = "#b5bac1"

STATUS_COLORS = {
    "green": "#57f287",
    "yellow": "#fee75c",
    "red": "#ed4245",
}

BOLD_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
REGULAR_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size, bold=False):
    candidates = BOLD_FONT_CANDIDATES if bold else REGULAR_FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _truncate_to_width(text, font, max_width):
    if font.getlength(text) <= max_width:
        return text
    ellipsis = "…"
    while text and font.getlength(text + ellipsis) > max_width:
        text = text[:-1]
    return text + ellipsis


def _fetch_thumbnail(img_url):
    if not img_url:
        return None
    try:
        resp = requests.get(img_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGB")
        img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        canvas = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), PLACEHOLDER_COLOR)
        offset = ((THUMB_SIZE - img.width) // 2, (THUMB_SIZE - img.height) // 2)
        canvas.paste(img, offset)
        return canvas
    except Exception:
        return None


def _rounded_thumbnail(img):
    mask = Image.new("L", (THUMB_SIZE, THUMB_SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, THUMB_SIZE - 1, THUMB_SIZE - 1], radius=18, fill=255)
    out = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), BG_COLOR)
    out.paste(img, (0, 0), mask)
    return out


def render_items_image(page_label, items, out_path):
    items = items[:10]
    height = HEADER_HEIGHT + ROW_HEIGHT * len(items) + FOOTER_HEIGHT

    img = Image.new("RGB", (WIDTH, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Left accent stripe
    draw.rectangle([0, 0, 14, height], fill=ACCENT_COLOR)

    title_font = _load_font(46, bold=True)
    label_font = _load_font(26)
    line1_font = _load_font(27, bold=True)
    line2_font = _load_font(25)
    status_font = _load_font(24)
    footer_font = _load_font(22)
    question_font = _load_font(56, bold=True)

    # Header
    draw.text((46, 26), "Your Tracked Items", font=title_font, fill=TITLE_COLOR)
    draw.text((46, 84), page_label, font=label_font, fill=LABEL_COLOR)

    for i, item in enumerate(items):
        row_top = HEADER_HEIGHT + i * ROW_HEIGHT
        if i > 0:
            draw.line([(46, row_top), (WIDTH - 46, row_top)], fill=DIVIDER_COLOR, width=1)

        thumb_y = row_top + (ROW_HEIGHT - THUMB_SIZE) // 2
        thumb = _fetch_thumbnail(item.get("img_url"))
        if thumb is not None:
            img.paste(_rounded_thumbnail(thumb), (THUMB_X, thumb_y))
        else:
            draw.rounded_rectangle(
                [THUMB_X, thumb_y, THUMB_X + THUMB_SIZE - 1, thumb_y + THUMB_SIZE - 1],
                radius=18,
                fill=PLACEHOLDER_COLOR,
            )
            draw.text(
                (THUMB_X + THUMB_SIZE / 2, thumb_y + THUMB_SIZE / 2),
                "?",
                font=question_font,
                fill=QUESTION_COLOR,
                anchor="mm",
            )

        # Line 1: id + title (truncated with ellipsis)
        title = _strip_emoji(item.get("title", ""))
        title_text = _strip_emoji(_truncate_to_width(
            f"#{item.get('id')} {title}", line1_font, MAX_TITLE_WIDTH
        ))
        draw.text((TEXT_X, row_top + 22), title_text, font=line1_font, fill=TITLE_COLOR)

        # Line 2: current price and target
        curr = item.get("curr", 0) or 0
        target = item.get("target", 0) or 0
        draw.text(
            (TEXT_X, row_top + 68),
            f"${curr:.2f}   |   Target ${target:.2f}",
            font=line2_font,
            fill=PRICE_COLOR,
        )

        # Line 3: status dot + status text
        dot_color = STATUS_COLORS.get(item.get("status_color"), LABEL_COLOR)
        dot_y = row_top + 108
        draw.ellipse([204, dot_y, 224, dot_y + 20], fill=dot_color)
        draw.text(
            (228, row_top + 106),
            _strip_emoji(item.get("status_text", "")),
            font=status_font,
            fill=STATUS_TEXT_COLOR,
        )

    # Footer
    draw.text(
        (WIDTH / 2, height - FOOTER_HEIGHT / 2),
        page_label,
        font=footer_font,
        fill=LABEL_COLOR,
        anchor="mm",
    )

    # Apply rounded-corner mask to the whole canvas
    mask = Image.new("L", (WIDTH, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, WIDTH - 1, height - 1], radius=26, fill=255)
    out = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    out.save(out_path)
    return out_path
