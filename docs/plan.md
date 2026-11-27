# D&D 5e (2014) — a character sheet in Ukrainian. Plan

Status: **approved** (v5), stages 1–7 done, stage 8 partly done (deploy, Telegram).
The site runs at https://dnd.voronin.app.
v5 (2026-11-26): stages revised — no external character imports, content and character
creation are entirely our own; the sheet is built against a screen reference (§13), not
against someone else's data.

## 1. Principle

The source of truth is not the layout but a domain document:

```
Character (aggregate) ──> DerivedStatsCalculator ──> ComputedSheet ──> SheetDocument (JSON, versioned)
                                                                          ├──> React rendering (web)
                                                                          ├──> PdfRenderer (print)
                                                                          ├──> MarkdownRenderer (chat/text)
                                                                          └──> [PngRenderer, FoundryJson] — later
```

Every renderer is an adapter behind the `SheetRenderer` port. Adding a renderer doesn't
change the domain. (The printed sheet later got its own paper-shaped view model — see
[`export.md`](export.md).)

## 2. Decisions

| Decision | Value |
|---|---|
| Rules | 2014 only (SRD 5.1 + books), `edition` in the model |
| Language | Ukrainian; every string carries the English original for the tooltip |
| Terminology | a separate glossary (`content/glossary.uk.yml`), not gettext |
| Translation | the official Ukrainian edition (PDF) where it exists → otherwise our own; MT draft + review |
| Frontend | SPA: React 18 + TypeScript + Vite |
| Computation | the server is authoritative; the client doesn't duplicate rules |
| Automation | hybrid: declarative modifiers + manual override |
| Accounts | Telegram sign-in, cookie sessions (Bearer in the Mini App) |
| Export | our own layout (no AcroForm) |
| Content | data, not code; a `license` field for a future SRD-only mode |
| Hosting | locally (docker-compose) → a VPS with auto-deploy from GitHub Actions |

## 3. Bounded contexts

| Context | Responsibility |
|---|---|
| `identity` | users, sessions, ownership |
| `compendium` | the compendium: classes, subclasses, species, backgrounds, feats, spells, items; versioned, read-only |
| `characters` | the `Character` aggregate, builder, levels, ASI/feats, inventory, spells |
| `sheets` | `ComputedSheet` → `SheetDocument`, templates, layout, custom fields, formulas |
| `export` | the `SheetRenderer` port + adapter registry |

Communication goes through domain events and read-only ports. Contexts share no tables.
(A separate `localization` context was planned; the glossary pipeline lives in
`content/`, `scripts/` and the terminology test instead.)

## 4. Domain model

**Aggregates:** `Character` (AR), `CompendiumEntry` (AR), `SheetTemplate` (AR), `LayoutOverride` (entity).

**Value objects:** `AbilityScore` (1..30), `DiceExpression`, `Armor`, `HitPoints`, `Money`, `Level`, `LocalizedText`, `Weight`.

**Services:** `DerivedStatsCalculator`, `ModifierResolver`, `SpellSlotService`, `FormulaEvaluator` (whitelisted AST, no `eval`).

**Events:** `CharacterCreated`, `LevelGained`, `AbilityScoresChanged`, `LayoutCustomized`, `SheetExported`.

Invariants: level 1..20, total level ≤ 20, ability 1..30, prepared spells within the limits.

## 5. Customization (4 levels)

1. Layout: order, visibility, grouping, page.
2. Labels: renaming terms per character.
3. New fields: `text|number|longtext|checkbox|list|counter|formula|dice`.
4. Overrides and custom modifiers (+ change history).

## 6. The contract and protection against diverging renderers

- `contract/sheet-document.schema.json` — the single source of types.
- Codegen: pydantic models (Python) and TS types (frontend). Not edited by hand.
- `contract/fixtures/*.json` — the conformance set: minimal, every field type, overflow, 3+ pages, custom fields, overrides, negative modifiers, missing translation.
- Every renderer must pass the fixture tests. A new renderer without tests isn't merged.
- `schemaVersion` is semver; a major mismatch → the renderer refuses.

## 7. Tooltip with the original

- Web: Radix Tooltip, `hint.en` (accessibility: aria-describedby, keyboard).
- PDF: the original in parentheses next to the Ukrainian name ("Ukrainian (English)").
- The sheet text is always bilingual in the model — the tooltip isn't a point fix.

## 8. Stack

Backend: Python 3.12, FastAPI, Pydantic v2, SQLite (WAL), WeasyPrint, pypdf.
(Planned originally: SQLAlchemy, Alembic, PostgreSQL, Argon2id — not needed so far;
Telegram sign-in replaced passwords.)
Frontend: React 18, TypeScript, Vite, TanStack Query, Radix UI.
Deploy: FastAPI serves `frontend/dist`, one origin, no CORS; Docker + Caddy on a VPS
(see [`deploy.md`](deploy.md)).

## 9. Stages

Stage 0 (skeleton) and the content stage (the book corpus) are closed. Then the order
"compendium first, then the character, then the screens": each stage delivers a working
piece, verified by tests.

**Stage 1 closed (2026-11-26):** the compendium is read by the domain and served over
HTTP (89 books, 9 categories); class spell lists are built from the books' "Spell Lists".
Details — [`api-compendium.md`](api-compendium.md).

**Stage 2 closed (2026-11-26):** `Character` v2 — multiclass, species, background,
proficiencies with sources, HP, inventory, spells; `ModifierResolver` (species and choice
bonuses), `SpellSlotService` (multiclass slots + Pact Magic), max HP and the hit dice pool.
The 5e.tools mirror provided derived mechanics indexes: `content/index/class-mechanics.json`
(13 classes of 2014) and `origin-mechanics.json` (69 species, 64 subraces, 94
backgrounds). Three reference characters — "Fighter 1", "Warlock 1", "Fighter 2 / Wizard
3" — are pinned by tests on two rules sources (a fixture and the real corpus). Details —
[`domain-character.md`](domain-character.md).

**Stage 3 closed (2026-11-26):** the creation wizard — six steps (species → class →
abilities → background → equipment → spells), the server validates every step, the
draft is saved, you can go back to any step, and changing a class or species clears the
dependent answers. Details — [`wizard.md`](wizard.md).

**Added after the level-1 choices audit:** exactly three classes require a subclass at
level 1 (cleric, sorcerer, warlock); species cantrips and spells (tiefling, drow, forest
gnome, high elf, etc.) are now in the index and on the sheet; the cleric's domain spells
show as always prepared, the patron's expanded list as additional options. The human's
`ability_unresolved` flag was fixed (a bug in merging the "standard" variant).

**Stage 4 closed (2026-11-26):** the sheet during play — tabs, in-place editing marked
"manual" with a reset, counters (HP, slots, Pact Magic, hit dice, death saves,
inspiration, exhaustion), short/long rest by the rules, weapon attacks from compendium
data. `PATCH` with `version` prevents two tabs from overwriting each other. Details —
[`sheet.md`](sheet.md).

**Stage 5 closed (2026-11-26):** full sheet export — `SheetDocument` is built from a real
`Character` + `SheetState` (not a demo) and holds every section of the screen. Both
renderers (PDF via an HTML template and Markdown) pass conformance on a real sheet. A
bug was found and fixed along the way: zero HP showed as the maximum (an unconscious
character looked healthy) — the character format became `character/2` with a migration.
Details — [`export.md`](export.md).

**Stage 6 closed (2026-11-27):** storage and accounts — SQLite (characters with versions
and owners, drafts, sessions, share links), Telegram sign-in (Login Widget and Mini App),
read-only share links, live sync between devices.

**Stage 7 closed (2026-11-26):** level-up on the same document — a "+1 level" screen with
the class (existing or new: multiclass per the PHB prerequisites), hit points (average or
roll, in its place in the pool), the subclass at its level, an ability improvement or a
feat (the cap of 20 counted after species bonuses), new spells and a "before → after"
summary. Details — [`level-up.md`](level-up.md).

**Spells outside of level-up (after stage 7):** daily preparation and adding spells from
the class list or **custom** ones. Multiclass prerequisites can be deliberately bypassed
with a checkbox — and the sheet remembers what was bypassed (`multiclass_waivers`).
Details — [`spells.md`](spells.md), [`level-up.md`](level-up.md).

**Stage 8 (in progress):** deploy to https://dnd.voronin.app (Terraform, Docker, Caddy),
CI/CD with GitHub Actions ([`ci.md`](ci.md)), the Telegram Mini App, a paper-style PDF.
Customization (§5) is still ahead.

Before stage 3 a **20-level check** was done: each of the 13 classes ran through the
service at every level against its own class table, and every pair of casting classes
against the multiclass table (6840 splits). It found a real bug: half casters
(paladin/ranger) got slots from the multiclass table on odd levels, i.e. 1–2 slots fewer.
Fixed: one casting class reads its own table, two or more — the multiclass one.

| # | Content | DoD | ~Time |
|---|---|---|---|
| 1 | **Compendium as an API**: `compendium` — a read-only domain over `content/*.jsonl`, indexes by category, book, name; queries "classes", "a class's subclasses", "a class's spells up to level N", "items by type" | All records available via `/api/v1/compendium/...`; filters work; index tests | 1 week |
| 2 | **`Character` v2**: classes and levels (multiclass), species, background, proficiencies with sources, HP, armor, inventory, spells, feats; `DerivedStatsCalculator` v2 + `ModifierResolver` for species and class bonuses | Golden "Fighter 1" and "Warlock 1" match the rules; invariants and tests | 1.5 weeks |
| 3 | **Creation wizard**: 6 steps (§13), server-authoritative, the draft is saved, back/forward between steps | Create and save a level-1 character; go back to any step | 1.5 weeks |
| 4 | **The sheet like the reference**: tabs, in-place editing with an override mark, counters (HP, slots, hit dice, death saves), rests | Everything changes and is saved; the state survives a reload | 1.5 weeks |
| 5 | **Full export**: PDF and Markdown of every section | A4 with all tabs, conformance on 2 renderers | 1 week |
| 6 | **Storage and accounts**: database, sessions, public link | Several characters per user; someone else's sheet is inaccessible | 1 week |
| 7 | **Levels 2–20**: level-up, ASI/feats, multiclass, slots by the table | A level-7 character created and printed | 2 weeks |
| 8 | **Customization** (§5), export polish, deploy | A custom section with a formula on the web and in PDF; the site on a domain | 3 weeks |

## 10. Book scope

**The corpus holds every book in the library** (sourcebooks and adventures). We take
everything there is, without curation: re-fetching individual books costs more than
reprocessing, and an extra record bothers nobody.

What the app *uses* is a separate question, decided by flags, not by deleting books:

| Layer | Books | In the app |
|---|---|---|
| Core | PHB, DMG, Basic Rules (SRD) | always |
| Options | XGtE, TCoE, SCAG, FToD, EGtW, AI, VGtM, MToF, MotM | on by default |
| Bestiary | MM, Monstrous Compendium, Fiendish Folio, MToF | for wild shapes and familiars |
| Settings and adventures | GGR, ERLW, MOoT, VRGtR, SCC, SAiS, BMT, WBtW, other adventures | per campaign |
| Playtest | Unearthed Arcana | off |
| Third party | Humblewood | off, a separate flag |

## 11. Risks

1. Translation volume (~1.5–2 million characters) — the main risk; mitigation: glossary-constrained MT + review + prioritization.
2. Diverging renderers — codegen + conformance.
3. Duplicating the engine in JS — forbidden in review.
4. Expecting "everything automated" — honestly: ~85–90% declarative, the rest overrides.
5. Legal — non-commercial fan project; book texts are stored only encrypted; the code is ready for an SRD-only mode.

## 12. Open questions

- Units: feet/pounds with metric in parentheses — decided as the default, changeable by a setting.
- Whether a Foundry VTT export is needed.

## 13. Screen reference (not data)

The reference is how a working sheet looks and behaves in D&D Beyond. We repeat **the
structure of screens and the behavior**, copying neither texts, data, illustrations nor
layout: all content comes from our own corpus (`content/`), all numbers from our own
rules. There is no import of someone else's characters and there won't be.

**Character screen.** Header: name, class(es) and level, species, background,
alignment. Combat panel: HP (current/max/temporary), AC, initiative, speed, hit dice,
death saves, inspiration, proficiency bonus. Then tabs:

- **Actions** — attacks, weapons, abilities: short text, bonus, die;
- **Spells** — by class, slots by level, prepared, cantrips/rituals, DC and attack bonus;
- **Inventory** — items with quantity, weight, "equipped/attuned", money, carrying capacity;
- **Features and feats** — class, subclass, species, feats, with full text;
- **Notes** — appearance, allies, enemies, backstory, own notes.

**Behavior.** Clicking a number edits it in place; a computed field changes only as an
override, and that's marked. Counters (slots, hit dice, charges) go down and are
restored; short and long rests restore what they should. Every line has a tooltip with
the English original (§7).

**Creation.** A step-by-step wizard: species → class (and subclass if it comes at level
1) → abilities (standard array / point buy / rolls) → background and proficiencies →
equipment → spells. You can go back between steps; the server validates every step and
saves the draft. Level-up is a separate flow on the same document, without "recreating"
the character.
