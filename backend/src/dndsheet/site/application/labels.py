"""Українські підписи для сторінок довідника — зі словників застосунку.

Словники живуть у `frontend/src` (назви видів, класів, предметів, навички,
глосарій); збірка SPA кладе їх у `dist/kb-labels.json`
(`frontend/scripts/export-kb-labels.mjs`). Немає файлу — сторінки працюють,
лише назви лишаються англійськими. Правила пошуку ключа — як у `uk.ts`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_SPACES = re.compile(r"\s+")


def norm(value: str) -> str:
    """Ключ словника, як `norm` в `uk.ts`: малі літери, один пробіл, апостроф «'»."""
    return _SPACES.sub(" ", value.strip().lower()).replace("’", "'").replace("ʼ", "'")


def title_case_key(key: str) -> str:
    """«mountain dwarf» → «Mountain Dwarf»: ключі виду малими літерами, у дужках — як у книзі."""
    if key != key.lower():
        return key
    return re.sub(r"(^|[\s(/-])(\w)", lambda match: match.group(1) + match.group(2).upper(), key)


def with_english(name_en: str, uk: str | None) -> str:
    """«Довгий меч (Longsword)»; без перекладу — оригінал."""
    if not uk or norm(uk) == norm(name_en):
        return name_en
    return f"{uk} ({name_en})"


#: Час, дистанція й тривалість закляття — як `unitsLabel` у `labels.ts`.
_UNITS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, flags), replacement)
    for pattern, replacement, flags in (
        (r"\bbonus action\b", "бонусна дія", re.I),
        (r"\bactions\b", "дії", re.I),
        (r"\baction\b", "дія", re.I),
        (r"\breaction\b", "реакція", re.I),
        (r"\bminutes?\b", "хв.", re.I),
        (r"\bhours?\b", "год.", re.I),
        (r"\bseconds?\b", "с", re.I),
        (r"\brounds?\b", "раунд", re.I),
        (r"\bfeet\b", "фт", re.I),
        (r"\bfoot\b", "фт", re.I),
        (r"\breach\b", "досяжність", re.I),
        (r"\bmiles?\b", "миля", re.I),
        (r"\bSelf\b", "на себе", 0),
        (r"\bTouch\b", "дотик", 0),
        (r"\bSight\b", "видиме", 0),
        (r"\bUnlimited\b", "без обмежень", 0),
        (r"\bInstantaneous\b", "миттєво", 0),
        (r"\bConcentration\b", "концентрація", 0),
        (r"\bup to\b", "до", re.I),
        (r"\bcone\b", "конус", re.I),
        (r"\bsphere\b", "сфера", re.I),
        (r"\bcube\b", "куб", re.I),
        (r"\bcylinder\b", "циліндр", re.I),
        (r"\bline\b", "лінія", re.I),
        (r"\bSpecial\b", "особлива", 0),
    )
)


def units(text: str) -> str:
    for pattern, replacement in _UNITS:
        text = pattern.sub(replacement, text)
    return text


class Labels:
    """Обгортка над `kb-labels.json`: кожен метод має запасний варіант — оригінал."""

    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self._data: Mapping[str, Any] = data or {}

    def _table(self, name: str) -> Mapping[str, Any]:
        table = self._data.get(name)
        return table if isinstance(table, Mapping) else {}

    def _get(self, table: str, key: str) -> str | None:
        value = self._table(table).get(key)
        return value if isinstance(value, str) and value else None

    @property
    def loaded(self) -> bool:
        return bool(self._data)

    # --- назви ----------------------------------------------------------------

    def term(self, name_en: str) -> str | None:
        return self._get("terms", norm(name_en))

    def species(self, raw_name: str) -> str | None:
        name = norm(title_case_key(raw_name))
        return self._get("species", name) or self._get("terms", name)

    def species_label(self, raw_name: str) -> str:
        """Як `speciesLabel`: у назвах з дужками англійська йде через тире."""
        name_en = title_case_key(raw_name)
        uk = self.species(raw_name)
        if not uk or norm(uk) == norm(name_en):
            return name_en
        return f"{uk} — {name_en}" if "(" in name_en else f"{uk} ({name_en})"

    def item(self, name_en: str) -> str | None:
        return self._get("items", norm(name_en))

    def feat(self, name_en: str) -> str | None:
        return self._get("feats", norm(name_en))

    # --- підписи --------------------------------------------------------------

    def ability(self, code: str) -> str:
        return self._get("abilities", code) or code.upper()

    def ability_short(self, code: str) -> str:
        return self._get("ability_short", code) or code.upper()

    def ability_genitive(self, code: str) -> str:
        return self._get("ability_genitive", code) or self.ability(code)

    def skill(self, code: str) -> str:
        return self._get("skills", code) or code

    def size(self, code: str) -> str:
        return self._get("sizes", code) or code

    def language(self, code: str) -> str:
        return self._get("languages", code) or self.term(code) or code

    def damage(self, code: str) -> str:
        return self._get("damage_types", code) or self.term(code) or code

    def school(self, code: str) -> str:
        return self._get("schools", code) or code

    def source(self, code: str | None) -> str:
        if not code:
            return ""
        return self._get("sources", code) or self._get("sources", code.lower()) or code.upper()

    def proficiency(self, kind: str, value: str) -> str:
        """Як `proficiencyValue` у `labels.ts`."""
        if kind == "skill":
            return self.skill(value)
        if kind == "saving_throw":
            return self.ability(value)
        if kind == "language":
            return self._get("languages", value) or value
        if kind == "tool":
            return self._get("tools", value) or value
        return self._get("proficiency_values", value) or value

    def proficiency_text(self, kind: str, value: str) -> str:
        """Як `proficiencyText` в `uk.ts`: конкретна зброя («battleaxe») — назвою предмета."""
        label = self.proficiency(kind, value)
        if label != value or kind not in {"weapon", "armor"}:
            return label
        uk = self.item(value) or (self.item(value[:-1]) if value.endswith("s") else None)
        return uk[0].lower() + uk[1:] if uk else value

    def class_guide(self, key: str) -> Mapping[str, Any]:
        guide = self._table("class_guide").get(key)
        return guide if isinstance(guide, Mapping) else {}

    def glossary(self) -> Mapping[str, Mapping[str, Any]]:
        return {key: value for key, value in self._table("glossary").items() if isinstance(value, Mapping)}
