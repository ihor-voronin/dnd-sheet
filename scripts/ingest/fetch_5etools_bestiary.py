"""Довантажити статблоки (bestiary) для книг, які вже є в content/raw.

Індекс дзеркала data/bestiary/index.json зіставляє source → файл. Беремо лише
для книг, чий текст уже лежить у content/raw (тобто тих, що ми свідомо взяли),
і кладемо поруч: content/raw/<тека>/bestiary-<source>.json.

Запуск:  python scripts/ingest/fetch_5etools_bestiary.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ingest.fetch_5etools import ROOT, fetch  # noqa: E402

IDX = ROOT / "content" / "raw" / "_index"

# У файлах Plane Shift книга зветься PS-A…PS-X, а в корпусах — PSA…PSX.
ALIASES = {"PSA": "PS-A", "PSI": "PS-I", "PSK": "PS-K", "PSD": "PS-D",
           "PSZ": "PS-Z", "PSX": "PS-X"}


def id_to_dir() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (ROOT / "content" / "raw").glob("*/*.json"):
        if path.name.startswith("bestiary-"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("bookData", "adventureData"):
            for entry in data.get(key, []) if isinstance(data.get(key), list) else []:
                if isinstance(entry, dict) and entry.get("id"):
                    found.setdefault(entry["id"], path.parent.name)
    return found


def main() -> None:
    index = json.loads((IDX / "mirror-bestiary-index.json").read_text(encoding="utf-8"))
    mapping = id_to_dir()
    total = blocks = 0
    for source, filename in sorted(index.items()):
        folder = mapping.get(source) or mapping.get(ALIASES.get(source, ""))
        if not folder:
            continue
        dest = ROOT / "content" / "raw" / folder / filename
        if not dest.exists():
            try:
                total += fetch("bestiary/" + filename, dest)
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {source}: {exc}")
                continue
        data = json.loads(dest.read_text(encoding="utf-8"))
        n = len(data.get("monster", []))
        blocks += n
        print(f"{source:12s} {folder:14s} {filename:26s} {n:4d} статблоків")
    print(f"\nразом: {blocks} статблоків, довантажено {total // 1024} KB")


if __name__ == "__main__":
    main()
