#!/usr/bin/env python3
"""The link preview image (Open Graph, 1200×630): what Telegram, Discord and search show.

    .venv/Scripts/python.exe scripts/make_og_image.py

Left: the site's name and what it does, in the site's fonts (Alegreya from
@fontsource — `npm ci` in frontend/ first). Right: the real printed sheet
(`frontend/public/previews/sheet-front.png`). Colors are theme.css's, as in
make_icons.py; no Wizards of the Coast logos or artwork.

@fontsource splits each font into Latin and Cyrillic files, so text is drawn
character by character with the file that has the glyph.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
FONTS = ROOT / "frontend" / "node_modules" / "@fontsource"
OUT = PUBLIC / "og-image.png"

WIDTH, HEIGHT = 1200, 630
PAPER = "#11141b"
INK = "#eef0f5"
MUTED = "#a3abbd"
BRASS = "#d1a654"
ACT = "#c2323d"


def font(family: str, weight: int, size: int) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """(Latin, Cyrillic) files of one face."""
    folder = FONTS / family / "files"
    return tuple(  # type: ignore[return-value]
        ImageFont.truetype(str(folder / f"{family}-{subset}-{weight}-normal.woff"), size)
        for subset in ("latin", "cyrillic")
    )


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, faces, fill: str) -> float:  # noqa: ANN001
    """Text from (x, y) baseline-aligned per character; returns the width drawn."""
    latin, cyrillic = faces
    x, y = xy
    for char in text:
        face = cyrillic if "Ѐ" <= char <= "ӿ" or char in "ʼ" else latin
        draw.text((x, y), char, font=face, fill=fill, anchor="ls")
        x += face.getlength(char)
    return x - xy[0]


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)

    # The printed sheet on the right, slightly lifted off the background.
    sheet = Image.open(PUBLIC / "previews" / "sheet-front.png").convert("RGB")
    sheet_height = HEIGHT - 70
    sheet = sheet.resize((round(sheet.width * sheet_height / sheet.height), sheet_height), Image.LANCZOS)
    left = WIDTH - sheet.width - 48
    shadow = Image.new("RGBA", (sheet.width + 60, sheet.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((30, 30, 30 + sheet.width, 30 + sheet.height), fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    image.paste(shadow, (left - 30, 35 - 22), shadow)
    image.paste(sheet, (left, 35))

    draw = ImageDraw.Draw(image)
    icon = Image.open(PUBLIC / "icon-192.png").convert("RGBA").resize((84, 84), Image.LANCZOS)
    image.paste(icon, (64, 64), icon)

    title = font("alegreya", 800, 70)
    body = font("alegreya-sans", 400, 31)
    draw_text(draw, (64, 250), "Лист персонажа", title, INK)
    draw_text(draw, (64, 330), "D&D 5e українською", title, INK)
    draw.rectangle((64, 362, 184, 368), fill=ACT)
    for row, line in enumerate(("Створення героя за правилами 2014,", "довідник, друк — і ІІ-асистент")):
        draw_text(draw, (64, 422 + row * 42), line, body, MUTED)
    draw_text(draw, (64, 566), "dnd.voronin.app", font("alegreya-sans", 700, 30), BRASS)

    image.save(OUT, optimize=True)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
