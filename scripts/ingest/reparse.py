"""Повторний розбір усіх HTML-джерел із захистом від регресій.

Навіщо окремий скрипт, а не `cli.py parse --source X` у циклі: розпізнавачі
сутностей змінюються, і після чергової зміни треба переконатися, що жодна
книга не стала коротшою. Якщо після розбору записів менше, ніж було, книга
відкочується до попереднього стану — краще стара база, ніж втрачений розділ.

Книга лежить у двох корпусах (компендіум і бестіарій), тому знімок і відкат
теж ідуть по обох: інакше відкат лишив би монстрів від невдалого розбору.

    python scripts/ingest/reparse.py            # усі книги з content/raw/*.html
    python scripts/ingest/reparse.py --source motm --source vgtm --show-text-loss

Після прогону варто перевірити, що текст не загубився:
`python scripts/ingest/verify_text.py --against <копія попереднього корпусу>`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ingest import records  # noqa: E402
from scripts.normalize import canonical  # noqa: E402

RAW = ROOT / "content" / "raw"


def corpus_dirs(spec: canonical.FormatSpec, source: str) -> list[Path]:
    """Теки цієї книги в усіх корпусах."""
    return [spec.corpus_dir(name) / source for name in spec.corpus_names()]


def snapshot(spec: canonical.FormatSpec, source: str) -> dict[str, list[dict]]:
    """Усі записи книги незалежно від корпусу: категорія -> записи."""
    rows: dict[str, list[dict]] = {}
    for directory in corpus_dirs(spec, source):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.jsonl")):
            rows[path.stem] = canonical.read_jsonl(path)
    return rows


def restore(spec: canonical.FormatSpec, source: str, rows: dict[str, list[dict]]) -> None:
    """Повертає книгу до знімка: кожна категорія — у свій корпус."""
    for directory in corpus_dirs(spec, source):
        if directory.is_dir():
            for path in directory.glob("*.jsonl"):
                path.unlink()
    for category, items in rows.items():
        directory = spec.category_dir(category, source)
        directory.mkdir(parents=True, exist_ok=True)
        canonical.write_jsonl(directory / f"{category}.jsonl", items)


def html_sources(spec: canonical.FormatSpec) -> list[str]:
    names: set[str] = set()
    for name in spec.corpus_names():
        root = spec.corpus_dir(name)
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_dir() and any(path.glob("*.jsonl")) and any((RAW / path.name).glob("*.html")):
                names.add(path.name)
    return sorted(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.ingest.reparse", description=__doc__)
    parser.add_argument("--source", action="append", default=[], help="лише ці книги")
    parser.add_argument(
        "--show-text-loss",
        action="store_true",
        help="друкувати, скільки символів додалося або зникло (дублювання сторінок теж змінює обсяг)",
    )
    args = parser.parse_args(argv)

    spec = canonical.load_spec()
    sources = args.source or html_sources(spec)
    print(f"джерел з HTML: {len(sources)}")
    restored = 0
    for source in sources:
        before = snapshot(spec, source)
        before_total = sum(len(items) for items in before.values())
        before_text = sum(len(row["text_en"]) for items in before.values() for row in items)
        try:
            records.parse_source(source)
        except Exception as exc:  # noqa: BLE001 — одна книга не має валити прогін
            restore(spec, source, before)
            restored += 1
            print(f"{source:20} ПОМИЛКА {exc!r} — лишаю як було")
            continue
        after = snapshot(spec, source)
        after_total = sum(len(items) for items in after.values())
        after_text = sum(len(row["text_en"]) for items in after.values() for row in items)
        if after_total < before_total:
            restore(spec, source, before)
            restored += 1
            print(f"{source:20} {before_total} → {after_total}, текст {before_text} → {after_text} — ВІДКАЧЕНО")
            continue
        detail = []
        for category in sorted(set(before) | set(after)):
            old = len(before.get(category, []))
            new = len(after.get(category, []))
            if old != new:
                detail.append(f"{category} {old}→{new}")
        extra = ""
        if args.show_text_loss:
            extra = f"  текст {before_text} → {after_text}"
        print(
            f"{source:20} {before_total} → {after_total} ({after_total - before_total:+d})  "
            + ", ".join(detail)
            + extra
        )
    print(f"\nкниг відкочено: {restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
