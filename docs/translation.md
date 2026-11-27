# Translating the content into Ukrainian

Status: **a machine draft** — checked on dice and numbers, but not proofread
against the official Ukrainian PDF. This is the same path as in the plan ("MT draft
+ proofreading"), and it's deliberately open: it's better to show a translation with an
honest label than English text where a person reads the rules.

Ukrainian words below are quoted as they appear in the app.

## Items

| Layer | Records | Where it lives |
|---|---|---|
| Names | 1109 (all unique names in the corpus, 54 books) | `frontend/src/features/character/uk-items.ts` |
| Descriptions | 235 (all Basic Rules descriptions) | `frontend/public/items-uk.json` |

Descriptions are translated only for `basic-rules-2014`: it's the same set as in
the free rules, and the only layer with real rule text rather than a table row. The
other books (adventures, settings) are still shown in English — they're next in line.

### How it's done

```
content/compendium/*/item.jsonl      (English, the corpus)
        │  scripts/items_uk_prepare.py — cuts it into queues of ~9k characters
        ▼
var/translations/items/in/*.json     (queues; not in git — generated)
        │  translation (an agent reads PROMPT.txt, writes one file per queue)
        ▼
content/translations/items/*.json    (Ukrainian; in git — the source of truth)
        │  scripts/items_uk_check.py  — length and dice
        │  scripts/items_uk_merge.py  — merge, term normalization
        ▼
frontend/src/features/character/uk-items.ts   (names, synchronous)
frontend/public/items-uk.json                 (descriptions, loaded on demand)
```

Names are synchronous because the inventory list mustn't "flash" English before the
dictionary loads. Descriptions are a separate file because it's ~200 KB of text that's
needed only when an item is expanded.

### Checks

`scripts/items_uk_check.py` catches a truncated translation (length below 55% of the
English) and lost dice (`2d4 + 2` must be in the translation). Both checks are crude, but
these are exactly the errors that show up on screen as a wrong rule.

`scripts/items_uk_merge.py` also fixes words that translators write the Russian way,
while the project glossary says otherwise:

* `ячейка` → `комірка` (glossary: Spell Slot — «Комірка закляття»);
* `палочка` → `паличка` (Wand).

### Adding a new book

1. `python scripts/items_uk_prepare.py` — re-cut the queues (the script takes the whole
   corpus, so descriptions of new books must be added to `PROSE_SOURCES`).
2. Translate the new files from `in/` into `content/translations/items/` (instructions
   for the translator — `var/translations/items/PROMPT.txt`).
3. `python scripts/items_uk_check.py && python scripts/items_uk_merge.py`.
4. `npm run build` — the generated files go into the bundle and `dist/`.

### Checking names against Ukrainian sources

Our names were compared with two translations people actually read at the table:

| Source | What it gives | Coverage |
|---|---|---|
| [5esrd.kyiv.ua](https://5esrd.kyiv.ua/) | an SRD translation by one translator (ІНРІУМ) | weapon, armor and gear tables; spells |
| [dndworld.space](https://www.dndworld.space/predmety/) | the largest catalog of items in Ukrainian | 4284 names as "Ukrainian + English" pairs |

Scripts: `scripts/reference_dndworld.py`, `scripts/reference_5esrd_spells.py`,
`scripts/items_uk_compare.py` (writes the differences, changes nothing).

**Items.** Of 1109 names, 666 are in the D&D World catalog; 342 of them match word for
word, 324 are a different variant. Some differences are style («Набір кісток» vs
«Набір гральних кісток»), some are real machine translation errors. So nothing was
accepted automatically: 50 weapon and armor names were checked against the 5esrd tables
and pinned in `uk.ts` (`ITEM_SRD`), 11 of them corrected in substance:

| Was (machine) | Became (SRD) |
|---|---|
| Стьобана броня | Гамбезон (Padded) |
| Кіраса | Нагрудник (Breastplate) |
| Кільчаста броня | Байдана (Ring Mail) |
| Шинна броня | Бригантина (Splint) |
| Дворучна палиця | Дубина (Greatclub) |
| Метальний спис | Сулиця (Javelin) |
| Бойова жердина | Бойовий посох (Quarterstaff) |
| Ціп | Бойовий ціп (Flail) |
| Спис-ланс | Кавалерійський спис (Lance) |
| Молот | Вершляг (Maul) |
| Шабля | Скимитар (Scimitar) |
| Бойове кайло | Клевець (War Pick) |

**Spells.** Here the sources disagree with each other, and picking the "right" one
without the book is impossible:

| Spell | Ours | 5esrd | D&D World | 1d20 |
|---|---|---|---|---|
| Eldritch Blast | Містичний постріл | Позамежний заряд | Потойбічний Розрив | Потойбічний вибух |
| Prestidigitation | Дрібні чари | Штукарство | — | — |
| Thaumaturgy | Чудотворство | Дивотворство | — | — |
| Burning Hands | Палаючі долоні | Палючі долоні | Палаючі Руки | — |
| Divine Favor | Божественна прихильність | Божа милість | Божа Прихильність | — |

The other six (Guidance, Light, Mending, Bless, Shield of Faith, Hex) match 5esrd.

**Conclusion.** A final check is only possible against the official Ukrainian PDF of the
Player's Handbook: community translations contradict each other even in the names of
level-1 spells. For now the app uses our own names, checked against the SRD where it's
unambiguous (weapons and armor), and machine ones for the rest.

### What's not here

* Proofreading against the official PDF: checked against two community translations
  (see the section above), and they disagree with each other. For items, weapons and
  armor are pinned to the SRD; the names of other items and spells stay machine-made
  until the book is available.
* Translation of descriptions from books other than the Basic Rules.
* Translation in the PDF/Markdown export: it still uses `name_en`.

## Species (races, subraces, their traits)

The second translation layer, done the same way — with files, not by editing the corpus.

| Layer | Records | Where it lives |
|---|---|---|
| Trait names | 274 (all names from the species corpus) | `content/translations/species/names*.json` |
| Trait texts | 524 (unique texts) | `content/translations/species/texts*.json` |
| Species and subrace descriptions | 105 | `content/translations/species/descriptions*.json` |

The key isn't the name but `sha1(original text)[:10]`: "Darkvision" in twenty species is
the same string, and there's no need to translate it twenty times. The files are read by
`backend/src/dndsheet/characters/api/trait_uk.py`, which adds `name_uk`, `text_uk`,
`description_uk` to the response; the screen shows «Темний зір (Darkvision)», and if there's
no translation — the original.

```
content/compendium/*/species.jsonl   (English, the corpus)
        │  scripts/species_uk_prepare.py [--missing]
        ▼
var/uk/input/*.json                  (queues; not in git — generated)
        │  translation (an agent reads var/uk/GLOSSARY.md, writes one file per queue)
        ▼
content/translations/species/*.json  (Ukrainian; in git — the source of truth)
        │  scripts/species_uk_check.py    — completeness (every id has a translation)
        │  scripts/species_uk_validate.py — numbers, dice, paragraphs, "not English"
        ▼
backend characters/api/trait_uk.py → API → the wizard, "Species" step
```

Why it isn't generated into the frontend like item names: the texts are ~240 KB, and
they're needed only at the creation step. The bundle shouldn't get heavier because of them.

Subraces must be prepared with `parent_name_en`: half of them are described in the text
of the parent species, and without it `species_details` returns only numbers. The first
pass "lost" 108 texts because of this — `--missing` added them.

### Checks

* `scripts/species_uk_check.py --strict` — completeness: 673 (first pass) + 230
  (subraces) records, every id exactly once.
* `scripts/species_uk_validate.py` — dice and numbers match the original, the same
  number of paragraphs, the text really is Ukrainian. This check caught
  «5×5 футів» instead of «квадратна ділянка 5 футів» — the numbers diverged.
* `backend/tests/api/test_species_uk.py::test_every_species_trait_has_ukrainian_name_and_text`
  — the same in tests: fails if a species without a translation appears.

### Status

A machine draft, checked on dice and numbers, but **not proofread** against the official
Ukrainian PDF — just like items. The original name is always next to it in parentheses,
so an error is visible and easy to fix in one file.

## Class features

The third layer, made by the same machinery: we don't touch the corpus, the translation
lives next to it and is joined by the hash of the original.

| Layer | Records | Where it lives |
|---|---|---|
| Feature names | 257: 174 chapter headings (`Rage`, `Extra Attack`, `Eldritch Invocations`…) + 83 names from the mechanics index (`Extra Attack (2)`, `Destroy Undead (CR 1)`, TCoE optional features) | `content/translations/classes/names.json` |
| Feature texts | 233 unique texts (45.7k words of original) | `content/translations/classes/texts-*.json` |
| Class descriptions | 12 (the prose at the start of the chapter) | `content/translations/classes/descriptions.json` |

The names are collected in one file by hand: `scripts/classes_uk_names.py` holds the
`NAMES` dictionary (chapter headings) and `EXTRA_NAMES` (names from the mechanics index),
because that's where the whole list is visible on one screen and a divergence is easy to
spot (`Arcane Tradition` for the wizard is the same subclass name as in `TERMS` on the
frontend). The script checks the dictionary against the corpus **and the mechanics index**
and fails if any name is left without a translation.

Texts — as files, like species:

```
content/compendium/phb-2014/class.jsonl  (English, the corpus)
        │  scripts/classes_uk_prepare.py [--missing]
        ▼
var/uk/classes/input/*.json          (queues of ~4k words; not in git)
        │  translation (an agent reads var/uk/classes/BRIEF.md, writes one file per queue)
        ▼
content/translations/classes/*.json  (Ukrainian; in git — the source of truth)
        │  scripts/classes_uk_check.py    — completeness
        │  scripts/classes_uk_validate.py — numbers, dice, paragraphs, list items
        ▼
backend characters/api/classes_uk.py → API → the wizard ("Class" step) and the sheet ("Features" tab)
```

Two lessons from species that are already taken into account here:

* **`id` in the queues** is the hash of the original, not the name. The first pass
  prepared texts without an `id` field, and the validator failed with a `KeyError`:
  translators computed the hash themselves. Now `classes_uk_prepare.py` writes an `id`
  into every record.
* **Tables in the text** (`Quick Build`, level progression) are part of the rule: the
  validator checks not only numbers but also the number of list items and `####`
  subheadings, because that's exactly where a translation "collapses" into a retelling.

### Checks

* `scripts/classes_uk_check.py --strict` — completeness: 174 names + 233 texts +
  12 descriptions, every id exactly once.
* `scripts/classes_uk_validate.py` — dice and numbers match the original, the same
  number of paragraphs/items/subheadings, the text really is Ukrainian.
* `backend/tests/api/test_classes_uk.py::test_every_class_feature_has_ukrainian_name_and_text`
  — the same in tests: fails if a class without a translation appears.
* `backend/tests/api/test_classes_uk.py::test_every_mechanics_feature_name_has_ukrainian_name`
  — names from the mechanics index (`Extra Attack (2)`, `Destroy Undead (CR 1)`) are
  translated too: otherwise the feature list mixes two languages.

### What this fixed on screen

Class feature texts used to come from the hand-written dictionary
`frontend/src/features/character/uk.ts`, and for `Spellcasting` it held **the cleric's
text**. The wizard, warlock and bard saw someone else's rule. Now `text_uk` comes from the
per-class layer, and the dictionary stays as a fallback.

### What's still missing

* **Proofreading** against the official PDF — as in the previous layers. (Subclass
  features are translated as a separate layer — see below.)

## Backgrounds

The fourth layer. A background isn't just a name: in the book it holds a description, a
feature with text and an `Equipment:` line from which the "Equipment" step adds items.
So all four are translated.

| Layer | Records | Where it lives |
|---|---|---|
| Background names | 94 (taken from `TERMS`, so there aren't two lists) | `content/translations/backgrounds/names.json` |
| Feature names | 70 (`Military Rank`, `Shelter of the Faithful`…) | same place |
| Descriptions | 66 unique (they repeat between variants in the books) | `descriptions-*.json` |
| Feature texts | 39 unique | `features-*.json` |
| Equipment phrases | 159 (`uniform`, `pouch containing 10 gp`…) | `equipment.json` |

About 29k words of original in total. Background names **aren't duplicated**: the script
`scripts/backgrounds_uk_names.py` reads `TERMS` from
`frontend/src/features/character/uk.ts` and takes the existing names — so «Солдат»
can't become «Воїн» in one place and «Солдат» in another.

```
content/compendium/*/background.jsonl  (English, the corpus)
        │  scripts/backgrounds_uk_prepare.py [--missing]
        ▼
var/uk/backgrounds/input/*.json        (queues; not in git)
        │  translation (an agent reads var/uk/backgrounds/BRIEF.md + the class glossary)
        ▼
content/translations/backgrounds/*.json
        │  scripts/backgrounds_uk_check.py    — completeness
        │  scripts/backgrounds_uk_validate.py — numbers, paragraphs, items, "not English"
        ▼
backend characters/api/backgrounds_uk.py → API → the wizard ("Background" step) and the sheet ("Background" tab)
```

Two particularities that the other layers didn't have:

* **Equipment isn't a rule but a list of items.** The phrases are translated separately
  and shown only as a caption: lookup in the compendium and adding to the inventory go by
  the English `text`, so a translation can't "break" an item. Choice variants ("bone dice
  or deck of cards") are translated as a parallel `choices_uk` array, so the `<select>`
  shows Ukrainian but submits English.
* **On the sheet equipment is one line** (as in the book), so its Ukrainian version is
  assembled from the translated phrases rather than translated a second time:
  «гаманець із 10 зм» reads the same in five backgrounds.

### Checks

* `scripts/backgrounds_uk_check.py --strict` — completeness: 164 names + 66 descriptions
  + 39 features + 159 phrases.
* `scripts/backgrounds_uk_validate.py` — numbers and dice, paragraphs, items,
  "is it not English".
* `backend/tests/api/test_backgrounds_uk.py` — lookup by hash, tolerance for a missing
  translation, the wizard step for «Солдат» and a completeness test for all 94
  backgrounds.

### Status

A machine draft, checked on numbers and structure, **not proofread** against the official
Ukrainian PDF — like items, species and classes. The original always stays next to it in
the payload, so an error is visible and easy to fix in one file.

## Subclass features

The fifth layer, and the last of those the sheet shows: now the «Уміння» (Features) tab
doesn't mix Ukrainian class features with English subclass ones.

| Layer | Records | Where it lives |
|---|---|---|
| Feature names | 639 (`Channel Divinity: Preserve Life`, `Oath Spells`…) | `content/translations/subclasses/names.json` |
| Texts | 684 unique (≈59k words of original) | `content/translations/subclasses/texts-*.json` |

The key, as in the previous layers, is the `sha1` of the original. The text is the
section body: the italic level caption (`*10th-level Cleric feature*`) is cut from it by
`features._strip_level_mark`, because the level is already a separate field; otherwise it
would be duplicated in every text (and the translator would have nothing to translate).

```
content/compendium/*/class.jsonl       (subclasses — ## headings in the class chapter)
        │  scripts/subclasses_uk_prepare.py [--missing]
        ▼
var/uk/subclasses/input/*.json         (queues; not in git)
        │  translation (an agent reads var/uk/subclasses/BRIEF.md + the class glossary)
        ▼
content/translations/subclasses/*.json
        │  scripts/subclasses_uk_check.py    — completeness
        │  scripts/subclasses_uk_validate.py — numbers, paragraphs, items, "not English"
        ▼
backend characters/api/subclasses_uk.py → the sheet ("Features" tab) and the level-up step
```

### Checks

* `scripts/subclasses_uk_check.py --strict` — 639 names + 684 texts.
* `scripts/subclasses_uk_validate.py` — numbers and dice, paragraphs, items,
  subheadings, "is it not English" (only dice like `(d10)` are allowed in names).
* `backend/tests/api/test_level_up_api.py::test_subclass_features_have_ukrainian_texts`
  — fails if a subclass without a translation appears.

### What this fixed on screen

* The «Уміння» tab on the sheet now shows subclass features in Ukrainian.
* The level-up step shows **the whole path** of the chosen specialization with levels,
  and the features of the current level also with their rule text.

### A find in the corpus

In the text of `Land's Stride` (Circle of the Land, druid) the corpus says
"moving through nonmagical **3** costs you no extra movement", and in `Ghost Walk`
(Phantom, rogue) — "as if they were **3**"; the digit 3 got in instead of "difficult
terrain" (apparently a footnote during ingest). The translation kept the number so the
validator wouldn't silently "fix" the rule, but it's a defect of the source, not of the
translation: it should be fixed in the corpus separately.

Three other source defects that are visible on screen:

* **`Lunar Sorcery` (SotDQ)** — the record in the corpus is **in Russian** and has no
  `##` at all: it's a translation of a whole adventure chapter, not a subclass chapter.
  So `subclass_intro` marks such a record `corrupt`, and the screen says "the text is
  damaged" instead of showing a sheet of someone else's text.
* **`SCAG` / `DMG`** in the deity tables — placeholders instead of book names
  (probably footnotes during ingest). The translation left them as they are, so as not to
  invent anything.
* Deity names in several tables were replaced by the same placeholder — this needs fixing
  in the corpus (§ ingest), not in the translation.

## Spelling: «хіти», not «хити»

The domain takes «хіти» (hit points) from the game, not from medicine:
**хіт → хіта → хітів** (Hit Points). So:

* the plural is **«хіти»**, «кістки **хітів**» («Кістки хітів» on the sheet card);
* one die is **«кістка хіту»** («Кістка хіту d10», «витратити кістку хіту»), not
  «кістка хітів»;
* «хит» is a different word, and it was once used to "fix" the translation.

All layers were checked and fixed (53 forms of «хитів» + 36 singular forms, 30 files:
translations, `uk.ts`, the sheet, README, docs). The glossary
(`content/glossary.uk.yml`) now says «Хіти / Кістки хітів / Тимчасові хіти», and the test
`backend/tests/api/test_translations_spelling.py` catches a regression: any «хитів»/«хиту»
in `content/translations/` fails the tests.

## Spell, feat and optional feature texts

| Layer | Texts | Where it lives | Where it's shown |
|---|---|---|---|
| Spells | 723 (description + "At Higher Levels") | `content/translations/spells/texts-NN.json` | the spell card on the sheet, the compendium |
| Feats | 109 | `content/translations/feats/texts-NN.json` | "Features → Feats", feat choice on level-up and in the wizard |
| Optional features | 151 | `content/translations/optional-features/texts-NN.json` | "Class and feat choices" |

The key is `sha1(original)[:10]` (`dndsheet.shared.translations`); for spells — the
description without the "3rd-level evocation" line, as the API returns it.

```
python scripts/rules_uk_prepare.py [--missing]   # queues var/uk/<layer>/input/texts-NN.json + var/uk/NAMES.md
# translation per var/uk/RULES_BRIEF.md (terms — var/uk/GLOSSARY.md, names — var/uk/NAMES.md)
python scripts/rules_uk_check.py [layer NN]      # completeness, dice, numbers, length, glossary-forbidden words
python scripts/translations_normalize.py --write # unify known term variants
```

Ten agents translated in parallel; term variants that weren't in the glossary were
unified by the script and added to the glossary: «показник небезпеки» (challenge rating),
«темний зір» (darkvision), «істинний зір» (truesight), «сліпе чуття» (blindsight); the
Investigation skill is «Розслідування», the Wisdom abbreviation is «МУД». The Darkvision
spell was renamed from «Темнозір» to «Темний зір».
