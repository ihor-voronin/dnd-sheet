# Compendium record format

One record is one entity of one category, and **all records of a category have the same
format**. This isn't a stylistic detail: the corpus is assembled by four different
pipelines (HTML from D&D Beyond pages, OCR of a scanned PDF, a PDF text layer, records
written by hand in builders), and before this contract existed "all spells" actually had
three different formats, "all monsters" — 55 sets of `data` keys, and "all feats" — two
different text openings.

There are two corpora, and the boundary between them is part of the same contract:

| Corpus | Folder | Contents | Read by the character sheet |
|---|---|---|---|
| `compendium` | `content/compendium/` | classes, subclasses, species, backgrounds, feats, optional features, spells, items, rules | yes |
| `bestiary` | `content/bestiary/` | monster stat blocks | **no** |

The record format is the same in both (same schema, same checks), so one reader serves
both corpora. The only difference is that monsters don't take part in building the sheet:
their volume exceeds all other entities combined, and keeping them in the sheet's data
flow would mean sifting through noise every time.

The source of truth is `contract/compendium-format.json`. Code — `scripts/normalize/`.
Test — `backend/tests/contract/test_compendium_format.py`.

## 1. What exactly is uniform

1. **Record fields** (`entry_keys`, in this order):

   ```
   id, schema, source_id, category, name_en, name_uk, edition, license,
   url, page, text_en, text_uk, data, status, fetched_at, notes
   ```

2. **`data` keys** — a fixed set in a fixed order per category. An unknown value is
   `null`, a flag is `false`, an empty list is `null`. A key that isn't in the contract
   can't be in a record.

3. **The `text_en` skeleton** — one of three:

   | Skeleton | What it looks like | Categories |
   |---|---|---|
   | `spell-block` | first line — `8th-level necromancy` or `Conjuration cantrip`, then an empty line and the body | `spell` |
   | `prose` | the body straight away, no heading | `species`, `background`, `feat`, `optionalfeature`, `subclass`, `item`, `monster` |
   | `section` | first line — `# <name>`, then an empty line and the body | `class`, `rule` |

   Plus shared hygiene: no soft hyphens (`U+00AD`), no BOM, no trailing whitespace, no
   three or more empty lines in a row.

## 2. Categories

| Category | `data` keys (in this order) | Text |
|---|---|---|
| `spell` | `level`, `school`, `ritual`, `concentration`, `casting_time`, `range`, `components`, `duration`, `classes`, `at_higher_levels` | `spell-block` |
| `species` | `ability_increases`, `size`, `speed`, `subrace_of` | `prose` |
| `background` | `feature` | `prose` |
| `feat` | `prerequisite` | `prose` |
| `optionalfeature` | `feature_type`, `prerequisite` | `prose` |
| `class` | — | `section` |
| `subclass` | `class`, `level` | `prose` |
| `item` | `item_type`, `rarity`, `magical`, `attunement`, `base_item`, `group`, `cost`, `weight`, `armor_class`, `damage`, `properties`, `stealth`, `strength` | `prose` |
| `monster` | `size`, `creature_type`, `subtype`, `alignment`, `armor_class`, `hit_points`, `hit_dice`, `speed`, `abilities`, `challenge_rating`, `xp`, `saving_throws`, `skills`, `damage_vulnerabilities`, `damage_resistances`, `damage_immunities`, `condition_immunities`, `senses`, `languages` | `prose` (`bestiary` corpus) |
| `rule` | — | `section` |

Special value types:

* `abilities` — always six keys `str, dex, con, int, wis, cha`, the value is an integer
  or `null`;
* `ability_increases` — six keys `strength, dexterity, constitution, intelligence,
  wisdom, charisma`, an integer or `null`;
* `lower` — a lowercase, sorted list (`classes`, `feature_type`): in the mirror the
  optional feature group is a code (`EI`, `FS:R`), while in the record it's
  `eldritch invocation`, `fighting style (ranger)`;
* `str_lower` — a lowercase string (`size`, `creature_type`, `alignment`, `rarity`):
  books contain both `Small fey` and `small fey`.

`data` for `class` and `rule` is always `{}`: rules and classes are text, and structured
fields (a town's population, a crew roster, book authors) aren't part of the contract;
they stay in `text_en`.

Which corpus each category belongs to is described in `corpora` in the same file:
`compendium` — every category except `monster`, `bestiary` — only `monster`. A category
with no corpus or in two corpora is a specification error; `_validate_spec` catches it and
preflight fails before checking any records.

## 3. Mechanical category fixes

A category's format is impossible if it contains a record of another type. So the
normalizer fixes the obvious cases (`refine` in the contract):

| Sign | Was | Becomes |
|---|---|---|
| the text starts with a `Chapter …`, `Appendix …`, `Part …` heading or a list-title (`Spells`, `Equipment`, `Monsters`, `Bestiary`, `Backgrounds`, `Races`, `Classes`, `Feats`, `Items`, `Magic Items`, `Spell Lists`) | any entity | `rule` |
| the entity starts with a foreign heading (Sage Advice: `#### If you have the Charger feat…`) | `feat` | `rule` |
| the text starts with a spell level line (`4th-level conjuration`) | `monster` | `spell` |
| the stat block has no creature type line (`Large aberration, lawful evil`) | `monster` | `rule` |
| an `id` repeats after the category fix | two records with one `id` | the fuller one stays (more filled `data` fields), the other is mentioned in `notes` |

## 4. How to use it

```powershell
# check the whole corpus (exit code 1 on differences)
python -m scripts.normalize --check

# check one book, with examples
python -m scripts.normalize --check --source eepc --limit 10

# bring the corpus to canon
python -m scripts.normalize --write

# "book × category" matrix
python -m scripts.normalize --stats
```

All commands work on both corpora at once: `--check` walks the books found in
`content/compendium/` and `content/bestiary/`, `--stats` shows a shared matrix, and
`--write` not only normalizes records but also moves them into the corpus the
specification assigns to their category.

The Makefile has `make format` and `make format-check`. In tests the format is checked by
`backend/tests/contract/test_compendium_format.py` (structure, `data`, text skeleton,
`id` uniqueness, minimum fields for spells and stat blocks, and separately — that no
`monster` came back into the compendium and the bestiary holds nothing else).

The pipelines apply the contract themselves:

* `scripts/ingest/records.py` — after parsing pages;
* `scripts/pdf/build_eepc.py`, `scripts/pdf/build_gotg.py` — after building a book.

So "convert everything to the format" is a one-time `--write`; every later pipeline run
already writes canon.

### Rebuilding the corpus without losses

The format doesn't help if a re-parse lost text. So a full rebuild of HTML books has two
commands:

```powershell
# re-parse all books from content/raw/*.html; a book that became shorter
# is rolled back to its previous state
python scripts/ingest/reparse.py --show-text-loss

# check that no paragraph of the previous corpus disappeared
python scripts/ingest/verify_text.py --against <copy of the previous corpus>
```

`reparse` and `verify_text` treat a book as a whole, i.e. across both corpora: the
snapshot is taken from `content/compendium/` and `content/bestiary/`, and if the book
became shorter after parsing, both of its folders are rolled back. `verify_text` accepts
`--against` twice (compendium and bestiary separately) or once — a folder that contains
both.

`verify_text` distinguishes a **loss** from a **fix**: if a paragraph isn't found but
the same record exists and is ≥90% similar, it's a fix (for example the OCR artifact
"fol lowing" → "following"), not a loss. That's how the move to 5393 records was
verified: 0 losses, 2 fixed paragraphs.

## 5. What this changed in the corpus

| | Before the contract | After |
|---|---|---|
| Records | 4639 | 5393 (3147 compendium + 2246 bestiary) |
| Monster `data` key sets | 55 | 1 |
| Item `data` key sets | 10 | 1 |
| Records with empty `data` in entity categories | 10 | 0 |
| Spells without a level line in `text_en` | 51 | 0 |
| Feats with a `Prerequisite:` line in the text | 34 | 0 |
| Records with a corrected category | 28 | — |
| Repeated `id`s | 2 (26 records) | 0 |

The number of monsters grew from 1596 to 2246 not because of new books, but because the
stat blocks of the Basic Rules, MToF, VGtM, Monstrous Compendium and supplements start
with a plain title paragraph rather than a markdown heading: previously these pages
merged into one record per page. Now they all live in the bestiary; the compendium is what
the character sheet reads.

## 6. How to add a category or a key

1. Add the description to `contract/compendium-format.json` (`categories.<name>` with
   `text` and `data`; for a new value type also a handler in `_KIND_COERCERS`) and set
   its corpus in `corpora`.
2. Add the name to `categories.enum` in `contract/compendium-entry.schema.json` —
   otherwise the JSON Schema rejects records of the new category.
3. If the mirror pipeline writes the category, add it to
   `scripts/ingest/sync_sources.py` too (`CATEGORY_ORDER` and `PLURALS`) — that's where
   `categories:` and `note:` in the source registry come from.
4. `python -m scripts.normalize --check` shows how many records this affects.
5. `python -m scripts.normalize --write`.
6. `python -m pytest backend/tests/contract/test_compendium_format.py`.

If an existing record's `category` changes, the normalizer rewrites its `id` too
(`<source_id>/<category>/<slug>`), and if the `id` starts to repeat it keeps the fuller
record and writes in `notes` which record was removed.
