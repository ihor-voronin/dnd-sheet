# Translation rules

The single source for the whole project: the UI (`frontend/src`), the server and the
export (`backend/src`), and corpus translations (`content/translations/`). The test
`backend/tests/api/test_terminology.py` catches regressions to old spellings.

The site's content is Ukrainian; this document describes how that content is written.

## How to display

1. **Everything in Ukrainian.** Explanations, hints, errors, rules texts.
2. **Names of game entities and key terms — "Ukrainian (English)".**
   Classes, subclasses, species, backgrounds, features, spells, feats, items,
   class options (fighting styles, invocations, maneuvers…), names of rules sections:
   `Містичний розряд (Eldritch Blast)`, `Чаклун (Warlock)`,
   `Рятівні кидки (Saving Throws)`.
3. **Data holds Ukrainian only.** `name_uk` in `content/translations/` and in the
   frontend dictionaries has no parentheses: the UI adds the English
   (`withEnglish` in `uk.ts`, `with_english` in `uk_text.py`).
4. **No translation — show the original**, never an invention. Add the translation to
   the right layer, not to a component.
5. Sentence case: «Кислотна стріла Мелфа», not «Кислотна Стріла Мелфа».
   Proper names are capitalized.
6. Apostrophe — the typographic `’` in data (code comparisons normalize `’ʼ'`).

## Where translations live

| What | Layer | Where the UI gets it |
|---|---|---|
| Class and subclass features | `content/translations/classes`, `subclasses` | `name_uk`/`text_uk` from the API |
| Species, backgrounds | `content/translations/species`, `backgrounds` | from the API + `uk.ts` |
| Spells (names) | `content/translations/spells/names.json` | `uk-spells.ts` (`scripts/spells_uk_names.py`) |
| Feats (names) | `content/translations/feats/names.json` | `uk-feats.ts` |
| Class options | `content/translations/optional-features` | `name_uk` from the API |
| Items | `content/translations/items` | `uk-items.ts` |
| Classes, species, subclasses for export | `content/translations/terms` (`scripts/terms_uk_export.py` from `uk.ts`) | — |

## Canonical terms

The single source is **`content/glossary.uk.yml`**: it decides how a term is
translated and holds the lists of forbidden spellings (`avoid`, `avoid_code`) that the
test checks against the code, the UI and all corpus translations.
Spell names — `content/translations/spells/names.json`; class, subclass and item texts
are aligned with these names (`Містичний розряд`, `Утримання особи`,
`Розвіювання магії`…).

A new term or a changed translation: the glossary (or the names layer) first, then
`pytest backend/tests/api/test_terminology.py` shows what else to fix. For example,
spell slots are always «комірки» and disadvantage is «завада».

## Translation style

1. Address the reader formally («ви»).
2. Numbers, dice (`1d6`), markdown — unchanged.
3. Translate 1:1, without "improvements".
4. No Russian-style participles in «-уючий/-аючий»: «сліпуча кара», «чіпка лоза»,
   «танцівні вогники».
5. Apostrophe in data — the typographic `’`.
