# The "book → compendium" pipeline

Two different cases that shouldn't be confused:

| Book | PDF state | What we do |
|---|---|---|
| **Bigby Presents: Glory of the Giants** (`gotg`) | a scan, 200 pages, **no text layer** | OCR + our own layout analysis: `pdf2md.py`, `xycut.py`, `despace.py`, `polish.py`, `slice.py`, `build_gotg.py` |
| **Elemental Evil Player's Companion** (`eepc`) | 25 pages, **a real text layer** | parse the text directly: `build_eepc.py` |

## EEPC: when the PDF already has text

`python scripts/pdf/build_eepc.py` reads `content/raw/eepc/EE_PlayersCompanion.pdf` and assembles records without OCR. The difficulty here isn't recognition but structure:

* **the text layer has no headings** — no capitals, no style markers. Spell names are taken from the book's own spell list (the "Spell Lists" section): a line matching a name from the list and followed by "Nth-level school" is treated as the start of a description;
* **the stat block wraps onto the next line** ("Casting Time: 1 reaction, which you take when you take … acid, cold, fire, lightning, or thunder damage"), so field values are joined until all four are collected;
* **the last spell (Whirlwind) runs into the back cover** with an ad for the Neverwinter MMORPG — the description body is cut at the marketing lines;
* soft hyphens `U+00AD` inside words are removed, otherwise "Abi-Dalzim's" can't be found.

Verification: `validate_eepc.py` — structural invariants (all four stat fields, a non-empty body, no foreign text, the expected `ability_increases`/`size`/`speed` for each species) plus a comparison with the same spells from `xgte`/`pota`. Differences there are expected — they're errata fixes between reprints, not parsing errors (`logs/eepc_validation.txt`).

## BGG: a scan without a text layer

For books that aren't on D&D Beyond as HTML: take a printed copy (a PDF of scans) and extract the text with OCR. This is how **Bigby Presents: Glory of the Giants** was added (`content/raw/gotg-pdf`, 200 pages, `source_id: gotg`).

The constraint everything follows from: such a PDF **has no text layer** — every page is a single 300 dpi image. So the quality of the records depends on OCR, and every record can be checked against the page image.

## The record format is a contract, not "whatever came out"

Both builders (and the HTML pipeline too) bring the book to
`contract/compendium-format.json` after assembly: the same fields, the same set and order
of `data` keys, the same `text_en` skeleton. Description — [`docs/format.md`](../../docs/format.md).

```powershell
python -m scripts.normalize --check --source eepc   # what diverges from the contract
python -m scripts.normalize --write                 # bring the whole corpus to canon
```

This matters especially for PDF books: scanned OCR and a text layer have different habits
(the line "8th-Level Necromancy" vs "8th-level necromancy", an "At Higher Levels" block
with and without a caption), and without a shared format the sheet couldn't read these
records the same way as records from D&D Beyond.

## Order of steps

| Step | Script | What it does | Cache |
|---|---|---|---|
| 1 | `pdf2md.py` | copies each page's embedded image without re-encoding, recognizes the text (RapidOCR/PP-OCR), assembles the page into markdown | `images/`, `ocr/`, `pages/` |
| 2 | `xycut.py` | reading order via recursive XY-cut: first cuts the page horizontally, then vertically, until it reaches a paragraph (used from step 1) | — |
| 3 | `book_index.py` | maps a PDF page to the printed page number and chapter (`CHAPTER 1 \| CHARACTER CREATION`), builds `index.json` | `index.json` |
| 4 | `despace.py` / `polish.py` | restores lost spaces using a dictionary from the existing corpus; joins broken words; fixes single-letter errors; removes illustrator credits | — |
| 5 | `slice.py` / `extract.py` | cuts the text into entities: `slice.py` — by a list of names (more reliable for items and feats), `extract.py` — by headings | — |
| 6 | `build_gotg.py` | assembles JSONL per the `contract/compendium-entry.schema.json` schema | `content/compendium/gotg/` |

## Verification (don't skip it)

One OCR is one opinion; so as not to mistake recognition errors for the book's text, everything is checked against a second source.

| Script | What it checks |
|---|---|
| `validate_ref.py` | every record against a second OCR of the same book (`logs/gotg_ref_text.pdf`, an Internet Archive scan with a text layer). It measures **coverage**: how much of our text is explained by the book, and whether a record was cut short. Report: `logs/gotg_validation.txt` |
| `compare_items.py` | the same, but per item, with the second OCR sliced by stat lines (`logs/gotg_ref_items.json`, `logs/gotg_items_diff.txt`) |
| `check_rules.py` | the Rune Spells table (13 "rune → spell" pairs) and the text of the Bonus Feats rule |
| `sweep_headings.py` | all book headings against the existing records — catches missed entities |

Outcome for this book: 37 of 41 records are fully explained by the book, 4 are cases where the second OCR is worse than ours (listed in `REVIEWED_OURS_PREFERRED` inside `validate_ref.py`), 2 authored records are verified by `check_rules.py`. Conflicting numbers are resolved by **the page image**, not by an OCR vote: that's how Elemental Cleaver turned out to be 60 ft, not 40.

Comparison must be done on normalized text (no spaces or punctuation): two OCRs break words differently ("max imum" vs "maximum"), and a naive word diff shows 0.5 where the texts are identical.

## How to reproduce

Run from the repository root:

```powershell
$root = (Get-Location).Path
$py = "$root\.venv\Scripts\python.exe"

# 1+2. pages -> markdown (can be rerun: finished steps are skipped)
& $py "$root\scripts\pdf\pdf2md.py" "C:\path\to\book.pdf" "$root\content\raw\gotg-pdf"

# 3. page map
& $py "$root\scripts\pdf\book_index.py" "$root\content\raw\gotg-pdf" "$root\content\raw\gotg-pdf\index.json"

# 5. slicing by names (the name list is a separate file, one per line)
& $py "$root\scripts\pdf\slice.py" "$root\content\raw\gotg-pdf" "$root\logs\gotg_items_names.txt" "$root\logs\gotg_items.json" 114-122

# 6. records + validation
& $py "$root\scripts\pdf\build_gotg.py"
& $py -c "import sys; sys.path.insert(0, r'$root\scripts'); from ingest import records; print(records.validate_source('gotg'))"
```

## Worth knowing

* **PDF page = printed page + 4.** Checked by `book_index.py`: it takes the number from the running footer and computes the offset (147 pages gave the same offset of 4).
* **Numbers in "d6" tables aren't recognized** — they're set in a decorative font in a light column. In the records the rows are numbered 1…6 in order, as in the book.
* **Two-column pages** sometimes merge (`to a max- Cloudy Escape … imum of 20.`). For entities that matter to the sheet, the text was proofread by hand (`build_gotg.py`, the constants `FEATS`, `BACKGROUNDS`, `SUBCLASS`), so these records don't depend on the quality of the automatic assembly.
* **Individual items** (`Ring of Amity`, `Thunderbuss`, `Lucent Destroyer`, `Mistral Mantle`) were transcribed by hand: the first is split across pages, the rest come from the page where the scan is recognized worst.
* **Scope limit:** chapters 2–4 (lore, organizations, enclaves) and 6 (bestiary) were **not** turned into records — the character sheet doesn't need them. Their OCR text is in `pages/` and available if it's ever needed.
