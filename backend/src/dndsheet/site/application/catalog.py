"""Каталог відкритих сторінок довідника: один запис на назву, одна адреса на запис.

Те саме закляття лежить у кількох книгах (Книга гравця, базові правила,
SRD) — на сайті це одна сторінка `/kb/spells/fireball`. Який запис стає
сторінкою, вирішує `_rank`: є український текст > відкрита ліцензія > основна
книга. Інші адреси (хвости id з різних книг) — псевдоніми з переадресацією.

Каталог збирається один раз і живе в памʼяті: кілька тисяч записів —
мегабайти, а не гігабайти. Дані видів, класів і передісторій приходять готовими
(ті самі, що бачить візард), записи довідника — з `CompendiumService`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from dndsheet.compendium.domain.entry import Category, CompendiumEntry
from dndsheet.shared import translations
from dndsheet.site.application.facts import spell_level_label
from dndsheet.site.application.labels import Labels, title_case_key, with_english
from dndsheet.site.domain.publication import OPEN_LICENSES, Policy, Publication, name_key, publication, slugify


@dataclass(frozen=True, slots=True)
class Section:
    id: str
    label: str
    hint: str
    #: «закляття D&D 5e» у заголовку сторінки запису.
    noun: str
    #: <title> і H1 сторінки розділу.
    heading: str
    intro: str


SECTIONS: tuple[Section, ...] = (
    Section(
        "species",
        "Види",
        "раси й підраси: швидкість, темний зір, особливості",
        "раса",
        "Раси (види) D&D 5e українською",
        "Усі раси — у правилах 2014 «види»: людина, ельф, дворф, тіфлінґ і ще десятки з доповнень. "
        "Розмір, швидкість, бонуси характеристик, мови й особливості, підраси.",
    ),
    Section(
        "classes",
        "Класи",
        "хіти, володіння, уміння за рівнями, підкласи",
        "клас",
        "Класи D&D 5e українською",
        "Тринадцять класів: кість хітів, володіння, уміння з 1 по 20 рівень, підкласи й закляття класу.",
    ),
    Section(
        "backgrounds",
        "Передісторії",
        "навички, інструменти, риса, спорядження",
        "передісторія",
        "Передісторії D&D 5e українською",
        "Ким був герой до пригод: навички, інструменти, мови, риса передісторії й стартове спорядження.",
    ),
    Section(
        "feats",
        "Риси",
        "замість підвищення характеристик",
        "риса",
        "Риси (feats) D&D 5e українською",
        "Риси замість підвищення характеристик: умови, що дають і як працюють.",
    ),
    Section(
        "spells",
        "Закляття",
        "рівень, школа, час, дистанція, опис",
        "закляття",
        "Закляття D&D 5e українською — усі закляття за рівнями",
        "Заговори й закляття 1–9 рівнів: школа, час накладання, дистанція, компоненти, тривалість і повний опис.",
    ),
    Section(
        "options",
        "Опційні вміння",
        "виклики, бойові стилі, маневри, інфузії",
        "опційне вміння",
        "Опційні вміння D&D 5e українською: виклики, маневри, бойові стилі",
        "Містичні виклики чаклуна, маневри майстра бою, бойові стилі, метамагія, наповнення винахідника.",
    ),
    Section(
        "items",
        "Предмети",
        "зброя, броня, спорядження, магічні предмети",
        "предмет",
        "Предмети D&D 5e українською: зброя, броня, магічні предмети",
        "Зброя, броня, спорядження й магічні предмети: ціна, вага, рідкість і опис.",
    ),
)

SECTION_BY_ID: Mapping[str, Section] = {section.id: section for section in SECTIONS}

_COMPENDIUM_SECTIONS: Mapping[str, Category] = {
    "feats": Category.FEAT,
    "spells": Category.SPELL,
    "options": Category.OPTIONAL_FEATURE,
    "items": Category.ITEM,
}

#: Основні книги спершу: при однаковому тексті сторінкою стає запис із них.
_BOOK_ORDER = ("phb-2014", "basic-rules-2014", "srd-5-1", "xge", "xgte", "tcoe", "dmg-2014")

#: Групи предметів на сторінці розділу — як чипи типів в інвентарі листа.
ITEM_GROUPS: Mapping[str, str] = {
    "weapon": "Зброя",
    "armor": "Броня",
    "shield": "Щити",
    "gear": "Спорядження",
    "tool": "Інструменти",
    "mount": "Верхові тварини й транспорт",
    "potion": "Зілля",
    "scroll": "Сувої",
    "ring": "Персні",
    "rod": "Жезли",
    "staff": "Посохи",
    "wand": "Палички",
    "wondrous item": "Дивовижні предмети",
    "art object": "Витвори мистецтва",
}
_ITEM_GROUP_ALIASES = {"siege weapon": "weapon", "explosive": "gear", "ship": "mount", "vehicle": "mount"}
OTHER_GROUP = "Інше"

RARITY: Mapping[str, str] = {
    "common": "звичайний",
    "uncommon": "незвичайний",
    "rare": "рідкісний",
    "very rare": "дуже рідкісний",
    "legendary": "легендарний",
    "artifact": "артефакт",
    "rarity varies": "різна рідкість",
    "varies": "різна рідкість",
    "unknown (magic)": "рідкість невідома",
}

#: Групи опційних умінь — назви, як на листі (`classChoices.tsx`).
FEATURE_GROUPS: Mapping[str, str] = {
    "eldritch invocation": "Містичні виклики",
    "pact boon": "Дари угоди",
    "maneuver (battle master)": "Маневри майстра бою",
    "metamagic": "Метамагія",
    "artificer infusion": "Наповнення винахідника",
    "elemental discipline": "Стихійні дисципліни",
    "arcane shot": "Арканні постріли",
    "rune": "Руни",
    "fighting style (fighter)": "Бойові стилі",
    "fighting style (ranger)": "Бойові стилі",
    "fighting style (paladin)": "Бойові стилі",
    "fighting style (bard)": "Бойові стилі",
}

_UK_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
_UK_ORDER = {letter: index for index, letter in enumerate(_UK_ALPHABET)}


def uk_sort_key(text: str) -> tuple[tuple[int, int], ...]:
    """Абетка: «і», «ї», «є», «ґ» стоять на своїх місцях, а не після «я»; латиниця — після кирилиці."""
    out = []
    for char in text.casefold():
        if char in _UK_ORDER:
            out.append((0, _UK_ORDER[char]))
        elif char.isalnum():
            out.append((1, ord(char)))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Record:
    """Одна сторінка довідника."""

    section: str
    slug: str
    name_en: str
    name_uk: str | None
    license: str
    source_id: str
    publication: Publication
    #: Група на сторінці розділу (рівень закляття, тип предмета…), «» — без груп.
    group: str = ""
    #: Короткий рядок біля посилання: «3 рівень · втілення», «d10».
    meta: str = ""
    entry: CompendiumEntry | None = None
    data: Mapping[str, Any] = field(default_factory=dict)
    #: Підклас — slug класу.
    parent: str | None = None

    @property
    def title(self) -> str:
        return with_english(self.name_en, self.name_uk)

    @property
    def path(self) -> str:
        if self.parent:
            return f"/kb/classes/{self.parent}/{self.slug}"
        return f"/kb/{self.section}/{self.slug}"

    @property
    def sort_key(self) -> tuple[tuple[int, int], ...]:
        return uk_sort_key(self.name_uk or self.name_en)


def _rank(entry: CompendiumEntry, has_text: bool) -> tuple[int, int, int, str]:
    book = _BOOK_ORDER.index(entry.source_id) if entry.source_id in _BOOK_ORDER else len(_BOOK_ORDER)
    return (0 if has_text else 1, 0 if entry.license in OPEN_LICENSES else 1, book, entry.id)


def item_group(item_type: str | None) -> str:
    raw = (item_type or "").strip().lower()
    base = raw.split(" (")[0]
    base = _ITEM_GROUP_ALIASES.get(base, base)
    return ITEM_GROUPS.get(base, OTHER_GROUP)


class KbCatalog:
    """Усі сторінки довідника: розділи, записи, псевдоніми, звʼязки «клас — закляття»."""

    def __init__(
        self,
        *,
        labels: Labels,
        policy: Policy,
        entries: Mapping[Category, Sequence[CompendiumEntry]],
        species: Sequence[Mapping[str, Any]] = (),
        classes: Sequence[Mapping[str, Any]] = (),
        backgrounds: Sequence[Mapping[str, Any]] = (),
        class_spells: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        self.labels = labels
        self.policy = policy
        self._records: dict[str, dict[str, Record]] = {section.id: {} for section in SECTIONS}
        self._aliases: dict[str, dict[str, str]] = defaultdict(dict)
        self._subclasses: dict[str, dict[str, Record]] = defaultdict(dict)
        self._licenses = self._best_licenses(entries)
        for section, category in _COMPENDIUM_SECTIONS.items():
            self._add_compendium(section, entries.get(category, ()))
        self._add_species(species)
        self._add_classes(classes, entries.get(Category.SUBCLASS, ()))
        self._add_backgrounds(backgrounds)
        self._sorted = {
            section: sorted(records.values(), key=lambda record: record.sort_key)
            for section, records in self._records.items()
        }
        self._class_spells: dict[str, list[Record]] = {}
        self._spell_classes: dict[str, list[Record]] = defaultdict(list)
        for class_key, names in (class_spells or {}).items():
            klass = self._records["classes"].get(slugify(class_key))
            spells = [
                self._records["spells"][key]
                for key in dict.fromkeys(map(name_key, names))
                if key in self._records["spells"]
            ]
            if klass is None:
                continue
            self._class_spells[klass.slug] = sorted(spells, key=lambda record: (_level(record), record.sort_key))
            for spell in spells:
                self._spell_classes[spell.slug].append(klass)

    # --- читання ---------------------------------------------------------------

    def records(self, section: str) -> list[Record]:
        return self._sorted.get(section, [])

    def find(self, section: str, slug: str) -> Record | None:
        return self._records.get(section, {}).get(slug)

    def alias(self, section: str, slug: str) -> str | None:
        """Канонічна адреса для старого чи «чужого» slug (`abi-dalzim-s-…` → `abi-dalzims-…`)."""
        return self._aliases.get(section, {}).get(slug)

    def subclasses(self, class_slug: str) -> list[Record]:
        return sorted(self._subclasses.get(class_slug, {}).values(), key=lambda record: record.sort_key)

    def subclass(self, class_slug: str, slug: str) -> Record | None:
        return self._subclasses.get(class_slug, {}).get(slug)

    def class_spells(self, class_slug: str) -> list[Record]:
        return self._class_spells.get(class_slug, [])

    def spell_classes(self, spell_slug: str) -> list[Record]:
        return sorted(self._spell_classes.get(spell_slug, []), key=lambda record: record.sort_key)

    def related(self, record: Record, limit: int = 8) -> list[Record]:
        """Сусіди в тій самій групі (той самий рівень закляття, тип предмета) — для перелінковки."""
        pool = [
            other
            for other in self.records(record.section)
            if other.group == record.group and other.slug != record.slug
        ]
        if not pool:
            return []
        # Сусіди за абеткою, а не перші в групі: так на кожну сторінку веде кілька інших.
        position = next((index for index, other in enumerate(pool) if other.sort_key > record.sort_key), len(pool))
        start = max(0, min(position - limit // 2, len(pool) - limit))
        return pool[start : start + limit]

    def groups(self, section: str) -> list[tuple[str, list[Record]]]:
        """Записи розділу по групах у сталому порядку (рівні 0–9, типи предметів як у листі)."""
        grouped: dict[str, list[Record]] = defaultdict(list)
        for record in self.records(section):
            grouped[record.group].append(record)
        if section == "spells":
            order = sorted(grouped, key=lambda group: int(group or 0))
        elif section == "items":
            names = list(dict.fromkeys(ITEM_GROUPS.values())) + [OTHER_GROUP]
            order = sorted(grouped, key=lambda group: names.index(group) if group in names else len(names))
        else:
            order = sorted(grouped, key=uk_sort_key)
        return [(group, grouped[group]) for group in order]

    def counts(self) -> dict[str, int]:
        return {section: len(records) for section, records in self._records.items()}

    def all_records(self) -> Iterator[Record]:
        for section in SECTIONS:
            yield from self.records(section.id)
            if section.id == "classes":
                for klass in self.records("classes"):
                    yield from self.subclasses(klass.slug)

    def text_uk(self, record: Record) -> str | None:
        """Український текст запису довідника (видам і класам текст дає візард, не каталог)."""
        return self._text_uk(record.section, record.entry) if record.entry else None

    # --- збирання --------------------------------------------------------------

    @staticmethod
    def _best_licenses(entries: Mapping[Category, Sequence[CompendiumEntry]]) -> dict[tuple[str, str], str]:
        """Найвідкритіша ліцензія для назви: вид із базових правил — SRD, навіть якщо він є й у PHB."""
        best: dict[tuple[str, str], str] = {}
        for category, rows in entries.items():
            for entry in rows:
                key = (category.value, name_key(entry.name_en))
                if key not in best or (entry.license in OPEN_LICENSES and best[key] not in OPEN_LICENSES):
                    best[key] = entry.license
        return best

    def _license(self, category: Category, name_en: str) -> str:
        return self._licenses.get((category.value, name_key(name_en)), "proprietary")

    def _publication(self, license: str, has_ukrainian: bool) -> Publication:
        return publication(license, self.policy, has_ukrainian=has_ukrainian)

    def _name_uk(self, section: str, entry: CompendiumEntry) -> str | None:
        if section == "items":
            return translations.read("items")["names"].get(entry.id) or self.labels.item(entry.name_en)
        name = entry.name_uk or translations.entry_name_uk(entry.category.value, entry.name_en)
        if section == "feats":
            name = name or self.labels.feat(entry.name_en)
        return name

    def _text_uk(self, section: str, entry: CompendiumEntry) -> str | None:
        if section == "items":
            return translations.read("items")["texts"].get(entry.id)
        return entry.text_uk or translations.entry_text_uk(entry.category.value, entry.text_en or "")

    def _add_compendium(self, section: str, entries: Iterable[CompendiumEntry]) -> None:
        by_name: dict[str, list[CompendiumEntry]] = defaultdict(list)
        for entry in entries:
            by_name[name_key(entry.name_en)].append(entry)
        for slug, group in by_name.items():
            if not slug:
                continue
            texts = {entry.id: self._text_uk(section, entry) for entry in group}
            chosen = min(group, key=lambda entry: _rank(entry, bool(texts[entry.id])))
            name_uk = self._name_uk(section, chosen) or next(
                (name for entry in group if (name := self._name_uk(section, entry))), None
            )
            license = (
                chosen.license if chosen.license in OPEN_LICENSES else self._license(chosen.category, chosen.name_en)
            )
            group_key, meta = self._group_and_meta(section, chosen)
            self._records[section][slug] = Record(
                section=section,
                slug=slug,
                name_en=chosen.name_en,
                name_uk=name_uk,
                license=license,
                source_id=chosen.source_id,
                publication=self._publication(license, bool(name_uk or texts[chosen.id])),
                group=group_key,
                meta=meta,
                entry=chosen,
            )
            for entry in group:
                tail = entry.id.rsplit("/", 1)[-1]
                if tail != slug:
                    self._aliases[section][tail] = slug

    def _group_and_meta(self, section: str, entry: CompendiumEntry) -> tuple[str, str]:
        data = entry.data
        prerequisite = entry.prerequisite
        if section == "spells":
            level = entry.spell_level or 0
            return str(level), spell_level_label(level, entry.spell_school, self.labels, bool(data.get("ritual")))
        if section == "items":
            parts = [RARITY.get(entry.rarity or "", entry.rarity or "")] if entry.rarity else []
            if entry.is_magical and not entry.rarity:
                parts.append("магічний")
            return item_group(entry.item_type), " · ".join(part for part in parts if part)
        if section == "options":
            kinds = [FEATURE_GROUPS.get(kind, kind) for kind in entry.feature_types]
            return (kinds[0] if kinds else OTHER_GROUP), (f"умова: {prerequisite}" if prerequisite else "")
        return "", (f"умова: {prerequisite}" if prerequisite else "")

    def _add_species(self, items: Sequence[Mapping[str, Any]]) -> None:
        for item in items:
            key = str(item.get("key") or "")
            slug = slugify(key)
            if not slug:
                continue
            name_en = title_case_key(str(item.get("name_en") or key))
            name_uk = self.labels.species(key)
            license = self._license(Category.SPECIES, name_en)
            subspecies = item.get("subspecies") or ()
            self._records["species"][slug] = Record(
                section="species",
                slug=slug,
                name_en=name_en,
                name_uk=name_uk,
                license=license,
                source_id=str(item.get("source_id") or ""),
                publication=self._publication(license, bool(name_uk or item.get("description_uk"))),
                meta=f"підрас: {len(subspecies)}" if subspecies else "",
                data=item,
            )
            for sub in subspecies:
                # Підраса — розділ сторінки виду; її стара адреса веде туди.
                self._aliases["species"].setdefault(slugify(str(sub.get("key") or "")), slug)

    def _add_classes(self, items: Sequence[Mapping[str, Any]], subclass_entries: Iterable[CompendiumEntry]) -> None:
        subclass_by_id = {entry.id: entry for entry in subclass_entries}
        for item in items:
            key = str(item.get("key") or "")
            slug = slugify(key)
            if not slug:
                continue
            name_en = str(item.get("name_en") or key)
            name_uk = self.labels.term(name_en)
            license = self._license(Category.CLASS, name_en)
            self._records["classes"][slug] = Record(
                section="classes",
                slug=slug,
                name_en=name_en,
                name_uk=name_uk,
                license=license,
                source_id=str(item.get("source_id") or ""),
                publication=self._publication(license, bool(name_uk or item.get("description_uk"))),
                meta=f"d{item.get('hit_die')}" if item.get("hit_die") else "",
                data=item,
            )
            for sub in item.get("subclasses_all") or ():
                sub_name = str(sub.get("name_en") or "")
                sub_slug = slugify(sub_name)
                if not sub_slug or sub_slug in self._subclasses[slug]:
                    continue
                entry = subclass_by_id.get(str(sub.get("id")))
                sub_license = entry.license if entry else "proprietary"
                level = sub.get("level")
                self._subclasses[slug][sub_slug] = Record(
                    section="classes",
                    slug=sub_slug,
                    name_en=sub_name,
                    name_uk=sub.get("name_uk") or None,
                    license=sub_license,
                    source_id=str(sub.get("source_id") or ""),
                    publication=self._publication(sub_license, bool(sub.get("name_uk"))),
                    meta=f"з {level} рівня" if level else "",
                    entry=entry,
                    data=sub,
                    parent=slug,
                )

    def _add_backgrounds(self, items: Sequence[Mapping[str, Any]]) -> None:
        for item in items:
            key = str(item.get("key") or "")
            slug = slugify(key)
            if not slug or slug in self._records["backgrounds"]:
                continue
            name_en = str(item.get("name_en") or key)
            name_uk = self.labels.term(name_en) or translations.name_uk("backgrounds", name_en)
            license = self._license(Category.BACKGROUND, name_en)
            self._records["backgrounds"][slug] = Record(
                section="backgrounds",
                slug=slug,
                name_en=name_en,
                name_uk=name_uk,
                license=license,
                source_id=str(item.get("source_id") or ""),
                publication=self._publication(license, bool(name_uk or item.get("description_uk"))),
                meta=self.labels.source(str(item.get("source_id") or "")),
                data=item,
            )


def _level(record: Record) -> int:
    return int(record.group or 0)
