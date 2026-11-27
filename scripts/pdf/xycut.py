"""Reading order by recursive XY-cut.

OCR gives line boxes in no useful order. Splitting the page recursively on the
widest horizontal then vertical whitespace gap recovers the reading order for
arbitrary layouts: full-width headers, two-column body text, sidebars, table
rows and captions all fall out naturally, without a hard-coded gutter.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class Line:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float = 1.0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def w(self) -> float:
        return self.x1 - self.x0


def _largest_gap(spans: list[tuple[float, float]], min_gap: float) -> tuple[float, float] | None:
    """Widest hole between merged intervals: (gap, split coordinate)."""
    if not spans:
        return None
    spans = sorted(spans)
    best: tuple[float, float] | None = None
    reach = spans[0][1]
    for start, end in spans[1:]:
        gap = start - reach
        if gap >= min_gap and (best is None or gap > best[0]):
            best = (gap, (reach + start) / 2)
        reach = max(reach, end)
    return best


def cut(lines: list[Line], med_h: float, width: float, depth: int = 0) -> list[list[Line]]:
    """Return blocks of lines in reading order (each block is one paragraph)."""
    if not lines:
        return []
    if len(lines) == 1 or depth > 12:
        return [sorted(lines, key=lambda line: (line.y0, line.x0))]

    # Horizontal first: paragraphs, rows, stacked bands.
    gap = _largest_gap([(line.y0, line.y1) for line in lines], med_h * 0.55)
    if gap is not None and len(lines) >= 2:
        split_y = gap[1]
        top = [line for line in lines if line.y1 <= split_y]
        bottom = [line for line in lines if line.y1 > split_y]
        if top and bottom:
            return cut(top, med_h, width, depth + 1) + cut(bottom, med_h, width, depth + 1)

    # Vertical next: columns, sidebar next to body text, table cells.
    gap = _largest_gap([(line.x0, line.x1) for line in lines], max(med_h * 0.8, width * 0.012))
    if gap is not None:
        split_x = gap[1]
        left = [line for line in lines if line.x1 <= split_x]
        right = [line for line in lines if line.x1 > split_x]
        if left and right:
            return cut(left, med_h, width, depth + 1) + cut(right, med_h, width, depth + 1)

    return [sorted(lines, key=lambda line: (line.y0, line.x0))]


def is_heading(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) > 0.85 and len(text) < 70


def render(lines: list[Line], width: float) -> str:
    """Join the lines of one block into a paragraph, fixing hyphenation."""
    heights = [line.h for line in lines if 0 < line.h < width * 0.25]
    med_h = statistics.median(heights) if heights else 18.0
    ordered = sorted(lines, key=lambda line: (round(line.y0 / max(med_h, 1)), line.x0))
    text = ""
    for line in ordered:
        piece = line.text.strip()
        if not piece:
            continue
        if not text:
            text = piece
        elif text.endswith("-") and piece[:1].islower():
            text = text[:-1] + piece
        else:
            text = text + " " + piece
    return " ".join(text.split())


def blocks_to_markdown(lines: list[Line], width: float) -> list[str]:
    out: list[str] = []
    med_h = _med_h(lines)
    for block in cut(lines, med_h, width):
        ordered = sorted(block, key=lambda line: (line.y0, line.x0))
        # A run-in display heading often shares a block with the body text that
        # follows it (no whitespace gap); peel it off so it marks a section.
        while len(ordered) > 1 and is_heading(ordered[0].text):
            out.append("### " + render([ordered[0]], width).title())
            ordered = ordered[1:]
        if not ordered:
            continue
        text = render(ordered, width)
        if not text:
            continue
        if len(ordered) == 1 and is_heading(text):
            out.append("### " + text.title())
        else:
            out.append(text)
    return out


def _med_h(lines: list[Line]) -> float:
    heights = [line.h for line in lines if 0 < line.h < 200]
    return statistics.median(heights) if heights else 18.0
