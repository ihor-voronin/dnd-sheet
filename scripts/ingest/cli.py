"""CLI конвеєра ingest.

Приклади:
    python -m scripts.ingest.cli discover --source phb-2014
    python -m scripts.ingest.cli fetch    --source phb-2014
    python -m scripts.ingest.cli parse    --source phb-2014
    python -m scripts.ingest.cli run      --source phb-2014 --delay 1.5
    python -m scripts.ingest.cli all      --tiers 1,1.5,2
    python -m scripts.ingest.cli verify
    python -m scripts.ingest.cli index
"""

from __future__ import annotations

import argparse
import json
import sys

import yaml

from ..normalize import canonical as compendium_format
from . import closure, config, discover, fetch, indexes, records, session


def _sources_by_tier(tiers: set[str]) -> list[str]:
    raw = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    selected: list[str] = []
    for entry in raw.get("sources", []):
        if entry.get("scope") == "excluded":
            continue
        tier = entry.get("tier")
        if tiers and str(tier) not in tiers:
            continue
        selected.append(entry["id"])
    return selected


def _run_discover(source: str, fetcher: session.Fetcher) -> None:
    print(f"[discover] {source}", flush=True)
    paths = discover.discover(fetcher, source)
    target = discover.save_index(source, paths)
    print(f"  сторінок: {len(paths)} → {target.name}", flush=True)


def _run_fetch(source: str, fetcher: session.Fetcher, refresh: bool) -> None:
    print(f"[fetch] {source}", flush=True)
    state = fetch.fetch_all(fetcher, source, refresh=refresh)
    print(f"  готово: {len(state['done'])}, збоїв: {len(state['failed'])}", flush=True)


def _run_parse(source: str) -> None:
    print(f"[parse] {source}", flush=True)
    counters = records.parse_source(source)
    print(f"  {records.summarize(counters)}", flush=True)
    problems = records.validate_source(source)
    if problems:
        print(f"  ВАЛІДАЦІЯ: {len(problems)} проблем", file=sys.stderr)
        for problem in problems[:20]:
            print(f"    {problem}", file=sys.stderr)
    else:
        print("  валідація: ок", flush=True)


def _run_status() -> None:
    """Зведення по всіх джерелах: скільки сторінок у змісті / на диску / у базі."""
    raw = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    print(f"{'джерело':22} {'scope':10} {'стор.':>6} {'файлів':>7} {'записів':>8}  категорії")
    totals = [0, 0, 0]
    spec = compendium_format.load_spec()
    for entry in raw.get("sources", []):
        source = entry["id"]
        index_file = config.INDEX_DIR / f"{source}.json"
        pages = 0
        if index_file.exists():
            pages = len(json.loads(index_file.read_text(encoding="utf-8")).get("pages") or [])
        done = len(fetch.load_checkpoint(source).get("done") or [])
        by_category: dict[str, int] = {}
        # Записи книги лежать у двох корпусах (компендіум і бестіарій), тому
        # зведення по книзі — сума по обох.
        for corpus in spec.corpus_names():
            directory = spec.corpus_dir(corpus) / source
            if not directory.exists():
                continue
            for file in sorted(directory.glob("*.jsonl")):
                count = sum(1 for line in file.read_text(encoding="utf-8").splitlines() if line.strip())
                by_category[file.stem] = by_category.get(file.stem, 0) + count
        total_records = sum(by_category.values())
        if pages or done or total_records:
            categories = ", ".join(f"{k}={v}" for k, v in sorted(by_category.items()))
            print(f"{source:22} {entry.get('scope', '')!s:10} {pages:6} {done:7} {total_records:8}  {categories}")
        totals[0] += pages
        totals[1] += done
        totals[2] += total_records
    print(f"{'РАЗОМ':22} {'':10} {totals[0]:6} {totals[1]:7} {totals[2]:8}")


def _run_verify() -> int:
    """Замикання сторінок: що книга посилається, але не завантажено."""
    raw = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    unknown_total = 0
    absent_total = 0
    for entry in raw.get("sources", []):
        source = entry["id"]
        if not (config.RAW_DIR / source).is_dir():
            continue
        unknown, absent = closure.report(source)
        unknown_total += len(unknown)
        absent_total += len(absent)
    print(f"\nразом: невідомих {unknown_total}, без файлів {absent_total}")
    return 0 if not (unknown_total or absent_total) else 1


def _run_index() -> None:
    counts = indexes.sync_all()
    if not counts:
        print("індекси вже повні")
        return
    for source, added in counts.items():
        print(f"{source:20} +{added}")


def _force_utf8() -> None:
    """Windows-консоль буває cp1251: без цього кирилиця й стрілки валять друк."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scripts.ingest", description="D&D Beyond -> компендіум")
    parser.add_argument(
        "command",
        choices=[
            "discover",
            "fetch",
            "parse",
            "run",
            "all",
            "status",
            "verify",
            "index",
        ],
    )
    parser.add_argument("--source", help="id джерела з content/sources.yml")
    parser.add_argument("--tiers", default="1", help="черги для command=all, напр. 1,1.5,2")
    parser.add_argument("--delay", type=float, default=config.DEFAULT_DELAY)
    parser.add_argument("--refresh", action="store_true", help="перезавантажити наявні сторінки")
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help="без cookies (лише безкоштовні книги: basic-rules-2014, ua)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)

    if args.command in ("discover", "fetch", "run", "all"):
        try:
            fetcher = session.Fetcher(delay=args.delay, anonymous=args.anonymous)
        except session.SessionError as exc:
            print(f"Сесія: {exc}", file=sys.stderr)
            return 3
    else:
        fetcher = None

    try:
        if args.command == "status":
            _run_status()
            return 0

        if args.command == "verify":
            return _run_verify()

        if args.command == "index":
            _run_index()
            return 0

        if args.command == "all":
            tiers = {tier.strip() for tier in args.tiers.split(",") if tier.strip()}
            for source in _sources_by_tier(tiers):
                try:
                    _run_discover(source, fetcher)
                    _run_fetch(source, fetcher, args.refresh)
                    _run_parse(source)
                except session.ChallengeError as exc:
                    print(f"\n[СТОП] {source}: {exc}", file=sys.stderr)
                    return 2
            return 0

        if not args.source:
            print("--source обовʼязковий для цієї команди", file=sys.stderr)
            return 64

        try:
            if args.command == "discover":
                _run_discover(args.source, fetcher)
            elif args.command == "fetch":
                _run_fetch(args.source, fetcher, args.refresh)
            elif args.command == "parse":
                _run_parse(args.source)
            elif args.command == "run":
                _run_discover(args.source, fetcher)
                _run_fetch(args.source, fetcher, args.refresh)
                _run_parse(args.source)
        except session.ChallengeError as exc:
            print(f"\n[СТОП] {exc}", file=sys.stderr)
            return 2
        except (session.SessionError, FileNotFoundError) as exc:
            print(f"[ПОМИЛКА] {exc}", file=sys.stderr)
            return 1
    finally:
        if fetcher is not None:
            fetcher.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
