#!/usr/bin/env python3
"""Record API responses for the frontend tests (a "tape") from the real backend.

The frontend tests render the real components, so they need real-shaped API data:
a character sheet, a wizard step, a level-up plan, the compendium. Writing those by
hand would drift from the backend; recording them keeps the shapes honest.

The corpus holds copyrighted book text, and the tape is committed in plaintext. So
every long string is scrubbed: words become "lorem", while numbers, dice and markdown
structure stay (the UI still parses headings, lists and dice). Short strings — names,
keys, labels — are kept as they are. Long lists are cut.

    python scripts/record_frontend_tape.py   # needs the unlocked corpus

Output: frontend/src/test/tape.json.gz (gzipped: the JSON is ~2 MB, the archive a fraction of it)
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "logs" / "tmp-frontend-tape"
OUT = ROOT / "frontend" / "src" / "test" / "tape.json.gz"

sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["DNDSHEET_CONTENT_DIR"] = str(ROOT / "content")
os.environ["DNDSHEET_AUTH"] = "off"
shutil.rmtree(DATA_DIR, ignore_errors=True)
DATA_DIR.mkdir(parents=True)
os.environ["DNDSHEET_DATA_DIR"] = str(DATA_DIR)

from dndsheet.api.app import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from print_samples import SAMPLES  # noqa: E402

#: Strings longer than this are treated as prose and scrubbed.
PROSE = 60
#: Lists longer than this are cut (pagination "total" is cut with them).
MAX_LIST = 10
#: Keys always kept when a list is cut, so the tests can rely on them.
KEEP = {
    "human",
    "dwarf",
    "elf",
    "hill dwarf",
    "high elf",
    "cleric",
    "fighter",
    "wizard",
    "warlock",
    "acolyte",
    "soldier",
    "sage",
    "life domain",
    "phb-2014/subclass/life-domain",
    "deep gnome",
    "gnome",
    "fire bolt",
    "light",
    "mage hand",
    "magic missile",
    "shield",
    "chain mail",
}
WORD = re.compile(r"[^\W\d_]+(?:['ʼ’-][^\W\d_]+)*", re.UNICODE)


#: A scrubbed text keeps at most this many lines, each cut to LINE characters.
LINES = 6
LINE = 90


def scrub_text(text: str) -> str:
    lines = WORD.sub("lorem", text).split("\n")
    kept: list[str] = []
    for line in lines:
        if line.strip():
            if sum(1 for row in kept if row.strip()) >= LINES:
                break
            kept.append(line[:LINE])
        elif kept and kept[-1].strip():
            kept.append("")
    return "\n".join(kept).strip()


def keep_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    for field in ("key", "id", "name_en", "class_key"):
        value = item.get(field)
        if isinstance(value, str) and value.casefold() in KEEP:
            return True
    return False


#: Starting equipment lists ("(a) chain mail or (b) leather armor…") are item names,
#: not prose, and the wizard parses them: kept as they are, only capped.
EQUIPMENT_KEYS = {"equipment", "equipment_uk", "choices", "choices_uk"}
EQUIPMENT_CAP = 600


def keep_equipment(value: object) -> object:
    if isinstance(value, str):
        return value[:EQUIPMENT_CAP]
    if isinstance(value, list):
        return [keep_equipment(item) for item in value[:MAX_LIST]]
    if isinstance(value, dict):
        return {key: keep_equipment(item) for key, item in value.items()}
    return value


def scrub(value: object) -> object:
    if isinstance(value, str):
        return scrub_text(value) if len(value) > PROSE else value
    if isinstance(value, list):
        items = value
        if len(items) > MAX_LIST:
            head = items[:MAX_LIST]
            head += [item for item in items[MAX_LIST:] if keep_item(item)]
            items = head
        return [scrub(item) for item in items]
    if isinstance(value, dict):
        # The class chapter's "Equipment" row: the text the equipment step reads.
        if value.get("name_en") == "Equipment":
            return {
                key: keep_equipment(item) if key.startswith("text") else scrub(item) for key, item in value.items()
            }
        out = {key: keep_equipment(item) if key in EQUIPMENT_KEYS else scrub(item) for key, item in value.items()}
        if isinstance(value.get("items"), list) and isinstance(value.get("total"), int):
            out["total"] = len(out["items"])
        return out
    return value


class Recorder:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.tape: list[dict] = []

    def call(self, method: str, url: str, body: object | None = None) -> dict:
        kwargs = {"json": body} if body is not None else {}
        response = self.client.request(method, url, **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            print(f"  {response.status_code} {method} {url}: {str(payload)[:160]}")
        entry = {"method": method, "url": url, "status": response.status_code, "body": scrub(payload)}
        # The request body (without the version): two POSTs to one URL (a short and a long
        # rest) are told apart by it.
        if isinstance(body, dict) and body:
            entry["request"] = {key: value for key, value in body.items() if key != "version"}
        self.tape.append(entry)
        return payload if isinstance(payload, dict) else {}

    def get(self, url: str) -> dict:
        return self.call("GET", url)


def rogue_6(rules):  # noqa: ANN001, ANN201
    from dndsheet.characters.domain.character import Character  # noqa: PLC0415
    from dndsheet.characters.domain.class_level import CharacterClass  # noqa: PLC0415
    from dndsheet.shared.kernel import Skill  # noqa: PLC0415
    from print_samples import _scores, _skills  # noqa: PLC0415

    return Character(
        id="rogue-6",
        name="Тінь",
        abilities=_scores(str=8, dex=16, con=12, int=13, wis=12, cha=14),
        rules=rules,
        species_key="human",
        background_key="criminal",
        classes=[CharacterClass(class_key="rogue", level=6, subclass_key="phb-2014/subclass/thief")],
        chosen=_skills("rogue", Skill.STEALTH, Skill.ACROBATICS, Skill.PERCEPTION, Skill.DECEPTION),
    )


def record_wizard(rec: Recorder) -> str:
    start = rec.call("POST", "/api/v1/characters/wizard", {})
    draft_id = start["draft"]["id"]
    steps = [
        ("species", {"name": "Сестра Анна", "species_key": "human"}),
        ("class", {"class_key": "cleric", "subclass_key": "phb-2014/subclass/life-domain"}),
        (
            "abilities",
            {"method": "standard_array", "scores": {"str": 12, "dex": 10, "con": 14, "int": 8, "wis": 15, "cha": 13}},
        ),
        (
            "background",
            {
                "background_key": "acolyte",
                "alignment": "lawful good",
                "picks": [
                    {"kind": "skill", "value": "history", "source": {"kind": "class", "key": "cleric"}},
                    {"kind": "skill", "value": "persuasion", "source": {"kind": "class", "key": "cleric"}},
                ],
            },
        ),
        ("equipment", {"items": [], "money": {"gp": 15}}),
        (
            "spells",
            {
                "spells": [
                    {"name_en": "Light", "level": 0, "class_key": "cleric"},
                    {"name_en": "Sacred Flame", "level": 0, "class_key": "cleric"},
                    {"name_en": "Guidance", "level": 0, "class_key": "cleric"},
                ]
            },
        ),
    ]
    for step, body in steps:
        rec.get(f"/api/v1/characters/wizard/{draft_id}/steps/{step}")
        rec.call("PUT", f"/api/v1/characters/wizard/{draft_id}/steps/{step}", body)
    rec.get(f"/api/v1/characters/wizard/{draft_id}")
    finished = rec.call("POST", f"/api/v1/characters/wizard/{draft_id}/finish", {})
    rec.call(
        "POST",
        "/api/v1/characters/wizard/feat-choices",
        {"feat": "phb-2014/feat/skilled", "species_key": "human", "subspecies_key": None, "choices": {}},
    )
    # An unfinished draft for the "continue" link on the home page.
    rec.call("POST", "/api/v1/characters/wizard", {})
    return finished.get("character_id", "")


def record_draft(rec: Recorder, steps: list[tuple[str, dict]]) -> str:
    """One more draft, step by step: each step read, then written (not finished)."""
    draft_id = rec.client.post("/api/v1/characters/wizard").json()["draft"]["id"]
    for step, body in steps:
        rec.get(f"/api/v1/characters/wizard/{draft_id}/steps/{step}")
        rec.call("PUT", f"/api/v1/characters/wizard/{draft_id}/steps/{step}", body)
    rec.get(f"/api/v1/characters/wizard/{draft_id}/steps/spells")
    return draft_id


#: A deep gnome wizard: an MotM species (+2/+1 spread), point buy, a wizard's spellbook.
GNOME_WIZARD = [
    ("species", {"name": "Тікі", "species_key": "deep gnome", "ability_spread": {"int": 2, "dex": 1}}),
    ("class", {"class_key": "wizard"}),
    ("abilities", {"method": "point_buy", "scores": {"str": 8, "dex": 14, "con": 14, "int": 15, "wis": 12, "cha": 8}}),
    (
        "background",
        {
            "background_key": "sage",
            "picks": [
                {"kind": "skill", "value": "investigation", "source": {"kind": "class", "key": "wizard"}},
                {"kind": "skill", "value": "insight", "source": {"kind": "class", "key": "wizard"}},
            ],
        },
    ),
    ("equipment", {"items": [{"name_en": "quarterstaff", "kind": "weapon", "weight_lb": 4}], "money": {"gp": 10}}),
]

#: A high elf fighter: a species cantrip choice, class equipment, a non-casting spells step.
ELF_FIGHTER = [
    (
        "species",
        {"name": "Ільвен", "species_key": "elf", "subspecies_key": "high elf", "spell_choices": ["fire bolt"]},
    ),
    ("class", {"class_key": "fighter"}),
    ("abilities", {"method": "manual", "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}}),
    (
        "background",
        {
            "background_key": "soldier",
            "picks": [
                {"kind": "skill", "value": "acrobatics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "survival", "source": {"kind": "class", "key": "fighter"}},
            ],
        },
    ),
    (
        "equipment",
        {"items": [{"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True}]},
    ),
]


def record_variant_human(rec: Recorder) -> str:
    """A variant human fighter: the only sheet with a species feat (and its choices)."""
    draft_id = rec.client.post("/api/v1/characters/wizard").json()["draft"]["id"]
    species = {
        "name": "Ліна",
        "species_key": "human",
        "subspecies_key": "variant human",
        "ability_choices": ["str", "con"],
    }
    steps = [
        ("species", {**species, "species_feat": "phb-2014/feat/skilled"}),
        ("class", {"class_key": "fighter"}),
        (
            "abilities",
            {"method": "standard_array", "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}},
        ),
        (
            "background",
            {
                "background_key": "soldier",
                "picks": [
                    {"kind": "skill", "value": "acrobatics", "source": {"kind": "class", "key": "fighter"}},
                    {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
                    {"kind": "skill", "value": "stealth", "source": {"kind": "species", "key": "variant human"}},
                ],
            },
        ),
    ]
    for step, body in steps:
        rec.client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
    character_id = rec.client.post(f"/api/v1/characters/wizard/{draft_id}/finish").json()["character_id"]
    sheet = rec.get(f"/api/v1/characters/{character_id}")["sheet"]
    version = sheet["character"]["version"]
    payload = rec.call(
        "POST",
        f"/api/v1/characters/{character_id}/species-feat",
        {"feat_key": "phb-2014/feat/skilled", "feat_ability": None, "version": version},
    )
    version = payload.get("sheet", {}).get("character", {}).get("version", version)
    for group in sheet.get("class_choices") or []:
        rec.call(
            "POST",
            f"/api/v1/characters/{character_id}/class-choices",
            {"group": group["key"], "values": group.get("chosen") or [], "version": version},
        )
        break
    return character_id


def record_character(rec: Recorder, character_id: str) -> None:
    base = f"/api/v1/characters/{character_id}"
    sheet = rec.get(base).get("sheet", {})
    rec.get(f"{base}/version")
    rec.get(f"{base}/share")
    plan = rec.get(f"{base}/level-up")
    for row in plan.get("plans") or []:
        for option in (row.get("subclass") or {}).get("options") or []:
            rec.get(f"/api/v1/characters/wizard/subclass/{option['id']}")
            break
    version = (sheet.get("character") or {}).get("version", 1)
    for cls in (sheet.get("character") or {}).get("classes") or []:
        key = cls.get("class_key") or cls.get("key")
        if key:
            rec.get(f"/api/v1/characters/wizard/class-features/{key}")
            rec.get(f"/api/v1/compendium/classes/{key}/spells?max_level=9")
    return version


def record_mutations(rec: Recorder, character_id: str) -> None:
    base = f"/api/v1/characters/{character_id}"
    version = rec.get(base)["sheet"]["character"]["version"]

    def mutate(method: str, url: str, body: dict) -> None:
        nonlocal version
        payload = rec.call(method, url, {**body, "version": version})
        version = ((payload.get("sheet") or {}).get("character") or {}).get("version", version)

    mutate("PATCH", base, {"hp": {"damage": 3}})
    mutate("POST", f"{base}/hit-dice", {"die": 8, "roll": 4})
    mutate("POST", f"{base}/rest", {"kind": "short"})
    mutate("POST", f"{base}/rest", {"kind": "long"})
    mutate("POST", f"{base}/spells", {"class_key": "cleric", "name_en": "Bless", "level": 1})
    mutate("POST", f"{base}/spells/prepare", {"class_key": "cleric", "spells": [{"name_en": "Bless", "level": 1}]})
    mutate("DELETE", f"{base}/spells", {"class_key": "cleric", "name_en": "Bless"})
    mutate("POST", f"{base}/expertise", {"expertise": []})
    mutate("POST", f"{base}/species-source", {"source": None})
    mutate("POST", f"{base}/items", {"item": {"name_en": "Rope, hempen (50 feet)", "kind": "gear", "quantity": 1}})
    mutate("PATCH", f"{base}/items/0", {"fields": {"equipped": True}})
    mutate("DELETE", f"{base}/items/0", {})
    # Custom entries: a feature with a counter (added, edited, removed) and a spell outside any class.
    added = rec.call(
        "POST",
        f"{base}/custom-features",
        {
            "feature": {"name": "Дар майстра", "text": "Раз на день — перекинути кидок.", "uses": 1},
            "version": version,
        },
    )
    version = added["version"]
    feature_url = f"{base}/custom-features/{added['feature_id']}"
    mutate("PATCH", feature_url, {"fields": {"origin": "Перстень"}})
    mutate("DELETE", feature_url, {})
    custom_spell = {"class_key": "other", "name_en": "Вогонь перстня", "level": 1, "custom": True}
    mutate("POST", f"{base}/spells", {**custom_spell, "description": "1d10 вогню."})
    mutate("PATCH", f"{base}/spells", {"class_key": "other", "name_en": "Вогонь перстня", "fields": {"level": 2}})
    mutate("DELETE", f"{base}/spells", {"class_key": "other", "name_en": "Вогонь перстня"})
    share = rec.call("POST", f"{base}/share", {})
    token = share.get("token")
    if token:
        rec.get(f"/api/v1/shared/{token}")
        rec.get(f"/api/v1/shared/{token}/version")
    rec.call("DELETE", f"{base}/share")


def record_compendium(rec: Recorder) -> None:
    for url in (
        "/api/v1/auth/config",
        "/api/v1/auth/me",
        "/api/v1/renderers",
        "/api/v1/compendium/books",
        "/api/v1/compendium/summary",
        "/api/v1/kb/species",
        "/api/v1/kb/classes",
        "/api/v1/kb/backgrounds",
        "/api/v1/compendium/items?limit=200&offset=0",
        "/api/v1/compendium/items?q=rope&limit=8",
        "/api/v1/demo/sheet",
    ):
        rec.get(url)
    for category in ("feat", "spell", "optionalfeature", "item", "background", "species"):
        page = rec.get(f"/api/v1/compendium/entries?category={category}&limit=200&offset=0")
        for item in (page.get("items") or [])[:2]:
            rec.get(f"/api/v1/compendium/entries/{item['id']}")


def main() -> int:
    app = create_app()
    if not app.state.golden_cases:
        sys.exit("No mechanics index: unlock the corpus first (git-crypt unlock).")
    rec = Recorder(TestClient(app))

    ids: dict[str, str] = {}
    for case in app.state.golden_cases:
        app.state.characters.save(replace(case.character, id=case.key))
        ids[case.key] = case.key
    for key, build in SAMPLES.items():
        app.state.characters.save(replace(build(app.state.rules), id=key))
        ids[key] = key
    # A rogue: the only sheet with expertise slots (and thieves' cant, sneak attack).
    app.state.characters.save(rogue_6(app.state.rules))
    ids["rogue-6"] = "rogue-6"

    record_compendium(rec)
    ids["wizard-cleric"] = record_wizard(rec)
    ids["variant-human"] = record_variant_human(rec)
    ids["draft-gnome-wizard"] = record_draft(rec, GNOME_WIZARD)
    ids["draft-elf-fighter"] = record_draft(rec, ELF_FIGHTER)
    rec.get("/api/v1/characters")
    for key, character_id in ids.items():
        if key.startswith("draft-"):
            continue
        record_character(rec, character_id)
    record_mutations(rec, "cleric-5")
    warlock = rec.get("/api/v1/characters/warlock-5")["sheet"]
    for group in warlock.get("class_choices") or []:
        rec.call(
            "POST",
            "/api/v1/characters/warlock-5/class-choices",
            {"group": group["key"], "values": group.get("chosen") or [], "version": warlock["character"]["version"]},
        )
        break
    # A cleric prepares spells: after the level the screen offers the day's set.
    cleric = rec.client.get("/api/v1/characters/cleric-5").json()["sheet"]["character"]
    body = {"class_key": "cleric", "hp": {"mode": "average"}, "version": cleric["version"]}
    response = rec.client.post("/api/v1/characters/cleric-5/level-up", json=body)
    if response.status_code == 422:
        response = rec.client.post(
            "/api/v1/characters/cleric-5/level-up", json={**body, "ability_increases": {"wis": 2}}
        )
    rec.tape.append(
        {
            "method": "POST",
            "url": "/api/v1/characters/cleric-5/level-up",
            "status": response.status_code,
            "body": scrub(response.json()),
        }
    )
    print(f"  cleric level-up: {response.status_code}")
    fighter = rec.get("/api/v1/characters/fighter-1")["sheet"]["character"]
    rec.call(
        "POST",
        "/api/v1/characters/fighter-1/level-up",
        {"class_key": "fighter", "hp": {"mode": "average"}, "version": fighter["version"]},
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Identical bodies (a wizard step read and written, two rests) are stored once.
    bodies: dict[str, object] = {}
    index: dict[str, str] = {}
    entries = []
    for entry in rec.tape:
        text = json.dumps(entry["body"], ensure_ascii=False, sort_keys=True)
        ref = index.setdefault(text, f"b{len(index)}")
        bodies[ref] = entry["body"]
        entries.append({**entry, "body": ref})
    payload = {"ids": ids, "bodies": bodies, "tape": entries}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0: the same recording gives the same bytes.
    OUT.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    print(f"{OUT.relative_to(ROOT)}: {len(rec.tape)} responses, {OUT.stat().st_size / 1024:.0f} KB")
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
