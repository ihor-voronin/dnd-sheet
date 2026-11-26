"""Завантаження сирого HTML книг із чекпойнтом (можна перезапускати)."""

from __future__ import annotations

import json
import pathlib
import sys

from . import config, discover, session


def raw_path(source: str, rel: str) -> pathlib.Path:
    slug = rel.replace("/", "__")
    return config.RAW_DIR / source / f"{slug}.html"


def _checkpoint_file(source: str) -> pathlib.Path:
    return config.RAW_DIR / source / "_checkpoint.json"


def load_checkpoint(source: str) -> dict:
    target = _checkpoint_file(source)
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    return {"source_id": source, "done": [], "failed": [], "challenge": False}


def save_checkpoint(source: str, state: dict) -> None:
    (config.RAW_DIR / source).mkdir(parents=True, exist_ok=True)
    _checkpoint_file(source).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def fetch_all(fetcher: session.Fetcher, source: str, refresh: bool = False) -> dict:
    rels = discover.load_index(source)
    state = load_checkpoint(source)
    done = set() if refresh else set(state["done"])
    state["challenge"] = False
    total = len(rels)

    for index, rel in enumerate(rels, start=1):
        target = raw_path(source, rel)
        if target.exists() and rel in done:
            continue
        try:
            html = fetcher.get(discover.page_url(rel))
        except session.ChallengeError as exc:
            state["challenge"] = True
            state["done"] = sorted(done)
            save_checkpoint(source, state)
            print(f"\n  ЗУПИНКА: {exc}\n  прогрес збережено ({len(done)}/{total})", file=sys.stderr)
            raise
        except session.SessionError as exc:
            state["failed"].append({"rel": rel, "error": str(exc)})
            state["done"] = sorted(done)
            save_checkpoint(source, state)
            print(f"  fail {rel}: {exc}", file=sys.stderr)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        done.add(rel)
        state["done"] = sorted(done)

        if index % 10 == 0 or index == total:
            save_checkpoint(source, state)
            print(f"  {index}/{total} {rel}", flush=True)

    save_checkpoint(source, state)
    return state
