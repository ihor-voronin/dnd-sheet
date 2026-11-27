"""Індекс сторінок книги: побудова зі змісту і доповнення за фактом на диску.

Індекс (content/raw/_index/<книга>.json) будується з блоку змісту книги. Після
докачки сторінок, яких у змісті немає (див. closure.py), їх треба внести в
індекс — інакше наступний прогін знову вважатиме їх відсутніми, а /todo
пропонуватиме завантажити їх удруге.
"""

from __future__ import annotations

import json

from . import config, discover


def sync(source: str) -> list[str]:
    """Дописує в індекс сторінки, файли яких уже є на диску. Повертає додані."""
    index_file = config.INDEX_DIR / f"{source}.json"
    if not index_file.exists():
        return []
    payload = json.loads(index_file.read_text(encoding="utf-8"))
    pages = payload.get("pages") or []
    tails = {discover.tail_of(rel) for rel in pages}
    added: list[str] = []
    for file in sorted((config.RAW_DIR / source).glob("*.html")):
        rel = file.stem.replace("__", "/")
        tail = discover.tail_of(rel)
        if not tail or tail in tails:
            continue
        tails.add(tail)
        pages.append(rel)
        added.append(rel)
    if added:
        payload["pages"] = pages
        payload["count"] = len(pages)
        index_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def sync_all() -> dict[str, int]:
    counts: dict[str, int] = {}
    for directory in sorted(config.RAW_DIR.iterdir()):
        if not directory.is_dir() or directory.name == "_index":
            continue
        added = sync(directory.name)
        if added:
            counts[directory.name] = len(added)
    return counts
