"""Dump a text-layer PDF page by page, so the structure can be read directly."""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

src = Path(sys.argv[1])
out = Path(sys.argv[2])
first = int(sys.argv[3]) if len(sys.argv) > 3 else 1
last = int(sys.argv[4]) if len(sys.argv) > 4 else 10**6

doc = pymupdf.open(src)
chunks = []
for index in range(first - 1, min(last, doc.page_count)):
    text = doc[index].get_text("text")
    chunks.append(f"===== page {index + 1} =====\n{text}")
body = "\n".join(chunks)
out.write_text(body, encoding="utf-8")
print("chars", len(body), "pages", len(chunks))
