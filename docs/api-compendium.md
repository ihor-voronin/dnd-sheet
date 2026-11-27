# Compendium API

The character wizard and the sheet take classes, subclasses, spells and items **over
HTTP** instead of reading `content/` themselves. The compendium is read-only: nothing is
created or changed through this API.

## Where the data comes from

`content/compendium/<book>/<category>.jsonl` — records from 89 books in 9 categories
(classes, subclasses, species, backgrounds, feats, optional features, spells, items,
rules). The record format is `contract/compendium-entry.schema.json`, the canonical field
order is `contract/compendium-format.json`.

The corpus is read into memory once at startup (≈0.6 s). The folder can be overridden
with `DNDSHEET_CONTENT_DIR` — that's how tests substitute their own small corpus.

In the repository the corpus is encrypted (git-crypt, book texts are copyrighted). In a
clone that isn't unlocked, `/summary` returns `entries: 0` and a warning, not a 500.

## Layers

```
compendium/
  domain/          # CompendiumEntry, Category, EntryQuery, Page, ports
  application/     # CompendiumService: summary, classes, class spells, books overview
  infrastructure/  # JSONL corpus, derived spell-list index, book names, market data
  api/             # APIRouter + serialization
```

`lint-imports` enforces this: the domain sees neither FastAPI nor infrastructure.

## Endpoints

All under `/api/v1/compendium`.

| Method | Path | Returns |
|---|---|---|
| GET | `/summary` | how many records, by category and book; whether class spell lists exist; warnings |
| GET | `/books` | books for the home page: what each contributes, price, D&D Beyond link, cover |
| GET | `/entries` | records with filters and pagination |
| GET | `/entries/{id}` | the full record card, including `text_en` |
| GET | `/classes` | classes + number of subclasses each |
| GET | `/classes/{class}/subclasses` | the class's subclasses |
| GET | `/classes/{class}/spells?max_level=` | the class's spells up to a level; `source` says where they came from |
| GET | `/spells?level=&school=&class_name=&q=` | spells |
| GET | `/optional-features?feature_type=` | invocations, maneuvers, metamagic, infusions… |
| GET | `/items?item_type=&rarity=&magical=&q=` | items |
| GET | `/mechanics` | how many classes, species and backgrounds have numbers |
| GET | `/classes/mechanics` | all classes with mechanics (for the selection screen) |
| GET | `/classes/{class}/mechanics` | hit die, proficiencies, slots, features by level, multiclass prerequisites |
| GET | `/species` | base species with ability bonuses |
| GET | `/species/{species}/subspecies` | the species' subraces (with inherited numbers) |
| GET | `/species/{species}/mechanics` | one species or subrace |
| GET | `/backgrounds` | backgrounds with skills and languages |
| GET | `/backgrounds/{name}/mechanics` | one background |

The wizard's Species step (`/characters/wizard/{id}/steps/species`) returns not only
numbers but also the book text — translated where a translation exists: every feature has
`name_en` / `text` (original) and `name_uk` / `text_uk` (Ukrainian), the description has
`description_uk`. Translations live in `content/translations/species/*.json`, keyed by the
`sha1` of the original; without a translation these fields are absent and the UI shows
the original. Details — `docs/translation.md`.

The knowledge base (`/api/v1/kb/*`) is the public, sign-in-free view of the same data for
the site's compendium section.

`/entries` filters: `category`, `source_id`, `q` (name search, case- and
punctuation-insensitive; exact name matches rank first), `level`, `school`,
`feature_type`, `item_type`, `rarity`, `magical`, `subclass_of`, `edition`, `status`,
`limit` (1..200), `offset`.

Lists return records **without** `text_en` (`brief`), the record card — **with** the
text (`full`). Not cosmetics: a class's text weighs more than all other fields combined.

Errors: `400` — impossible query parameters, `404` — no such record, `422` — type/bounds
failed FastAPI validation.

## Class spell lists

In the corpus `data.classes` is filled for only a small share of spells (the books whose
source provided a list). So "wizard spells up to level 3" can't be read from the records
alone.

The solution is the derived index `content/index/spell-lists.json`, built from the
"Spell Lists" tables in the books:

```powershell
.venv\Scripts\python -m scripts.ingest.spell_lists --write   # build
.venv\Scripts\python -m scripts.ingest.spell_lists --check   # verify
```

It covers the 8 PHB casting classes (Wizard 215, Sorcerer 129, Bard 120, Druid 110,
Cleric 106, Warlock 74, Ranger 46, Paladin 45). Every name is checked against the corpus:
if a book has a spell that the records don't, the script reports it.

The `source` field in the response is the confidence level of the list:

* `spell-lists` — from the books' lists (complete);
* `entry-data` — from the spells' `data.classes` (incomplete, only where present);
* `none` — no list: an empty result means "unknown", not "zero".

The index is derived from the corpus and, like it, is stored in git encrypted.

## Mechanics

The corpus has feature texts but no numbers for the sheet: hit die, proficiencies,
species bonuses, slot tables. A second derived index from the 5e.tools mirror provides
them:

```powershell
.venv\Scripts\python -m scripts.ingest.mechanics --write   # build both
.venv\Scripts\python -m scripts.ingest.mechanics --check   # compare with disk
```

* `content/index/class-mechanics.json` — 13 classes of 2014 (12 PHB + the TCE artificer):
  hit die, saving throws, skill choices, proficiencies, spellcasting ability, spell
  progression, the 20×9 slot table, Pact Magic 20×2, multiclass prerequisites, features
  by level, optional features, starting equipment;
* `content/index/origin-mechanics.json` — 69 species, 64 subraces, 94 backgrounds: ability
  bonuses (fixed and "choose"), size, speed, darkvision, resistances, skills, languages,
  tools.

Subraces carry the parent's inherited numbers (Hill Dwarf: +2 CON, +1 WIS, speed 25,
darkvision 60). The format is described in
[`contract/mechanics-format.json`](../contract/mechanics-format.json).

`ability_unresolved: true` — the species has no encoded ability bonuses: in the 2022
reprints (MPMM, RHW) the mirror leaves `ability` empty and the rule lives in text. The
wizard gives such species a choice of "+2/+1 or +1/+1/+1 to any".

Without indexes (a locked clone) `/mechanics` returns `available: false` with an
explanation, and `/summary` adds a warning. Errors: `404` — no such class, species or
background.
