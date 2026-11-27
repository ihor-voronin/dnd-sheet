"""Site icons and the bot avatar: a d20 in the site's colors.

One drawing, several sizes:

    frontend/public/favicon.svg            the browser tab (scales)
    frontend/public/favicon.ico            16 + 32 + 48 for old browsers
    frontend/public/apple-touch-icon.png   180×180, iOS "add to home screen"
    frontend/public/icon-192.png           Android / manifest
    frontend/public/icon-512.png           Android / manifest (and maskable)
    branding/bot-avatar.png                640×640 for @BotFather (/setuserpic)

Colors come from theme.css: background `--paper` #11141b, faces `--brass` #d1a654,
the central face `--act` #c2323d. The drawing is our own (a d20 outline is ordinary
gaming iconography), with no Wizards of the Coast logos or artwork.

Small sizes have thicker lines and no small faces: at 16 px thin lines
blur into a blob.

    .venv/Scripts/python.exe scripts/make_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
BRANDING = ROOT / "branding"

PAPER = "#11141b"
LEAF = "#212634"
BRASS = "#d1a654"
ACT = "#c2323d"


def geometry(size: float, scale: float) -> dict[str, list[tuple[float, float]]]:
    """The d20 outline (a hexagon), the central face and the edges to the vertices."""
    cx = cy = size / 2
    r = size * scale / 2
    hexagon = [
        (cx + r * math.cos(math.radians(angle)), cy + r * math.sin(math.radians(angle)))
        for angle in (-90, -30, 30, 90, 150, 210)
    ]
    top, upper_right, lower_right, bottom, lower_left, upper_left = hexagon
    # The central face is an upward-pointing triangle slightly below center, as on a real die.
    a = (cx, cy - 0.50 * r)
    b = (cx - 0.47 * r, cy + 0.30 * r)
    c = (cx + 0.47 * r, cy + 0.30 * r)
    edges = [
        (a, top),
        (a, upper_left),
        (a, upper_right),
        (b, upper_left),
        (b, lower_left),
        (b, bottom),
        (c, upper_right),
        (c, lower_right),
        (c, bottom),
    ]
    return {"hexagon": hexagon, "face": [a, b, c], "edges": edges}  # type: ignore[dict-item]


def svg(size: int = 512, scale: float = 0.74, line: float = 14, radius: float = 96) -> str:
    g = geometry(size, scale)
    pts = lambda points: " ".join(f"{x:.1f},{y:.1f}" for x, y in points)  # noqa: E731
    edges = "".join(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>' for (x1, y1), (x2, y2) in g["edges"]
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">'
        f'<rect width="{size}" height="{size}" rx="{radius}" fill="{PAPER}"/>'
        f'<polygon points="{pts(g["hexagon"])}" fill="{LEAF}"/>'
        f'<polygon points="{pts(g["face"])}" fill="{ACT}"/>'
        f'<g stroke="{BRASS}" stroke-width="{line}" stroke-linecap="round" stroke-linejoin="round" fill="none">'
        f'{edges}<polygon points="{pts(g["face"])}"/><polygon points="{pts(g["hexagon"])}"/></g>'
        "</svg>\n"
    )


def raster(size: int, *, scale: float, line: float, radius: float, edges: bool = True) -> Image.Image:
    """Draw four times larger and downscale: that way Pillow gives smooth edges."""
    big = size * 4
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=radius * 4, fill=PAPER)
    g = geometry(big, scale)
    width = max(1, round(line * 4))
    draw.polygon(g["hexagon"], fill=LEAF)
    draw.polygon(g["face"], fill=ACT)
    if edges:
        for start, end in g["edges"]:
            draw.line((start, end), fill=BRASS, width=width)
    for shape in (g["face"], g["hexagon"]):
        closed = [*shape, shape[0]]
        draw.line(closed, fill=BRASS, width=width, joint="curve")
        for x, y in shape:  # round corners, like stroke-linejoin="round"
            draw.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=BRASS)
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    BRANDING.mkdir(parents=True, exist_ok=True)

    (PUBLIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    (BRANDING / "icon.svg").write_text(svg(), encoding="utf-8")

    # The browser tab: no small edges, only the outline and the red face — readable at 16 px.
    small = [
        raster(16, scale=0.90, line=1.7, radius=3, edges=False),
        raster(32, scale=0.88, line=1.7, radius=6),
        raster(48, scale=0.86, line=2.4, radius=9),
    ]
    small[-1].save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=small[:-1])

    # iOS rounds the corners itself and dislikes transparency — a square without rounding.
    raster(180, scale=0.74, line=7, radius=0).convert("RGB").save(PUBLIC / "apple-touch-icon.png")
    raster(192, scale=0.70, line=7.5, radius=0).save(PUBLIC / "icon-192.png")
    # 512 is also maskable: Android crops to a circle or a "drop", so the die is smaller (80% safe zone).
    raster(512, scale=0.62, line=18, radius=0).save(PUBLIC / "icon-512.png")
    # Telegram crops the avatar to a circle: the background fills the square, the die is centered.
    raster(640, scale=0.66, line=22, radius=0).convert("RGB").save(BRANDING / "bot-avatar.png")

    for path in sorted([*PUBLIC.glob("favicon.*"), *PUBLIC.glob("*icon*.png"), *BRANDING.iterdir()]):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size:,} B")


if __name__ == "__main__":
    main()
