# Next steps

State as of 27.11.2026, after the redesign ("The player's table") and a check against the
PHB 2014 rules. The 5.5e (2024) rules are deliberately not supported — only the free
distribution of species bonuses from MotM/TCoE, as before.

Ukrainian words in quotes are the labels the app shows.

## What was checked and fixed

Checked on live characters and in code; every fix has a test in
`backend/tests/characters/test_rules_2014.py` or `test_expertise.py`.

| Rule | Was | Now | Source |
|---|---|---|---|
| Multiclassing into fighter | required STR 13 **and** DEX 13 | STR 13 **or** DEX 13 | PHB, p. 163 |
| Requirement text (monk, paladin) | "DEX 13 or WIS 13" | "DEX 13 and WIS 13" | PHB, p. 163 |
| Second class proficiencies | gave no armor or weapons at all, all tools | the multiclass table | PHB, p. 164 |
| Paladin and artificer preparation limit | mod + level | mod + ½ level (rounded down) | PHB, p. 84; TCE, p. 10 |
| Level 1 paladin and ranger | had "spells" and a DC | spells from level 2 | PHB, p. 84, 91 |
| Slots for "paladin + warlock" | the multiclass table | the paladin table; Pact Magic separately | PHB, p. 164–165 |
| Monk AC with a shield | 10 + DEX + WIS + shield | without Wisdom | PHB, p. 78 |
| Several unarmored AC methods | the first was taken | the best is taken | PHB, p. 14 |
| Weapon attack without proficiency | the proficiency bonus was added | not added | PHB, p. 146 |
| Expertise (rogue, bard) | missing | a choice on the sheet, double bonus | PHB, p. 54, 96 |
| Jack of All Trades, Remarkable Athlete | missing | ½ bonus to non-proficient checks and initiative | PHB, p. 54, 72 |
| Aura of Protection | missing | + CHA (min. 1) to saves | PHB, p. 85 |
| Unarmored Movement, Fast Movement | missing | + to speed | PHB, p. 48, 78 |
| Dwarven Toughness, Draconic Resilience | missing | +1 HP per level; AC 13 + DEX | PHB, p. 20, 102 |
| Feats Alert, Mobile, Tough, Observant | text only | numbers on the sheet | PHB, p. 165–169 |
| Improvement to 21 (19 + 2) | the server refused, the screen was silent | unavailable in the choice, explained in plain words | PHB, p. 165 |
| Wizard's spellbook at level 1 | only INT + 1 could be written | 6 spells in the book | PHB, p. 114 |
| Fighting style, invocations, pact boon, metamagic, maneuvers, favored enemy and terrain | missing | a choice on the sheet ("Features → Class choices"); Defense +1 AC, Archery +2 to ranged attacks | PHB, p. 72, 91, 101, 107, 110 |
| Eldritch Knight, Arcane Trickster | didn't cast | ⅓ progression, known spells and slots from level 3 | PHB, p. 75, 98 |
| Domain and oath spells | level 1 only | per the subclass table at every level | PHB, p. 58, 86 |
| Wizard prepares spells | from the whole class list | only from the book; on level-up — a reminder about +2 | PHB, p. 114 |
| Replacing a spell on level-up | missing | a choice on the level screen (bard, warlock, sorcerer, ranger, third casters) | PHB, p. 53, 101, 107 |
| Multiclass skill (bard, ranger, rogue) | not offered | a choice on the level screen | PHB, p. 164 |
| Half feats, Resilient | +1 was entered by hand | ability choice when taking the feat; Resilient grants the save | PHB, p. 165–169 |
| Heavy armor without Strength | had no effect | −10 ft (doesn't apply to dwarves) | PHB, p. 144 |

Checked with no differences: hit dice, saves and number of skills of all 13 classes,
subclass levels, the standard array and point-buy cost (27 points, 8–15), the proficiency
bonus, hit points (max at level 1, average after, Constitution retroactively), multiclass
caster level, slots and Pact Magic, spell save DC and attack bonus, armor and shield AC,
finesse/ranged attacks, half the hit dice on a long rest.

## What still doesn't follow the rules (by priority)

Done from the previous list: class choices with prerequisites, ⅓ casters, domain/oath and
Circle of the Land spells by level, the wizard's book, new and replacement spells and the
multiclass skill on the level screen, half feats, Defense, Archery, Dueling, heavy armor
(speed and disadvantage on Stealth).

Done 27.11.2026 (tests — `test_rules_effects.py`, `test_multiclass_matrix.py`,
`test_sheet_api.py`):

- **Species feat** (variant human, custom lineage) — a required choice at the species
  step in the wizard; on the sheet ("Features → Class and feat choices") it can be
  replaced, and replacing removes the previous feat's choices.
- **Pact weapon and Hexblade** — marks on an inventory item (expand the item, or a
  checkbox in the "Custom item" form); one weapon of each kind, a new mark removes the old
  one. The pact grants proficiency and magical attacks (bow and crossbow only with
  Improved Pact Weapon), Hexblade — Charisma (two-handed only as a pact weapon). Without
  the mark the attack is ordinary, and "Actions" hints where to mark it.
- **Armor without proficiency** — disadvantage on STR/DEX, a note on attacks, no
  spellcasting.
- **Feats with a choice** — Magic Initiate, Ritual Caster, Skilled, Skill Expert, Prodigy,
  Linguist, Weapon Master, Elemental Adept, Martial Adept, Eldritch Adept, Metamagic Adept,
  Fighting Initiate, Fey and Shadow Touched, Artificer Initiate, Wood Elf Magic. The choice
  uses the same mechanism as class choices (key `feat:<feat>:<group>`); the effect —
  proficiencies, expertise, spells with DC and attack bonus. The armor feats, Tavern
  Brawler, Chef, Poisoner, Gunner — proficiencies without a choice.
- **Eldritch invocations** — at-will / once-per-rest spells, Devil's Sight (120 ft),
  Armor of Shadows (13 + DEX), Beguiling Influence (Deception and Persuasion), notes on
  Eldritch Blast (Agonizing Blast +CHA, Eldritch Spear…), Improved Pact Weapon, Lifedrinker,
  Thirsting Blade.
- **Fighting styles** — Two-Weapon, Thrown Weapon, Unarmed, Blind Fighting (blindsight
  10 ft), Blessed/Druidic Warrior (two cantrips), Superior Technique (a maneuver).
- **Attacks** — the unarmed strike from the server; species natural weapons (tabaxi,
  aarakocra, lizardfolk, minotaur, leonin, tortle, centaur, satyr, dhampir, longtooth
  shifters); the monk's martial arts (DEX and a bigger die for monk weapons, strikes and
  natural weapons); Battle Ready (INT for magic weapons), Shillelagh (spellcasting ability
  and d8).
- **Subclass proficiencies** — hexblade, domains, the colleges of Valor and Swords,
  battle smith, armorer, bladesinger, assassin.
- **AC** — Bladesong (a note), Dragon Hide, Medium Armor Master (+3 DEX).
- **The bard's instrument on multiclassing**, **spell schools** of the Eldritch Knight and
  Arcane Trickster, **multiclass requirements on all 156 pairs** — checked.

Done next (`test_rules_choices_more.py`, `test_sheet_api.py`):

- **The wizard's book** — on the spells tab: how many are in the book and how many the
  levels gave (6 + 2 per level); more — "copied", fewer — "can be added".
- **Kensei weapons** — a mark on an item (2 at level 3, +1 at 6, 11, 17): proficiency, a
  monk weapon (DEX and the martial arts die), Kensei's Shot / Agile Parry in a note; heavy
  and special weapons don't qualify.
- **The species book (VGM or MPMM)** — a choice in the wizard and on the sheet where the
  natural weapon die depends on it (tabaxi, aarakocra, tortle, centaur, satyr).
- **Feat resources** — Luck Points (Lucky, 3 per long rest), superiority dice of Martial
  Adept and Superior Technique (a separate counter or +1 to the Battle Master's pool).
- **Species feat choices in the wizard** — under the feat, the same component as on the
  sheet; "Finish" won't let through a skill that already comes from the background or
  class.
- **Subclass and pact boon choices** — Knowledge Domain (2 languages, 2 skills with double
  bonus), Nature Domain (a druid cantrip and a skill), College of Lore (3 skills), College
  of Swords (a fighting style), Samurai (a skill or a language), Pact of the Tome (3
  cantrips of any class, Charisma).

- **Magical Secrets** of the bard (2 at levels 10, 14, 18; they count as known, so the
  limit from the bard list is 2/4/6 lower) and **Additional Magical Secrets** of the
  College of Lore (2 at level 6, beyond known) — spells of any class up to the bard's
  highest level, with search in a long list; the chosen spell's level is stored for the
  sheet and the PDF.
- **Book of Ancient Secrets** — 2 level-1 rituals of any class (only as rituals).
- **Subclass choices without numbers** — Hunter (4 choices), Totem Warrior (spirit,
  aspect, attunement), Draconic Ancestry, Storm Aura, Elemental Disciplines, Arcane Shot,
  Runes: the choice is stored and visible on the sheet, the effect is in the feature text.

- **Copied rituals** — Book of Ancient Secrets (up to ½ the warlock level) and Ritual
  Caster (up to ½ the character level): a group without a limit, a ritual from the
  starting pair can't be chosen twice.
- **Numbers from text choices** — rage (+2/+3/+4 damage in the note on Strength attacks,
  resistance while raging), the Bear totem (resistance to everything but psychic; the
  Aspect — doubled carrying capacity), Draconic Ancestry (the Draconic language, Elemental
  Affinity: +CHA in the note of spells of that type and resistance for a sorcery point),
  Hunter (Colossus Slayer, Horde Breaker, Volley, Whirlwind Attack in attack notes).
- **Class attack notes** — Sneak Attack (Nd6 for finesse and ranged weapons), Divine
  Smite (paladin 2+, melee).

The PHB 2014 rules the sheet computes are closed with this; the other features are text in
"Features".

### Rules check: all class features 1–20

Every feature from the mechanics index was checked against the code. Those that change
numbers on the sheet but weren't computed now are (tests — `test_rules_choices_more.py`):

| Feature | What the sheet computes |
|---|---|
| Primal Champion (barbarian 20) | +4 Strength and Constitution, max 24 |
| Diamond Soul (monk 14), Slippery Mind (rogue 15) | saving throw proficiency |
| Lay on Hands, Cleansing Touch (paladin) | counters: 5 × level HP; CHA times |
| Improved Divine Smite (paladin 11) | +1d8 radiant in the attack note |
| Flash of Genius (artificer 7) | a counter, INT times |
| Magic Item Adept / Savant / Master (artificer 10/14/18) | attunement to 4/5/6 items |
| Soul of Artifice (artificer 20) | +1 to saving throws per attuned item |
| Mystic Arcanum (warlock 11/13/15/17) | spells of levels 6–9, once per long rest |
| Spell Mastery (wizard 18), Signature Spells (wizard 20) | spell choices, "at will" / once per short rest |
| Improved / Superior Critical (champion 3/15) | "critical hit on 19–20 / 18–20" in attacks |
| Brutal Critical (barbarian 9/13/17) | +1/2/3 dice on a critical |
| Danger Sense, Feral Instinct, Reliable Talent, Blindsense, Feral Senses, Stillness of Mind, War Caster | notes in "Senses and resistances" |
| Purity of Body, Divine Health | immunities in "Senses and resistances" |

Deliberately left as text (the sheet has nothing to compute, or it's a call at the table):
Song of Rest, Countercharm, Destroy Undead, Deflect Missiles, Slow Fall, Empty Body,
Timeless Body, Cunning Action, Evasion, the Wild Shape CR limit, TCoE choice replacements
at levels 4/8/12/16.

## Translation

The rule and canonical terms — `docs/translation-rules.md`; the `test_terminology.py` test
watches the interface.

Done: **the texts of all spells** (723 texts with "At Higher Levels" paragraphs), **feats**
(109) and **optional features** (151) — a machine draft following the glossary, checked for
completeness, dice and numbers (`scripts/rules_uk_check.py`). The pipeline and term
decisions — `docs/translation.md`, section "Spell, feat and optional feature texts".

What's left:

- Human proofreading against the official PDF (as for the other layers).
- Proper names the translators chose themselves (Acquisitions Incorporated, Jim
  Darkmagic, the Strixhaven colleges), and item names in the "Magic Item Replication"
  tables — reconcile them with the item dictionary when that gets translated further.
- The Dragonlance feats (Knight of Solamnia, the Robes adepts) are recorded in Russian in
  the corpus and were translated from it; those records are worth rebuilding from the
  English source.

## Interface and design

Done:

- **The "Equipment" step** — the names of all 31 pack items are found in the compendium;
  the artificer pack (TCoE), which was missing, was added.
- **Spell preparation on the level screen** — cleric, druid, paladin, artificer and wizard
  prepare the day's set right after leveling up (the same panel as on the sheet); known
  spells and the wizard's book were already chosen on the level screen.
- **`ddb-*` → `sheet-*`**, `ddb.css` → `sheet.css`, `ddb.tsx` → `sheetParts.tsx`; ~75
  rules whose classes no longer exist in the code were removed (`styles.css` 1662 → 1241
  lines).
- **Contrast (WCAG AA)** — `--act-text` for crimson text in the dark theme (was 3.8:1, now
  ≥5:1), `--field-line` for field, button and chip borders (was 1.4:1, now ≥3:1), a darker
  brass in the light theme; the «Урон» (Damage) label in the light theme was nearly
  invisible.
- **Keyboard** — a visible focus ring on fields, counters, notes; on clipped (clip-path)
  buttons and sheet buttons the ring is inside, because an outer outline got clipped; the
  sheet tabs mark the active one with `aria-current`. There are no clickable non-buttons.

- **Alegreya fonts** — from `@fontsource/*` in the build (only the styles used, Cyrillic
  and Latin by `unicode-range`); no requests to Google Fonts.
- **Red text** — `--wax-text`: error messages and damage labels in the light theme were
  pale pink on white.
- **The wizard walked through every step** (paladin, mountain dwarf, soldier → sheet).
  Fixed: the "Spells" step offered slots and preparation to level 1 paladins and rangers
  (they cast from level 2; the class card now says "from level 2"); "Shield" from the
  starting pack became the "Shield of Ruidium" — compendium search now puts the exact name
  first (the catalog too); a shield from the pack is equipped, like armor; quantities
  («Сулиця × 5», "Javelin × 5"); pack and javelin names are the same in the choice and the
  inventory; "choose one" species and background tools are chosen in the wizard; PHB
  backgrounds come first; the draft summary shows abilities with the species bonus;
  species weapons, the sheet header and proficiencies are in Ukrainian («бойова сокира»,
  not "battleaxe"); «концентрація» instead of a doubled «концентрація · зосередження».
- **"Spend N" pools** — Lay on Hands, sorcery points and ki (and any counter above 10)
  have a "how many" field next to "Spend / Restore".

## Home page

Done: a fan of real PDF pages (`frontend/public/previews/`, cleric 5 from
`scripts/print_samples.py`), the compendium contents with counts
(`/api/v1/compendium/books`), a shelf of books with covers, price and a link to D&D Beyond,
a disclaimer (a non-commercial fan project, the Fan Content Policy notice).

Prices and covers — `content/books_market.json`, checked by hand against the D&D Beyond
marketplace on 27.11.2026; the date is shown on the page. Prices change — review them every
few months. Covers are shown from the D&D Beyond site by link and aren't copied into the
repository.

Refresh the sheet previews: `scripts/print_preview.py --pdf` (in Docker), then
`pdftoppm -r 120` pages 1, 2, 5 of `cleric-5.pdf` into
`frontend/public/previews/sheet-{front,spells,features}.png`.

## Print and PDF

Done: a printable character sheet following the logic of the paper sheet (and the DDB
export), black on white, frames with inverted corners, Alegreya fonts embedded. Data —
`characters/api/print_view.py` (the same as on screen), template —
`export/infrastructure/templates/character.html.jinja`.

- **The play sheet** (`/export/pdf`): a main page without running text (abilities, saves,
  skills, combat, hit points and death saves for a pencil, attacks, limited features as
  boxes, proficiencies, a list of features), spells (slots, preparation marks, a table
  without descriptions), equipment and notes with lines for writing.
- **Adventure log** — a separate page with lines for recording events (session, what
  happened, what was gained).
- **Extra sheets** at the end of the same PDF: the full texts of features, species traits,
  background and spell descriptions in two columns (`?detailed=false` — without them).
- **Print from the browser** (`/print`): the same HTML — works even without WeasyPrint.
- Previewing the layout: `python scripts/print_preview.py --pdf` (reference characters →
  `logs/print-preview/`).

Next: check against the DDB PDF item by item (personality traits, ideals, bonds, flaws —
the character model doesn't have them yet); a companion page for beasts and summoned
creatures.

## Players, sign-in, compendium

Done (setup — `RUN.md`, section 3.2):

- **Telegram sign-in** (Login Widget): the server checks the signature and freshness and
  issues its own 30-day cookie session; the `identity` context (users, sessions). For
  `localhost` — a development sign-in by name (only with `DNDSHEET_DEV_LOGIN=1`).
- **Telegram Mini App**: the same sheet inside Telegram; `initData` is checked with the
  same HMAC under a different key, the session is a Bearer token; a shared link opens in
  the Mini App via `startapp=s_<token>`.
- **Characters and drafts in SQLite** (`var/dndsheet.sqlite3`) with an owner: available
  from any device; old `var/characters/*.json` files are migrated once and go to the app
  owner. Someone else's character doesn't exist for the API (404).
- **Sheet sync**: polling the version every 4 s; writes are conditional
  (`WHERE version < new`), so two simultaneous changes won't overwrite each other, and
  after a conflict the screen shows the fresh version.
- **Compendium without sign-in** (server pages `/kb/…` since the SEO work, see [seo.md](seo.md); was `#/kb`): species with subraces, classes with features by
  level and all subclasses, backgrounds — the same cards as in the wizard; feats, spells
  (filter by level), optional features, items (the inventory catalog with filters). Search
  in Ukrainian and English.

- **Share a character**: the owner creates a `/#/s/<token>` link — the sheet without
  sign-in, view only (buttons and fields are disabled, tabs and descriptions work), print
  and PDF by link, the page refreshes when the owner changes the sheet. A new link
  invalidates the old one, "Disable" revokes it. Everything is visible, notes included.

Next:

- Parties and a DM view — deliberately postponed.
- There are no monsters in the compendium: the bestiary is kept apart from the compendium
  corpus.

## Infrastructure

Frontend dependencies: `npm audit` — 0 vulnerabilities (the unused `zod` was removed,
`vite` 6.4.6 closes the `esbuild` dev-server warning).

Done:

- Tests in the image (`test-docker.cmd`, the `test` stage in the `Dockerfile`; the PDF
  tests pass there too) and a fast dev mode (`dev-docker.cmd`: Vite + `uvicorn --reload`,
  code from disk).
- Production at <https://dnd.voronin.app>: a VPS with Caddy and Let's Encrypt, Cloudflare
  DNS, infrastructure in Terraform — [deploy.md](deploy.md).
- GitHub Actions: pre-commit, backend and frontend checks on every PR, auto-deploy after a
  green `main` — [ci.md](ci.md). The book corpus is encrypted with git-crypt, and CI
  unlocks it with the `GIT_CRYPT_KEY` secret.
