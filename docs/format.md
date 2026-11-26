# Формат записів довідника

Один запис — одна сутність однієї категорії, і **всі записи однієї категорії
мають однаковий формат**. Це не стилістична дрібниця: корпус збирають чотири
різні конвеєри (HTML зі сторінок D&D Beyond, OCR сканованого PDF, текстовий шар
PDF, рукописні записи в білдерах), і до впровадження цього контракту «всі
закляття» на ділі мали три різні формати, «всі монстри» — 55 наборів ключів
`data`, а «всі риси» — два різні початки тексту.

Корпусів два, і межа між ними — частина того самого контракту:

| Корпус | Тека | Що всередині | Читає лист персонажа |
|---|---|---|---|
| `compendium` | `content/compendium/` | класи, підкласи, види, передісторії, риси, опційні вміння, закляття, предмети, правила | так |
| `bestiary` | `content/bestiary/` | статблоки монстрів | **ні** |

Формат запису в обох однаковий (та сама схема, ті самі перевірки), тому один
читач обслуговує обидва корпуси. Різниця лише в тому, що монстри не беруть
участі в збиранні листа: їхній обсяг (3605 записів) перевищує решту сутностей
разом, і тримати їх у потоці листка означало б щоразу просіювати непотріб.

Джерело істини — `contract/compendium-format.json`. Код — `scripts/normalize/`.
Тест — `backend/tests/contract/test_compendium_format.py`.

## 1. Що саме однакове

1. **Поля запису** (`entry_keys`, у цьому порядку):

   ```
   id, schema, source_id, category, name_en, name_uk, edition, license,
   url, page, text_en, text_uk, data, status, fetched_at, notes
   ```

2. **Ключі `data`** — фіксований набір і фіксований порядок для категорії.
   Невідоме значення — `null`, прапорець — `false`, порожній список — `null`.
   Ключа, якого немає в контракті, в записі бути не може.

3. **Скелет `text_en`** — один із трьох:

   | Скелет | Як виглядає | Категорії |
   |---|---|---|
   | `spell-block` | перший рядок — `8th-level necromancy` або `Conjuration cantrip`, далі порожній рядок і тіло | `spell` |
   | `prose` | одразу тіло, без заголовка | `species`, `background`, `feat`, `optionalfeature`, `subclass`, `item`, `monster` |
   | `section` | перший рядок — `# <назва>`, далі порожній рядок і тіло | `class`, `rule` |

   Плюс спільна гігієна: без м'яких переносів (`U+00AD`), без BOM, без
   хвостових пробілів, без трьох і більше порожніх рядків підряд.

## 2. Категорії

| Категорія | Ключі `data` (у цьому порядку) | Текст |
|---|---|---|
| `spell` | `level`, `school`, `ritual`, `concentration`, `casting_time`, `range`, `components`, `duration`, `classes`, `at_higher_levels` | `spell-block` |
| `species` | `ability_increases`, `size`, `speed`, `subrace_of` | `prose` |
| `background` | `feature` | `prose` |
| `feat` | `prerequisite` | `prose` |
| `optionalfeature` | `feature_type`, `prerequisite` | `prose` |
| `class` | — | `section` |
| `subclass` | `class`, `level` | `prose` |
| `item` | `item_type`, `rarity`, `magical`, `attunement`, `base_item`, `group`, `cost`, `weight`, `armor_class`, `damage`, `properties`, `stealth`, `strength` | `prose` |
| `monster` | `size`, `creature_type`, `subtype`, `alignment`, `armor_class`, `hit_points`, `hit_dice`, `speed`, `abilities`, `challenge_rating`, `xp`, `saving_throws`, `skills`, `damage_vulnerabilities`, `damage_resistances`, `damage_immunities`, `condition_immunities`, `senses`, `languages` | `prose` (корпус `bestiary`) |
| `rule` | — | `section` |

Особливі типи значень:

* `abilities` — завжди шість ключів `str, dex, con, int, wis, cha`, значення —
  ціле число або `null`;
* `ability_increases` — шість ключів `strength, dexterity, constitution,
  intelligence, wisdom, charisma`, ціле число або `null`;
* `lower` — список у нижньому регістрі, відсортований (`classes`,
  `feature_type`): у дзеркала група опційного вміння — це код
  (`EI`, `FS:R`), а в записі вона зветься `eldritch invocation`,
  `fighting style (ranger)`;
* `str_lower` — рядок у нижньому регістрі (`size`, `creature_type`,
  `alignment`, `rarity`): у книгах трапляється і `Small fey`, і `small fey`.

`data` категорій `class` і `rule` — завжди `{}`: правила й класи — це текст, а
структуровані поля (населення міста, склад команди, автори книги) до контракту
не входять; вони лишаються в `text_en`.

Якій категорії в якому корпусі лежати — описано в `corpora` того самого файлу:
`compendium` — усі категорії, крім `monster`, `bestiary` — лише `monster`.
Категорія без корпусу або в двох корпусах — помилка специфікації, її ловить
`_validate_spec`, і preflight падає ще до перевірки записів.

## 3. Механічні виправлення категорії

Формат категорії неможливий, якщо в ній лежить чужий тип запису. Тому
нормалізатор виправляє очевидні випадки (`refine` у контракті):

| Ознака | Було | Стало |
|---|---|---|
| текст починається заголовком `Chapter …`, `Appendix …`, `Part …` або назвою-списком (`Spells`, `Equipment`, `Monsters`, `Bestiary`, `Backgrounds`, `Races`, `Classes`, `Feats`, `Items`, `Magic Items`, `Spell Lists`) | будь-яка сутність | `rule` |
| сутність починається з чужого заголовка (Sage Advice: `#### If you have the Charger feat…`) | `feat` | `rule` |
| текст починається рядком рівня закляття (`4th-level conjuration`) | `monster` | `spell` |
| у статблоці немає рядка типу істоти (`Large aberration, lawful evil`) | `monster` | `rule` |
| `id` повторюється після виправлення категорії | два записи з одним `id` | лишається повніший (більше заповнених полів `data`), другий згадується в `notes` |

## 4. Як користуватися

```powershell
# перевірити весь корпус (код виходу 1, якщо є розбіжності)
python -m scripts.normalize --check

# перевірити одну книгу, з прикладами
python -m scripts.normalize --check --source eepc --limit 10

# привести корпус до канону
python -m scripts.normalize --write

# матриця «книга × категорія»
python -m scripts.normalize --stats
```

Усі команди працюють одразу з обома корпусами: `--check` обходить книги,
знайдені в `content/compendium/` і `content/bestiary/`, `--stats` показує
спільну матрицю, а `--write` не лише нормалізує записи, а й переносить їх у
корпус, який приписала категорії специфікація.

У Makefile — `make format` і `make format-check`. У тестах формат перевіряє
`backend/tests/contract/test_compendium_format.py` (структура, `data`,
скелет тексту, унікальність `id`, мінімум полів для закляття й статблока,
і окремо — що `monster` не повернувся в компендіум, а в бестіарії немає
нічого, крім нього).

Конвеєри застосовують контракт самі:

* `scripts/ingest/records.py` — після розбору сторінок;
* `scripts/pdf/build_eepc.py`, `scripts/pdf/build_gotg.py` — після збірки книги.

Тобто «перевести все у формат» — це `--write` один раз; далі кожен новий
запуск конвеєра вже пише канон.

### Перебудова корпусу без втрат

Формат не допоможе, якщо перерозбір загубив текст. Тому для повної перебудови
HTML-книг є дві команди:

```powershell
# перерозібрати всі книги з content/raw/*.html; книгу, яка стала коротшою,
# буде відкочено до попереднього стану
python scripts/ingest/reparse.py --show-text-loss

# перевірити, що жоден абзац попереднього корпусу не зник
python scripts/ingest/verify_text.py --against <копія попереднього корпусу>
```

`reparse` і `verify_text` працюють із книгою як із цілим, тобто по обох
корпусах: знімок робиться з `content/compendium/` і `content/bestiary/`, і
якщо після розбору книга стала коротшою, відкочуються обидві її теки. Для
`verify_text` можна передати `--against` двічі (окремо компендіум і бестіарій)
або один раз — теку, у якій вони лежать поруч.

`verify_text` розрізняє **втрату** і **виправлення**: якщо абзац не знайдено,
але той самий запис існує і схожий на нього ≥90%, це виправлення (наприклад,
OCR-артефакт «fol lowing» → «following»), а не втрата. Саме так було звірено
перехід на 5393 записи: 0 втрат, 2 виправлені абзаци.

## 5. Що це змінило в корпусі

| | До контракту | Після |
|---|---|---|
| Записів | 4639 | 5393 (3147 довідник + 2246 бестіарій) |
| Наборів ключів `data` у монстрів | 55 | 1 |
| Наборів ключів `data` у предметів | 10 | 1 |
| Записів із порожнім `data` в категоріях-сутностях | 10 | 0 |
| Заклять без рядка рівня в `text_en` | 51 | 0 |
| Рис із рядком `Prerequisite:` у тексті | 34 | 0 |
| Записів, яким виправлено категорію | 28 | — |
| Повторюваних `id` | 2 (26 записів) | 0 |

Монстрів побільшало з 1596 до 2246 не через нові книги, а тому що статблоки
Basic Rules, MToF, VGtM, Monstrous Compendium і додатків починаються звичайним
абзацом-назвою, а не заголовком markdown: раніше ці сторінки злипалися в один
запис на сторінку. Тепер вони всі живуть у бестіарії — компендіум містить 3147
записів, і саме їх читає лист персонажа.

## 6. Як додати категорію або ключ

1. Додати опис у `contract/compendium-format.json` (`categories.<назва>` з
   `text` і `data`; для нового типу значення — ще й обробник у
   `_KIND_COERCERS`) і вказати корпус у `corpora`.
2. Додати назву до `categories.enum` у `contract/compendium-entry.schema.json`
   — інакше JSON Schema відкине записи нової категорії.
3. Якщо категорію пише конвеєр дзеркала, дописати її ще й у
   `scripts/ingest/sync_sources.py` (`CATEGORY_ORDER` і `PLURALS`) — звідти
   беруться `categories:` і `note:` у реєстрі джерел.
4. `python -m scripts.normalize --check` покаже, скільки записів це зачепить.
5. `python -m scripts.normalize --write`.
6. `python -m pytest backend/tests/contract/test_compendium_format.py`.

Якщо змінюється `category` наявного запису, нормалізатор переписує і `id`
(`<source_id>/<category>/<slug>`), а якщо `id` почне повторюватися — лишає
повніший запис і пише в `notes`, який саме запис прибрано.
