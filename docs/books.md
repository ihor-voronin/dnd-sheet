# The D&D 5e (2014) book library — an inventory for the character sheet

Status: **reference document**. It records the books of the 2014 line (2014–2024), what each gives the character sheet, and **whether it's in the owned D&D Beyond library** — and if not, whether its text is on the 5e.tools mirror. The source of truth for content is the book audit itself, not this list.

Availability was checked on 25.11.2026 against [My Library (D&D Beyond)](https://www.dndbeyond.com/en/library?ownership=owned&ruleset=5e&type=sourcebooks): **33 sourcebooks + 15 adventures**. Separately, **not on DDB**, three books are worked from PDF: the printed *Bigby Presents: Glory of the Giants* (text taken via OCR, §7.1), the free *Elemental Evil Player's Companion* (a real text layer, §7.3) and *Dragonlance: Shadow of the Dragon Queen* (a Russian translation, §8). So the corpus holds **52 books**.

The second source is the unofficial **[5e.tools](https://5e.tools/)** mirror: the same books as JSON, including those that aren't in the library. As of 26.11.2026 **41 folders** have been downloaded from it (8 first-wave books + 33 second-wave files, §7.4) — together 22 species, 27 backgrounds, 10 feats, 12 subclasses, 5 spells, 279 items and 1337 stat blocks that weren't in the corpus. They're not in `content/compendium/` yet, so the §8 counters don't include them. What the mirror doesn't have is listed in §11.5.

Markers in the tables: `✅` — in the D&D Beyond library; `📄 PDF` — not on DDB, but an own copy exists; `🌐` — not on DDB, but the text was downloaded from the 5e.tools mirror; `❌` — nowhere.

## 0. Purpose and caveats

- The list exists so as **not to lose a book** with playable options and not to drag anything extra into the translation pipeline.
- `✅` — in the D&D Beyond library; `📄 PDF` — not on DDB, but the text was taken from an own copy; `🌐` — not on DDB, but the text was downloaded from the 5e.tools mirror; `❌` — nowhere.
- Exact counts differ between references: a coverage catalog counts records **unique to the book** (for example, SCAG has 9 subclasses, but 3 of them are reprinted in XGtE/TCoE — so the catalog shows 6). So the numbers below are approximate, marked "~".
- The 2014 line is finished; **the 2024 rules (PHB 2024, DMG 2024, MM 2025) are a different edition** and are not part of the project.
- The 5e.tools mirror holds **both lines at once** (XPHB 2024 with 77 feats and 16 backgrounds, plus FRHoF, EFA, RHW, AU, PL, WoW). So you can't take "everything there is" from it — every record is filtered by `source` (§7.4).
- Legally: only **SRD 5.1** (a subset of the PHB, CC-BY) may be published. The other books are for personal use, and every record carries `license: proprietary`.

## 1. Core

| Book | Year | DDB | What it gives the sheet |
|---|---|---|---|
| **Player's Handbook (PHB)** | 2014 | ✅ | 12 classes, 40 subclasses, 9 races, 13 backgrounds (+5 variants = 18), 42 feats, ~360 spells, gear, weapons and armor |
| **Dungeon Master's Guide (DMG)** | 2014 | ✅ | ~270 magic items; 2 subclasses for "evil" campaigns (Death Domain, Oathbreaker); travel and reward rules |
| **Monster Manual (MM)** | 2014 | ✅ | for the sheet — **beasts only**: druid wild shapes, `find familiar`, `find steed`, polymorph |
| **Basic Rules / SRD 5.1** | 2014 | ✅ | a free subset of the PHB; **the only legally clean layer** for a future public mode |

## 2. Big collections of rules and options

| Book | Year | DDB | Classes/subclasses | Other for the sheet |
|---|---|---|---|---|
| **Xanathar's Guide to Everything (XGtE)** | 2017 | ✅ | 29 subclasses | 95 spells, 15 racial feats, tools, ~48 items |
| **Tasha's Cauldron of Everything (TCoE)** | 2020 | ✅ | 26 subclasses | 21 spells, 15 feats, **Optional Class Features** (feature swaps — a separate engine mode), Custom Lineage, sidekicks, group patrons |
| **Mordenkainen Presents: Monsters of the Multiverse (MotM)** | 2022 | ✅ | — | **33 races/subraces in revised versions** — effectively a "race collection"; plus stat blocks |
| **Fizban's Treasury of Dragons (FToD)** | 2021 | ✅ | 2 (Drakewarden, Ascendant Dragon) | Dragonborn (chromatic/gem/metallic), 7 spells, 3 feats, ~15 items |
| **Bigby Presents: Glory of the Giants (BGG)** | 2023 | 📄 PDF | 1 (Path of the Giant) | 8 feats, 2 backgrounds, **27 items**, the Rune Spells table. The printed edition was bought; not bought on DDB — the text was taken from a scan via OCR (§7.1) |
| **The Book of Many Things (BMT)** | 2023 | ✅ | — | 3 spells, 1 feat, 2 backgrounds, ~58 items |
| **Elemental Evil Player's Companion (EEPC)** | 2015 | 📄 PDF | — | 4 race entries (Aarakocra, Deep Gnome, Genasi with 4 subraces, Goliath) + **43 spells**. A free PDF, taken from the text layer without OCR (§7.3); **zero new content** — it's all already in MotM and PotA/XGtE |

## 3. Setting books with playable options

| Book | Setting | DDB | What it gives |
|---|---|---|---|
| **Sword Coast Adventurer's Guide (SCAG)** | Forgotten Realms | ✅ | 6 unique subclasses (Battlerager, Arcana, Banneret, Long Death, Crown, Undying), blade cantrips (Booming Blade, Green-Flame Blade), 13 backgrounds, half-elf and tiefling variants |
| **Volo's Guide to Monsters (VGtM)** | FR | ✅ | 12 "monstrous" races: Aasimar, Firbolg, Goliath, Kenku, Lizardfolk, Tabaxi, Triton, Bugbear, Goblin, Hobgoblin, Kobold, Orc, Yuan-ti |
| **Mordenkainen's Tome of Foes (MToF)** | FR/planes | ✅ | Subraces: Eladrin, Sea Elf, Shadar-kai, Duergar, Svirfneblin; Githyanki/Githzerai; tiefling variants; 1 feat |
| **Guildmasters' Guide to Ravnica (GGR)** | Ravnica | ✅ | 5 races (Centaur, Loxodon, Minotaur, Simic Hybrid, Vedalken), 2 subclasses (Order Domain, Circle of Spores), 10 guild backgrounds |
| **Eberron: Rising from the Last War (ERLW)** | Eberron | ✅ | **the Artificer class** (+3 subclasses), 4 races (Changeling, Kalashtar, Shifter, Warforged), dragonmarks, 1 background |
| **Explorer's Guide to Wildemount (EGtW)** | Wildemount | ✅ | 3 subclasses (Echo Knight, Chronurgy, Graviturgy), dunamancy spells, subraces (Draconblood/Ravenite, Pallid, Lotusden), Hollow One |
| **Mythic Odysseys of Theros (MOoT)** | Theros | ✅ | 4 races (Centaur, Leonin, Minotaur, Satyr), 2 subclasses (Oath of Glory, Eloquence), Piety, supernatural gifts |
| **Van Richten's Guide to Ravenloft (VRGtR)** | Ravenloft | ✅ | 3 lineages (Dhampir, Hexblood, Reborn), 2 subclasses (College of Spirits, The Undead), Dark Gifts |
| **Strixhaven: A Curriculum of Chaos (SCC)** | Strixhaven | ✅ | The Owlin race, 5 backgrounds, 2 feats, 5 spells |
| **Spelljammer: Adventures in Space (SAiS)** | Spelljammer | ✅ | 6 races (Astral Elf, Autognome, Giff, Hadozee, Plasmoid, Thri-kreen) |
| **Dragonlance: Shadow of the Dragon Queen (SotDQ)** | Dragonlance | 📄 PDF | The Kender race, the Lunar Sorcery subclass, 9 feats (knights and mages), 2 backgrounds, 9 items (§8). The text is a Russian fan translation |
| **Planescape: Adventures in the Multiverse (PS:AitM)** | Planescape | 🌐 | 2 backgrounds (Gate Warden, Planar Philosopher), **7 feats**, 2 spells (warp sense, gate seal), 5 items. The mirror serves it as two books: *Sigil and the Outlands* (options) + *Morte's Planar Parade* (54 creatures); the adventure "Turn of Fortune's Wheel" isn't needed by the sheet (§7.4) |
| **Acquisitions Incorporated (AI)** | FR | ✅ | The Verdan race, 5 backgrounds, 7 spells, franchise rules |
| **The Wild Beyond the Witchlight (WBtW)** | Feywild | ✅ | 2 races (Fairy, Harengon), 2 backgrounds (Feylost, Witchlight Hand). *On DDB this is an "adventure", not a sourcebook — but the options are unlocked* |

## 4. Adventures that also gave the sheet something

| Book | DDB | What it gives |
|---|---|---|
| **Curse of Strahd (CoS)** | 🌐 | The **Haunted One** background + 14 items (Sunsword, Icon of Ravenloft…), 97 stat blocks, Dark Gifts |
| **Tomb of Annihilation (ToA)** | 🌐 | 2 backgrounds (Anthropologist, Archaeologist), 26 items, 89 stat blocks |
| **Storm King's Thunder (SKT)** | ✅ | ~17 magic items |
| **Princes of the Apocalypse (PotA)** | ✅ | items |
| **Out of the Abyss (OotA)** | 🌐 | 103 stat blocks (demon lords, duergar, spore servants), 16 items (Dawnbringer, Piwafwi…); no backgrounds or feats |
| **Tyranny of Dragons (ToD)** | ✅ | items |
| **Waterdeep: Dragon Heist (WDH)** | ✅ | items |
| **Waterdeep: Dungeon of the Mad Mage (WDMM)** | ✅ | items |
| **Baldur's Gate: Descent into Avernus (BG:DiA)** | 🌐 | **14 backgrounds** (13 "Baldur's Gate X" + Faceless), 13 items, 53 stat blocks, 7 charms, 4 infernal war machines + 9 upgrades (App. B) |
| **Ghosts of Saltmarsh (GoS)** | 🌐 | **4 backgrounds** (Fisher, Marine, Shipwright, Smuggler), 6 items (App. B), 9 subsections of ship rules (App. A), 57 stat blocks (App. C) |
| **Candlekeep Mysteries (CM)** | ✅ | items |
| **Lost Laboratory of Kwalish (LLoK)** | ✅ | 3 spells, 8 items |
| **Tales from the Yawning Portal (TftYP)** | ✅ | items |
| **Infernal Machine Rebuild (IMR)** | 🌐 | 26 stat blocks (App. B: Thessalhydra, Thessalkraken, Neo-Otyugh…), 11 items and poisons (App. C: Thessaltoxin, Ruinblade, Infernal Machine of Lum the Mad) |

The remaining adventures — Keys from the Golden Vault, Journeys through the Radiant Citadel, Phandelver and Below, Vecna: Eve of Ruin, Quests from the Infinite Staircase, Chains of Asmodeus, Rime of the Frostmaiden and a dozen small ones — **are now downloaded from the mirror** (§7.4) and together give 137 items, 3 spells and 539 stat blocks. Parse them last: for the sheet it's almost exclusively items.

## 5. Free content, Adventurers League and DMs Guild (official, but outside the core)

| Item | DDB | What it gives |
|---|---|---|
| **Plane Shift** (Amonkhet, Ixalan, Kaladesh, Zendikar, Dominaria, Innistrad) | 🌐 | free PDFs: races, subclasses, sometimes feats. Not on DDB, but **all six were downloaded** from the mirror (`ps-amonkhet`…`ps-dominaria`): 20 species (+24 subraces), 5 backgrounds, 3 feats, 12 subclasses |
| **The Tortle Package** | ✅ | the Tortle race |
| **One Grung Above** | ✅ | the Grung race |
| **Locathah Rising** | 🌐 | the Locathah race — **downloaded** (`lr`, 1 species + 6 stat blocks); on DDB only as a separate adventure |
| **Wayfinder's Guide to Eberron** | ✅ | the ERLW predecessor (races, 1 feat) — outdated, but available |
| **State of Hillsfar** / **Mulmaster Bonds and Backgrounds** / **Curse of Strahd: Optional Backgrounds** | ❌ | AL material: 7 / 5 / 6 backgrounds. **Checked: they're not on the mirror** (§11.5) |
| **Minsc and Boo's Journal of Villainy** | 🌐 | **checked:** it's on the mirror (`MaBJoV`), but gives only 56 stat blocks and 2 items — no subclasses (DMs Guild) |
| **Adventure with Muk** (2019, free) | 🌐 | the Goblin (Dankwood) species + 11 stat blocks; **downloaded** (`awm`) |
| **Legends of Runeterra: Dark Tides of Bilgewater** | ❌ | items (crossover) |

## 6. What we DON'T take

- **Unearthed Arcana** (✅ in the library, free) — playtest material superseded by official versions; individual cases only as homebrew.
- **2024 rules (PHB 2024, DMG 2024, MM 2025)** — a different edition; we're `edition: 2014`.
- **Books without player content**: most adventures, monster compendiums, setting guides without options, Starter/Essentials Sets.
- **Blood Hunter** — not WotC (Critical Role/DMs Guild); would come in as homebrew, not as official content.

## 7. Pipeline priority and availability

| Queue | Books | Availability | Why |
|---|---|---|---|
| **1** | PHB, XGtE, TCoE, SCAG, DMG, FToD, EGtW, AI, BMT | **9/9** ✅ | 90% of real characters: classes, subclasses, spells, items |
| **1.5** | VGtM, MToF, MotM, GGR, ERLW, MOoT, VRGtR, SCC, SAiS, WBtW, **BGG (PDF)** | **11/11** ✅ | exotic races and setting subclasses |
| **1.5 🌐** | SotDQ, PS:AitM | **2/2** — source available | SotDQ from PDF (§8), PS:AitM from the mirror (§7.4): the only subclass outside the library (Lunar Sorcery) + 7 feats |
| **2** | MM, Monstrous Compendium 1/2/4, Fiendish Folio, MToF, Misplaced Monsters, Vecna Dossier | **8/8** ✅ | wild shapes, familiars, `find steed` |
| **3** | adventures with items and backgrounds | **15/15** ✅ | the selection from §4 |
| **4 🌐** | BG:DiA, GoS, ToA, CoS, PS:AitM | **5/5** — downloaded from the mirror, not parsed | 14+4+2+1+2 = 23 backgrounds that exist nowhere else |

**EEPC** isn't sold on DDB as a separate book, but it's a free PDF: taken from the text layer (§7.3). Its Aarakocra/Genasi/Goliath/Svirfneblin are already in MotM, the spells in PotA and XGtE, so nothing was lost even before; now there's also a primary source with the same texts.

**Translation volume:** ~**2.5–3 million characters** for the corpus of 52 books. The 41 mirror folders (§7.4) will add as much as their playable part gives — the figure will be known after parsing, because the JSON also contains adventure text that the sheet doesn't need.

### 7.1 How BGG was taken without buying it on DDB

The book exists in print, so the text was taken from a scan (200 pages, 300 dpi, **no text layer**) with our own pipeline in `scripts/pdf/`:

1. `pdf2md.py` — extracts each page's embedded image without re-encoding, recognizes the text (RapidOCR, PP-OCR) and assembles the pages into markdown; the reading order is restored by a recursive XY-cut (`xycut.py`), so two-column spreads, sidebars and tables don't get mixed up.
2. `despace.py` — restores the spaces OCR lost in dense typesetting (`characterstothe…` → `characters to the…`), using a dictionary built from the existing corpus.
3. `polish.py` — joins broken words (`max imum` → `maximum`), fixes single-letter errors (`attuncs` → `attunes`) and removes illustrator credits.
4. `build_gotg.py` — assembles the records: the subclass, backgrounds and feats were proofread by hand from the page text; the 27 items are split by name and parsed into `item_type`/`rarity`/`attunement`.

The raw pages are in `content/raw/gotg-pdf/{images,ocr,pages}/`, so any record can be checked against the page image.

### 7.2 How it was verified

One OCR is one opinion, so every record was checked against an independent source:

| What | Against what | Result |
|---|---|---|
| **27 items** | the book's item list on [dungeonsports.com](https://www.dungeonsports.com/pricing-by-book/bigby-presents-glory-of-the-giants-item-pricings/) (32 entries: 26 items + 4 giant figurines) | a 1:1 match; this is exactly how two items missing from the references were found — **Lucent Destroyer** and **Mistral Mantle** |
| **Names and rarity** | [kobold.wiki](https://kobold.wiki/wondrous-items:wyrmreaver-gauntlets), [dnd5e.wikidot.com](https://dnd5e.wikidot.com/wondrous-items:lash-of-immolation) | "Lash of Immolation" and "Wyrmreaver Gauntlets" — exactly as we have them (third-party tables misspell these names) |
| **1 subclass, 2 backgrounds, 8 feats** | the book's description on [D&D Beyond Marketplace](https://www.dndbeyond.com/marketplace/sourcebooks/bigby-presents-glory-of-the-giants) | "1 new barbarian subclass, 2 backgrounds, 8 feats" — matches |
| **All texts (43 records)** | **a second independent OCR** of the same book (an Internet Archive scan, 200 pages with a text layer) | 37/41 records are fully explained by the book; 4 — where the OCR source is worse than ours; 2 — authored by us (the Rune Spells table and the Bonus Feats rule), verified separately |
| **The Rune Spells table** | the table in the scan | 13 of 13 "rune → spell" pairs match |
| **Conflicting numbers** | the page image | Elemental Cleaver: the second OCR says "40 ft", the page says **60 ft** — we have 60 |

The check is reproducible: `scripts/pdf/validate_ref.py` (coverage of every record), `compare_items.py` (coverage per item), `check_rules.py` (the table and the rule), `sweep_headings.py` (whether any heading was missed). Scans for comparison — `logs/gotg_ref_text.pdf` (the second OCR) and `content/raw/gotg-pdf/images/` (ours).

**What this check changed in the corpus:** the Rune Carver section was originally reconstructed from fragments — replaced with the exact book text; in 8 items (Crown of the Wrath Bringer, Delver's Claws, Helm of Perfect Potential, Longbow of the Healing Hearth, Prehistoric Figurines, Shield of the Blazing Dreadnought, Orb of Skoraeus, Glowrune Pigment) the columns were mixed up — rebuilt; Adze of Annam and Wayfarer's Boots "swallowed" neighboring text (the Giant-Crafted Items sidebar and the Thunderbuss item) — trimmed; in the "Chapter 1" rules a phrase was corrected to match the book.

**Scope limit:** the "Big Heroes, Big Stories" section (pp. 15–17: Heroes of the Giants, Birthplaces and Hometowns, the Giant Trinkets / Elemental Marks / Underground Quirks / Tall Tales tables, Primordial Nexus, Sequestered Caverns) was **not** turned into records — these are inspiration tables for backstory, neither rules nor options; its OCR text is in `pages/`.

### 7.3 EEPC: a free PDF with real text

`Elemental Evil Player's Companion` is 25 pages, and unlike BGG it **has a text layer** (85k characters). So no OCR is needed: `scripts/pdf/build_eepc.py` reads the page text directly.

What had to be solved during parsing (this is no longer about recognition but about structure):

* **The text layer has no headings** — no capitals, no style markers. So spell names are taken from the book's own spell list (the "Spell Lists" section), not from outside: a line matching a name from the list and followed by an "Nth-level school" line is treated as the start of a description.
* **A spell's stat block wraps onto the next line** ("Casting Time: 1 reaction, which you take when you take … acid, cold, fire, lightning, or thunder damage"). So field values are joined until all four fields appear.
* **The last spell (Whirlwind) runs into the back cover** with an ad for the Neverwinter MMORPG — the description body is cut at the marketing lines, otherwise that text gets into the record.
* Soft hyphens (U+00AD) inside words are removed, otherwise "Abi-Dalzim's" can't be found.

**Result:** 8 species records (4 race entries: Aarakocra, Deep Gnome as a gnome subrace, Genasi with 4 subraces, Goliath) + 43 spells (8 cantrips + 35 leveled) + 2 rules. External check: the 43 spells match the [Elemental Evil list](http://memoriasdelabismo.blogspot.com/2015/03/elemental-evil-lista-de-hechizos.html), the 25 pages and four race options match the [description of the release](https://www.escapistmagazine.com/download-the-dd-5e-elemental-evil-players-companion-for-free/).

**Why it adds nothing to the sheet:** all 43 spells are already in `pota` and `xgte`, all races in `motm`, `mtof`, `vgtm`, `egtw`. EEPC is valuable as a **primary source**: `validate_eepc.py` compares our records with the reprints (similarity of 0.85–0.97 — these are errata fixes, not parsing errors) and checks them structurally: 0 problems, 0 length outliers.

### 7.4 The 5e.tools mirror: JSON instead of PDF

[5e.tools](https://5e.tools/) is an unofficial 5e mirror where the same books are broken down into nodes and stored as JSON. For us it's a **second source** next to D&D Beyond, and it covers exactly the books that aren't in the library.

**Access.** HTML pages without scripts give nothing (in a browser `adventure.html#bgdia` hangs on "Loading…"), so you have to read `data/…json` — and only with a browser `User-Agent` and `Referer: https://5e.tools/…`, otherwise you get **403**. In this environment TLS works through `urllib`, while `curl` fails with `SEC_E_NO_CREDENTIALS`, so the downloader is `scripts/ingest/fetch_5etools.py`:

```
python scripts/ingest/fetch_5etools.py adventure/adventure-toa.json content/raw/toa/adventure-toa.json
```

**Structure — two layers.**

1. *Indexes*: `data/books.json` (**68 books**), `data/adventures.json` (**104 adventures**) — id, name, group, date.
2. *Book text*: `data/book/book-<id>.json` or `data/adventure/adventure-<id>.json` — a tree of sections (`section` → `entries` → text, `inset`, `table`, `list`), with tags inside: `{@creature …}`, `{@item …}`, `{@spell …}`, `{@area …|}`, `{@dc 15}`.

**The main pitfall:** a book file **contains** no stat blocks, items or feats — only references:

```json
{"type": "statblock", "name": "Giant Crab", "tag": "creature", "source": "GoS"}
```

The text itself lives in topical corpora: `data/bestiary/bestiary-<id>.json`, `data/items.json`, `data/feats.json`, `data/backgrounds.json`, `data/races.json`, `data/spells/spells-<id>.json`. So "count what a book gives" = count the references and join the text from the corpus to them.

**What was downloaded and parsed (26.11.2026)** — `content/raw/<folder>/`, **41 folders**: the book file plus the stat block file if the mirror keeps it separately. All 41 are parsed into the corpus — `content/compendium/<folder>/` and `content/bestiary/<folder>/` — by `scripts/ingest/mirror5e.py`; the source registry is extended by `scripts/ingest/sync_sources.py` (name, year and type from the mirror's catalog, categories and counts from the parsed records).

| Group | Folders | Species | Backgr. | Feats | Subcl. | Spells | Items | Stat bl. | Records |
|---|---|---|---|---|---|---|---|---|---|
| first wave: BGDIA, ToA, GoS, CoS, OotA, IMR, SatO, MPP | 8 | — | 22 | 7 | — | 2 | 94 | 479 | 604 |
| **Plane Shift ×6** (PS-A…PS-X) | 6 | **45** (species + subraces) | 5 | 3 | **6** | — | 50 | 168 | 277 |
| small: AWM, AL, MaBJoV, MGELFT, BAM, LR | 6 | 2 | — | — | — | — | 1 | 151 | 154 |
| adventures with items (IDRotF, PaBTSO, CoA, QftIS, KftGV, HotDQ, XMtS, JttRC, VEoR, RoT…) | 21 | — | — | — | — | 3 | 137 | 539 | 679 |
| **total** | **41** | **47** | **27** | **10** | **6** | **5** | **282** | **1337** | **1714** |

Counts come from what actually landed in the corpus, not from references in the book text: ToA, for example, has 7 item references but 27 item records. Reference corpora in `_index/`: `books` (68 books), `adventures` (104), `backgrounds` (175 records), `feats` (317), `races` (177 + 98 subraces), `items` (2607) + `items-base` (230), `spells` (19 files, 1038 spells), `classes` (23 classes), `optionalfeatures` (233), `magicvariants` (230), `rewards` (315), `bestiary/index` (110 sources) and `bestiary/` — 7 base files without which `_copy` can't be resolved (see the pitfalls).

**The second find — subclasses.** The mirror keeps the subclasses of ALL books, including those long in our corpus but without subclasses: DDB pages didn't serve them, so across 52 books there were **2** subclasses. `mirror5e.py --subclasses` filled them in for 8 books: **PHB 40, XGE 31, TCE 30, SCAG 6, EGW 3, DMG 2, FTD 2, VRGtR 2 — 116 in total**. The corpus now has 124 subclasses, and the character builder can level up.

**The third find — optional features.** These are invocations, maneuvers, metamagic, fighting styles, infusions, runes, arcane shots, pact boons: what a character chooses **inside** a class feature, not as a feat. The mirror keeps all 233 in one index (`_index/mirror-optionalfeatures.json`), not in a book folder — because the same feature appears in several books and classes. At first the contract had no category for them; now it does (`optionalfeature`), and `mirror5e.py --optionalfeatures` added **151 records** to three books: **PHB 82 (32 invocations, 17 elemental disciplines, 16 maneuvers, 8 metamagic, 16 fighting styles, 3 pacts), TCE 47 (16 artificer infusions, 8 invocations, 7 maneuvers, 6 runes, 11 fighting styles, 2 metamagic, 1 pact), XGE 22 (14 invocations, 8 arcane shots)**. The mirror's other 82 records were deliberately left out: they're the 2024 line (`XPHB` 58, `WoW` 12, `AU` 8, `EFA` 4).

In total the mirror gave **1714 records** (27 backgrounds, 10 feats, 47 species, 6 subclasses, 5 spells, 282 items, 1337 stat blocks) plus 116 subclasses and 151 optional features for existing books. The corpus grew from **5558** to **7423 records** (3818 compendium + 3605 bestiary); the registry has 93 sources, 92 of them with records (`al` has no entities).

**What the mirror doesn't have or what we deliberately don't take.** Only these remain:

* **AAG** (Astral Adventurer's Guide) — 20 "items" in the mirror, but they're ships and helms (`Spelljamming Helm`, `Nautiloid`, `Bombard`), i.e. vehicles, not sheet gear; the book itself we have from DDB (`sais`).
* **HAT-LMI** (Honor Among Thieves: Legendary Magic Items) and **EET** — there are records in `items.json` (5 and 1 item), but the mirror has no separate book file; there's nothing to take beyond the records themselves.
* **UATheMysticClass** — mystic subclasses from Unearthed Arcana; UA itself is parsed by us as `rule` (§8).
* bestiaries and adventures without playable content: DIP, SLW, OoW, RtG, ToFW, KKW, HoL, GotSF, DoSI, HAT-TG, AATM, NRH-*, AitFR-ISF/DN/FCD — only stat blocks and adventure text, nothing for the sheet.

**Pitfalls:**

* **The ids don't match ours**: `FTD`→`ftod`, `MPMM`→`motm`, `DSotDQ`→`sotdq`, `AIS`→`sais`, `PS-Z`…`PS-D` are `ps-zendikar`…`ps-dominaria`, while in the corpus records the same books are called `PSZ`…`PSD`. Compare by `id` + `name`, not by catalog name, otherwise "104 adventures vs 52 books" produces false gaps.
* **The mirror mixes lines**: `XPHB` (2024: 77 feats, 16 backgrounds), `FRHoF`, `EFA`, `RHW`, `AU`, `PL`, `WoW` are a different edition; every record is filtered by `source`.
* **It's an unofficial mirror**, so our `license` stays `proprietary`, and the book has to be checked against an official description (as was done for BGG in §7.2).
* **A reference ≠ text**: in GoS some creatures appear as a tag in the text rather than a `statblock` node, so "how many monsters the book has" can't be seen from references — only from `bestiary-<id>.json`.
* **A reference ≠ the number of records**: the ToA file has 7 item references, while `items.json` has 26 records with `source: ToA` (the rest are variants and tables). So the counters here come from the corpora, not from the book.
* **`items.json` expands variants**: `Wand of the War Mage` in the mirror is three records (`+1`, `+2`, `+3`), while our DDB corpus has one "+1, +2, or +3". Because of this a naive diff shows "260 DMG items missing", though it's the same entry in a different form.
* **Parentheses in names aren't noise**: `Goblin (Dankwood)` and `Goblin` are different species from different books; comparing with the parentheses stripped gives false matches.
* **`_copy` is a reference, not text.** "Ammit" in Plane Shift: Amonkhet isn't a stat block but `{"_copy": {"name": "Giant Crocodile", "source": "MM"}}` with a word replacement; likewise 566 references to the Monster Manual, 14 to Volo's, a few each to CoS, PaBTSO, BAM, VRGR, MPMM, SKT, LLK. Without the base files only 3 of Amonkhet's 24 stat blocks were left. So `content/raw/_index/bestiary/` holds `bestiary-mm/vgm/mtf/mpmm/vrgr/skt/llk.json` (fetched by `fetch_5etools.py`), and `mirror5e.resolve_copy` resolves the chain and applies `_mod` (`replaceTxt` with `flags: i`, `appendArr`, `replaceArr`, `removeArr`).
* **Case in names is unstable**: in the Monster Manual the creature is called `Kuo-Toa`, but references use `kuo-toa`; so the `_copy` index is built with `casefold` names.
* **Two tag syntaxes**: `{@item …}` and `{#itemEntry Grenade|DMG}`; a tag can sit inside another tag (`{@item X|CoA|… {@note …}}`), so `inline()` makes up to four passes until the string stops changing.
* **The third part of a tag isn't always the display text**: in `{@item name|source|display}` it is, but in `{@adventure Chain Lightning|IDRotF|17|Chain Lightning}` it's the fourth; in `{@quickref Cover||3||three-quarters cover}` — the last one. Without this the text got "See 21 for different kinds of magen".
* **`hp.special` instead of `hp.average`**: AWM keeps hit points as a string (`{"special": "58"}`), ToA with a note ("127 (17d8 + 51) reduced to 107…"), and Meeseeks (RMBRE) as "—(immune to damage)", i.e. no number at all. The first number is taken, and the no-number case is written to `notes`, which the test skips.
* **A subclass appears twice in the mirror**: the same feature exists with `classSource: PHB` (the 2014 edition) and with `classSource: XPHB` (2024, different feature text). We take only 2014 — otherwise level-3 features get into the corpus instead of level-1 ones.
* **A table inside a list item**: in Sword of Zariel four tables sit inside one `list-hang` item; if the item is squashed into a string, the tables merge into one line with `|`.
* **The 50 "items" of PS-Ixalan are art objects** from treasure tables (`type: $A`, no description). They're recorded as `item_type: art object` with a price, but the sheet doesn't need them — it's treasure, not gear.


## 8. Pipeline status

Filled in from the actual contents of `content/`. "Pages" — book pages on disk, "Compendium" — records in `content/compendium/<book>/` (what the character sheet is built from), "Best." — stat blocks in `content/bestiary/<book>/`. Monsters live in a separate corpus: together that's 7423 records, but the sheet reads only the compendium. Both corpora are validated against a JSON Schema. Translation and proofreading haven't started yet (see §13).

All **52 books** (33 sourcebooks + 15 adventures from the library + the free Rick and Morty + BGG, EEPC and SotDQ from PDF) are fully downloaded: **678 pages from DDB + 225 pages from PDF**, **5558 records (3290 compendium + 2268 bestiary)**, 0 validation errors. The table below covers exactly these 52 books; separately the corpus holds **41 folders from the mirror** (1714 records, §7.4). Every record is in the canonical format of its category (see [format.md](format.md)): the same fields, the same `data` keys in the same order, the same text skeleton.

**Separately — the 41 folders parsed from the mirror** (§7.4): 1714 records, 1337 of them stat blocks. They aren't in the table below (it's about the 52 library books) and are added to the overall numbers. On top of that, the mirror added **116 subclasses** and **151 optional features** to the library books (`--subclasses`, `--optionalfeatures`). In total — **7423 records** in two corpora.

| Book | Pages | Compendium | Best. | Items | Spells | Rules | Species | Feats | Backgr. | Classes / subcl. / opt. |
|---|---|---|---|---|---|---|---|---|---|---|
| PHB | 39 | 802 | 31 | 215 | 361 | 19 | 18 | 42 | 13 | 12 / 40 / 82 |
| DMG | 24 | 301 | 2 | 274 | — | 25 | — | — | — | 2 subcl. |
| MM | 30 | 30 | 428 | — | — | 30 | — | — | — | — |
| Basic Rules | 46 | 769 | 316 | 420 | 304 | 23 | 16 | — | 6 | — |
| Sage Advice | 1 | 13 | — | — | — | 13 | — | — | — | — |
| XGtE | 14 | 224 | — | 48 | 95 | 13 | — | 15 | — | 31 subcl. / 22 |
| TCoE | 22 | 182 | 17 | 47 | 21 | 10 | — | 15 | — | 12 + 30 subcl. / 47 |
| SCAG | 8 | 26 | — | — | — | 8 | — | — | 12 | 6 subcl. |
| FToD | 12 | 37 | 73 | 13 | 7 | 12 | 3 | — | — | 2 subcl. |
| EGtW | 24 | 101 | 29 | 48 | 15 | 24 | 9 | — | 2 | 3 subcl. |
| AI | 16 | 30 | 21 | 7 | 7 | 15 | 1 | — | — | — |
| VGtM | 8 | 21 | 123 | — | — | 8 | 13 | — | — | — |
| MToF | 9 | 15 | 139 | — | — | 9 | 6 | — | — | — |
| MotM | 10 | 42 | 260 | — | — | 9 | 33 | — | — | — |
| GGR | 20 | 36 | 78 | — | — | 20 | 6 | — | 10 | — |
| ERLW | 16 | 51 | 36 | 25 | 1 | 16 | 8 | — | 1 | — |
| MOoT | 9 | 28 | 49 | 13 | — | 9 | 5 | — | 1 | — |
| VRGtR | 33 | 41 | 36 | 1 | — | 33 | 3 | — | 2 | 2 subcl. |
| SCC | 20 | 28 | 45 | — | — | 19 | 1 | 3 | 5 | — |
| SAiS | 22 | 31 | 73 | 1 | — | 22 | 6 | — | 2 | — |
| BMT | 23 | 31 | 29 | 6 | — | 23 | — | — | 2 | — |
| WBtW | 17 | 41 | 43 | 21 | — | 16 | 2 | — | 2 | — |
| Tortle | 1 | 2 | 5 | — | — | 1 | 1 | — | — | — |
| Grung | 1 | 2 | — | — | — | 1 | 1 | — | — | — |
| Wayfinder | 12 | 35 | 1 | 19 | — | 12 | 3 | — | 1 | — |
| Domains of Delight | 1 | 1 | 1 | — | — | 1 | — | — | — | — |
| PotA | 14 | 57 | 42 | — | 43 | 13 | 1 | — | — | — |
| SKT | 19 | 35 | 8 | 17 | — | 18 | — | — | — | — |
| ToD | 24 | 35 | 22 | 11 | — | 24 | — | — | — | — |
| WDH | 15 | 26 | 31 | 12 | — | 14 | — | — | — | — |
| WDMM | 29 | 29 | 12 | — | — | 29 | — | — | — | — |
| CM | 21 | 21 | 27 | — | — | 21 | — | — | — | — |
| TftYP | 18 | 32 | 39 | 15 | — | 17 | — | — | — | — |
| LLoK | 12 | 23 | 38 | 9 | 3 | 11 | — | — | — | — |
| CotN | 16 | 30 | 44 | 15 | — | 15 | — | — | — | — |
| LMoP | 8 | 8 | 27 | — | — | 8 | — | — | — | — |
| Frozen Sick | 1 | 1 | — | — | — | 1 | — | — | — | — |
| Lightning Keep | 1 | 1 | — | — | — | 1 | — | — | — | — |
| Prisoner 13 | 1 | 1 | 1 | — | — | 1 | — | — | — | — |
| Rrakkma | 5 | 5 | 9 | — | — | 5 | — | — | — | — |
| Rick and Morty | 6 | 6 | — | — | — | 6 | — | — | — | — |
| Unearthed Arcana | 26 | 26 | — | — | — | 26 | — | — | — | — |
| Misplaced Monsters | 1 | 1 | 6 | — | — | 1 | — | — | — | — |
| Monstrous Comp. 1 | 1 | 1 | 10 | — | — | 1 | — | — | — | — |
| Monstrous Comp. 2 | 1 | 1 | 11 | — | — | 1 | — | — | — | — |
| Monstrous Comp. 4 | 1 | 1 | 20 | — | — | 1 | — | — | — | — |
| Fiendish Folio 1 | 1 | 1 | 18 | — | — | 1 | — | — | — | — |
| Vecna Dossier | 1 | 1 | 1 | — | — | 1 | — | — | — | — |
| Humblewood | 18 | 56 | 45 | 7 | — | 17 | 22 | 7 | 3 | — |
| **BGG (PDF, OCR)** | 200 | 43 | — | 27 | — | 5 | — | 8 | 2 | — |
| **EEPC (PDF, text)** | 25 | 53 | — | — | 43 | 2 | 8 | — | — | — |
| **SotDQ (PDF, ru)** | 205 | 27 | 22 | 9 | — | 5 | 1 | 9 | 2 | — |
| **Total (52 books)** | **1108** | **3441** | **2268** | **1280** | **900** | **636** | **167** | **99** | **66** | **24 classes / 118 subcl. / 151 opt.** |

SotDQ was added from the PDF of a Russian fan translation (205 pp., a real text layer, no OCR): 27 compendium records + 22 stat blocks. The record text is as in the book, in Russian; the structured `data` values were translated into the corpus's canonical vocabulary. The adventure chapters (2–7) weren't parsed: the sheet doesn't need them, and the text stays in `content/raw/sotdq/pages/`.

What's behind the numbers:

* **Monsters are a separate corpus** `content/bestiary/`, not part of the compendium: the character sheet doesn't read them, and 2268 stat blocks would bloat what the sheet is built from. The record format is the same (shared schema and contract), so the reader is shared too; the boundary is held by `corpora` in `contract/compendium-format.json` and a test that fails if a monster comes back into the compendium.
* **There are 2268 monsters, not 1596, and that's not "new books" but parsing of the same pages.** In the Basic Rules, Mordenkainen's Tome, Volo's, Monstrous Compendium and supplements the stat block name is a plain paragraph (`Aboleth`), not a markdown heading; the old recognizer only saw headings, so the 24 Basic Rules pages merged into 24 "Monster Stat Blocks" records, each with dozens of creatures. Now a stat block starts where a short name line comes before a creature type line. Also fixed along the way: the vertical ability table (in some books `STR` and `16 (+3)` are separate paragraphs), `Skills` + `History` without a space, a creature type without capitalization (`Small fey`) and XP with a space inside the number (`(20 ,000 XP)`).
* **Monsters and lore are no longer mixed.** On MToF/VGtM pages stat blocks take ~3/4 of the text, the rest is lore about a group of creatures. Previously the page was treated as "entities only" and the lore disappeared; now the page record keeps the text that didn't become an entity (without duplicating stat blocks).
* **Items are two different layers in one category.** Magic items (the "Wondrous item, rare" line) and ordinary gear from the PHB tables (weapons, armor, adventuring gear, tools). In a record they're distinguished by `data.item_type` (`wondrous item`, `weapon`, `armor`, `gear`, `tool`, `mount`, `trade_good`, …) and `data.magical`.
* **Classes — 24 page-level records** (there were 27: the "Classes" records are section pages, they moved to `rule`). **Subclasses were filled in from the mirror** (§7.4): 118 records across 52 books, each an introduction plus features by level ("## Dread Ambusher · *3rd-level Ranger feature*"). **Optional features also come from the mirror**: 151 records in PHB, XGE and TCE (§7.4), the `optionalfeature` category with the fields `feature_type` (group) and `prerequisite` (level, pact, required spell). The features of the classes themselves (not subclasses) aren't parsed as separate records yet — they were and still are text inside the class records.
* **Sage Advice** isn't 12 feats but 13 `rule` records: each is a question and answer about a feat (the text starts with a question heading), so the "feats" category was wrong.
* **Unearthed Arcana** — 26 pages of solid text (playtest articles), so all records are in the `rule` category.
* **Humblewood** is third-party; in the registry it's marked `license: third_party`, and enabling it in the app needs a separate flag.

## 9. What's in the D&D Beyond library but missing from §1–5

| Item | Type | What it is | Decision |
|---|---|---|---|
| **Sage Advice Compendium (2014)** | rules | official clarifications and errata | **included** (13 records): not content, but a source of rulings for the engine |
| **Domains of Delight: A Feywild Accessory** | accessory (free) | Feywild domains, monsters | **included** |
| **Humblewood Campaign Setting** | **third-party** (Hit Point Press) | a setting with its own races | **included** with `license: third_party`; enabled by a separate flag |
| **Misplaced Monsters: Volume One** | free | monsters | **included** (6 monsters) |
| **Monstrous Compendium Vol. 1 / 2 / 4** | free | monsters (Spelljammer, Dragonlance, Eldraine) | **included** (39 monsters) |
| **Mordenkainen's Fiendish Folio Vol. 1** | free | monsters | **included** (16) |
| **The Vecna Dossier** | free | Vecna's stat block | **included** |
| **Unearthed Arcana** | playtest | 26 articles | **included** as `rule` |
| **The Tortle Package / One Grung Above** | accessory | the Tortle and Grung races | **included** |
| **Wayfinder's Guide to Eberron** | sourcebook | the ERLW predecessor | **included** (outdated, 3 species) |
| **Critical Role: Call of the Netherdeep** | adventure | items | **included** |
| **Frozen Sick, Lightning Keep, Prisoner 13, Rrakkma, Lost Mine of Phandelver** | free adventures | small items, the starter set | **included** |
| **Dungeons & Dragons vs. Rick and Morty** | free box | simplified rules (6 pages) | **included** as `rule` |

### 9.1 Free content that can no longer be claimed (checked 25.11.2026)

The D&D Beyond catalog shows these items as free, and they even appear to be "in the library" under the `ownership=all` filter. In reality the account has no content for them: each opens either a claim page saying **"This promotion is no longer available"** or a marketplace page with a price. Nothing to download.

| Item | Where it leads | What it was |
|---|---|---|
| Baldur's Gate Gazetteer | `/claim/source/baldurs-gate-gazetteer` — promo ended | a gazetteer of Baldur's Gate (items, backgrounds) |
| Descent into the Lost Caverns of Tsojcanth | `/claim/source/descent-into-tsojcanth` — promo ended | a promo adventure |
| Giants of the Star Forge | `/claim/source/giants-of-the-star-forge` — "no longer available" | a promo adventure for Glory of the Giants |
| Monstrous Compendium Vol. 3: Minecraft Creatures | `/claim/source/minecraft-creatures-monstrous-compendium` — "no longer available" | Minecraft monsters |
| The Radiant Citadel | `/claim/source/the-radiant-citadel` — promo ended | a prologue to Journeys through the Radiant Citadel |
| Spelljammer Academy | stays at `/sources/dnd/sja`, but the book pages serve a placeholder | an introductory Spelljammer adventure |
| Intro to Stormwreck Isle | marketplace, "Quickplay Adventure Pack" | a starter set |
| Legendary Magic Items | marketplace (Honor Among Thieves) | a selection of legendary items |
| Thieves' Gallery | marketplace | an NPC gallery |

Practical conclusion: **everything free that's available to this account at all is already in the corpus**. If these items are ever needed, they can be bought or you can wait for a new promo wave, but they can't be fetched with code.

## 10. Gaps and how to close them

| Gap | What we lose | Impact | Action |
|---|---|---|---|
| **Glory of the Giants** | ~~Path of the Giant, 8 feats, 2 backgrounds, 27 items~~ | **closed** ✅ | taken from the bought PDF via OCR (§7.1), 43 records in the corpus |
| **Dragonlance: SotDQ** | ~~Kender, Lunar Sorcery, 9 feats, 2 backgrounds~~ | **closed** 📄 | taken from the PDF of the Russian translation (§8), 49 records in the corpus; translating into Ukrainian will need the English original |
| **Planescape: AitM** | ~~7 feats, 2 backgrounds, 2 spells, 5 items~~ | **closed by source** ✅ | `SatO` + `MPP` downloaded and parsed (§7.4): 7 feats, 2 backgrounds, 2 spells, 5 items. There will be no general chapters about Sigil — they're in neither SatO nor MPP |
| ~~**EEPC**~~ | ~~Aarakocra, Genasi, Goliath, Svirfneblin~~ | **zero** ✅ | closed: the free PDF was taken (§7.3). There really is no new content — it was all already in MotM and PotA/XGtE |
| **Curse of Strahd** | ~~Haunted One~~ | **closed by source** ✅ | `CoS` parsed — 14 items and 97 stat blocks. One caveat remains: the Haunted One text itself in the mirror belongs to `RHW` (the 2024 line), i.e. it's a reprint, and the 2014 version needs checking against the book |
| **Tomb of Annihilation** | ~~Anthropologist, Archaeologist~~ | **closed by source** ✅ | `ToA` parsed from the mirror: 2 backgrounds, 27 items, 89 stat blocks. No PDF needed — its text layer is broken by kerning |
| **Ghosts of Saltmarsh** | ~~4 backgrounds, ship rules~~ | **closed by source** ✅ | `GoS` parsed: 4 backgrounds, 6 items, 57 stat blocks. The 9 subsections of ship rules weren't added: they're rules, not sheet records |
| **BG:DiA** | ~~14 backgrounds, 13 items, infernal war machines~~ | **closed by source** ✅ | `BGDIA` parsed: 14 backgrounds, 13 items, 53 stat blocks — no need to buy it. Infernal war machines (4 + 9 upgrades) are rules, not added |
| **Plane Shift ×6** | ~~races and subclasses~~ | **closed by source** ✅ | all six parsed (`ps-zendikar`…`ps-dominaria`): 45 species (species + subraces), 5 backgrounds, 3 feats, 6 subclasses, 168 stat blocks |
| **Locathah Rising** | ~~Locathah~~ | **closed by source** ✅ | `LR` parsed: the Locathah species + 6 stat blocks |
| **Minsc and Boo's Journal of Villainy** | ~~FR subclasses~~ | **low** ✅ | checked on the mirror: the book is there (`MaBJoV`), but gives **only 56 stat blocks** — no subclass, feat or species; the subclass item was a mistake |

**Summary:** there are no more source gaps — all 41 mirror folders are parsed (§7.4), subclasses were filled in for 8 books, optional features for 3, spells and species added. Outside the corpus there's only what's on neither DDB nor the mirror: AL modules (State of Hillsfar, Mulmaster Bonds, CoS: Optional Backgrounds), Runeterra, Blood Hunter and third-party content (§11.3).

Optional features were the only gap not about sources but about the model: the mirror has 233 of them, but the contract had no `optionalfeature` category, so they existed only as text in the class records. Now the category exists, 151 records were taken, and 82 were deliberately left out of the corpus — they're the 2024 line (`XPHB`, `WoW`, `AU`, `EFA`), while the corpus is defined as 2014.

## 11. The full diff of the D&D Beyond catalog (2014)

The DDB catalog for `ruleset=5e`: **100 items**. Actually in the library — **48 books**; the filter shows 10 more items as "owned", but 9 of them are expired promos without content (§9.1), so they aren't in the corpus. Below are **all 42 books not bought**, with what each gives the sheet. The ✅ marker means the book has already been taken from the 5e.tools mirror and parsed into the corpus (§7.4), even if it wasn't bought on DDB.

**How it was checked.** Not from references, but from D&D Beyond itself:

* the table of contents of each book (the `compendium-toc-full` block) — available even for books not bought, so the chapter names are visible;
* the DDB index pages `Backgrounds`, `Feats`, `Species` list every record **together with its source book** — the exact names and counts come from there.

Monsters and maps aren't counted: the sheet doesn't need them (except wild shapes, and we already have enough bestiaries).

### 11.1 Official books with playable content outside the library

All books in this table (except DoSI) are already available and **parsed**: 41 folders were taken from the 5e.tools mirror (§7.4), SotDQ from PDF (§8). The counts in the table were computed from the mirror's data (`items.json`, `bestiary/`), not taken from references, so they're sometimes larger than "7 items from App. C": the mirror's corpus also includes variants and items from the adventure text.

| Book | Species | Subclasses | Feats | Backgrounds | Items / other | Status |
|---|---|---|---|---|---|---|
| ~~**Bigby Presents: Glory of the Giants** (gotg)~~ | — | Path of the Giant (barbarian) | **8**: Ember of the Fire Giant, Fury of the Frost Giant, Guile of the Cloud Giant, Keenness of the Stone Giant, Rune Shaper, Soul of the Storm Giant, Strike of the Giants, Vigor of the Hill Giant | **2**: Giant Foundling, Rune Carver | 27 items (Ch. 5: Giant Treasures) | **closed** ✅ — from PDF, §7.1 |
| **Dragonlance: Shadow of the Dragon Queen** (sotdq) | **Kender** | **Lunar Sorcery** (sorcerer) | **9**: Adept of the White/Red/Black Robes, Initiate of High Sorcery, Knight of the Crown/Rose/Sword, Squire of Solamnia, Divinely Favored | **2**: Knight of Solamnia, Mage of High Sorcery | 9 items (App. A: Gear and Magic Items) | **closed** 📄 — from the PDF of the Russian translation, 49 records (§8) |
| **Planescape: Adventures in the Multiverse** (paitm) | — | — | **7**: Agent of Order, Baleful Scion, Cohort of Chaos, Outlands Envoy, Planar Wanderer, Righteous Heritor, Scion of the Outer Planes | **2**: Gate Warden, Planar Philosopher | 2 spells (warp sense, gate seal), 5 items; + 54 creatures in *Morte's Planar Parade* | ✅ parsed (`SatO` + `MPP`) |
| **Plane Shift ×6** (ps-zendikar…ps-dominaria) | **20** species (+24 subraces): Aven, Khenra, Naga, Minotaur (Amonkhet), Aetherborn, Vedalken, Kor, Merfolk, Vampire, Siren, Goblin (Zendikar), Orc (Ixalan)… | — | **3**: Quicksmithing, Servo Crafting, Vampiric Exultation | **5**: Initiate (+Dissenter), Vizier (+Dissenter), Inquisitor | 50 items (Ixalan treasures), 12 subclasses (10 from Amonkhet, 2 from Kaladesh) | ✅ parsed |
| **Baldur's Gate: Descent into Avernus** (bgdia) | — | — | — | **14**: 13 PHB variants ("Baldur's Gate Acolyte" … "Baldur's Gate Urchin") + Faceless | 13 items, 7 charms, 4 infernal war machines + 9 upgrades, 53 stat blocks | ✅ parsed |
| **Ghosts of Saltmarsh** (gos) | — | — | — | **4**: Fisher, Marine, Shipwright, Smuggler | 6 items (App. B), 9 subsections of ship rules (App. A), 57 stat blocks (App. C) | ✅ parsed |
| **Locathah Rising** (lr) | **Locathah** | — | — | — | 6 stat blocks | ✅ parsed |
| **Tomb of Annihilation** (toa) | — | — | — | **2**: Anthropologist, Archaeologist | 26 items, 89 stat blocks | ✅ parsed from the mirror (the PDF is broken, §10) |
| **Curse of Strahd** (cos) | — | — | — | **Haunted One** (+ Dark Gifts) — in the mirror the record belongs to `RHW` (2024), so the text exists only as a reprint | 14 items, 97 stat blocks | ✅ parsed |
| **Infernal Machine Rebuild** (imr) | — | — | — | — | 11 items and poisons, 26 stat blocks | ✅ parsed |
| **Icewind Dale: Rime of the Frostmaiden** (idrotf) | — | — | — | — | 31 items, 2 spells, 83 stat blocks | ✅ parsed |
| **Out of the Abyss** (oota) | — | — | — | — | 16 items, 103 stat blocks | ✅ parsed |
| **Quests from the Infinite Staircase** (qftis) | — | — | — | — | App. A: Magic Items and Technology — 10 items, 49 stat blocks | ✅ parsed |
| **Phandelver and Below: The Shattered Obelisk** (pbtso) | — | — | — | — | 23 items, 56 stat blocks | ✅ parsed |
| **Vecna: Eve of Ruin** (veor) | — | — | — | — | 3 items, 69 stat blocks | ✅ parsed |
| **Keys from the Golden Vault** (kftgv) | — | — | — | — | 8 items, 57 stat blocks | ✅ parsed |
| **Journeys through the Radiant Citadel** (jttrc) | — | — | — | — | 5 items, 71 stat blocks | ✅ parsed |
| **Chains of Asmodeus** (coa) | — | — | — | — | 24 items, 61 stat blocks | ✅ parsed |
| **Dragons of Stormwreck Isle** (dosi) | — | — | — | — | — | not taken: stat blocks only, not a single item |

**Spells:** until recently this said that none of the official books not bought adds spells. **That turned out to be wrong:** *Sigil and the Outlands* (part of PS:AitM) adds two — `warp sense` (2nd level, divination) and `gate seal` (4th, abjuration); they weren't in the corpus. After parsing the mirror three more were found: two in *Rime of the Frostmaiden* (`IDRotF`) and one in `AitFR-AVT`. All five are now in the corpus — `content/compendium/sato/spell.jsonl`, `idrotf/spell.jsonl`, `aitfr-avt/spell.jsonl`. More new spells exist only in third-party books (§11.3) and in the 2024+ line.

**Species:** outside the library there are three sources — **Plane Shift ×6** (20 species: Aven, Khenra, Naga, Minotaur (Amonkhet), Aetherborn, Vedalken, Kor, Merfolk, Vampire, Siren, Goblin (Zendikar), Orc (Ixalan)…), **Locathah** (Locathah Rising) and **Goblin (Dankwood)** (*Adventure with Muk*). Kender is already in the corpus from SotDQ. All other races and subraces of the 2014 line (including MotM's 33 records) are in the corpus.

### 11.2 ❌ Official books without playable content

Only monsters, maps, sidekicks or adventure text — nothing for the sheet:

| Book | What's in it |
|---|---|
| Dragon of Icespire Peak (doip) | an adventure + sidekicks |
| Storm Lord's Wrath (slw), Sleeping Dragon's Wake (sdw), Divine Contention (dc) | an adventure trilogy + sidekicks |
| Hunt for the Thessalhydra (hftt) | a promo adventure (Stranger Things) |
| Adventure Atlas: The Mortuary (aatm) | maps and monsters |
| Vecna: Nest of the Eldritch Eye (vnee) | a promo adventure |
| Heroes' Feast: Saving the Children's Menu (hfscm) | a promo adventure |
| Tales from the Shadows (tfts) | an adventure anthology; no playable options visible |

### 11.3 ❌ Third-party books with playable content

These books aren't WotC, so in the app they can only be a separate flag (like Humblewood). But their content is real — and the DDB index shows exactly how much:

| Book | Species | What else |
|---|---|---|
| **The Illrigger Revised** (tir) | — | **a whole Illrigger class** with subclasses (MCDM) |
| **Grim Hollow: Player Pack** (ghpp) | 2 | subclasses, feats, spells, items |
| **Tal'Dorei Campaign Setting Reborn** (tcsr) | — | Ch. 4: Character Options — subclasses, feats, spells |
| **Book of Ebon Tides** (boet) | **10** | items, spells, "Umbral People and Heroes" |
| **Obojima: Tales from the Tall Grass** (ottg) | 3 | Player Options, items, spells |
| **Heliana's Guide to Monster Hunting: Part 1** (hgtmh1) | 5 | Species, Classes and Feats, items, spells |
| **Heliana's Guide to Monster Hunting: Part 2** (hgtmh2) | 5 | Species, Classes, items, spells |
| **The Griffon's Saddlebag: Book Two** (gsb2) | 2 | Part 1 Magic Items, Part 2 Character Options |
| **Dungeons of Drakkenheim** (dodr) | — | App. F: Character Backgrounds, App. D: spells and items |
| **Ruins of Symbaroum: Setting Handbook** (ssh) | "Folks" | new rules, backgrounds |
| **The Lord of the Rings Roleplaying** (lotrr) | 6 | Ch. 3: Adventurers (classes), a separate system |
| **Humblewood Tales** (hwt) | — | items (App. C) and spells (App. D); no races |

### 11.4 ❌ Third-party books without playable content

Bestiaries and encounter collections: Flee, Mortals! (fm), Tome of Beasts 1 (tob1), Where Evil Lives (wel), Lairs of Etharis (loe).

### 11.5 What DDB doesn't have at all

- **Elemental Evil Player's Companion** — not sold on DDB as a separate book (the races are in MotM, the spells in PotA), but the PDF itself is free and already in the corpus (§7.3).
- **Plane Shift ×6** — free PDFs from the WotC site; **all six are parsed** from the mirror (§7.4) — `ps-zendikar`…`ps-dominaria`.
- **Locathah Rising** — on the mirror (`LR`), **parsed**; on DDB only as a separate adventure (and it's not in the library).
- **Adventure with Muk** (`AWM`) — **parsed**; gives Goblin (Dankwood) and 11 stat blocks.
- **Minsc and Boo's Journal of Villainy** — checked on 26.11.2026 and parsed: it **is** on the mirror (`MaBJoV`), but it's 56 stat blocks; there's **no subclass, feat or species** in it, so the former "FR subclasses" was a mistake.
- **State of Hillsfar**, **Mulmaster Bonds and Backgrounds**, **Curse of Strahd: Optional Backgrounds** — AL modules; checked twice (before and after parsing): **they're not on the mirror**. The `AL` book is just the `Faction Guide` (2 chapters, not a single reference to backgrounds), and `backgrounds.json` has no record with `source: AL`. They can only be taken from DMs Guild.
- **Legends of Runeterra: Dark Tides of Bilgewater** — a PDF; the book isn't on the mirror.
- **Blood Hunter** — DMs Guild (not WotC), not on the mirror.
- **Haunted One** — the DDB index attributes it to "Ravenloft: The Horrors Within" (2026, the 2024 line), but `CoS` itself on the mirror contains it in the 2014 version (§11.1).

## 12. Sources

- The owned library: <https://www.dndbeyond.com/en/library?ownership=owned&ruleset=5e&type=sourcebooks> (checked 25.11.2026).
- The DDB catalog without the ownership filter — this is what shows the books not bought: `ownership=all&ruleset=5e`.
- DDB indexes tied to the source book: `/backgrounds`, `/feats`, `/species` — every row contains the book name, so the counts in §11 come from DDB data, not references.
- Book tables of contents (`compendium-toc-full`) can be read even for books not bought — that's where the chapter names come from ("Ch. 1: Character Creation", "App. A: Gear and Magic Items").
- One builder's book coverage catalog: <https://play5e.net/sourcebooks> — a "book → content categories" cross-check.
- The list of releases: <https://en.wikipedia.org/wiki/List_of_Dungeons_%26_Dragons_rulebooks>.
- Counts and contents were checked against the books' tables of contents; differences from catalogs come from options reprinted in later books (SCAG → XGtE/TCoE, MOoT → TCoE, etc.).
- **The 5e.tools mirror** (unofficial): indexes `https://5e.tools/data/books.json` and `adventures.json`, books — `data/book/book-<id>.json`, adventures — `data/adventure/adventure-<id>.json`. Reference corpora the counts are computed from: `data/{items,items-base,feats,backgrounds,races,optionalfeatures,magicvariants,rewards}.json`, `data/spells/spells-<src>.json`, `data/class/class-<name>.json`, `data/bestiary/bestiary-<src>.json` (index — `data/bestiary/index.json`). Access requirements and pitfalls — §7.4.
- Scripts for working with the mirror (everything is reproducible):
  * `fetch_5etools.py` — one URL pair → a file (plus `_index/bestiary/` for base stat blocks);
  * `fetch_5etools_batch.py` — the 41 book folders that still give the sheet something; `fetch_5etools_bestiary.py` — stat blocks for books already taken;
  * `mirror5e.py` — **parsing the mirror**: the `entries` tree → book text, `_copy` → the full record, converters for `monster`/`species`/`background`/`feat`/`optionalfeature`/`subclass`/`spell`/`item`; `--all`, `--folder <folder>`, `--subclasses`, `--optionalfeatures`;
  * `sync_sources.py` — the `content/sources.yml` registry from the mirror's catalog and the parsed records (`--write`, `--force`);
  * `survey_5etools.py` — a cross-section of the reference corpora; `survey_5etools_book.py` — what one book gives; `diff_5etools.py` — a "mirror ↔ corpus" diff by name.

## 13. Next

| Step | Status | What's left |
|---|---|---|
| Collect all library books | **done** | 48/48 library books + 1 free outside it = 49 books, 678 pages; plus BGG from PDF (200 scanned pages → OCR), EEPC from PDF (25 pages of text) and SotDQ from PDF (205 pages) = **52 books** |
| Download books from the 5e.tools mirror | **done** | **41 folders** (§7.4): 8 first-wave books + 33 second-wave files. What's left on the mirror gives the sheet nothing: `AAG` ships, `HAT-LMI`/`EET` without a book file, bestiary adventures |
| Reconcile the corpus with the mirror | **done** | `diff_5etools.py`: 5285 mirror records against 5542 corpus names; of 233 optional features 207 matched, and the 26 "missing" are names that exist only in the 2024 line (`WoW`, `AU`, `EFA`, `XPHB`) |
| Parse the mirror's books | **done** | 41 folders → 1714 records: 27 backgrounds, 10 feats, 47 species, 6 subclasses, 5 spells, 282 items, 1337 stat blocks. Plus 116 subclasses and 151 optional features for 8+3 corpus books (§7.4) |
| Parse items | **done** | 1280 records: magic items from all books (including 27 from BGG) + ordinary gear from the tables |
| Parse backgrounds | **done** | 93 from PHB, SCAG, GGR, SCC, SAiS, BMT, WBtW, VRGtR, EGtW, ERLW, AI, ToD, Wayfinder, Humblewood + 27 from the mirror (BGDIA, GoS, ToA, Planescape, Plane Shift) |
| Parse species | **done** | 214 (species + subraces): 167 from the corpus, including MotM (33), Humblewood (22) and EEPC (8), plus 47 from the mirror (Plane Shift, Locathah, Dankwood) |
| Parse monsters | **done** | 3605 stat blocks: 2268 from DDB/PDF (verified that no paragraph of a book was lost) + 1337 from the mirror |
| One format for all records of a category | **done** | `contract/compendium-format.json` + `python -m scripts.normalize --check`, test `backend/tests/contract/test_compendium_format.py` |
| Classes → subclasses → optional features | **done** | 124 subclasses with features by level and 151 optional features with prerequisites (§7.4). What's left: the features of the classes themselves (not subclasses) as separate records |
| Ukrainian translation | **started for the sheet** | the character screen translates content from `frontend/src/features/character/uk.ts` (features, spells, backgrounds, items, weapon properties; the English name in parentheses). The rest of the corpus isn't translated yet: with no dictionary entry the original is shown. A full pipeline for 7423 records is ahead |
| Term glossary | skeleton | the official WotC translation where it exists; our own for the rest; the original in a tooltip |
| Buy more books with options | **not needed** | all books with playable content are either in the corpus or parsed from the mirror (§10). The only things outside are third-party content (§11.3) and AL modules |
