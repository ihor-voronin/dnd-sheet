"""Диф дзеркала 5e.tools проти нашого корпусу: що є на сайті й чого в нас немає.

Порівняння йде **за назвами**, а не за id: id дзеркала не збігаються з нашими
тека­ми (FTD→ftod, MPMM→motm, DSotDQ→sotdq, AIS→sais, PS-Z→ps-zendikar), а
назви записів у корпусах ті самі. Тому (категорія, нормалізована назва) —
достатній ключ.

Джерела даних:
  наш корпус      content/compendium/<книга>/*.jsonl, content/bestiary/<книга>/monster.jsonl
  дзеркало        content/raw/_index/*.json (довідники), mirror-spells/, mirror-class/

Друкує:
  1) за категорією: скільки на дзеркалі, скільки збіглося, скільки бракує;
  2) брак, згрупований за книгою-джерелом, з поміткою «текст у нас / не взято»;
  3) за --list — усі назви, яких бракує.

Запуск:  python scripts/ingest/diff_5etools.py [--list]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IDX = REPO / "content" / "raw" / "_index"

# Лінійка 2024+ — поза скоупом (порівнюємо лише 2014).
OTHER_EDITION = {"XPHB", "XDMG", "XMM", "XSAC", "XScreen", "FRHoF", "EFA", "RHW",
                 "AU", "PL", "WoW", "LFL", "ABH", "NF", "FRAiF", "CaBoMP", "HFLotT",
                 "XScreenRHW", "AUD", "DDE", "ICC", "SoS", "RWG", "BQDD", "WttHC",
                 "HotB", "HBTD", "BQGT", "DrDe-DaS", "DrDe-BD", "DrDe-TWoO",
                 "DrDe-FWtVC", "DrDe-TDoN", "DrDe-TFV", "DrDe-BtS", "DrDe-SD",
                 "DrDe-ACfaS", "DrDe-DotSC", "UtHftLH", "ScoEE", "LRDT", "FRAiF-TLLoL",
                 "FFotR", "VNotEE", "HFStCM", "PaF", "TD", "DMTCRG"}

# Текст книг, які лежать у content/raw, але ще не розібрані. Обчислюється з
# самих файлів дзеркала: у кожному є "id" (PS-A, ToA, LR…), тому id → тека.


def downloaded_books() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in (REPO / "content" / "raw").glob("*/*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("bookData", "adventureData"):
            entries = data.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id"):
                    found.setdefault(entry["id"], path.parent.name)
    return found


# Дзеркало позначає частину книг коротким source, але файлом — довгим id
# (PSA у записах = книга PS-A). Тут — лише такі розбіжності.
ALIASES = {"PSA": "PS-A", "PSI": "PS-I", "PSK": "PS-K", "PSD": "PS-D",
           "PSZ": "PS-Z", "PSX": "PS-X", "MCV1SC": "MCV1SC", "MisMV1": "MisMV1",
           "MFF": "MFF", "VD": "VD", "RMR": "RMR", "ESK": "ESK"}

# Джерела, які ми вже розібрали, але в каталозі дзеркала їх немає як книг:
# Basic Rules — це PHB/MM/DMG з прапорцем basicRules, EEPC — PDF WotC,
# третьої сторони (Humblewood) і AL-модулів на дзеркалі немає взагалі.
PARSED_ELSEWHERE = {"EEPC", "PHB", "MM", "DMG"}


def held_sources() -> set[str]:
    """id дзеркала, текст яких у нас уже є (розібраний або лише завантажений)."""
    held = set(downloaded_books()) | set(ALIASES.values()) | PARSED_ELSEWHERE
    catalog = {}
    for name, key in (("books-5etools.json", "book"),
                      ("adventures-5etools.json", "adventure")):
        for entry in load_json(name)[key]:
            catalog[norm(entry.get("name", ""))] = entry["id"]
    try:
        import yaml

        sources = yaml.safe_load(
            (REPO / "content" / "sources.yml").read_text(encoding="utf-8"))["sources"]
    except Exception:  # noqa: BLE001 - без реєстру працює лише часткова помітка
        return held
    for src in sources:
        hit = catalog.get(norm(src.get("title", "")))
        if hit:
            held.add(hit)
    return held


def norm(name: str) -> str:
    """Нормалізація назви: регістр, апострофи, пунктуація, наголоси.

    Дужки **не** відкидаються: у дзеркалі вони розрізняють записи
    («Goblin (Dankwood)» ≠ «Goblin»), і саме на цьому ламався попередній диф.
    """
    s = unicodedata.normalize("NFKD", name)
    s = s.replace("’", "'").replace("‘", "'").replace("—", "-").replace("–", "-")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def load_json(name: str):
    path = IDX / name
    if not path.exists():
        raise SystemExit(f"немає {path} — спершу scripts/ingest/fetch_5etools.py")
    return json.loads(path.read_text(encoding="utf-8"))


def our_records():
    """(category, norm_name) з обох корпусів."""
    seen: dict[str, set[str]] = defaultdict(set)
    for corpus in ("compendium", "bestiary"):
        for path in sorted((REPO / "content" / corpus).glob("*/*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                name = rec.get("name_en") or rec.get("name")
                if name:
                    seen[rec["category"]].add(norm(name))
    return seen


def mirror_records():
    """(category, name, source) з усіх довідкових корпусів дзеркала."""
    out: list[tuple[str, str, str]] = []

    def add(cat, rows):
        for row in rows:
            out.append((cat, row.get("name", "?"), row.get("source", "?")))

    add("background", load_json("backgrounds-5etools.json")["background"])
    add("feat", load_json("feats-5etools.json")["feat"])
    races = load_json("races-5etools.json")
    add("species", races["race"])
    add("species", races.get("subrace", []))
    add("item", load_json("mirror-items.json")["item"])
    add("item", load_json("mirror-items-base.json")["baseitem"])
    for path in sorted((IDX / "mirror-spells").glob("*.json")):
        add("spell", json.loads(path.read_text(encoding="utf-8"))["spell"])
    for path in sorted((IDX / "mirror-class").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        add("class", data.get("class", []))
        add("subclass", data.get("subclass", []))
    add("optionalfeature", load_json("mirror-optionalfeatures.json")["optionalfeature"])
    return out


def source_titles():
    titles = {}
    for name, key in (("books-5etools.json", "book"),
                      ("adventures-5etools.json", "adventure")):
        for entry in load_json(name)[key]:
            titles[entry["id"]] = entry.get("name", entry["id"])
    return titles


def main() -> None:
    show_list = "--list" in sys.argv
    ours = our_records()
    mirror = mirror_records()
    titles = source_titles()
    downloaded = downloaded_books()
    held = held_sources()

    ours_total = sum(len(v) for v in ours.values())
    print(f"корпус: {ours_total} записів у {len(ours)} категоріях")
    print(f"дзеркало: {len(mirror)} записів\n")

    per_cat_total = Counter(cat for cat, _, _ in mirror)
    per_cat_hit = Counter()
    missing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for cat, name, source in mirror:
        if norm(name) in ours.get(cat, set()):
            per_cat_hit[cat] += 1
        else:
            missing[cat].append((source, name))

    print(f"{'категорія':16s} {'дзеркало':>9s} {'збіглося':>9s} {'бракує':>7s}")
    for cat in sorted(per_cat_total):
        print(f"{cat:16s} {per_cat_total[cat]:9d} {per_cat_hit[cat]:9d} "
              f"{per_cat_total[cat] - per_cat_hit[cat]:7d}")

    print("\n--- брак за книгою-джерелом (лінійка 2014) ---")
    for cat in sorted(missing):
        by_src: dict[str, list[str]] = defaultdict(list)
        for source, name in missing[cat]:
            by_src[source].append(name)
        rows = [(src, names) for src, names in by_src.items()
                if src not in OTHER_EDITION]
        if not rows:
            continue
        print(f"\n## {cat}")
        for src, names in sorted(rows, key=lambda kv: (-len(kv[1]), kv[0])):
            real = ALIASES.get(src, src)
            if real in downloaded:
                mark = f"текст у нас (content/raw/{downloaded[real]}) — не розібрано"
            elif real in held:
                mark = "книга в корпусі — назви розійшлися"
            else:
                mark = "НЕ ВЗЯТО"
            title = titles.get(real, titles.get(src, src))
            print(f"  {src:14s} {len(names):3d}  {title}   [{mark}]")
            if show_list:
                for name in sorted(names):
                    print(f"        - {name}")


if __name__ == "__main__":
    main()
