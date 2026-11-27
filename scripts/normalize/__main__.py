"""CLI формату: перевірити або привести корпуси до канону.

Обидва корпуси (довідник листа й бестіарій) обробляються разом: яка
категорія в якому корпусі живе — визначає `corpora` у контракті.

    python -m scripts.normalize --check             # що розійшлося зі специфікацією
    python -m scripts.normalize --check --source eepc
    python -m scripts.normalize --write             # привести все до канону
    python -m scripts.normalize --stats             # матриця «книга × категорія»

Код виходу: 0 — усе за каноном, 1 — є розбіжності або проблеми.
"""

from __future__ import annotations

import argparse
import collections

from . import canonical


def _all_sources(spec) -> list[str]:
    return canonical.corpus_sources(spec)


def _print_changes(source: str, changes: list[tuple[str, str, list[str]]], limit: int) -> None:
    if not changes:
        print(f"  {source}: за каноном")
        return
    kinds: collections.Counter = collections.Counter()
    for _, _, reasons in changes:
        for reason in reasons:
            key = reason.split(" (")[0]
            kinds[key.split(":")[0] if reason.startswith(("data", "text_en")) else key] += 1
    summary = ", ".join(f"{name}×{count}" for name, count in kinds.most_common())
    print(f"  {source}: {len(changes)} записів розійшлися — {summary}")
    for category, record_id, reasons in changes[:limit]:
        print(f"    [{category}] {record_id}")
        for reason in reasons:
            print(f"      - {reason}")


def _stats(spec, sources: list[str]) -> None:
    # Ширина колонки — за найдовшою назвою категорії (+1 пробіл-розділювач):
    # `optionalfeature` довше за 12 символів, і з фіксованою шириною заголовок
    # наїжджав на сусідній.
    width = max([12] + [len(name) + 1 for name in spec.categories_ordered()])
    header = f"{'книга':20}" + "".join(f"{name:>{width}}" for name in spec.categories_ordered())
    print(header + f"{'разом':>9}")
    totals: collections.Counter = collections.Counter()
    for source in sources:
        counts = collections.Counter()
        for corpus in spec.corpus_names():
            directory = spec.corpus_dir(corpus) / source
            if not directory.is_dir():
                continue
            for category in canonical.categories_of(directory):
                counts[category] += len(canonical.read_jsonl(directory / f"{category}.jsonl"))
        line = f"{source:20}" + "".join(f"{(counts[name] or ''):>{width}}" for name in spec.categories_ordered())
        print(line + f"{sum(counts.values()):>9}")
        totals.update(counts)
    line = f"{'РАЗОМ':20}" + "".join(f"{(totals[name] or ''):>{width}}" for name in spec.categories_ordered())
    print(line + f"{sum(totals.values()):>9}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.normalize", description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="перевірити (типово)")
    mode.add_argument("--write", action="store_true", help="привести корпус до канону")
    mode.add_argument("--stats", action="store_true", help="матриця «книга × категорія»")
    parser.add_argument("--source", action="append", default=[], help="лише ці книги")
    parser.add_argument("--limit", type=int, default=5, help="скільки прикладів друкувати")
    parser.add_argument("--spec", default=None, help="альтернативний файл специфікації")
    args = parser.parse_args(argv)

    spec = canonical.load_spec(args.spec)
    sources = args.source or _all_sources(spec)
    if args.stats:
        _stats(spec, sources)
        return 0

    write = bool(args.write)
    print(("запис: " if write else "перевірка: ") + f"{len(sources)} книг")
    total_changed = 0
    problems: list[str] = []
    for source in sources:
        count, changes, source_problems = canonical.normalize_source(source, spec, write=write)
        total_changed += count
        problems.extend(source_problems)
        _print_changes(source, changes, args.limit)

    print()
    if problems:
        print(f"ПРОБЛЕМИ: {len(problems)}")
        for problem in problems[:20]:
            print(f"  {problem}")
    if write:
        print(f"переписано записів: {total_changed}")
        return 0 if not problems else 1
    if total_changed:
        print(f"розбіжностей: {total_changed} (виправляє `python -m scripts.normalize --write`)")
        return 1
    print("корпус за каноном")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
