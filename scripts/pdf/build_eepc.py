"""Build compendium records for the Elemental Evil Player's Companion (2015).

Unlike Glory of the Giants, this PDF has a real text layer, so no OCR is needed:
the page text is parsed directly. The book holds four race entries (three races
plus the deep gnome subrace) and 43 spells, whose class lists live in a separate
"Spell Lists" section from the descriptions.

    python scripts/pdf/build_eepc.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical as compendium_format  # noqa: E402

COMPENDIUM = ROOT / "content" / "compendium" / "eepc"
SOURCE = "eepc"
URL = "https://media.wizards.com/2015/downloads/dnd/EE_PlayersCompanion.pdf"
LICENSE = "free"
FETCHED = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

FURNITURE = re.compile(
    r"^\s*(?:Chapter\s*[12]\s*[|:]\s*.{0,30}|\d{1,3}|Chapter\s*2:\s*Spells)\s*$",
    re.IGNORECASE,
)
SPELL_HEADER = re.compile(r"^(?:(?P<level>\d+)(?:st|nd|rd|th)-level (?P<school>[a-z]+)(?P<ritual> \(ritual\))?"
                          r"|(?P<cantrip_school>[a-z]+) cantrip(?P<cantrip_ritual> \(ritual\))?)$", re.I)
RACE_HEADINGS = ("Aarakocra", "Deep Gnome", "Genasi", "Goliath")
GENASI_SUBRACES = ("Air Genasi", "Earth Genasi", "Fire Genasi", "Water Genasi")
TRAIT = re.compile(r"^([A-Z][A-Za-z’' \-]{2,34})\.\s+(.+)$")
SCHOOLS = (
    "abjuration", "conjuration", "divination", "enchantment", "evocation",
    "illusion", "necromancy", "transmutation",
)
# The last spell runs into the back-cover marketing page; nothing after these
# lines belongs to a spell description.
BODY_STOP = re.compile(
    r"(?i)^(?:\s*what happens next|ontinue unraveling|continue unraveling"
    r"|.*downloadable module|.*MMORPG|.*Gale Force Nine|.*WizKids"
    r"|.*Adventurers League|.*board game provides)"
)


def normalise(text: str) -> str:
    # U+00AD is a soft hyphen the PDF inserts inside wrapped words; dropping it
    # keeps names like "Abi-Dalzim's" searchable.
    text = text.replace("\u00ad", "")
    return (text.replace("\ufffd", "'").replace("\u2019", "'")
            .replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2022", "-"))


def load_pages(pdf: Path) -> list[str]:
    doc = pymupdf.open(pdf)
    return [doc[index].get_text("text") for index in range(doc.page_count)]


def load_lines(pages: list[str]) -> tuple[list[str], list[int]]:
    """Flat list of body lines with the PDF page each came from.

    This book has no styled headings in the text layer (no caps, no bold flags),
    but it does keep one logical line per PDF line, which is a much steadier
    anchor than paragraph reconstruction.
    """
    lines: list[str] = []
    page_of: list[int] = []
    for page_index, raw in enumerate(pages, start=1):
        for line in raw.splitlines():
            if FURNITURE.match(line):
                continue
            text = normalise(line.strip())
            if not text:
                continue
            lines.append(text)
            page_of.append(page_index)
    return lines, page_of


def join_lines(lines: list[str]) -> str:
    """Join wrapped lines into prose, repairing end-of-line hyphenation."""
    out = ""
    for line in lines:
        if not out:
            out = line
        elif out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        else:
            out = out + " " + line
    return re.sub(r"\s+", " ", out).strip()


def slugify(name: str) -> str:
    slug = normalise(name).lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


# --- spells --------------------------------------------------------------

def spell_lists(lines: list[str]) -> dict[str, list[str]]:
    """class -> spell names, read from the 'Bard Spells' style lists."""
    classes: dict[str, list[str]] = {}
    current: str | None = None
    in_lists = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Spell Lists":
            in_lists = True
            continue
        if in_lists and stripped.startswith("Spell Descriptions"):
            break
        match = re.fullmatch(r"(Bard|Cleric|Druid|Paladin|Ranger|Sorcerer|Warlock|Wizard) Spells", stripped)
        if match:
            current = match.group(1).lower()
            classes[current] = []
            continue
        if not in_lists or current is None:
            continue
        if re.fullmatch(r"(Cantrips \(0 Level\)|\d+(?:st|nd|rd|th) Level)", stripped):
            continue
        match = re.match(r"([A-Z][A-Za-z’' \-]+?)\s*\((?:[a-z, ]+)\)\s*$", stripped)
        if match:
            classes[current].append(normalise(match.group(1)).strip())
    return {name: sorted(set(values)) for name, values in classes.items() if values}


def parse_spells(lines: list[str], page_of: list[int], lists: dict[str, list[str]]) -> list[dict]:
    known = {normalise(name).lower(): name for values in lists.values() for name in values}
    spells: list[dict] = []
    index = 0
    while index < len(lines) - 2:
        candidate = normalise(lines[index]).strip()
        header = SPELL_HEADER.match(lines[index + 1].strip())
        # A description starts at the spell's own name (as listed) followed by
        # its level/school line; this also skips the alphabetical list itself.
        if not header or candidate.lower() not in known:
            index += 1
            continue

        # Use the name as the description prints it ("Absorb Elements"), not
        # the sentence-case form used in the class lists.
        name = normalise(lines[index]).strip()
        fields: dict[str, str] = {}
        body: list[str] = []
        current_field: str | None = None
        cursor = index + 2
        while cursor < len(lines):
            line = lines[cursor].strip()
            # The entry ends where the next spell's name line is followed by its
            # level/school line; checking the current line (not the next one)
            # keeps the last body sentence from being swallowed.
            following = lines[cursor + 1] if cursor + 1 < len(lines) else ""
            if normalise(line).lower() in known and SPELL_HEADER.match(following.strip()):
                break
            if BODY_STOP.match(line):
                break
            head = re.match(r"^(Casting Time|Range|Components|Duration):\s*(.+)$", line)
            if head:
                current_field = head.group(1).lower()
                fields[current_field] = head.group(2).strip()
                cursor += 1
                continue
            if len(fields) == 4:
                body.append(line)
            elif current_field:
                # A field value that wrapped onto the next line, e.g.
                # "Casting Time: 1 reaction, which you take when you take
                #  acid, cold, fire, lightning, or thunder damage".
                fields[current_field] = fields[current_field] + " " + line
            cursor += 1

        level = 0 if header.group("cantrip_school") else int(header.group("level"))
        school = (header.group("cantrip_school") or header.group("school")).lower()
        ritual = bool(header.group("ritual") or header.group("cantrip_ritual"))
        duration = fields.get("duration", "")
        text_body = join_lines(body)
        higher = ""
        marker = text_body.find("At Higher Levels.")
        if marker >= 0:
            higher = text_body[marker + len("At Higher Levels."):].strip()
            text_body = text_body[:marker].strip()

        spells.append(
            {
                "name": name,
                "page": page_of[index],
                "data": {
                    "level": level,
                    "school": school,
                    "ritual": ritual,
                    "concentration": duration.lower().startswith("concentration"),
                    "casting_time": fields.get("casting time"),
                    "range": fields.get("range"),
                    "components": fields.get("components"),
                    "duration": duration or None,
                    "classes": sorted(name_class for name_class, values in lists.items()
                                      if any(slugify(name) == slugify(value) for value in values)),
                    "at_higher_levels": higher or None,
                },
                "text": text_body,
            }
        )
        index = cursor
    return spells


# --- species -------------------------------------------------------------

def parse_species(lines: list[str], page_of: list[int]) -> list[dict]:
    """Four race entries; genasi carries four subraces worth separate records."""
    marks: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        title = line.strip()
        if title not in RACE_HEADINGS and title not in GENASI_SUBRACES:
            continue
        if "...." in title:
            continue  # table of contents on page 2
        marks.append((index, title))

    species: list[dict] = []
    for position, (index, title) in enumerate(marks):
        end = marks[position + 1][0] if position + 1 < len(marks) else len(lines)
        for cursor in range(index + 1, end):
            if lines[cursor].strip() in ("Spell Lists", "Spell Descriptions"):
                end = cursor
                break
        body = lines[index + 1:end]
        text = join_lines(body)
        data: dict = {"ability_increases": {}, "size": None, "speed": None, "subrace_of": None}
        if title in GENASI_SUBRACES:
            data["subrace_of"] = "genasi"
        if title == "Deep Gnome":
            data["subrace_of"] = "gnome"
        data.update(extract_race_data(text))
        species.append({"name": title, "page": page_of[index], "data": data, "text": text})
    return species


def extract_race_data(text: str) -> dict:
    data: dict = {}
    increases: dict[str, int] = {}
    for match in re.finditer(
        r"(?:Ability Score Increase\.)\s*(.+?)(?=[A-Z][A-Za-z’' ]{2,34}\.\s|$)", text
    ):
        clause = match.group(1)
        for score, amount in re.findall(
            r"(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+score[s]?\s+"
            r"(?:increases|increase)\s+by\s+(\d+)", clause
        ):
            increases[score.lower()] = int(amount)
    data["ability_increases"] = increases

    size = re.search(r"Your size is (Small|Medium)", text)
    if size:
        data["size"] = size.group(1).lower()
    speed = re.search(r"Speed\.\s+Your base (?:walking|flying) speed is (\d+) feet", text)
    data["speed"] = int(speed.group(1)) if speed else None
    return data


# --- records -------------------------------------------------------------

def record(category: str, name: str, text: str, data: dict, page: int | None) -> dict:
    return {
        "id": f"{SOURCE}/{category}/{slugify(name)}",
        "schema": "compendium-entry/1",
        "source_id": SOURCE,
        "category": category,
        "name_en": normalise(name),
        "name_uk": None,
        "edition": "2014",
        "license": LICENSE,
        "url": URL,
        "page": page,
        "text_en": text.strip(),
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": FETCHED,
        "notes": ["text extracted from the published PDF (real text layer, no OCR)"],
    }


def main() -> None:
    default = ROOT / "content" / "raw" / "eepc" / "EE_PlayersCompanion.pdf"
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not pdf.exists():
        raise SystemExit(f"немає PDF: {pdf}")
    pages = load_pages(pdf)
    lines, page_of = load_lines(pages)
    lists = spell_lists(lines)
    spells = parse_spells(lines, page_of, lists)
    species = parse_species(lines, page_of)

    records: dict[str, list[dict]] = {"species": [], "spell": [], "rule": []}
    for item in species:
        records["species"].append(record("species", item["name"], item["text"], item["data"], item["page"]))
    for item in spells:
        records["spell"].append(record("spell", item["name"], item["text"], item["data"], item["page"]))

    rules = [
        ("Chapter 1: Races", "chapter-1-races",
         "This chapter presents three new races to supplement those in the Player's Handbook: "
         "aarakocra, genasi, and goliaths. A gnome subrace—the deep gnome—is also included. These "
         "new options are available when you make a character, provided that your DM allows them in "
         "your campaign.", 3),
        ("Chapter 2: Spells", "chapter-2-spells",
         "This chapter offers new spells for many of the classes in the Player's Handbook. The spells "
         "provide various ways to harness the power of the four elements. Your DM determines whether "
         "these spells are available at character creation, whether they are discovered in a treasure "
         "trove, or whether you stumble upon them in an ancient library or other storehouse of magical "
         "knowledge.", 12),
    ]
    for name, slug, text, page in rules:
        entry = record("rule", name, text, {}, page)
        entry["id"] = f"{SOURCE}/rule/{slug}"
        records["rule"].append(entry)

    COMPENDIUM.mkdir(parents=True, exist_ok=True)
    for category, items in records.items():
        target = COMPENDIUM / f"{category}.jsonl"
        with target.open("w", encoding="utf-8") as handle:
            for entry in items:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"{category}: {len(items)}")

    # Формат записів не залежить від конвеєра: після збірки приводимо книгу до
    # contract/compendium-format.json (рядок рівня школи, порядок ключів data).
    compendium_format.normalize_source(SOURCE, compendium_format.load_spec(), write=True)


if __name__ == "__main__":
    main()
