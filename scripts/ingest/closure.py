"""Замикання сторінок книги: чи завантажено все, на що книга сама посилається.

Зміст книги на D&D Beyond не містить сторінок-продовжень. У MotM розділ рас
розбитий на «fantastical-races» і «fantastical-races-continued», і другої
сторінки в блоці змісту немає; у FToD бестіарій порізаний на «bestiary-ak»,
«bestiary-lz» тощо, і в змісті є лише перша. Через це книга виглядала
завантаженою повністю, а половина рас і монстрів була відсутня.

Тому після завантаження рахуємо замикання: збираємо всі посилання на власні
сторінки книги зі збереженого HTML і порівнюємо з індексом. Те, чого індекс не
знає, — кандидати на докачку.
"""

from __future__ import annotations

import collections
import json

from . import config, discover

# Посилання, які DDB віддає зламаними: якір склеюється зі шляхом сторінки
# («…/friends-and-foes#LadyIllmarrow» → «…/friends-and-foesladyillmarrow»).
# Такі адреси віддають 404, у корпусі їм місця немає.
IGNORE = {
    ("cotn", "magic-itemsmedalofmuscle"),
    ("erftlw", "friends-and-foesladyillmarrow"),
    ("erftlw", "friends-and-foeswarforgedsoldier"),
    ("tod", "monster"),
}


def book_keys(index_pages: list[str]) -> set[tuple[str, str]]:
    """Ключ книги (kind, slug) — те, що відрізняє її сторінки від чужих."""
    counts = collections.Counter(discover.key_of(rel) for rel in index_pages)
    if not counts:
        return set()
    return {counts.most_common(1)[0][0]}


def saved(source: str, rel: str) -> bool:
    return (config.RAW_DIR / source / (rel.replace("/", "__") + ".html")).exists()


def missing(source: str) -> tuple[list[str], list[str]]:
    """(невідомі сторінки, сторінки змісту без файлів)."""
    index_file = config.INDEX_DIR / f"{source}.json"
    if not index_file.exists():
        return [], []
    pages = json.loads(index_file.read_text(encoding="utf-8")).get("pages") or []
    keys = book_keys(pages)
    # Порівнюємо за хвостом шляху: та сама сторінка буває під
    # sources/dnd/<book>/… і sources/<book>/…, і це не різні сторінки.
    known_tails = {discover.tail_of(rel) for rel in pages}
    known_tails.discard("")

    seen: dict[str, str] = {}
    directory = config.RAW_DIR / source
    for file in directory.glob("*.html"):
        try:
            html = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rel in discover.extract_rels(html):
            if discover.key_of(rel) not in keys:
                continue
            tail = discover.tail_of(rel)
            if tail and tail not in seen:
                seen[tail] = rel

    unknown = sorted(rel for tail, rel in seen.items() if tail not in known_tails and (source, tail) not in IGNORE)
    absent = [rel for rel in pages if discover.tail_of(rel) and not saved(source, rel)]
    return unknown, absent


def report(source: str) -> tuple[list[str], list[str]]:
    unknown, absent = missing(source)
    if unknown or absent:
        print(f"! {source:20} невідомих {len(unknown):3}  без файлів {len(absent):3}")
        for rel in unknown:
            print(f"      + {rel}")
        for rel in absent:
            print(f"      ? {rel}")
    return unknown, absent
