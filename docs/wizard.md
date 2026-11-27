# The character creation wizard

Six steps from "nothing" to a saved level-1 character. The server is the only authority
that decides whether a step is valid; the screen only shows the choices and sends the
answer. The draft is saved on every step, so a closed tab loses no work, and it lives on
the server, so it can be finished on another device.

```
POST /wizard ──► draft (revision 0)
   │
   ├─ PUT /steps/species      species, subrace, name, chosen bonuses
   ├─ PUT /steps/class        class, subclass (if it comes at level 1)
   ├─ PUT /steps/abilities    standard array / point buy / rolls / manual
   ├─ PUT /steps/background   background, alignment, skills, languages
   ├─ PUT /steps/equipment    items and money (optional)
   └─ PUT /steps/spells       cantrips and spells (casters only)
          │
          └─ POST /finish ──► Character + sheet, the draft is removed
```

## Steps

| # | Step | What the server checks |
|---|---|---|
| 1 | `species` | the name isn't empty; the species exists and isn't a subrace; the subrace belongs to the species; the bonus choice is exactly `count` different abilities; the cantrip choice is exactly `count` from the class list |
| 2 | `class` | the class exists; the subclass is required if `subclass_level == 1` (cleric, sorcerer, warlock) and forbidden earlier; the subclass key is in the compendium; the option shows domain/patron spells |
| 3 | `abilities` | the array = the multiset 15,14,13,12,10,8; point buy ≤ 27 points and 8..15; rolls 3..18, each used once; manual 3..20; with the species bonus ≤ 20 |
| 4 | `background` | the background exists; every proficiency passes its source's rules; exactly `skill_limit` class skills; exactly `skill_any` species skills |
| 5 | `equipment` | the inventory is valid (one armor, one shield, weight ≥ 0, money ≥ 0) |
| 6 | `spells` | the class casts; cantrips ≤ limit; known ≤ limit; spell level ≤ the level-1 maximum; prepared ≤ limit; the list is extended by the patron's expanded list, domain spells show as "always prepared" |

Step rules live in the domain (`characters/domain/wizard.py`), not in the HTTP layer:
the same code checks the step and the assembled aggregate.

### Order and going back

A step opens only when all previous ones are complete — otherwise you could reach spells
without a class. Going back is always allowed; changing the species, class or background
clears dependent answers:

* species → proficiencies from the `species` source disappear (languages, skills);
* class → `class` skills and **all spells** disappear (they belong to the class);
* background → proficiencies come from its rules, so the choices stay intact.

Equipment is the only optional step: it can be skipped and the character is still
created with an empty inventory.

The UI scrolls to the top on every step change; on a phone a sticky bar jumps between
the step's sections, and under the "Next" button the screen says what's still missing.

## API

Every response contains both `options` (what can be chosen) and `answers` (what is
chosen). `PUT` takes **the step answer in the same shape** as `answers`, so the client
translates nothing.

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `/api/v1/characters/wizard` | — | the first step with choices |
| `GET` | `/api/v1/characters/wizard/{id}` | — | `{draft}` without step choices |
| `GET` | `/api/v1/characters/wizard/{id}/steps/{step}` | — | the step: `draft`, `answers`, `options`, `locked`, `complete` |
| `PUT` | `/api/v1/characters/wizard/{id}/steps/{step}` | the step answer (+ `revision`) | the updated step |
| `POST` | `/api/v1/characters/wizard/{id}/finish` | — | `{character_id, sheet}` |
| `GET` | `/api/v1/characters` | — | the saved list (with species, classes, HP, AC for the cards) |
| `GET` | `/api/v1/characters/{id}` | — | `{sheet}` — the full computed sheet |

Errors: `404` — no such draft/character/step; `409` — a stale `revision` (someone else
changed the draft); `422` — the step failed, `detail` gives the reason in plain language.

### Example bodies

```json
{"name": "Дарія Залізний Крок", "species_key": "human",
 "subspecies_key": null, "ability_choices": [], "spell_choices": []}

{"name": "Ільвен", "species_key": "elf", "subspecies_key": "high elf",
 "ability_choices": [], "spell_choices": ["fire bolt"]}
```

```json
{"class_key": "warlock", "subclass_key": "phb-2014/subclass/the-fiend"}
```

```json
{"method": "standard_array",
 "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
 "rolls": []}
```

```json
{"background_key": "soldier", "alignment": "lawful good",
 "picks": [
   {"kind": "skill", "value": "athletics",
    "source": {"kind": "class", "key": "fighter"}},
   {"kind": "skill", "value": "perception",
    "source": {"kind": "class", "key": "fighter"}}
 ]}
```

```json
{"items": [{"name_en": "chain mail", "kind": "armor",
            "armor_base": 16, "dex_cap": 0, "equipped": true}],
 "money": {"gp": 10}}
```

```json
{"spells": [{"name_en": "Eldritch Blast", "level": 0,
             "class_key": "warlock", "entry_id": "phb-2014/spell/eldritch-blast"},
            {"name_en": "Hex", "level": 1,
             "class_key": "warlock", "entry_id": "phb-2014/spell/hex"}]}
```

## Step options: where the numbers come from

`characters/api/wizard_options.py` is the assembly layer: it takes mechanics from
`RulesSource` and the compendium from `CompendiumService`; the domain knows about neither.

* **species** — `CompendiumService.species_list()` + each species' subraces + **traits
  from the book** (`characters/api/species_traits.py`): description and features
  ("Hare-Trigger", "Rabbit Hop"). Mechanics provide only numbers, so without this the
  Harengon looked like "no bonuses" and had no traits at all;
* **classes** — 13 classes with hit die, saves, skill limit and subclasses (real records
  for level 1, otherwise only the name and level);
* **abilities** — the point buy cost table and species bonuses;
* **background** — 94 backgrounds, 9 alignments, class and species skills;
* **equipment** — items are looked up in the compendium (`/api/v1/compendium/items?q=`);
* **spells** — the class list from the books' "Spell Lists", up to level 1.

## The Species step: subrace, names and traits

1. **No subrace — no next step.** It's required where it provides part of the numbers:
   dwarf, elf, gnome, halfling (PHB, p. 20–24), genasi (EEPC), shifter (ERLW), aasimar
   (EGtW), gith. The list is explicit — `SUBRACE_REQUIRED` in `shared/rules.py`: the
   corpus doesn't mark "required", and "has subraces" isn't the same thing (the human has
   `Variant Human`, which is optional). The server checks it
   (`Draft._validate_species`); the screen just explains why "Next" is disabled.
2. **Species description and traits from the book.** `species_traits.py` cuts the
   description and features out of `text_en`. Corpus formats differ: a
   `### Harengon Traits` heading; text without a heading ("Hill Dwarf" — two lines); a
   single line (EEPC books); a section in a rules chapter (`GHOSTWISE HALFLINGS` in SCAG,
   `#### Pallid Elf` in EGtW). 50 of 64 subraces have no record of their own, so the
   lookup goes in three steps: the exact name → the name without the parent word
   ("Lightfoot" for "Lightfoot Halfling") → a section in the parent's text or a rules
   chapter.

   Screen order, **top to bottom**: the chosen species (name and "Change species") →
   subrace → "what the species gives" (numbers, including the subrace) → "what it looks
   like" (the book's description) → traits (shared + what the subrace adds). The list of
   69 species **collapses** once a species is chosen; "Change species" brings it back and
   scrolls to it.
3. **Names in Ukrainian with English in parentheses.** The `SPECIES_UK` dictionary in
   `frontend/src/features/character/uk.ts` (69 species and 64 subraces), as for classes
   and spells.

Feature texts and descriptions are **in Ukrainian**, with the original name in
parentheses («Темний зір (Darkvision)»). The translation isn't in the corpus: it's a
separate layer in `content/translations/species/*.json`, keyed by the `sha1` of the
original text (`characters/api/trait_uk.py`). So "Darkvision" in twenty species is
translated once, and the corpus remains the source of rules. No translation — the
original is shown, nothing invented. Next to the text — the numbers: skills, weapons,
tools, languages, resistances, darkvision.

Coverage today: **274 feature names, 524 texts, 105 descriptions** — every species and
subrace (`tests/api/test_species_uk.py` fails if a gap appears). Subraces are parsed
**with their parent**: half of them are described in the species text, and without
`parent_name_en` their features aren't found.

Trait coverage (`test_species_traits.py`): **68 of 69 species** have a description or
features (except "Gnoll" — in the corpus it's a monster, not a playable species) and
**57 of 64 subraces**. Seven subraces are described in the corpus only as a table
without text — for them the numbers and an honest note remain.

**Free distribution (2022 rules).** Species with `ability_unresolved` (Harengon, Custom
Lineage, Genasi, Shifter, Aasimar and others) have no fixed bonuses: the player chooses
**+2 and +1** to two different abilities or **+1, +1 and +1** to three. The choice lives
in `Character.ability_spread` (and in the draft), is checked by
`shared.rules.ability_spread`, added to abilities in `ModifierResolver`, and the sheet
shows where the number came from: "13 + 1 = 14". The cap of 20 applies here too. Without
the choice the step doesn't complete.

## The Class step

The same approach as for species: the chosen class shows **as a card at the top**, the
list of 13 classes collapses ("Change class" brings it back). The card has:

1. the name in Ukrainian with English in parentheses and the subclass if the class
   chooses it at level 1 (cleric, warlock, sorcerer) — as chips, with the book in the
   caption when names repeat;
2. **what the class gives**: hit die, saves, "skills: 2 from the list (8) — …", armor,
   weapons, tools, spellcasting (ability, prepares or knows, how many cantrips and
   spells at level 1);
3. **the class description** — in Ukrainian (`description_uk`);
4. **level-1 features with descriptions** — names and texts in Ukrainian
   (`name_uk`/`text_uk`), the original stays in the payload for reference;
5. a collapsed list of **all** class features by level — each expands into its rules
   text (`GET /api/v1/characters/wizard/class-features/{key}`, loaded only when opened:
   for 13 classes that's a few hundred kilobytes);
6. for a subclass — what it gives (always-prepared spells, an expanded list).

The description and feature texts come from `characters/api/features.py`
(`class_details`): the numbers domain doesn't know the book text, so the step takes it
from the compendium. The artificer (TCE) has no class record in the corpus, so it gets
numbers and an honest note.

Class feature translation is a separate layer (`characters/api/classes_uk.py`, files in
`content/translations/classes/`), the same as for species: keyed by the `sha1` of the
original; without a translation the English book text is shown. How it was made and how
to extend it — `docs/translation.md`.

## The Abilities, Background and Equipment steps

**Abilities.** In the standard array (15, 14, 13, 12, 10, 8) every number lives in one
ability: chosen values **don't show** in the other lists, and empty cells are "—" until
all six are assigned. "Lay it out as the book suggests" fills the array by the class's
primary abilities. On a phone each ability becomes a small card.

**Background.** A list in Ukrainian («Солдат (Soldier)»), with a card under it: the
book's description, the feature with its text (`#### Feature: …`), numbers (skills,
tools, languages, money) and **equipment from the `Equipment:` line**. The line is parsed
into items (`background_info.parse_equipment`): a comma inside parentheses doesn't split
an item, the book's options ("bone dice or deck of cards") stay a choice, "a pouch
containing 10 gp" also gives money.

The last item in the list is **«Власна передісторія» (Custom Background)**: the player
writes a name, description, the feature's name and text, chooses money, and **takes
equipment from the same catalog as the inventory**. Proficiencies follow the standard
rules (2 skills, 1 tool, 1 language). The text and items go into
`Character.custom_background`; the sheet's Background tab shows it instead of the book.

Descriptions, names, feature texts and each equipment phrase are shown in Ukrainian from
`content/translations/backgrounds/` (`backgrounds_uk.py`); the original stays next to it
in the payload. Translating phrases doesn't break adding items: the compendium lookup uses
the English text, the translation is only a label.

**Equipment.** Background items **are added automatically** (with a choice where the book
offers one: changing the option replaces the added item). Then — **the compendium catalog
with the same filters as on the sheet** (`ItemCatalogBrowser`) and "Own item" for what the
compendium lacks. A `від передісторії` ("from the background") mark in the notes shows an
item's origin and prevents adding it twice.

Each inventory item is a framed row that expands into **"What it gives"** (`ItemFacts` in
`character/inventory.tsx`): numbers from the compendium (damage with type, weapon
properties, AC, price, weight) and the book description — in Ukrainian, or the English
original with a toggle. Items with no description and nothing beyond type and weight show
no "What it gives" at all.

## The last step and creating the character

The Spells step is the last one: its button says **«Створити персонажа»** ("Create
character") and really finishes the creation (`CreateWizard.submit` has no next step, so
it calls `finish`). If the server refuses (something isn't filled in), the reason is shown.

## Storage

Drafts and characters live in SQLite (`var/dndsheet.sqlite3`), each with an owner; the
data folder can be moved with `DNDSHEET_DATA_DIR` (the tests do this). What's stored is
**state**, not derived values: classes, levels, base abilities, proficiency choices,
items, spells, current HP. AC, max HP, slots and DC aren't stored — they're computed from
the rules on every read, so a rules change leaves no "stale" numbers behind.

In the browser, `localStorage["dndsheet.draft"]` keeps the draft `id`, so a page reload
returns to the same step; the account's latest draft can also be resumed from the
character list on another device. "Start over" drops the old draft and creates a new one.

## Frontend

`frontend/src/features/wizard/` — `CreateWizard` (navigation, finish, scroll on step
change), `steps.tsx` (the six forms), `StepJumpBar.tsx` (section jumps on a phone). Each
step gets `answers` + `options` and returns a payload; it has no rules of its own, a
server error is shown as is.

## Deliberately not done

* **Level-up and multiclass in the wizard** — a separate screen ([`level-up.md`](level-up.md)).
  The aggregate is multiclass-ready, but the draft holds exactly one level-1 class.
* **A language catalog** — the mechanics have only "how many languages to choose", not a
  list; languages are chosen from a fixed set and checked by count.
* **Free "+1 to anything" outside the 2022 distribution** — a species either gives
  +2/+1 or fixed bonuses.
* **Subclass feats** — the feat text is in the compendium, but there are no numeric
  effects at level 1 beyond what the class mechanics themselves give.

## Tests

| File | What it holds |
|---|---|
| `tests/characters/test_wizard.py` | steps, order, going back, limits, class/species changes |
| `tests/characters/test_wizard_service.py` | the scenario: steps → finish, revisions, restart |
| `tests/characters/test_json_store.py` | aggregate → file → aggregate without losses |
| `tests/api/test_wizard_api.py` | HTTP end-to-end on the real corpus + server restart |

## Level-1 choices in the wizard

* **The species step** shows what the species gives right away: species cantrips, innate
  level-1 spells, and for the high elf — a cantrip choice from the wizard list.
* **The class step** for the three classes with a level-1 subclass shows the effect of
  the choice: "Always prepared: bless, cure wounds" (domain) or "Expanded list: burning
  hands, command" (patron).
* **The spells step** has a block of granted spells (not counted against class limits)
  and adds the patron's expanded list to the choosable spells.
* **The sheet** shows every spell with its source: class, species or subclass, and an
  "always prepared" mark.
