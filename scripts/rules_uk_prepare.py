"""Підготувати тексти заклять, рис і опційних умінь до перекладу.

Ключ перекладу — `sha1(оригіналу)[:10]`, як в усіх шарах (`uk_text.ident`):

* закляття — тіло опису без першого рядка «3rd-level evocation» (той самий
  `_body`, що віддає API) і окремо абзац «At Higher Levels»;
* риси й опційні вміння — повний `text_en` запису.

    python scripts/rules_uk_prepare.py [--missing]

Пише `var/uk/<шар>/input/texts-NN.json` (черги ~10 тис. символів) і словник
назв `var/uk/NAMES.md` (закляття, риси, вибори класу: English → українська),
щоб усі перекладачі називали закляття в тексті однаково. `--missing` бере лише
те, чого ще немає в `content/translations/<шар>/`.
"""

from __future__ import annotations

import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

# Той самий `_body`, що віддає API: інакше хеш перекладу не збігся б з екраном.
from dndsheet.characters.api.spell_meta import _body as body  # noqa: E402

CHARS_PER_CHUNK = 10_000


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def records(category: str) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(str(ROOT / "content" / "compendium" / "*" / f"{category}.jsonl"))):
        with open(path, encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def done(layer: str) -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "content" / "translations" / layer).glob("texts-*.json"):
        for row in json.loads(path.read_text(encoding="utf-8")):
            if str(row.get("text_uk") or "").strip():
                keys.add(str(row["id"]))
    return keys


def collect() -> dict[str, list[dict]]:
    layers: dict[str, dict[str, dict]] = {"spells": {}, "feats": {}, "optional-features": {}}
    for entry in records("spell"):
        text = body(entry.get("text_en") or "")
        if text:
            layers["spells"].setdefault(ident(text), {"id": ident(text), "name_en": entry["name_en"], "text_en": text})
        higher = str((entry.get("data") or {}).get("at_higher_levels") or "").strip()
        if higher:
            layers["spells"].setdefault(
                ident(higher),
                {"id": ident(higher), "name_en": f"{entry['name_en']} — At Higher Levels", "text_en": higher},
            )
    for category, layer in (("feat", "feats"), ("optionalfeature", "optional-features")):
        for entry in records(category):
            text = str(entry.get("text_en") or "").strip()
            if text:
                layers[layer].setdefault(
                    ident(text), {"id": ident(text), "name_en": entry["name_en"], "text_en": text}
                )
    return {layer: sorted(items.values(), key=lambda item: item["name_en"]) for layer, items in layers.items()}


def write_chunks(layer: str, items: list[dict]) -> int:
    folder = ROOT / "var" / "uk" / layer / "input"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("texts-*.json"):
        old.unlink()
    chunks: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for item in items:
        length = len(item["text_en"])
        if current and size + length > CHARS_PER_CHUNK:
            chunks.append(current)
            current, size = [], 0
        current.append(item)
        size += length
    if current:
        chunks.append(current)
    for number, chunk in enumerate(chunks, start=1):
        path = folder / f"texts-{number:02d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(chunks)


def write_names() -> None:
    """Словник назв для перекладачів: закляття, риси, вибори класу."""
    lines = ["# Назви (згенеровано scripts/rules_uk_prepare.py — не правити)", ""]
    for layer, title in (("spells", "Закляття"), ("feats", "Риси"), ("optional-features", "Вибори класу")):
        path = ROOT / "content" / "translations" / layer / "names.json"
        rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        lines += [f"## {title}", "", "| English | Українською |", "|---|---|"]
        lines += [
            f"| {row.get('en', '')} | {row.get('name_uk', '')} |"
            for row in rows
            if row.get("en") and row.get("name_uk")
        ]
        lines.append("")
    (ROOT / "var" / "uk" / "NAMES.md").write_text("\n".join(lines), encoding="utf-8")


def main(missing: bool) -> None:
    for layer, items in collect().items():
        if missing:
            finished = done(layer)
            items = [item for item in items if item["id"] not in finished]
        count = write_chunks(layer, items)
        print(f"{layer}: {len(items)} текстів, {sum(len(i['text_en']) for i in items)} символів, {count} черг")
    write_names()


if __name__ == "__main__":
    main("--missing" in sys.argv)
