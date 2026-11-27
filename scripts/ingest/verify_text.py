"""Перевірка, що повторна збірка корпусу не загубила тексту книг.

Порівнює два стани корпусу (наприклад, копію до перерозбору й поточний) і для
кожної книги шукає кожен абзац старого запису в новому тексті тієї самої книги.
Абзац у 120+ символів, якого немає ніде в книзі, — це втрачений текст, і його
треба подивитися очима.

Книга може лежати у двох корпусах (компендіум і бестіарій), тому стан — це
набір корпусів, а не одна тека: поточний стан береться з контракту, а
`--against` приймає або теку корпусу, або теку, у якій лежать `compendium/` і
`bestiary/` поруч.

    python scripts/ingest/verify_text.py --against logs/_corpus_before

М'які переноси (`U+00AD`) і пробіли перед порівнянням прибираються: книги
набирають їх по-різному, а для читача це той самий текст.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical  # noqa: E402

MIN_PARAGRAPH = 120


def compact(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def paragraphs(directory: Path) -> list[tuple[str, str]]:
    """(id запису, абзац) для кожного абзацу довшого за MIN_PARAGRAPH."""
    out: list[tuple[str, str]] = []
    for path in sorted(directory.glob("*.jsonl")):
        for row in canonical.read_jsonl(path):
            for block in re.split(r"\n\s*\n", row["text_en"]):
                key = compact(block)
                if len(key) >= MIN_PARAGRAPH:
                    out.append((row["id"], key))
    return out


def records_text(directory: Path) -> dict[str, str]:
    return {
        row["id"]: compact(row["text_en"])
        for path in sorted(directory.glob("*.jsonl"))
        for row in canonical.read_jsonl(path)
    }


def haystack(directory: Path) -> str:
    return "\n".join(records_text(directory).values())


def state_books(root: Path) -> dict[str, list[Path]]:
    """Книга -> теки, у яких вона лежить (їх може бути дві — по корпусах).

    `root` — або тека одного корпусу (`<книга>/*.jsonl`), або тека, у якій
    лежать теки корпусів.
    """
    books: dict[str, list[Path]] = {}

    def collect(container: Path) -> None:
        for path in sorted(container.iterdir()):
            if path.is_dir() and any(path.glob("*.jsonl")):
                books.setdefault(path.name, []).append(path)

    if not root.is_dir():
        return books
    nested = [root / name for name in ("compendium", "bestiary") if (root / name).is_dir()]
    for container in nested or [root]:
        collect(container)
    return books


def current_books(spec: canonical.FormatSpec) -> dict[str, list[Path]]:
    books: dict[str, list[Path]] = {}
    for name in spec.corpus_names():
        for book, dirs in state_books(spec.corpus_dir(name)).items():
            books.setdefault(book, []).extend(dirs)
    return books


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scripts.ingest.verify_text", description=__doc__)
    parser.add_argument(
        "--against",
        action="append",
        required=True,
        help="стан до зміни: тека корпусу (можна кілька — компендіум і бестіарій окремо)",
    )
    parser.add_argument("--show", type=int, default=3, help="скільки прикладів друкувати")
    parser.add_argument(
        "--ratio", type=float, default=0.9, help="поріг схожості для «абзац виправлено, а не втрачено»"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    old_books: dict[str, list[Path]] = {}
    for raw_path in args.against:
        root = Path(raw_path)
        if not root.is_dir():
            print(f"немає каталогу {root}", file=sys.stderr)
            return 2
        for book, dirs in state_books(root).items():
            old_books.setdefault(book, []).extend(dirs)

    new_books = current_books(canonical.load_spec())

    lost = 0
    changed = 0
    missing_sources = 0
    for book in sorted(old_books):
        new_dirs = new_books.get(book) or []
        if not new_dirs:
            print(f"{book:20} зникла ціла книга")
            missing_sources += 1
            continue
        stack = "\n".join(haystack(directory) for directory in new_dirs)
        texts: dict[str, str] = {}
        for directory in new_dirs:
            texts.update(records_text(directory))
        source_lost: list[str] = []
        source_changed: list[str] = []
        for directory in old_books[book]:
            for record_id, key in paragraphs(directory):
                if key in stack:
                    continue
                replacement = texts.get(record_id, "")
                similarity = difflib.SequenceMatcher(None, key, replacement).ratio() if replacement else 0.0
                if similarity >= args.ratio:
                    source_changed.append(f"{record_id}: {key[:80]}")
                else:
                    source_lost.append(f"{record_id}: {key[:80]}")
        if source_lost:
            print(f"{book:20} ВТРАЧЕНО абзаців: {len(source_lost)}")
            for line in source_lost[: args.show]:
                print(f"    {line}")
        lost += len(source_lost)
        changed += len(source_changed)

    print()
    print(f"виправлено абзаців (той самий запис, інший текст): {changed}")
    if lost or missing_sources:
        print(f"ВТРАЧЕНО: {lost} абзаців, книг зникло: {missing_sources}")
        return 1
    print("текст збережено повністю")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
