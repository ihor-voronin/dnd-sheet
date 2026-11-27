# Запуск dndsheet

Покрокова інструкція: перше встановлення, щоденний запуск, тести, діагностика проблем.
Актуально для стану «етап 4»: довідник, персонаж, візард, лист під час гри, демо-листок і експорт.

**Що перевірено на цій машині:** Python 3.13 (venv), Node 24, Windows 11 / PowerShell 7.
Потрібно: Python ≥ 3.11, Node ≥ 20. Git — опційно.

---

## 0. Куди йти

```
C:\Users\User\Desktop\work_docs\dnd-sheet
```

Усі команди нижче виконуються з цієї теки, якщо не вказано інше.

---

## 1. Перше встановлення (один раз)

### 1.1 Python-середовище

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

Що ставиться: FastAPI, Pydantic, Jinja2, uvicorn + тестові pytest, jsonschema, httpx, import-linter.

Перевірка:

```powershell
.\.venv\Scripts\python.exe -m pytest backend -q
```

Очікувано: **557 passed, 2 skipped** (скіп — PDF, див. розділ 6).

### 1.2 Фронтенд

```powershell
cd frontend
npm install
npm run contract      # генерує TypeScript-типи з contract/sheet-document.schema.json
```

> `npm run contract` треба повторювати **щоразу після зміни** `contract/sheet-document.schema.json`.
> Файл `src/contract/sheetDocument.ts` генерований — руками не редагувати.

### 1.3 (Опційно) PDF-рендер

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet
.\.venv\Scripts\python.exe -m pip install -e "backend[pdf]"
```

Цього **недостатньо** на Windows: WeasyPrint потребує GTK (Pango/cairo). Деталі й варіанти — розділ 6.

---

## 2. Щоденний запуск (режим розробки)

Потрібні **два термінали**.

**Термінал 1 — API:**

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet
.\.venv\Scripts\python.exe -m uvicorn dndsheet.main:app --reload
```

**Термінал 2 — SPA з гарячим перезавантаженням:**

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet\frontend
npm run dev
```

Відкрити: **http://127.0.0.1:5173**

Vite проксіює `/api` і `/healthz` на `http://127.0.0.1:8000` (налаштовано у `frontend/vite.config.ts`),
тому CORS не потрібен.

---

## 3. Запуск як один сервер (як буде на хостингу)

FastAPI сам роздає зібраний фронтенд з того ж origin.

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet\frontend
npm run build

cd ..
.\.venv\Scripts\python.exe -m uvicorn dndsheet.main:app --host 127.0.0.1 --port 8000
```

Відкрити: **http://127.0.0.1:8000**

Чернетки візарда й збережені персонажі лежать у `var/` (у git не потрапляє).
Каталог можна змінити:

```powershell
$env:DNDSHEET_DATA_DIR = "C:\dndsheet-data"
```


> Поки що SPA-fallback на `index.html` для клієнтських маршрутів не зроблено: працює `/`,
> але не `/characters/123` після перезавантаження. Це зʼявиться разом із React Router на етапі 1.

---

## 3.1 Docker: усе в контейнері (рекомендований запуск)

Локальний Python і Node для цього не потрібні — потрібен лише Docker Desktop.

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet

docker compose up -d --build        # зібрати образ і підняти
docker compose ps                   # стан і порт
docker compose logs -f app          # журнали
docker compose down                 # зупинити
```

Відкрити: **http://127.0.0.1:8000** (порт прокинутий `8000:8000`).

Що всередині образу:

- етап `web` (node:22-alpine) збирає SPA — `tsc --noEmit && vite build`, у фінальний образ Node не потрапляє;
- етап `runtime` (python:3.12-slim) ставить backend із extra `pdf`, кладе `content/sources.yml`,
  `content/compendium`, `content/bestiary`, `content/index` (без `content/raw` — він потрібен лише ingest);
- `content/raw`, `var/`, `logs/`, `.venv`, `node_modules` відсікає `.dockerignore`.

Дані живуть на хості: `./var` прокинутий у `/app/var`, тому збережені персонажі, чернетки
візарда й відпочинок переживають `docker compose down` і перезбірку.

```powershell
Get-ChildItem var\characters        # персонажі на хості
docker compose exec app ls /app/var # те саме зсередини
```

Змінні, якими керується образ: `DNDSHEET_DATA_DIR=/app/var`, `DNDSHEET_CONTENT_DIR=/app/content`,
`DNDSHEET_SPA_DIST=/app/frontend/dist` (усі вже виставлені в `docker-compose.yml`).

**PDF у Docker працює.** `GET /api/v1/demo/export/pdf` і `/api/v1/characters/<id>/export/pdf`
віддають 4–5 сторінок A4 із кирилицею — на відміну від Windows, де без GTK було 503.

Після змін у коді:

```powershell
docker compose up -d --build     # перезібрати й перезапустити
```

**Автоперезбірка.** `watch-docker.cmd` (або `docker compose up -d --build` і потім
`docker compose watch`) стежить за `frontend/`, `backend/src`, `backend/pyproject.toml` і
`content/translations`: після збереження файлу образ перезбирається, а контейнер
перезапускається сам (1–2 хв на збірку). Вікно має лишатися відкритим; закрили — стеження
зупиниться, а контейнер працюватиме далі з останньою версією.

**Швидкий режим розробки.** `dev-docker.cmd` (або `docker compose --profile dev up api-dev web-dev`)
піднімає Vite на http://127.0.0.1:5173 і API з `uvicorn --reload` на 8001. Код монтується з
диска, тож зміни у `frontend/` і `backend/src` видно за секунди, без перезбирання образу.

**Тести в Docker.** `test-docker.cmd` (або `docker compose --profile test run --rm --build test`)
запускає `pytest` і DDD-гейти в образі, де є корпус довідника й WeasyPrint — тобто разом із
PDF-тестами, які на Windows пропускаються. CI на GitHub тут не допоможе: корпус книг у git не
зберігається (`.gitignore`), а без нього тести правил не мають на чому працювати.

PostgreSQL у compose є, але застосунок його поки не використовує (стан — файли в `var/`).
Підняти за потреби: `docker compose --profile db up -d` (порт 5433).

---

## 4. Що можна подивитись одразу

| Адреса | Що це |
|---|---|
| `http://127.0.0.1:8000/` | SPA: список збережених персонажів, візард (`#/create`), демо-листок |
| `http://127.0.0.1:8000/healthz` | `{"status":"ok"}` |
| `http://127.0.0.1:8000/#/create` | візард створення персонажа (6 кроків) |
| `http://127.0.0.1:8000/#/character/<id>/level-up` | підвищення рівня: клас, хіти, підклас, характеристики, закляття |
| `http://127.0.0.1:8000/api/v1/characters` | збережені персонажі |
| `http://127.0.0.1:8000/api/v1/demo/sheet` | `SheetDocument` (JSON) |
| `http://127.0.0.1:8000/api/v1/renderers` | `{"formats":["markdown","pdf"]}` |
| `http://127.0.0.1:8000/api/v1/demo/export/markdown` | Markdown-листок |
| `http://127.0.0.1:8000/docs` | Swagger UI |

Швидка перевірка з консолі:

```powershell
(Invoke-WebRequest http://127.0.0.1:8000/healthz).Content
(Invoke-WebRequest http://127.0.0.1:8000/api/v1/demo/export/markdown).Content
```

У SPA наведи або сфокусуй значок **«?»** біля підпису — покаже оригінальний англійський текст.

---

## 5. Тести й гейти якості

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet

python scripts\preflight.py                                       # без залежностей, stdlib only
.\.venv\Scripts\python.exe -m pytest backend -q                   # 109 passed, 1 skipped
.\.venv\Scripts\lint-imports.exe backend/pyproject.toml           # 4 contracts kept

cd frontend
npm run typecheck                                                 # tsc --noEmit
npm run build                                                     # tsc + vite build
```

Що саме перевіряє `scripts/preflight.py`: синтаксис усіх `.py`, валідність JSON-контракту,
інваріанти `SheetDocument` (посилання на поля, `id == ключ`, двомовність, типи значень),
чистоту домену (заміна import-linter), golden-числа домену й те, що обчислювач формул
не пропускає `__import__`.

Окремо conformance-набір рендерів:

```powershell
.\.venv\Scripts\python.exe -m pytest backend -k conformance -v
```

---

## 6. PDF: чому 503 і що робити

`GET /api/v1/demo/export/pdf` повертає 503, поки немає робочого WeasyPrint.
На Windows сам pip-пакет не працює без GTK (Pango/cairo).

> **У Docker PDF уже працює** (розділ 3.1): образ ставить WeasyPrint і системні бібліотеки,
> тому `/export/pdf` віддає справжній файл. 503 лишається тільки для запуску без контейнера.

Варіанти для запуску без контейнера:

1. **GTK-рантайм локально** — поставити GTK3 і додати його `bin` у `PATH`.
2. **Docker / WSL для PDF** — так само буде на хостингу, Windows лишається чистим. *(рекомендовано)*
3. **Замінити адаптер на Chromium-друк** — без нативних залежностей, але важчий рантайм.

Заміна адаптера не зачіпає домен: усе за портом `SheetRenderer`
(`backend/src/dndsheet/export/domain/renderer.py`).

---

## 7. Діагностика проблем

### `Access is denied` / `The directory is not empty` при перестворенні `.venv`

Файли тримає процес, що лишився від перерваного встановлення:

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet
Get-Process | Where-Object { $_.Path -like '*dnd-sheet\.venv\Scripts\python.exe' } |
  ForEach-Object { Stop-Process -Id $_.Id -Force }
Remove-Item -Recurse -Force .venv
python -m venv .venv
```

### `No module named pip` у `.venv`

Venv створено з `--without-pip` (так буває, коли `ensurepip` не відпрацював). Перестворити:

```powershell
python -m venv --clear .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
```

### `spawn EPERM` під час `npm run build`

Це обмеження пісочниці, коли команду запускає агент: esbuild не може створити дочірній процес.
У звичайному терміналі збірка працює. Якщо бачиш це у власному терміналі — перевір антивірус
або запусти `npm rebuild esbuild`.

### Кирилиця в консолі як `??????`

Це лише відображення, файли UTF-8. Для читабельного виводу:

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

### Порт зайнятий

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
```

або запустити на іншому порту: `--port 8010` (і тоді оновити проксі у `frontend/vite.config.ts`).

### `ModuleNotFoundError: No module named 'dndsheet'`

Забуто `pip install -e "backend[dev]"` або команда виконується не тим інтерпретатором.
Використовуй саме `.\.venv\Scripts\python.exe`, а не глобальний `python`.

---

## 8. Повне перевстановлення з нуля

```powershell
cd C:\Users\User\Desktop\work_docs\dnd-sheet
Remove-Item -Recurse -Force .venv, frontend\node_modules, frontend\dist -ErrorAction SilentlyContinue
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
cd frontend; npm install; npm run contract; npm run build
```

---

## 9. Linux / CI (коротко)

Є `Makefile` з цілями `install`, `test`, `arch`, `contract`, `dev`, `web-dev`, `web-build`:

```bash
make install
make test
make arch
make web-build
```

---

## 10. Де що лежить

```
backend/src/dndsheet/
  shared/        # VO: Ability, AbilityScore, DiceExpression, Armor, errors → kernel.py
  characters/    # агрегат Character + DerivedStatsCalculator
  sheets/        # SheetDocument, формули, лейбли, build_document
  export/        # порт SheetRenderer, реєстр, адаптери Markdown/PDF, Jinja-шаблон
  api/           # FastAPI: create_app()
contract/        # JSON Schema + фікстури (єдине джерело типів)
content/         # глосарій v0 (чернетка)
frontend/        # React SPA (Vite, TanStack Query, Radix Tooltip)
docs/            # план і ADR
scripts/         # preflight.py
```
