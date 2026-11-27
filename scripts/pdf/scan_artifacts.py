"""Scan item texts for residual OCR artifacts before publishing them."""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import despace  # noqa: E402

PATH = pathlib.Path(r"C:\Users\User\Desktop\work_docs\dnd-sheet\content\compendium\gotg\item.jsonl")
PATTERNS = {
    "trailing caps heading": r"[A-Z][A-Z'’]{2,}(?:\s+[A-Za-z'’]{1,}){1,4}\s*$",
    "stray symbols": r"[<>|~]{1,}",
    "double punctuation": r"[,.;:]\s*[,.;:]",
    "glued sentence": r"[a-z]\.[A-Z]",
    "lowercase s in caps heading": r"[A-Z]{3,}s\b",
}
GLUE = re.compile(r"\b[a-z]{3,}(?:and|the|to|in|on|at|is|has|it)\b")

vocab = despace.build_vocab()
for line in PATH.read_text(encoding="utf-8").splitlines():
    record = json.loads(line)
    text = record["text_en"]
    hits = []
    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            hits.append(f"{label}: {match.group(0)!r}")
    # Only flag a glued pair when the whole token is not a real word, otherwise
    # every "action" and "weapon" (ends with "on") would be reported.
    for match in GLUE.finditer(text):
        for piece in match.group(0).split():
            if piece.lower() not in vocab:
                hits.append(f"glued function word: {piece!r}")
    if hits:
        print(record["name_en"])
        for hit in sorted(set(hits)):
            print("   ", hit)
