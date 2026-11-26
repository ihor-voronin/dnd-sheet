/** Екран персонажа: огляд у дусі D&D Beyond, вкладки, правки на місці.
 *
 * Усі числа приходять із сервера; компонент їх не перераховує. Клік по
 * похідному числу (КЗ, ініціатива, навичка) створює **виправлення** — сервер
 * зберігає його окремо й позначає поле як «вручну», доки гравець не скине.
 * Лічильники (хіти, слоти, хіт-дайси, кидки смерті) — це стан, а не
 * виправлення: кожна зміна одразу йде на диск.
 *
 * Розкладка повторює звичний аркуш D&D Beyond: шапка з портретом, рядок
 * характеристик-гексагонів, далі три колонки — порятунки й володіння,
 * ініціатива з навичками, робоча панель із вкладками.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { exportUrl, fetchRenderers, patchCharacter, restCharacter, spendHitDie } from "../../api";
import {
  ABILITY_LABELS,
  ALIGNMENT_LABELS,
  ITEM_KIND_LABELS,
  abilityLabel,
  damageTypeLabel,
  modifierLabel,
  subclassLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";
import {
  AbilityHex,
  HexStat,
  PassiveList,
  ProficiencyGroups,
  SavePills,
  SkillTable,
  initials,
} from "./ddb";
import { EditableNumber, Pips } from "./editing";
import { AttacksTable, CastingBlock, FeaturesList, ProficienciesList, SpellsKnownList } from "./panels";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];

const TABS: { id: string; label: string }[] = [
  { id: "actions", label: "Дії" },
  { id: "spells", label: "Закляття" },
  { id: "inventory", label: "Інвентар" },
  { id: "features", label: "Уміння" },
  { id: "notes", label: "Нотатки" },
];

/** Стандартні дії ходу з правил 2014 — не дані персонажа, а памʼятка. */
const COMBAT_ACTIONS = [
  "Атака",
  "Ривок",
  "Відхід",
  "Ухиляння",
  "Захват",
  "Допомога",
  "Сховатися",
  "Імпровізація",
  "Вплив",
  "Магія",
  "Готовність",
  "Пошук",
  "Штовханина",
  "Вивчення",
  "Використання",
];

const NOTE_LABELS: Record<string, string> = {
  appearance: "Зовнішність",
  allies: "Союзники",
  enemies: "Вороги",
  backstory: "Передісторія",
  notes: "Нотатки",
};

function partLabel(raw: string): string {
  if (raw.startsWith("armor:")) return `броня ${raw.slice("armor:".length)}`;
  if (raw === "unarmored") return "без броні";
  if (raw === "dexterity") return "Спритність";
  if (raw === "shield") return "щит";
  if (raw === "bonus") return "бонус";
  if (raw === "override") return "вручну";
  if (raw === "manual-override") return "вписано вручну";
  const max = raw.match(/^level-1-max: (d\d+)$/);
  if (max) return `1 рівень: максимум ${max[1]}`;
  const roll = raw.match(/^level-(\d+)-roll: (d\d+)$/);
  if (roll) return `${roll[1]} рівень: кидок ${roll[2]}`;
  const average = raw.match(/^level-(\d+)-average: (d\d+)$/);
  if (average) return `${average[1]} рівень: середнє ${average[2]}`;
  if (raw.startsWith("unarmored-defense:")) {
    return `безбронний захист (${abilityLabel(raw.split(":")[1])})`;
  }
  return raw;
}

function partList(parts: { label: string; value: number }[]): string {
  return parts.map((part) => `${partLabel(part.label)} ${part.value}`).join(" · ");
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function CharacterView({ initial }: { initial: SheetViewPayload }) {
  const [sheet, setSheet] = useState<SheetViewPayload>(initial);
  const [tab, setTab] = useState("actions");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rollDraft, setRollDraft] = useState<Record<string, string>>({});
  const [notesDraft, setNotesDraft] = useState<Record<string, string>>({
    ...initial.state.notes,
  });

  const id = sheet.character.id;
  const version = sheet.character.version;

  // PDF збирається на сервері через WeasyPrint: без GTK його немає, і тоді
  // посилання не показуємо, замість того щоб віддати 503 у новій вкладці.
  const renderers = useQuery({ queryKey: ["renderers"], queryFn: fetchRenderers });
  const pdfReady = renderers.data?.available.includes("pdf") ?? false;

  async function run(action: Promise<{ sheet: SheetViewPayload }>) {
    setBusy(true);
    setError(null);
    try {
      const result = await action;
      setSheet(result.sheet);
      setNotesDraft({ ...result.sheet.state.notes });
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setBusy(false);
    }
  }

  const patch = (body: Record<string, unknown>) =>
    run(patchCharacter(id, { ...body, version }));

  const overridden = new Set(sheet.overridden);
  const { character } = sheet;
  const casting = sheet.spellcasting;

  function overrideNumber(key: string, value: number, title: string, suffix = "") {
    return (
      <EditableNumber
        value={value}
        title={title}
        suffix={suffix}
        overridden={overridden.has(key)}
        onSave={(next) => patch({ overrides: { [key]: next } })}
        onReset={() => patch({ overrides: { [key]: null } })}
      />
    );
  }

  const totalLevel = character.total_level;
  const speciesText = character.species
    ? (character.species.subspecies ?? character.species.name_en)
    : "вид не вказано";
  const classText = character.classes.length
    ? character.classes
        .map(
          (item) =>
            `${item.name_en} ${item.level}${item.subclass ? ` (${subclassLabel(item.subclass)})` : ""}`,
        )
        .join(" / ")
    : "клас не вказано";
  const originText = [
    character.alignment ? (ALIGNMENT_LABELS[character.alignment] ?? character.alignment) : "",
    character.background?.name_en ?? "",
    "правила 2014",
  ]
    .filter(Boolean)
    .join(" · ");

  // Пасивна уважність рахується на сервері; розслідування й проникливість
  // показуємо як 10 + навичка — це похідне число для ока, воно не зберігається.
  const passives = [
    { label: "Пасивна спостережливість", value: sheet.passive_perception },
    {
      label: "Пасивне розслідування",
      value: 10 + (sheet.skills.investigation?.value ?? 0),
      note: "10 + навичка",
    },
    {
      label: "Пасивна проникливість",
      value: 10 + (sheet.skills.insight?.value ?? 0),
      note: "10 + навичка",
    },
  ];

  const hitDice = Object.entries(sheet.resources.hit_dice);
  const freeHitDice = hitDice.reduce((sum, [, item]) => sum + (item.total - item.used), 0);
  const totalHitDice = hitDice.reduce((sum, [, item]) => sum + item.total, 0);
  const hitDieFaces = hitDice.map(([die]) => die).join(" / ");

  const workTab = (() => {
    if (tab === "actions") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Атаки</span>
            <span className="short">дій за хід: 1</span>
          </h3>
          <AttacksTable attacks={sheet.attacks} />
          <h3 className="ddb-work__title">
            <span>Дії в бою</span>
            <span className="short">стандартні</span>
          </h3>
          <ul className="ddb-actions">
            {COMBAT_ACTIONS.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </>
      );
    }
    if (tab === "spells") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Чарування</span>
          </h3>
          <CastingBlock
            casting={casting}
            resources={sheet.resources}
            onSlotsUsed={(level, used) => {
              const usedMap: Record<string, number> = {};
              for (const [key, value] of Object.entries(sheet.resources.slots)) {
                const next = key === level ? used : value.used;
                if (next) usedMap[key] = next;
              }
              patch({ slots: usedMap });
            }}
            onPactUsed={(used) => patch({ pact_used: used })}
          />
          <h3 className="ddb-work__title">
            <span>Відомі закляття</span>
          </h3>
          <SpellsKnownList spells={sheet.spells} />
        </>
      );
    }
    if (tab === "inventory") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Інвентар</span>
            <span className="short">
              вага {sheet.carrying.weight} з {sheet.carrying.capacity} фнт
            </span>
          </h3>
          <div className="money-row">
            {Object.entries({ gp: "золото", sp: "срібло", cp: "мідь" }).map(([coin, label]) => (
              <span key={coin} className="resource">
                {label}: {sheet.inventory.money[coin] ?? 0}
              </span>
            ))}
          </div>
          {sheet.inventory.items.length ? (
            <ul className="item-list">
              {sheet.inventory.items.map((item) => (
                <li key={item.name_en} className="item-row">
                  <span className="item-main">
                    <span className="item-name">
                      {item.name_en}
                      {item.quantity > 1 ? ` × ${item.quantity}` : ""}
                    </span>
                    <span className="item-meta">
                      {ITEM_KIND_LABELS[item.kind] ?? item.kind}
                      {item.armor_base ? ` · КЗ ${item.armor_base}` : ""}
                      {item.weight_lb ? ` · ${item.weight_lb} фнт` : ""}
                    </span>
                  </span>
                  <button
                    type="button"
                    className={`chip ${item.equipped ? "chip--active" : ""}`}
                    onClick={() => patch({ equip: { name: item.name_en, equipped: !item.equipped } })}
                  >
                    {item.equipped ? "споряджено" : "не споряджено"}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">Порожньо.</p>
          )}
        </>
      );
    }
    if (tab === "features") {
      return (
        <>
          <h3 className="ddb-work__title">
            <span>Уміння</span>
          </h3>
          <FeaturesList features={sheet.features} />
          <h3 className="ddb-work__title">
            <span>Володіння з джерелами</span>
          </h3>
          <ProficienciesList proficiencies={sheet.proficiencies} />
        </>
      );
    }
    return (
      <>
        <h3 className="ddb-work__title">
          <span>Нотатки</span>
        </h3>
        <div className="notes-grid">
          {Object.entries(NOTE_LABELS).map(([key, label]) => (
            <label key={key} className="field">
              <span>{label}</span>
              <textarea
                rows={4}
                value={notesDraft[key] ?? ""}
                onChange={(event) => setNotesDraft({ ...notesDraft, [key]: event.target.value })}
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => patch({ notes: notesDraft })}
        >
          Зберегти нотатки
        </button>
      </>
    );
  })();

  return (
    <article className="sheet character-view">
      <header className="ddb-top">
        <div className="ddb-identity">
          <span className="ddb-portrait" aria-hidden="true">
            {initials(character.name)}
          </span>
          <div>
            <p className="ddb-kicker">Лист персонажа · {originText}</p>
            <h1 className="ddb-name">{character.name}</h1>
            <p className="ddb-sub">
              <span>{speciesText}</span>
              <span>·</span>
              <span>{classText}</span>
              <span>· рівень {totalLevel}</span>
            </p>
          </div>
        </div>
        <div className="ddb-top__actions">
          <div className="ddb-rest">
            <button
              type="button"
              className="ddb-btn"
              disabled={busy}
              onClick={() => run(restCharacter(id, "short"))}
            >
              Короткий відпочинок
            </button>
            <button
              type="button"
              className="ddb-btn ddb-btn--primary"
              disabled={busy}
              onClick={() => run(restCharacter(id, "long"))}
            >
              Довгий відпочинок
            </button>
          </div>
          <div className="ddb-export">
            <span className="ddb-export__label">Експорт</span>
            <a className="ddb-btn ddb-btn--link" href={exportUrl(id, "markdown")} download>
              Markdown
            </a>
            <a
              className="ddb-btn ddb-btn--link"
              href={`${exportUrl(id, "markdown")}?originals=false`}
              download
            >
              без англ.
            </a>
            {pdfReady ? (
              <a
                className="ddb-btn ddb-btn--link ddb-btn--primary"
                href={exportUrl(id, "pdf")}
                download
              >
                PDF (A4)
              </a>
            ) : (
              <span className="meta" title="На сервері немає WeasyPrint (extra `pdf` + GTK)">
                без PDF
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="ddb-strip">
        <ul className="ddb-abilities">
          {ABILITIES.map((ability) => (
            <AbilityHex key={ability} code={ability} ability={sheet.abilities[ability]} />
          ))}
        </ul>

        <HexStat label="Майстерність" value={modifierLabel(sheet.proficiency_bonus)} />
        <HexStat
          label="Швидкість"
          value={overrideNumber("speed", sheet.speed, "Швидкість", " фт")}
        />

        <div className="ddb-hitdice">
          <span className="ddb-hitdice__label">Кістки хитів</span>
          <div className="ddb-hitdice__face" title="Тип і кількість кісток хитів">
            {hitDieFaces || "—"}
          </div>
          <span className="ddb-hexstat__note">
            {freeHitDice} / {totalHitDice}
          </span>
        </div>

        <section className="ddb-hp" aria-label="Хіти">
          <div className="ddb-hp__marks">
            <span className="ddb-hp__mark ddb-hp__mark--heal" title="Поточні хіти змінюються кліком по числу">
              Лікування
            </span>
            <span className="ddb-hp__mark ddb-hp__mark--damage" title="Поточні хіти змінюються кліком по числу">
              Шкода
            </span>
          </div>
          <div className="ddb-hp__fields">
            <div className="ddb-hp__field">
              <span>Поточні</span>
              <strong>
                <EditableNumber
                  value={sheet.hit_points.current}
                  title="Поточні хіти"
                  onSave={(value) => patch({ hp: { current: value } })}
                  min={0}
                  max={999}
                />
              </strong>
            </div>
            <div className="ddb-hp__field">
              <span>Макс.</span>
              <strong>
                {overrideNumber("hit_points_max", sheet.hit_points.maximum, "Максимум хітів")}
              </strong>
            </div>
            <div className="ddb-hp__field ddb-hp__field--temp">
              <span>Тимч.</span>
              <strong>
                <EditableNumber
                  value={sheet.hit_points.temporary}
                  title="Тимчасові хіти"
                  onSave={(value) => patch({ hp: { temporary: value } })}
                  min={0}
                />
              </strong>
            </div>
          </div>
          <p className="ddb-hp__caption">
            Хіти{sheet.hit_points.bloodied ? " · поранений" : ""}
          </p>
        </section>
      </div>

      {error ? <p className="status status--error ddb-status">{error}</p> : null}
      {busy ? <p className="meta ddb-status">Зберігаємо…</p> : null}

      <div className="ddb-grid">
        <div className="ddb-col">
          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Кидки порятунку</span>
            </h2>
            <SavePills saves={sheet.saving_throws} render={overrideNumber} />
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Пасивні показники</span>
            </h2>
            <PassiveList items={passives} />
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Чуття та опір</span>
            </h2>
            <ul className="ddb-rows">
              <li>
                <span className="ddb-rows__label">Темний зір</span>
                <span>{sheet.darkvision ? `${sheet.darkvision} фт` : "—"}</span>
              </li>
              <li>
                <span className="ddb-rows__label">Швидкість</span>
                <span>{sheet.speed} фт</span>
              </li>
              <li>
                <span className="ddb-rows__label">Опір</span>
                <span>{sheet.resistances.length ? sheet.resistances.map(damageTypeLabel).join(", ") : "—"}</span>
              </li>
            </ul>
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Володіння</span>
            </h2>
            <ProficiencyGroups proficiencies={sheet.proficiencies} />
          </section>
        </div>

        <div className="ddb-col ddb-col--mid">
          <div className="ddb-hexrow">
            <HexStat
              label="Ініціатива"
              value={overrideNumber("initiative", sheet.initiative, "Ініціатива")}
            />
            <HexStat
              label="Клас захисту"
              value={overrideNumber("armor_class", sheet.armor_class.value, "Клас захисту")}
              note="КЗ"
              title={partList(sheet.armor_class.parts)}
            />
          </div>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Навички</span>
            </h2>
            <SkillTable skills={sheet.skills} render={overrideNumber} />
            <details className="reckoning">
              <summary>Звідки числа</summary>
              <table className="ability-table ability-table--compact">
                <thead>
                  <tr>
                    <th>Характеристика</th>
                    <th>База</th>
                    <th>Бонус</th>
                    <th>Разом</th>
                    <th>Мод.</th>
                    <th>Порятунок</th>
                  </tr>
                </thead>
                <tbody>
                  {ABILITIES.map((ability) => {
                    const value = sheet.abilities[ability];
                    const save = sheet.saving_throws[ability];
                    return (
                      <tr key={ability}>
                        <th scope="row">{abilityLabel(ability)}</th>
                        <td>{value.base}</td>
                        <td>{value.bonus ? modifierLabel(value.bonus) : "—"}</td>
                        <td>
                          <strong>{value.total}</strong>
                        </td>
                        <td>{modifierLabel(value.modifier)}</td>
                        <td>
                          {overrideNumber(
                            `save:${ability}`,
                            save.value,
                            `Порятунок ${ABILITY_LABELS[ability]}`,
                          )}
                          {save.proficient ? <span className="dot" title="володіє" /> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </details>
          </section>
        </div>

        <div className="ddb-col ddb-col--work">
          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Стан</span>
            </h2>
            <div className="state-row">
              <span>
                Натхнення:{" "}
                <button
                  type="button"
                  className={`chip ${sheet.state.inspiration ? "chip--active" : ""}`}
                  onClick={() => patch({ inspiration: !sheet.state.inspiration })}
                >
                  {sheet.state.inspiration ? "є" : "немає"}
                </button>
              </span>
              <span>
                Втома:{" "}
                <EditableNumber
                  value={sheet.state.exhaustion}
                  title="Рівень втоми"
                  min={0}
                  max={6}
                  onSave={(value) => patch({ exhaustion: value })}
                />
              </span>
              <span className="state-row__wide">
                Кидки смерті: успіхи{" "}
                <Pips
                  count={sheet.state.death_saves.successes}
                  max={3}
                  title="Успіхи кидків смерті"
                  onChange={(value) =>
                    patch({
                      death_saves: {
                        successes: value,
                        failures: sheet.state.death_saves.failures,
                      },
                    })
                  }
                />{" "}
                провали{" "}
                <Pips
                  count={sheet.state.death_saves.failures}
                  max={3}
                  title="Провали кидків смерті"
                  onChange={(value) =>
                    patch({
                      death_saves: {
                        successes: sheet.state.death_saves.successes,
                        failures: value,
                      },
                    })
                  }
                />
              </span>
            </div>
          </section>

          <section className="ddb-card">
            <h2 className="ddb-card__title">
              <span>Кістки хитів</span>
            </h2>
            {hitDice.length ? (
              <ul className="hitdice-list">
                {hitDice.map(([die, resource]) => {
                  const size = Number(die.replace("d", ""));
                  return (
                    <li key={die}>
                      {die}: {resource.total - resource.used} з {resource.total} вільних{" "}
                      <input
                        className="inline-number"
                        type="number"
                        min={1}
                        max={size}
                        placeholder="кидок"
                        value={rollDraft[die] ?? ""}
                        onChange={(event) =>
                          setRollDraft({ ...rollDraft, [die]: event.target.value })
                        }
                        aria-label={`Кидок ${die}`}
                      />
                      <button
                        type="button"
                        className="button"
                        disabled={resource.used >= resource.total || !rollDraft[die]}
                        onClick={() =>
                          run(spendHitDie(id, size, Number(rollDraft[die]))).then(() =>
                            setRollDraft({ ...rollDraft, [die]: "" }),
                          )
                        }
                      >
                        витратити
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="hint">—</p>
            )}
          </section>

          <div className="ddb-work">
            <nav className="ddb-tabs" aria-label="Розділи листа">
              {TABS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`ddb-tab ${tab === item.id ? "is-active" : ""}`}
                  onClick={() => setTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <div className="ddb-work__body">{workTab}</div>
          </div>
        </div>
      </div>
    </article>
  );
}
