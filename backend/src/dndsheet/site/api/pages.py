"""Модель сторінки запису: заголовки, числа, текст і посилання — для одного шаблону.

Кожен вид запису (закляття, вид, клас, підклас, передісторія, риса, предмет)
зводиться до `EntryPage`: H1, рядок «що це», факти, розділи з текстом і групи
посилань. Шаблон `entry.html.jinja` один на всіх, тож розмітка, хлібні крихти
й JSON-LD однакові скрізь.

Текст правил розбирає той самий `rule_blocks`, що й друк листа: абзаци,
заголовки, списки, таблиці виглядають однаково на екрані, у PDF і тут.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from dndsheet.characters.api.print_view import rule_blocks
from dndsheet.shared.translations import spell_body
from dndsheet.site.application.catalog import SECTION_BY_ID, KbCatalog, Record
from dndsheet.site.application.facts import (
    Fact,
    background_facts,
    class_facts,
    species_facts,
    spell_facts,
    spell_level_label,
)
from dndsheet.site.application.labels import with_english


@dataclass(frozen=True, slots=True)
class TextSection:
    heading: str | None
    blocks: list[dict[str, Any]]
    level: int = 2
    anchor: str | None = None
    facts: list[Fact] = field(default_factory=list)
    #: «Перекладу ще немає — текст книги англійською».
    english: bool = False


@dataclass(frozen=True, slots=True)
class LinkGroup:
    heading: str
    records: list[Record]
    level: int = 2


@dataclass(frozen=True, slots=True)
class Crumb:
    name: str
    path: str


@dataclass(slots=True)
class EntryPage:
    record: Record
    meta_title: str
    description: str
    kind: str
    crumbs: list[Crumb]
    facts: list[Fact] = field(default_factory=list)
    sections: list[TextSection] = field(default_factory=list)
    links: list[LinkGroup] = field(default_factory=list)
    #: Текст книги приховано політикою (`summary`): показуємо, де його читати.
    withheld: bool = False
    source: Mapping[str, Any] = field(default_factory=dict)

    @property
    def indexable(self) -> bool:
        return self.record.publication.index


_SPACES = re.compile(r"\s+")
_MARKUP = re.compile(r"[*#|_>`]+")


def summary(text: str | None, limit: int = 155) -> str:
    """Перші ~155 знаків тексту без розмітки — для meta description."""
    plain = _SPACES.sub(" ", _MARKUP.sub(" ", text or "")).strip()
    if len(plain) <= limit:
        return plain
    cut = plain[:limit].rsplit(" ", 1)[0].rstrip(",;:—-")
    return f"{cut}…"


def describe(lead: str, text: str | None) -> str:
    body = summary(text, max(60, 158 - len(lead)))
    return f"{lead}. {body}" if body else f"{lead}."


def crumbs_for(record: Record, catalog: KbCatalog) -> list[Crumb]:
    section = SECTION_BY_ID[record.section]
    crumbs = [Crumb("Головна", "/"), Crumb("Довідник", "/kb"), Crumb(section.label, f"/kb/{section.id}")]
    if record.parent:
        parent = catalog.find("classes", record.parent)
        if parent:
            crumbs.append(Crumb(parent.name_uk or parent.name_en, parent.path))
    crumbs.append(Crumb(record.name_uk or record.name_en, record.path))
    return crumbs


def _text(uk: str | None, en: str | None) -> tuple[list[dict[str, Any]], bool]:
    if uk:
        return rule_blocks(uk), False
    return rule_blocks(en), bool(en)


_MONEY = (("gp", "зм"), ("sp", "ср"), ("cp", "мд"), ("pp", "пм"), ("ep", "ем"))


def _money(value: str) -> str:
    for en, uk in _MONEY:
        value = re.sub(rf"\b{en}\b", uk, value)
    return value


def compendium_page(record: Record, catalog: KbCatalog, source: Mapping[str, Any]) -> EntryPage:
    """Закляття, риса, опційне вміння, предмет — записи загального довідника."""
    entry = record.entry
    assert entry is not None
    section = SECTION_BY_ID[record.section]
    data = entry.data
    labels = catalog.labels
    facts: list[Fact] = []
    text_en = entry.text_en or ""
    noun = section.noun
    if record.section == "spells":
        facts = spell_facts(data, labels)
        text_en = spell_body(text_en)
        kind = f"Закляття · {spell_level_label(entry.spell_level or 0, entry.spell_school, labels, bool(data.get('ritual')))}"
    elif record.section == "items":
        noun = "магічний предмет" if entry.is_magical else "предмет"
        facts.append(Fact("Тип", record.group))
        if record.meta:
            facts.append(Fact("Рідкість", record.meta))
        for label, key in (("Ціна", "cost"), ("Вага", "weight"), ("Урон", "damage"), ("Клас захисту", "armor_class")):
            value = data.get(key)
            if value not in (None, "", 0):
                facts.append(Fact(label, _money(str(value)).replace(" lb.", " фнт").replace(" lb", " фнт")))
        if data.get("attunement"):
            facts.append(
                Fact(
                    "Налаштування", "потрібне" if data["attunement"] is True else str(data["attunement"]), "attunement"
                )
            )
        kind = f"{noun[0].upper()}{noun[1:]} · {record.group}"
    elif record.section == "options":
        facts.append(Fact("Група", record.group))
        kind = f"Опційне вміння · {record.group}"
    else:
        kind = "Риса"
    if entry.prerequisite:
        facts.append(Fact("Умова", entry.prerequisite))
    page = EntryPage(
        record=record,
        meta_title=f"{record.title} — {noun} D&D 5e українською",
        description="",
        kind=kind,
        crumbs=crumbs_for(record, catalog),
        facts=facts,
        source=source,
    )
    text_uk = catalog.text_uk(record)
    if record.publication.text:
        blocks, english = _text(text_uk, text_en)
        page.sections.append(TextSection(None, blocks, english=english))
    else:
        page.withheld = True
    lead = kind.replace(" · ", ", ")
    page.description = describe(lead, text_uk or (text_en if record.publication.text else ""))
    if record.section == "spells":
        classes = catalog.spell_classes(record.slug)
        if classes:
            page.facts.append(Fact("Класи", ", ".join(klass.name_uk or klass.name_en for klass in classes)))
            page.links.append(LinkGroup("Класи, які мають це закляття", classes))
        page.links.append(
            LinkGroup(
                f"Інші закляття: {spell_level_label(entry.spell_level or 0, None, labels)}", catalog.related(record)
            )
        )
    else:
        related = catalog.related(record)
        if related:
            page.links.append(LinkGroup(f"Інші {section.label.lower()}", related))
    return page


def _traits(traits: Sequence[Mapping[str, Any]], level: int = 3) -> list[TextSection]:
    out = []
    for trait in traits:
        name = with_english(str(trait.get("name_en") or ""), trait.get("name_uk"))
        blocks, english = _text(trait.get("text_uk"), trait.get("text"))
        out.append(TextSection(name, blocks, level=level, english=english))
    return out


def species_page(record: Record, catalog: KbCatalog, source: Mapping[str, Any]) -> EntryPage:
    item = record.data
    labels = catalog.labels
    page = EntryPage(
        record=record,
        meta_title=f"{record.title} — раса D&D 5e українською",
        description="",
        kind="Вид (раса) персонажа",
        crumbs=crumbs_for(record, catalog),
        facts=species_facts(item, labels),
        source=source,
    )
    withheld = not record.publication.text
    if item.get("description") and not withheld:
        blocks, english = _text(item.get("description_uk"), item.get("description"))
        page.sections.append(TextSection("Опис", blocks, english=english))
    if item.get("traits") and not withheld:
        page.sections.append(TextSection("Особливості", []))
        page.sections.extend(_traits(item["traits"]))
    for sub in item.get("subspecies") or ():
        name = labels.species_label(str(sub.get("name_en") or sub.get("key") or ""))
        blocks, english = ([], False) if withheld else _text(sub.get("description_uk"), sub.get("description"))
        page.sections.append(
            TextSection(
                f"Підраса: {name}",
                blocks,
                anchor=str(sub.get("key") or "").replace(" ", "-"),
                facts=species_facts(sub, labels),
                english=english,
            )
        )
        if sub.get("traits") and not withheld:
            page.sections.extend(_traits(sub["traits"]))
    page.withheld = withheld
    facts_text = ", ".join(f"{fact.label.lower()} {fact.value}" for fact in page.facts[:3])
    page.description = describe(f"Раса D&D 5e українською: {facts_text}", item.get("description_uk"))
    others = catalog.related(record)
    if others:
        page.links.append(LinkGroup("Інші раси", others))
    return page


def background_page(record: Record, catalog: KbCatalog, source: Mapping[str, Any]) -> EntryPage:
    item = record.data
    feature = (
        with_english(str(item.get("feature_en") or ""), item.get("feature_uk")) if item.get("feature_en") else None
    )
    page = EntryPage(
        record=record,
        meta_title=f"{record.title} — передісторія D&D 5e українською",
        description="",
        kind="Передісторія",
        crumbs=crumbs_for(record, catalog),
        facts=background_facts(item, catalog.labels, feature),
        source=source,
    )
    if record.publication.text:
        if item.get("description"):
            blocks, english = _text(item.get("description_uk"), item.get("description"))
            page.sections.append(TextSection("Опис", blocks, english=english))
        if feature:
            blocks, english = _text(item.get("feature_text_uk"), item.get("feature_text"))
            page.sections.append(TextSection(f"Риса: {feature}", blocks, english=english))
        equipment = item.get("equipment") or ()
        if equipment:
            rows = [
                str(row.get("text_uk") or catalog.labels.item(str(row.get("text") or "")) or row.get("text"))
                for row in equipment
            ]
            page.sections.append(TextSection("Спорядження", [{"kind": "ul", "items": rows}]))
    else:
        page.withheld = True
    page.description = describe(
        "Передісторія D&D 5e українською", item.get("description_uk") or item.get("description")
    )
    others = catalog.related(record)
    if others:
        page.links.append(LinkGroup("Інші передісторії", others))
    return page


def _features(rows: Sequence[Mapping[str, Any]], text_key: str = "text") -> list[TextSection]:
    out = []
    for row in rows:
        name = with_english(str(row.get("name_en") or ""), row.get("name_uk"))
        blocks, english = _text(row.get("text_uk"), row.get(text_key))
        out.append(TextSection(f"{row.get('level')} рівень · {name}", blocks, level=3, english=english))
    return out


def class_page(
    record: Record, catalog: KbCatalog, features: Sequence[Mapping[str, Any]], source: Mapping[str, Any]
) -> EntryPage:
    item = record.data
    page = EntryPage(
        record=record,
        meta_title=f"{record.title} — клас D&D 5e українською: уміння й підкласи",
        description="",
        kind="Клас",
        crumbs=crumbs_for(record, catalog),
        facts=class_facts(item, catalog.labels),
        source=source,
    )
    if record.publication.text:
        if item.get("description"):
            blocks, english = _text(item.get("description_uk"), item.get("description"))
            page.sections.append(TextSection("Опис класу", blocks, english=english))
        if features:
            page.sections.append(TextSection("Уміння за рівнями", []))
            page.sections.extend(_features(features))
    else:
        page.withheld = True
    subclasses = catalog.subclasses(record.slug)
    if subclasses:
        page.links.append(LinkGroup(f"Підкласи — {len(subclasses)}", subclasses))
    spells = catalog.class_spells(record.slug)
    if spells:
        page.links.append(LinkGroup("Закляття класу", [], level=2))
        by_level: dict[str, list[Record]] = {}
        for spell in spells:
            by_level.setdefault(spell.group, []).append(spell)
        for level, group in by_level.items():
            heading = "Заговори" if level == "0" else f"{level} рівень"
            page.links.append(LinkGroup(heading, group, level=3))
    names = ", ".join(fact.value for fact in page.facts[:1])
    lead = f"Клас D&D 5e українською{': ' + names if names else ''}"
    page.description = describe(lead, item.get("description_uk") or item.get("description"))
    return page


def subclass_page(
    record: Record, catalog: KbCatalog, details: Mapping[str, Any], source: Mapping[str, Any]
) -> EntryPage:
    parent = catalog.find("classes", record.parent or "")
    class_name = (parent.name_uk or parent.name_en) if parent else ""
    page = EntryPage(
        record=record,
        meta_title=f"{record.title} — підклас D&D 5e ({class_name})"
        if class_name
        else f"{record.title} — підклас D&D 5e",
        description="",
        kind=f"Підклас · {class_name}" if class_name else "Підклас",
        crumbs=crumbs_for(record, catalog),
        source=source,
    )
    if record.meta:
        page.facts.append(Fact("Відкривається", record.meta))
    if record.publication.text:
        if details.get("description"):
            blocks, english = _text(details.get("description_uk"), details.get("description"))
            page.sections.append(TextSection(None, blocks, english=english))
        features = details.get("features") or ()
        if features:
            page.sections.append(TextSection("Уміння підкласу", []))
            page.sections.extend(_features(features, text_key="description"))
    else:
        page.withheld = True
    page.description = describe(
        f"Підклас D&D 5e українською{': ' + class_name if class_name else ''}",
        details.get("description_uk") or details.get("description"),
    )
    if parent:
        siblings = [sub for sub in catalog.subclasses(parent.slug) if sub.slug != record.slug]
        page.links.append(LinkGroup(f"Клас: {parent.title}", [parent]))
        if siblings:
            page.links.append(LinkGroup("Інші підкласи", siblings))
    return page
