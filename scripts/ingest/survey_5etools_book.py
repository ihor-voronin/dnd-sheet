"""Що дає одна книга з дзеркала 5e.tools: посилання, згруповані за типом.

Файл книги не містить тексту статблоків і предметів — лише вузли-посилання
(`{"type":"statblock","tag":"creature","name":…,"source":…}`) і теги в тексті
(`{@item …}`). Тому тут рахуються саме посилання: це і є перелік того, що книгу
треба доєднати до тематичних корпусів (bestiary/items/feats/backgrounds).

Запуск:
  python scripts/ingest/survey_5etools_book.py content/raw/toa/adventure-toa.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TAG = re.compile(
    r"\{@(creature|item|spell|feat|background|subclass|class|race|condition|"
    r"object|vehicle|vehupgrade|reward|deity|boon|table|variantrule)\s+([^}|]+)"
)

# скільки inline-тегів показувати в рядку (решта — лише кількість)
SHOW_LIMIT = 16


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    refs = defaultdict(set)  # вузли statblock: точний перелік самостійних записів
    inline = defaultdict(set)  # теги в тексті: посилання на чужі записи
    ref_count = 0

    def walk(node):
        nonlocal ref_count
        if isinstance(node, dict):
            if node.get("type") == "statblock" and isinstance(node.get("tag"), str):
                refs[node["tag"]].add(str(node.get("name")))
                ref_count += 1
            if isinstance(node.get("entries"), list):
                for entry in node["entries"]:
                    if isinstance(entry, str):
                        for m in TAG.finditer(entry):
                            inline[m.group(1)].add(m.group(2).strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    print(f"файл: {path.name} ({path.stat().st_size // 1024} KB) | statblock-посилань: {ref_count}")
    for tag in sorted(refs):
        names = sorted(refs[tag])
        print(f"  ref {tag:11s} {len(names):3d}: " + ", ".join(names))
    for tag in sorted(inline):
        names = sorted(inline[tag])
        if len(names) > 2:
            shown = ", ".join(names[:SHOW_LIMIT])
            more = "" if len(names) <= SHOW_LIMIT else f" … (+{len(names) - SHOW_LIMIT})"
            print(f"  inl {tag:11s} {len(names):3d}: {shown}{more}")


if __name__ == "__main__":
    main()
