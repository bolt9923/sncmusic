"""
helpers/thumbnail.py — Generate custom now-playing thumbnail cards using Pillow
Falls back gracefully if Pillow or fonts are unavailable.
"""

import io
import os
import textwrap
from typing import Optional

from helpers.logger import LOGGER

log = LOGGER(__name__)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import aiohttp
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    log.warning("Pillow not available. Thumbnail generation disabled.")

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")

# Card dimensions
CARD_W, CARD_H = 1280, 720


def _load_font(size: int, bold: bool = False) -> Optional[object]:
    """Try to load a TTF font; fall back to default."""
    if not PILLOW_AVAILABLE:
        return None
    candidates = [
        os.path.join(FONT_DIR, "Bold.ttf" if bold else "Regular.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


async def _fetch_image_bytes(url: str) -> Optional[bytes]:
    """Download image from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        log.warning(f"Thumbnail fetch error: {e}")
    return None


async def generate_now_playing_card(
    title: str,
    requester: str,
    duration_str: str,
    thumbnail_url: Optional[str] = None,
) -> Optional[bytes]:
    """
    Generate a 1280×720 now-playing card image.
    Returns JPEG bytes or None if generation fails.
    """
    if not PILLOW_AVAILABLE:
        return None

    try:
        # Base: dark gradient background
        card = Image.new("RGB", (CARD_W, CARD_H), color=(15, 15, 25))
        draw = ImageDraw.Draw(card)

        # Background gradient (simple top-to-bottom)
        for y in range(CARD_H):
            ratio = y / CARD_H
            r = int(15 + (30 - 15) * ratio)
            g = int(15 + (20 - 15) * ratio)
            b = int(25 + (45 - 25) * ratio)
            draw.line([(0, y), (CARD_W, y)], fill=(r, g, b))

        # Thumbnail (left side, blurred background effect)
        thumb_x, thumb_y = 60, 120
        thumb_size = 480

        if thumbnail_url:
            img_bytes = await _fetch_image_bytes(thumbnail_url)
            if img_bytes:
                try:
                    thumb = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    # Blurred background
                    bg = thumb.resize((CARD_W, CARD_H)).filter(ImageFilter.GaussianBlur(40))
                    bg_overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 160))
                    card.paste(bg, (0, 0))
                    card.paste(Image.new("RGB", (CARD_W, CARD_H), (0, 0, 0)), mask=bg_overlay)

                    # Main thumbnail (rounded corners via mask)
                    thumb_sq = thumb.resize((thumb_size, thumb_size))
                    # Simple rounded corner mask
                    mask = Image.new("L", (thumb_size, thumb_size), 0)
                    m_draw = ImageDraw.Draw(mask)
                    radius = 30
                    m_draw.rounded_rectangle([(0, 0), (thumb_size, thumb_size)], radius=radius, fill=255)
                    card.paste(thumb_sq, (thumb_x, thumb_y), mask)
                except Exception as e:
                    log.debug(f"Thumbnail paste error: {e}")

        # Text area
        text_x = 600
        font_title = _load_font(52, bold=True)
        font_sub = _load_font(34)
        font_small = _load_font(28)

        # Title (wrap at ~30 chars)
        wrapped = textwrap.fill(title, width=28)
        draw.text((text_x, 200), wrapped, font=font_title, fill=(255, 255, 255))

        # Requester
        draw.text((text_x, 420), f"Requested by  {requester}", font=font_sub, fill=(180, 180, 210))

        # Duration
        draw.text((text_x, 480), f"⏱  {duration_str}", font=font_small, fill=(140, 200, 255))

        # Decorative accent line
        draw.rectangle([(text_x, 180), (text_x + 6, 390)], fill=(108, 99, 255))

        # "NOW PLAYING" label
        font_label = _load_font(24)
        draw.text((text_x, 155), "▶  NOW PLAYING", font=font_label, fill=(108, 99, 255))

        # Export
        output = io.BytesIO()
        card.save(output, format="JPEG", quality=92)
        return output.getvalue()

    except Exception as e:
        log.error(f"Card generation error: {e}", exc_info=True)
        return None
