# content/ — the knowledge base (data)

Everything here is **data**, not code (see ADR 0003).

| File / folder | What it is | In git |
|---|---|---|
| `glossary.uk.yml` | Ukrainian terminology glossary | plain |
| `sources.yml` | **source registry**: 93 sources (52 library books + 41 mirror folders), queues, licenses, gaps | plain |
| `books_market.json` | book prices, covers and D&D Beyond links for the home page | plain |
| `translations/` | Ukrainian names and texts (see [docs/translation-rules.md](../docs/translation-rules.md)) | plain |
| `compendium/<source>/<category>.jsonl` | compendium records — what the character sheet is built from | **encrypted** (contain `text_en`) |
| `bestiary/<source>/monster.jsonl` | monster stat blocks: same record format, a separate corpus (the sheet doesn't read it) | **encrypted** (contain `text_en`) |
| `index/spell-lists.json` | derived index: class spell lists from the books' "Spell Lists" | **encrypted** (derived from texts) |
| `index/class-mechanics.json` | derived index: hit dice, proficiencies, slot tables, multiclass prerequisites, features by level | **encrypted** |
| `index/origin-mechanics.json` | derived index: ability bonuses, speed, darkvision, skills and languages of species and backgrounds | **encrypted** |
| `raw/<source>/*.html` | raw HTML of book pages | **no** (copyright) |
| `raw/_index/<source>.json` | page list of a book (result of discover) | **no** |
| `.session/cookies.json` | site session cookies | **no** (live credentials) |

Encryption uses git-crypt (`.gitattributes` in each of `compendium/`, `bestiary/`,
`index/`): the public repository holds only ciphertext, CI and the owner unlock it
(see [docs/deploy.md](../docs/deploy.md)). Without unlocking, these files are binary and
the compendium is empty.

Derived indexes (`index/`) are built by scripts:

```powershell
python -m scripts.ingest.spell_lists --write   # class spell lists
python -m scripts.ingest.mechanics --write     # class, species and background mechanics
```

The boundary between corpora is part of the `contract/compendium-format.json` contract
(the `corpora` block), not a convention in code: if a monster ends up in
`compendium/`, preflight and the tests fail.

Record schema: [`contract/compendium-entry.schema.json`](../contract/compendium-entry.schema.json).

## Pipeline

```
sources.yml ──> discover ──> fetch ──> parse ──┬──> compendium/<source>/*.jsonl
                 (BFS)      (HTML)  (markdown + fields)  │   (sheet categories)
                                                         └──> bestiary/<source>/monster.jsonl
                                                              │
                                                              └──> validate (jsonschema)
```

Run from the repository root (needs the session file):

```bash
python -m scripts.ingest.cli discover --source phb-2014
python -m scripts.ingest.cli fetch    --source phb-2014
python -m scripts.ingest.cli parse    --source phb-2014
python -m scripts.ingest.cli run      --source phb-2014 --delay 1.5
python -m scripts.ingest.cli all      --tiers 1,1.5,2
```

Every stage is idempotent and resumes where it stopped (`_checkpoint.json`).
On a CAPTCHA the pipeline stops with exit code 2 and keeps its progress.

## Legal

- `license: proprietary` — book texts; stored in git only encrypted, never published in plain text.
- `license: srd` — CC-BY, the only layer that may be shown publicly as is.
- Raw HTML and session cookies are never committed.
