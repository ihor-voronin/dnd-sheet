"""Probe a PDF: pages, metadata, whether it carries a real text layer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

src = Path(sys.argv[1])
out = Path(sys.argv[2])
doc = pymupdf.open(src)

info = {
    "pages": doc.page_count,
    "metadata": doc.metadata,
    "toc": doc.get_toc()[:40],
    "chars_total": 0,
    "pages_detail": [],
}
for index in range(doc.page_count):
    page = doc[index]
    text = page.get_text("text")
    info["chars_total"] += len(text)
    info["pages_detail"].append(
        {
            "page": index + 1,
            "chars": len(text),
            "images": len(page.get_images(full=True)),
            "head": text.strip().splitlines()[:5],
        }
    )
out.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print("pages", info["pages"], "chars", info["chars_total"])
print("empty pages", [p["page"] for p in info["pages_detail"] if p["chars"] < 40])
print("toc", info["toc"][:12])
