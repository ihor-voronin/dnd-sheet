/** Екран персонажа: вкладки, редагування на місці, лічильники й відпочинок.
 *
 * Усі числа приходять із сервера; компонент їх не перераховує. Клік по
 * похідному числу (КЗ, ініціатива, навичка) створює **виправлення** — сервер
 * зберігає його окремо й позначає поле як «вручну», доки гравець не скине.
 * Лічильники (хіти, слоти, хіт-дайси, кидки смерті) — це стан, а не
 * виправлення: кожна зміна одразу йде на диск.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { exportUrl, fetchRenderers, patchCharacter, restCharacter, spendHitDie } from "../../api";
import {
  ABILITY_SHORT,
  ALIGNMENT_LABELS,
  ITEM_KIND_LABELS,
  SKILL_ABILITY,
  SKILL_LABELS,
  abilityLabel,
  modifierLabel,
  skillLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";
import { EditableNumber, Pips } from "./editing";
import { AttacksTable, CastingBlock, FeaturesList, ProficienciesList, SpellsKnownList } from "./panels";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];
const SKILL_ORDER = Object.keys(SKILL_LABELS);

const TABS: { id: string; label: string }[] = [
  { id: "overview", label: "Огляд" },
  { id: "actions", label: "Дії" },
  { id: "spells", label: "Закляття" },
  { id: "inventory", label: "Інвентар" },
  { id: "features", label: "Уміння" },
  { id: "notes", label: "Нотатки" },
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
  const [tab, setTab] = useState("overview");
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

  function overrideNumber(
    key: string,
    value: number,
    title: string,
    suffix = "",
  ) {
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

  const totalLevel = character.classes.reduce((sum, item) => sum + item.level, 0);

  return (
    <article className="sheet character-view">
      <header className="sheet-banner">
        <div className="banner-main">
          <p className="banner-kicker">Лист персонажа</p>
          <h1>{character.name}</h1>
          <p className="banner-sub">
            <span className="banner-level">рівень {totalLevel}</span>
            {character.classes.map((item) => `${item.name_en} ${item.level}`).join(" / ")}
            {character.species ? ` · ${character.species.name_en}` : ""}
            {character.species?.subspecies ? ` (${character.species.subspecies})` : ""}
            {character.background ? ` · ${character.background.name_en}` : ""}
            {character.alignment ? ` · ${ALIGNMENT_LABELS[character.alignment] ?? character.alignment}` : ""}
          </p>
        </div>
        <div className="export-bar">
          <span className="export-label">Експорт зі станом</span>
          <a className="button" href={exportUrl(id, "markdown")} download>
            Markdown
          </a>
          <a className="button" href={`${exportUrl(id, "markdown")}?originals=false`} download>
            Markdown без англ.
          </a>
          {pdfReady ? (
            <a className="button button--primary" href={exportUrl(id, "pdf")} download>
              PDF (A4)
            </a>
          ) : (
            <span className="meta" title="На сервері немає WeasyPrint (extra `pdf` + GTK)">
              PDF недоступний на цьому сервері
            </span>
          )}
        </div>
      </header>

      <nav className="tabs" aria-label="Розділи листа">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tab ${tab === item.id ? "tab--active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {error ? <p className="status status--error">{error}</p> : null}
      {busy ? <p className="meta">Зберігаємо…</p> : null}

      {tab === "overview" ? (
        <>
          <section className="vitals">
            <div className="stat stat--ac">
              <span className="stat-label">Клас захисту</span>
              <span className="stat-value">
                {overrideNumber("armor_class", sheet.armor_class.value, "Клас захисту")}
              </span>
              <span className="stat-note">{partList(sheet.armor_class.parts)}</span>
            </div>
            <div className="stat stat--hp">
              <span className="stat-label">Хіти</span>
              <span className="stat-value">
                <EditableNumber
                  value={sheet.hit_points.current}
                  title="Поточні хіти"
                  onSave={(value) => patch({ hp: { current: value } })}
                  min={0}
                  max={999}
                />
                <span className="stat-slash"> / </span>
                {overrideNumber("hit_points_max", sheet.hit_points.maximum, "Максимум хітів")}
              </span>
              <span className="stat-note">{partList(sheet.hit_points.parts)}</span>
              <span className="stat-note">
                тимчасові:{" "}
                <EditableNumber
                  value={sheet.hit_points.temporary}
                  title="Тимчасові хіти"
                  onSave={(value) => patch({ hp: { temporary: value } })}
                  min={0}
                />
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Ініціатива</span>
              <span className="stat-value">
                {overrideNumber("initiative", sheet.initiative, "Ініціатива")}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Швидкість</span>
              <span className="stat-value">
                {overrideNumber("speed", sheet.speed, "Швидкість", " фт")}
              </span>
            </div>
            <div className="stat stat--wide">
              <span className="stat-label">Майстерність</span>
              <span className="stat-value">{modifierLabel(sheet.proficiency_bonus)}</span>
            </div>
            <div className="stat stat--wide">
              <span className="stat-label">Пасивна уважність</span>
              <span className="stat-value">
                {overrideNumber("passive_perception", sheet.passive_perception, "Пасивна уважність")}
              </span>
            </div>
          </section>

          <div className="sheet-columns">
          <div className="sheet-column sheet-column--combat">
          <section className="panel">
            <h3>Стан</h3>
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
            </div>
            <div className="state-row">
              <span>
                Кидки смерті — успіхи:{" "}
                <Pips
                  count={sheet.state.death_saves.successes}
                  max={3}
                  title="Успіхи кидків смерті"
                  onChange={(value) =>
                    patch({ death_saves: { successes: value, failures: sheet.state.death_saves.failures } })
                  }
                />
              </span>
              <span>
                провали:{" "}
                <Pips
                  count={sheet.state.death_saves.failures}
                  max={3}
                  title="Провали кидків смерті"
                  onChange={(value) =>
                    patch({ death_saves: { successes: sheet.state.death_saves.successes, failures: value } })
                  }
                />
              </span>
            </div>
            <div className="button-row button-row--start">
              <button
                type="button"
                className="button"
                onClick={() => run(restCharacter(id, "short"))}
              >
                Короткий відпочинок
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={() => run(restCharacter(id, "long"))}
              >
                Довгий відпочинок
              </button>
            </div>
          </section>

          <section className="panel">
            <h3>Хіт-дайси</h3>
            {Object.entries(sheet.resources.hit_dice).length ? (
              <ul className="plain-list">
                {Object.entries(sheet.resources.hit_dice).map(([die, resource]) => {
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

          <section className="sheet-section">
            <h2>Атаки</h2>
            <AttacksTable attacks={sheet.attacks} />
          </section>

          {casting.classes.length ? (
            <section className="sheet-section">
              <h2>Чарування</h2>
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
            </section>
          ) : null}

          <section className="sheet-section">
            <h2>Уміння</h2>
            <FeaturesList features={sheet.features} />
          </section>

          <section className="sheet-section">
            <h2>Володіння</h2>
            <ProficienciesList proficiencies={sheet.proficiencies} showSource={false} />
          </section>
          </div>

          <div className="sheet-column sheet-column--stats">
          <section className="sheet-section">
            <h2>Характеристики</h2>
            <ul className="ability-cards">
              {ABILITIES.map((ability) => {
                const value = sheet.abilities[ability];
                const save = sheet.saving_throws[ability];
                return (
                  <li key={ability} className="ability-card">
                    <span className="ability-card__name" title={abilityLabel(ability)}>
                      {ABILITY_SHORT[ability]}
                    </span>
                    <span
                      className="ability-card__score"
                      title={`База ${value.base}${value.bonus ? `, бонус ${modifierLabel(value.bonus)}` : ""}`}
                    >
                      {value.total}
                    </span>
                    <span className="ability-card__mod">{modifierLabel(value.modifier)}</span>
                    <span className="ability-card__save">
                      {save.proficient ? <span className="dot" title="володіє порятунком" /> : null}
                      порятунок{" "}
                      {overrideNumber(`save:${ability}`, save.value, `Порятунок ${abilityLabel(ability)}`)}
                    </span>
                  </li>
                );
              })}
            </ul>
            <details className="reckoning">
              <summary>Звідки числа</summary>
              <table className="ability-table">
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
                        <th scope="row">
                          {abilityLabel(ability)} <span className="short">{ABILITY_SHORT[ability]}</span>
                        </th>
                        <td>{value.base}</td>
                        <td>{value.bonus ? modifierLabel(value.bonus) : "—"}</td>
                        <td>
                          <strong>{value.total}</strong>
                        </td>
                        <td>{modifierLabel(value.modifier)}</td>
                        <td>
                          {overrideNumber(`save:${ability}`, save.value, `Порятунок ${abilityLabel(ability)}`)}
                          {save.proficient ? <span className="dot" title="володіє" /> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </details>
          </section>

          <section className="sheet-section">
            <h2>Навички</h2>
            <ul className="skill-grid">
              {SKILL_ORDER.map((skill) => {
                const value = sheet.skills[skill];
                if (!value) return null;
                const key = `skill:${skill}`;
                return (
                  <li key={skill} className={value.proficient ? "skill skill--proficient" : "skill"}>
                    <span className="skill-mark" aria-hidden>
                      {value.proficient ? "●" : "○"}
                    </span>
                    <span className="skill-name">{skillLabel(skill)}</span>
                    <span className="skill-ability">{ABILITY_SHORT[SKILL_ABILITY[skill]] ?? ""}</span>
                    <span className="skill-value">
                      {overrideNumber(key, value.value, `Навичка ${skillLabel(skill)}`)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
          </div>
          </div>
        </>
      ) : null}

      {tab === "actions" ? (
        <section className="sheet-section">
          <h2>Атаки</h2>
          <AttacksTable attacks={sheet.attacks} />
        </section>
      ) : null}

      {tab === "spells" ? (
        <>
          <section className="sheet-section">
            <h2>Чарування</h2>
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
          </section>

          <section className="sheet-section">
            <h2>Відомі закляття</h2>
            <SpellsKnownList spells={sheet.spells} />
          </section>
        </>
      ) : null}

      {tab === "inventory" ? (
        <section className="sheet-section">
          <h2>Інвентар</h2>
          <p className="hint">
            Вага {sheet.carrying.weight} з {sheet.carrying.capacity} фнт
          </p>
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
        </section>
      ) : null}

      {tab === "features" ? (
        <>
          <section className="sheet-section">
            <h2>Уміння</h2>
            <FeaturesList features={sheet.features} />
          </section>
          <section className="sheet-section">
            <h2>Володіння</h2>
            <ProficienciesList proficiencies={sheet.proficiencies} />
          </section>
        </>
      ) : null}

      {tab === "notes" ? (
        <section className="sheet-section">
          <h2>Нотатки</h2>
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
        </section>
      ) : null}
    </article>
  );
}
