"""Довідник назв із D&D World: англійська → українська.

Свої назви ми перекладали самі, і їх треба звірити з тим, як ці самі речі
звуть українською в уживаному перекладі. Сторінка предметів D&D World дає
саме пару «назва українською + [English]» — цього досить, щоб порівняти
назви, не тягнучи чужі тексти.

Скрипт складає `var/reference/dndworld-<kind>.json`:
{ "abacus": "Абак", ... } — ключ це англійська назва в нижньому регістрі.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "var" / "reference"

PAGES = {
    # сторінка: (URL з пагінацією, скільки сторінок)
    "items": ("https://www.dndworld.space/predmety/?paged={page}", 90),
    "spells": ("https://www.dndworld.space/zaklynannia/?paged={page}", 40),
}

#: Рядок таблиці предметів: посилання з українською назвою і span з англійською.
ROW = re.compile(
    r'<a class="[^"]*__title"[^>]*>(?P<uk>.*?)</a>.*?__eng[^>]*>\s*\[(?P<en>.*?)\]',
    re.S,
)
#: Картка закляття: `spell-link` + `spell-eng-name`.
SPELL = re.compile(
    r'class="spell-link"[^>]*>(?P<uk>.*?)</a>.*?spell-eng-name[^>]*>\s*\[(?P<en>.*?)\]',
    re.S,
)
CLEAN = re.compile(r"<[^>]+>")


def norm(value: str) -> str:
    return " ".join(html.unescape(value).split()).lower().replace("’", "'").replace("ʼ", "'")


def scrape(kind: str, template: str, pages: int) -> dict[str, str]:
    found: dict[str, str] = {}
    with httpx.Client(
        timeout=40,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as client:
        for page in range(1, pages + 1):
            url = template.format(page=page)
            try:
                response = client.get(url)
            except httpx.HTTPError as error:
                print(f"{kind} {page}: {error}", file=sys.stderr)
                continue
            if response.status_code != 200:
                break
            pattern = SPELL if kind == "spells" else ROW
            rows = pattern.findall(response.text)
            if not rows:
                print(f"{kind} {page}: рядків немає — кінець", file=sys.stderr)
                break
            for uk, en in rows:
                ukrainian = " ".join(html.unescape(CLEAN.sub("", uk)).split())
                english = " ".join(html.unescape(CLEAN.sub("", en)).split())
                if not ukrainian or not english:
                    continue
                found.setdefault(norm(english), ukrainian)
            print(f"{kind} {page}: +{len(rows)} (усього {len(found)})", file=sys.stderr)
            time.sleep(0.2)
    return found


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, (template, pages) in PAGES.items():
        found = scrape(kind, template, pages)
        path = OUT / f"dndworld-{kind}.json"
        path.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{kind}: {len(found)} назв → {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
