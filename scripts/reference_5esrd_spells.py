"""Назви заклять із 5esrd (український переклад SRD): друге джерело для звірки."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "var" / "reference" / "5esrd-spells.json"

SPELLS = [
    "eldritch_blast",
    "hex",
    "prestidigitation",
    "burning_hands",
    "thaumaturgy",
    "guidance",
    "light",
    "mending",
    "bless",
    "divine_favor",
    "shield_of_faith",
]

TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
TAGS = re.compile(r"<[^>]+>")


def main() -> None:
    found: dict[str, str] = {}
    with httpx.Client(
        timeout=40,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as client:
        for slug in SPELLS:
            url = f"https://5esrd.kyiv.ua/spells/{slug}.html"
            response = client.get(url)
            if response.status_code != 200:
                print(f"{slug}: {response.status_code}")
                continue
            match = TITLE.search(response.text)
            if not match:
                print(f"{slug}: без h1")
                continue
            text = " ".join(TAGS.sub("", match.group(1)).split())
            pair = re.match(r"(?P<uk>[^\[]+)\[(?P<en>[^\]]+)\]", text)
            if not pair:
                print(f"{slug}: не пара — {text!r}")
                continue
            found[pair.group("en").strip().lower()] = pair.group("uk").strip()
            print(f"{slug}: {pair.group('uk').strip()} [{pair.group('en').strip()}]")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
