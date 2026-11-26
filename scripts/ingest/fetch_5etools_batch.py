"""Довантажити з дзеркала 5e.tools усе, що ще дає листку персонажа.

Список складено за дифом дзеркала (scripts/ingest/diff_5etools.py) і довідковими
корпусами: беремо кожну книгу/пригоду лінійки 2014, у якої є передісторії,
риси, види, підкласи, закляття або предмети, і якої ще немає в content/raw/.

Свідомо НЕ беремо (лише статблоки й пригодницький текст, листку нічого не
дають): AATM, BAM-без-предметів, DIP, SLW, OoW, RtG, ToFW, KKW, HoL, GotSF,
DoSI, HAT-TG, NRH-*, AitFR-ISF/DN/FCD, DrDe-*, книги 2024+.

Запуск:  python scripts/ingest/fetch_5etools_batch.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ingest.fetch_5etools import ROOT, fetch  # noqa: E402

TARGETS = [
    # книга, id дзеркала, тека в content/raw
    ("book", "ps-a", "ps-amonkhet"),
    ("book", "ps-i", "ps-innistrad"),
    ("book", "ps-k", "ps-kaladesh"),
    ("book", "ps-d", "ps-dominaria"),
    ("book", "ps-z", "ps-zendikar"),
    ("book", "ps-x", "ps-ixalan"),
    ("book", "awm", "awm"),
    ("book", "al", "al"),
    ("book", "mabjov", "mabjov"),
    ("book", "mgelft", "mgelft"),
    ("book", "bam", "bam"),
    ("adventure", "lr", "lr"),
    ("adventure", "idrotf", "idrotf"),
    ("adventure", "pabtso", "pabtso"),
    ("adventure", "coa", "coa"),
    ("adventure", "qftis", "qftis"),
    ("adventure", "kftgv", "kftgv"),
    ("adventure", "hotdq", "hotdq"),
    ("adventure", "xmts", "xmts"),
    ("adventure", "jttrc", "jttrc"),
    ("adventure", "aitfr-avt", "aitfr-avt"),
    ("adventure", "ditlcot", "ditlcot"),
    ("adventure", "veor", "veor"),
    ("adventure", "rot", "rot"),
    ("adventure", "dc", "dc"),
    ("adventure", "sdw", "sdw"),
    ("adventure", "hftt", "hftt"),
    ("adventure", "lox", "lox"),
    ("adventure", "rmbre", "rmbre"),
    ("adventure", "azfyt", "azfyt"),
    ("adventure", "aitfr-thp", "aitfr-thp"),
    ("adventure", "nrh-at", "nrh-at"),
    ("adventure", "nrh-tlt", "nrh-tlt"),
]


def sections(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("bookData", "adventureData"):
        if key in data:
            return len(data[key][0].get("data", []))
    return 0


def main() -> None:
    total = 0
    for kind, sid, slug in TARGETS:
        rel = f"{kind}/{kind}-{sid}.json"
        dest = ROOT / "content" / "raw" / slug / rel.split("/")[-1]
        if dest.exists():
            print(f"--- {slug:14s} уже є ({dest.stat().st_size // 1024} KB)")
            continue
        try:
            size = fetch(rel, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {rel}: {exc}")
            continue
        total += size
        print(f"OK  {slug:14s} {size // 1024:5d} KB  розділів: {sections(dest)}")
    print(f"\nразом довантажено: {total // 1024} KB")


if __name__ == "__main__":
    main()
