# content/ — база знань (дані)

Тут живе все, що є **даними**, а не кодом (див. ADR 0003).

| Файл / тека | Що це | У git |
|---|---|---|
| `glossary.uk.yml` | глосарій української термінології | так |
| `sources.yml` | **реєстр джерел**: 93 джерела (52 книги бібліотеки + 41 тека дзеркала), черги, ліцензії, прогалини | так |
| `raw/<source>/*.html` | сирий HTML сторінок книги з D&D Beyond | **ні** (copyright) |
| `raw/_index/<source>.json` | список сторінок книги (результат discover) | **ні** |
| `compendium/<source>/<category>.jsonl` | записи довідника за схемою — те, з чого збирається лист персонажа | **ні** (містять text_en) |
| `bestiary/<source>/monster.jsonl` | статблоки монстрів: той самий формат запису, окремий корпус (листок їх не читає) | **ні** (містять text_en) |
| `index/spell-lists.json` | похідний індекс: класові списки заклять зі «Spell Lists» книг | **ні** (похідне від текстів) |
| `index/class-mechanics.json` | похідний індекс: хіт-дайси, володіння, таблиці слотів, вимоги мультикласу, риси за рівнями | **ні** (похідне від дзеркала) |
| `index/origin-mechanics.json` | похідний індекс: бонуси характеристик, швидкість, темний зір, навички й мови видів і передісторій | **ні** (похідне від дзеркала) |
| `.session/cookies.json` | cookies сесії D&D Beyond | **ні** (живі креденшели) |

Похідні індекси (`index/`) складаються скриптами й не комітяться:

```powershell
python -m scripts.ingest.spell_lists --write   # класові списки заклять
python -m scripts.ingest.mechanics --write     # механіки класів, видів, передісторій
```

Межа між корпусами — частина контракту `contract/compendium-format.json`
(блок `corpora`), а не домовленість у коді: якщо монстр опиниться в
`compendium/`, preflight і тести впадуть.

Схема запису: [`contract/compendium-entry.schema.json`](../contract/compendium-entry.schema.json).

## Конвеєр

```
sources.yml ──> discover ──> fetch ──> parse ──┬──> compendium/<source>/*.jsonl
                 (BFS)      (HTML)     (markdown + поля)  │   (категорії листа)
                                                         └──> bestiary/<source>/monster.jsonl
                                                              │
                                                              └──> validate (jsonschema)
```

Запуск з кореня репозиторію (потрібен файл сесії):

```bash
python -m scripts.ingest.cli discover --source phb-2014
python -m scripts.ingest.cli fetch    --source phb-2014
python -m scripts.ingest.cli parse    --source phb-2014
python -m scripts.ingest.cli run      --source phb-2014 --delay 1.5
python -m scripts.ingest.cli all      --tiers 1,1.5,2
```

Кожен етап ідемпотентний і продовжується з місця зупинки (`_checkpoint.json`).
При CAPTCHA конвеєр зупиняється з кодом 2 і зберігає прогрес.

## Правове

- `license: proprietary` — персональне використання, публікація заборонена.
- `license: srd` — CC-BY, єдиний шар, який можна показувати публічно.
- Сирі тексти й переклади **не комітяться**; у git — лише реєстр, схема й код.
