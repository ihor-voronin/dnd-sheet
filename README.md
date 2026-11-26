# dndsheet

Сервіс для створення й експорту листків персонажа **D&D 5e (правила 2014)** українською.
Персональний проєкт: спочатку локальний запуск, пізніше — власний сайт.

## Як це влаштовано

```
Character (агрегат) ──> DerivedStatsCalculator ──> ComputedSheet ──> SheetDocument (JSON, v1.0)
                                                                        ├──> React-рендер (веб)
                                                                        └──> адаптери за портом SheetRenderer (PDF, Markdown, …)
```

`SheetDocument` — доменний артефакт, а не DTO. Кожен підпис у ньому двомовний:
`uk` показується, `en` — оригінал для тултіпа. Деталі рішень — у [`docs/plan.md`](docs/plan.md) і [`docs/adr/`](docs/adr/).

## Статус: етап 0 (каркас)

Готово:

- [x] домен: `AbilityScore`, `DiceExpression`, `Armor`, `Character`, `DerivedStatsCalculator`
- [x] безпечний обчислювач формул (whitelisted AST, без `eval`)
- [x] контракт `contract/sheet-document.schema.json` + 2 фікстури
- [x] pydantic-модель `SheetDocument`
- [x] порт `SheetRenderer` + реєстр + 2 адаптери (Markdown, PDF)
- [x] conformance-тести на фікстурах
- [x] DDD-гейти (`import-linter`): домен не тягне FastAPI/SQLAlchemy
- [x] HTTP API: `/healthz`, `/api/v1/demo/sheet`, `/api/v1/demo/export/{format}`
- [x] каркас SPA (React + TS + Vite) з тултіпами «?» → оригінал англійською
- [x] глосарій v0 (`content/glossary.uk.yml`) — **чернетка, потребує звірки з офіційним PDF**

### Перевірено локально (Python 3.13, Node 24)

| Гейт | Результат |
|---|---|
| `pytest backend` | **109 passed, 1 skipped** (PDF-тест скіпнуто: немає WeasyPrint/GTK) |
| `lint-imports` | **4 contracts kept, 0 broken** |
| `tsc --noEmit` | чисто |
| `vite build` | 104 модулі, ~242 kB JS (~78 kB gzip) |
| SPA end-to-end | FastAPI віддає `/`, рендериться `SheetDocument`, тултіп на фокусі показує оригінал («Strength») |

Далі: етап 1 — PHB-підмножина, акаунти, візард, перший справжній листок.

## Швидкий старт (Windows / PowerShell)

> Детальна інструкція — встановлення, запуск, тести, діагностика проблем: **[RUN.md](RUN.md)**.

```powershell
cd dnd-sheet

# backend
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e "backend[dev]"

# тести
.venv\Scripts\python -m pytest backend

# API
.venv\Scripts\python -m uvicorn dndsheet.main:app --reload

# frontend (окремий термінал)
cd frontend
npm install
npm run dev
```

Відкрити: http://127.0.0.1:5173 (SPA, проксі на API :8000).

PDF-рендер потребує `weasyprint` + GTK:
`.venv\Scripts\python -m pip install -e "backend[pdf]"`. Без нього PDF-тести скіпаються,
а `/api/v1/demo/export/pdf` віддає 503 — це очікувано.

**На Windows** WeasyPrint додатково потребує GTK (Pango/cairo) — pip його не ставить.
Варіанти: (а) поставити GTK-рантайм, (б) рендерити PDF у Docker/WSL (так само буде на хостингу),
(в) замінити адаптер на Chromium-друк (важчий, але без нативних залежностей).
Рішення — за тобою; порт `SheetRenderer` дозволяє замінити адаптер без змін у домені.

## Гейти якості

```powershell
# швидко, БЕЗ встановлення залежностей (stdlib only):
python scripts/preflight.py

.venv\Scripts\python -m pytest backend            # тести
.venv\Scripts\python -m pytest backend -k conformance
.venv\Scripts\lint-imports --config backend/pyproject.toml   # архітектура
cd frontend; npm run typecheck                                # типи
cd frontend; npm run contract                                 # перегенерація типів із JSON Schema

# корпус книг: одна категорія — один формат
.venv\Scripts\python -m scripts.normalize --check   # або: make format-check
.venv\Scripts\python -m scripts.normalize --write   # або: make format
```

`scripts/preflight.py` перевіряє синтаксис, JSON-контракт, інваріанти `SheetDocument`,
чистоту домену (заміна import-linter), golden-числа, безпеку обчислювача формул і
формат обох корпусів книг (`content/compendium/` — довідник для листа персонажа,
`content/bestiary/` — статблоки монстрів).

Формат записів довідника описано в [`docs/format.md`](docs/format.md): однакові
поля, однаковий набір і порядок ключів `data`, однаковий скелет `text_en` для
кожної категорії. Специфікація — `contract/compendium-format.json`; там же
блок `corpora` каже, яка категорія в якому корпусі живе (монстри — окремо,
бо в листі персонажа вони не задіяні).

## Структура

```
backend/src/dndsheet/
  shared/          # kernel: Ability, Skill, AbilityScore, DiceExpression, Armor
  characters/      # агрегат Character + DerivedStatsCalculator
  sheets/          # SheetDocument, формули, лейбли, build_document
  export/          # порт SheetRenderer, реєстр, адаптери PDF/Markdown
  identity/        # (порожньо, етап 1)
  compendium/      # (порожньо, етап 2)
  localization/    # (порожньо, етап 2)
  api/             # FastAPI
contract/          # JSON Schema + фікстури (єдине джерело типів)
content/           # глосарій, реєстр джерел, корпуси записів (compendium + bestiary)
frontend/          # React SPA
docs/              # план + ADR
```

## Правові застереження

- Проєкт — **персонального використання**, без розповсюдження.
- Тексти правил не живуть у коді: усе в БД із полем `license` (`srd` / `proprietary`),
  щоб публічний режим «тільки SRD» вмикався перемикачем.
- D&D Beyond використовується лише як **ручний довідник** (звірка назв/полів).
  Автоматизоване викачування їхнього контенту — проти їхніх умов, тому його в коді не буде.
- Офіційний український PDF — джерело термінології; у глосарії зберігаються терміни
  й посилання (книга + сторінка), а не текст.
