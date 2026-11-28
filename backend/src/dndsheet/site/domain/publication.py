"""Що публікувати на відкритих сторінках довідника й що віддавати пошуковикам.

Рішення власника (docs/seo.md): записи всіх ліцензій — повним текстом і в
індексі. Але книги платні, тож політика для записів з книг під авторським
правом (`proprietary`, `third_party`) перемикається змінною
`DNDSHEET_KB_PROPRIETARY` без зміни коду — наприклад, після вимоги правовласника:

* `full` (типово) — повний текст, сторінка в індексі й у карті сайту;
* `summary` — назва, числа й джерело без тексту книги, сторінка в індексі;
* `noindex` — повний текст для людей, але `noindex` і поза картою сайту.

SRD (CC BY 4.0) і безкоштовні матеріали WotC (`free`) завжди публікуються повністю.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

#: Ліцензії, які показуємо повністю за будь-якої політики.
OPEN_LICENSES = frozenset({"srd", "free"})


class Policy(StrEnum):
    FULL = "full"
    SUMMARY = "summary"
    NOINDEX = "noindex"

    @classmethod
    def parse(cls, value: str | None) -> "Policy":
        """Невідоме значення — типова політика, а не падіння застосунку на старті."""
        try:
            return cls((value or "").strip().lower() or cls.FULL)
        except ValueError:
            return cls.FULL


@dataclass(frozen=True, slots=True)
class Publication:
    """Як показати один запис: з текстом книги чи без, і чи кликати пошуковик."""

    text: bool
    index: bool


def publication(license: str, policy: Policy, *, has_ukrainian: bool = True) -> Publication:
    """Правило для запису: ліцензія × політика × чи є що читати українською.

    Сторінка без жодного українського слова (ні назви, ні тексту) — копія
    англомовних сайтів, тож вона відкрита людям, але не індексується.
    """
    if license in OPEN_LICENSES or policy is Policy.FULL:
        shown = Publication(text=True, index=True)
    elif policy is Policy.SUMMARY:
        shown = Publication(text=False, index=True)
    else:
        shown = Publication(text=True, index=False)
    if not has_ukrainian:
        return Publication(text=shown.text, index=False)
    return shown


_APOSTROPHES = re.compile(r"['’ʼ`]")
_NOT_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Адреса сторінки з англійської назви: «Abi-Dalzim's Horrid Wilting» → `abi-dalzims-horrid-wilting`.

    Англійська, бо вона однакова в усіх книгах і не змінюється, коли
    уточнюють переклад; апостроф просто зникає (як у більшості сайтів 5e).
    """
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    text = _APOSTROPHES.sub("", text)
    return _NOT_SLUG.sub("-", text).strip("-")


def name_key(name: str) -> str:
    """Ключ дублікатів: те саме закляття в PHB і в базових правилах — один запис."""
    return slugify(name)
