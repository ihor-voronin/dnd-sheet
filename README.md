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

## Статус: етап 4 (лист під час гри)

Готово:

- [x] домен: `AbilityScore`, `DiceExpression`, `Armor`, `Money`, `Character`, `DerivedStatsCalculator`
- [x] безпечний обчислювач формул (whitelisted AST, без `eval`)
- [x] контракт `contract/sheet-document.schema.json` + 2 фікстури
- [x] pydantic-модель `SheetDocument`
- [x] порт `SheetRenderer` + реєстр + 2 адаптери (Markdown, PDF)
- [x] conformance-тести на фікстурах
- [x] DDD-гейти (`import-linter`): домен не тягне FastAPI/SQLAlchemy
- [x] HTTP API: `/healthz`, `/api/v1/demo/sheet`, `/api/v1/demo/export/{format}`
- [x] каркас SPA (React + TS + Vite) з тултіпами «?» → оригінал англійською
- [x] глосарій v0 (`content/glossary.uk.yml`) — **чернетка, потребує звірки з офіційним PDF**
- [x] **етап 1 — довідник як API**: `compendium` (домен + JSONL-корпус + індекси + сервіс + ендпоінти),
      класові списки заклять зі «Spell Lists» книг — деталі в [`docs/api-compendium.md`](docs/api-compendium.md)
- [x] **етап 2 — персонаж v2**: мультиклас, вид, передісторія, володіння з джерелами, хіти,
      інвентар, закляття; `ModifierResolver`, `SpellSlotService` (мультикласові слоти + Pact Magic),
      максимум хітів і пул хіт-дайсів; похідні індекси механік із дзеркала 5e.tools
      (13 класів, 69 видів, 94 передісторії). Три еталонні персонажі зафіксовані тестами —
      деталі в [`docs/domain-character.md`](docs/domain-character.md)
- [x] **етап 3 — візард створення**: шість кроків (вид → клас → характеристики → передісторія →
      спорядження → закляття), сервер перевіряє кожен крок, чернетка зберігається на диску
      й відновлюється в браузері, назад — з будь-якого кроку; створений персонаж лягає у `var/`
      і переживає перезапуск. Вибір на 1 рівні враховано: підклас у жреця/чаклуна/варлока,
      підраси, вибір заговору високого ельфа, заговори й закляття видів, доменні/патронні
      закляття. Деталі — [`docs/wizard.md`](docs/wizard.md)
- [x] **етап 4 — лист під час гри**: вкладки, редагування на місці з позначкою «вручну»,
      лічильники (хіти, слоти, Pact Magic, хіт-дайси, кидки смерті, натхнення, втома),
      короткий/довгий відпочинок, атаки зі зброї з довідника; стан зберігається у `var/`
      і переживає перезапуск. Деталі — [`docs/sheet.md`](docs/sheet.md)

### Перевірено локально (Python 3.13, Node 24)

| Гейт | Результат |
|---|---|
| `pytest backend` | **460 passed, 1 skipped** (PDF-тест скіпнуто: немає WeasyPrint/GTK) |
| `lint-imports` | **5 contracts kept, 0 broken** |
| `tsc --noEmit` | чисто |
| `vite build` | 110 модулів, ~285 kB JS (~91 kB gzip) |
| SPA end-to-end | FastAPI віддає `/`, рендериться `SheetDocument`, тултіп на фокусі показує оригінал («Strength») |
| довідник end-to-end | `/api/v1/compendium/summary` → 3818 записів, 89 книг; `/classes/wizard/spells` → 215 заклять, `source: spell-lists`; `/mechanics` → 13 класів, 69 видів, 94 передісторії |
| персонаж end-to-end | `/api/v1/characters/golden` → 3 листи: Воїн 1 (AC 18, HP 12), Варлок 1 (Pact Magic 1 слот, DC 13), Воїн 2 / Візард 3 (рівень заклинателя 3, слоти 4×1 + 2×2) |
| візард end-to-end | створено Воїна 1 через UI (Людина, Солдат, набір, кольчуга): AC 16, HP 12, навички з джерелами; після перезавантаження сторінки чернетка повертається на той самий крок |
| вибір на 1 рівні | жрець Life: доменні `bless`/`cure wounds` завжди підготовлені; варлок The Fiend: `burning hands`/`command` у виборі; високий ельф: обраний заговір візарда на листі |
| лист end-to-end | Воїн 1 із довгим мечем: атака +5, `1d8+3 slashing`; хіти 4/12, довгий відпочинок → 12/12; КЗ 16 → 19 виправленням і назад; Pact Magic 1/1 → 0/1 → короткий відпочинок 1/1 |

Далі — етап 5: повний експорт листа (PDF і Markdown усіх секцій).
Порядок етапів і еталон екранів — у [`docs/plan.md`](docs/plan.md) (§9, §13).

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
чистоту домену (заміна import-linter), golden-числа персонажа (v2: бонуси виду, хіти,
мультикласові слоти), безпеку обчислювача формул, формат обох корпусів книг
(`content/compendium/` — довідник для листа персонажа, `content/bestiary/` — статблоки
монстрів) і базові інваріанти похідних індексів механік (`content/index/*-mechanics.json`).

Формат записів довідника описано в [`docs/format.md`](docs/format.md): однакові
поля, однаковий набір і порядок ключів `data`, однаковий скелет `text_en` для
кожної категорії. Специфікація — `contract/compendium-format.json`; там же
блок `corpora` каже, яка категорія в якому корпусі живе (монстри — окремо,
бо в листі персонажа вони не задіяні).

## Структура

```
backend/src/dndsheet/
  shared/          # kernel: Ability, Skill, AbilityScore, DiceExpression, Armor, Money
                   # + rules: механіки класів/видів, таблиці слотів (VO, без I/O)
  characters/      # агрегат Character v2, володіння, інвентар, закляття
                   # + сервіси: DerivedStatsCalculator, ModifierResolver, SpellSlotService
                   # + application/golden.py: еталонні персонажі
  sheets/          # SheetDocument, формули, лейбли, build_document
  export/          # порт SheetRenderer, реєстр, адаптери PDF/Markdown
  compendium/      # довідник: JSONL-корпус, індекси заклять і механік, сервіс, API
  identity/        # (порожньо, етап 6)
  localization/    # (порожньо, етап 5)
  api/             # FastAPI
contract/          # JSON Schema + фікстури + формати корпусів і механік (єдине джерело типів)
content/           # глосарій, реєстр джерел, корпуси записів, похідні індекси
frontend/          # React SPA
docs/              # план + ADR + описи етапів
```

## Правові застереження

- Проєкт — **персонального використання**, без розповсюдження.
- Тексти правил не живуть у коді: усе в БД із полем `license` (`srd` / `proprietary`),
  щоб публічний режим «тільки SRD» вмикався перемикачем.
- D&D Beyond використовується лише як **ручний довідник** (звірка назв/полів).
  Автоматизоване викачування їхнього контенту — проти їхніх умов, тому його в коді не буде.
- Офіційний український PDF — джерело термінології; у глосарії зберігаються терміни
  й посилання (книга + сторінка), а не текст.
