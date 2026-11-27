# Sheet export

The screen shows the sheet to the player, the printout goes to the table. So the export
isn't built from a demo character or from the screen, but from the same character, and it
carries the **state**: current hit points, spent slots, numbers entered by hand.

```
Character + SheetState ──DerivedStatsCalculator──> ComputedSheet
        │                                              │
        └──────────────┬───────────────────────────────┘
                       ▼
     ┌─────────────────┴──────────────────────────┐
     ▼                                            ▼
SheetDocument (JSON by the contract)        print view (characters/api/print_view.py)
  ├── MarkdownRenderer → .md (API only)       └── character.html.jinja → WeasyPrint → .pdf
  └── React rendering (screen)                    └── the same HTML at /print (browser printing)
```

The **printed sheet** (PDF and the `/print` page) has its own view model shaped for paper:
a main page (abilities, saves, skills, combat, attacks, resources, features), spells,
equipment and notes, an adventure log page and, by default, extra pages with the full text
of features and spells. Black and white, frames, room for a pencil; fonts are embedded
(see `templates/fonts/README.md`). Markdown is still available from the API but has no
button in the UI.

## What goes into the document

| Section | From | Example |
|---|---|---|
| **Identity** | species, subclass, background, alignment | `Fighter 2 / Wizard 3`, `Human`, `Soldier` |
| **Abilities** | `ComputedSheet.abilities` (base + species bonuses) | `Strength 13`, `Mod +1` |
| **Combat** | AC, initiative, speed, max HP + **state** | current HP, max, temporary, inspiration, death saves |
| **Saving throws / Skills** | proficiencies + overrides | `Stealth 5` (marked "manual" when overridden) |
| **Attacks** | weapons from the inventory + compendium data | `longsword: +5 · 1d8+3 slashing`, hint "Strength · versatile (1d10)" |
| **Features and feats** | class features at the current level | `Second Wind: Fighter 1` |
| **Proficiencies** | gathered from class, species, background, player choices | armor, weapons, tools, languages |
| **Spellcasting** | DC, attack bonus, slots by level + Pact Magic | `Level 1 slots 2/4`, `Pact Magic, level 1 0/1` |
| **Known spells** | player choices + those granted by species and subclass | `Hex: level 1 · prepared` |
| **Inventory** | items, "equipped", armor AC, weight | `chain mail: armor · AC 16 · 55 lb · equipped` |
| **Money and weight** | purse and carrying capacity | `Weight: 58 of 195 lb` |
| **Notes** | five free-text sections | `Appearance: a scar on the cheek` |
| **Warnings** | `ComputedSheet.warnings` | `current HP (99) above maximum (10)` |

There are no empty sections: no spells — no "Spells" page; no notes — no "Notes" page.
A heading without content is noise on paper.

## Where a number comes from (`origin`)

Every field of the document says where its number came from:

| `origin` | What it is | Mark in PDF | Mark in Markdown |
|---|---|---|---|
| `computed` | computed by the domain (AC, saves, max HP, slots) | `•` | — |
| `input` | state: the player changes it at the table (HP, exhaustion, notes) | — | — |
| `override` | the player entered their own number instead of the computed one | `✎` | _(manual)_ |

"Computed" is marked with a symbol, not a word next to each line: otherwise half the
text on an 80-field sheet would be bookkeeping. "Manual" is always marked: it's the only
place where the sheet diverges from the rules, and the player must see it.

## API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/v1/characters/{id}/export/pdf` | `application/pdf` (or `503` without WeasyPrint) |
| `GET` | `/api/v1/characters/{id}/print` | the same sheet as HTML for browser printing |
| `GET` | `/api/v1/characters/{id}/export/markdown` | `text/markdown`, attachment `character-sheet.md` |
| `GET` | `/api/v1/characters/{id}/export/{fmt}?originals=false` | the same without English labels |
| `GET` | `/api/v1/shared/{token}/export/pdf`, `/api/v1/shared/{token}/print` | printing a shared read-only sheet |
| `GET` | `/api/v1/renderers` | `{"formats": [...], "available": [...]}` |
| `GET` | `/api/v1/demo/export/{fmt}` | the demo sheet with the same renderer |
| `GET` | `/api/v1/characters/golden/{key}/export/{fmt}` | a reference sheet |

`formats` are the registered renderers, `available` — those that actually work in this
environment. The difference matters: PDF without WeasyPrint is registered, but `render()`
raises `RendererUnavailable` → `503`. The UI shows the PDF button only when the format is
in `available`.

An unknown format is `404`, someone else's or a missing character is `404`, a malformed
`id` is `422`.

## Deliberately not done

* **English export.** The document is built in Ukrainian — the app's language.
  `RenderOptions.lang` (uk/en) existed since stage 1, but nothing read it: a renderer
  doesn't translate, it draws. The dead option was removed so it wouldn't promise what
  doesn't exist. Translation is the glossary pipeline, not a renderer flag.
* **Trimming long lists.** All 18 skills and all proficiencies are printed in full: two
  pages are better than a sheet missing a line.

## Fixed along the way

1. **Zero HP showed as the maximum.** `HitPointState.current` was an `int` defaulting to
   `0`, and the calculator wrote `current if current else maximum`. An unconscious
   character with three failed death saves looked perfectly healthy — on screen and on
   paper. Now `current: int | None`, where `None` means "the player hasn't touched HP yet"
   and `0` is zero. Old files (`character/1`) read as "not set": in that schema 0 couldn't
   mean a real zero, because the sheet never showed it. The format became `character/2`;
   the migration is covered by tests.
2. **`RenderOptions.lang`** — removed (see "Deliberately not done").
3. **Duplicated lists.** Spells, features and proficiencies were gathered separately in
   the screen serializer and in the document builder — so they could diverge. Now both take
   rows from `characters/application/rows.py`.
4. **The computed-field mark in PDF** matched the override mark (`•` for both), while the
   caption claimed `•` means "computed automatically". Overrides are now `✎`, and the
   caption matches.

## Tests

| File | What it holds |
|---|---|
| `tests/sheets/test_build_document.py` | structure (all sections, none empty), state in the document, 0 HP, `override` changes `origin`, slots "remaining/total", notes, warnings, the document passes the JSON Schema |
| `tests/characters/test_print_view.py` | the print view: sections, spells grouped by class in multiclass, item names |
| `tests/conformance/test_character_document.py` | a real sheet → Markdown and HTML (what the PDF is made of): every section, label and value in place; `%PDF` only where WeasyPrint exists |
| `tests/api/test_export_api.py` | HTTP export of a character with state, printing, `originals=false`, `404` for format and character |
| `tests/characters/test_json_store.py` | migration `character/1` → `character/2` (0 = "not set", a real 0 is kept) |

On Windows without GTK the PDF conformance test is **skipped**; in Docker and in CI it
runs (the image has WeasyPrint).
