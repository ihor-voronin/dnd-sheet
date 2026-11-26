/** Екран персонажа: вкладки, редагування на місці, лічильники й відпочинок.
 *
 * Усі числа приходять із сервера; компонент їх не перераховує. Клік по
 * похідному числу (КЗ, ініціатива, навичка) створює **виправлення** — сервер
 * зберігає його окремо й позначає поле як «вручну», доки гравець не скине.
 * Лічильники (хіти, слоти, хіт-дайси, кидки смерті) — це стан, а не
 * виправлення: кожна зміна одразу йде на диск.
 */

import { useState } from "react";

import { patchCharacter, restCharacter, spendHitDie } from "../../api";
import {
  ABILITY_SHORT,
  ALIGNMENT_LABELS,
  ITEM_KIND_LABELS,
  PROFICIENCY_LABELS,
  SKILL_LABELS,
  abilityLabel,
  modifierLabel,
  skillLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";
import { Counter, EditableNumber, Pips } from "./editing";

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

const LANGUAGE_LABELS: Record<string, string> = {
  common: "спільна",
  elvish: "ельфійська",
  dwarvish: "дворфська",
  infernal: "пекельна",
  celestial: "небесна",
  draconic: "драконяча",
  gnomish: "гномівська",
  goblin: "гоблінська",
  halfling: "півросликів",
  orc: "ороча",
  abyssal: "безодні",
  sylvan: "лісова",
  undercommon: "підземна",
  primordial: "первісна",
  giant: "велетнів",
  "deep speech": "глибока мова",
};

const PROFICIENCY_VALUE_LABELS: Record<string, string> = {
  light: "легка броня",
  medium: "середня броня",
  heavy: "важка броня",
  shield: "щити",
  simple: "проста зброя",
  martial: "воєнна зброя",
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

function proficiencyValue(kind: string, value: string): string {
  if (kind === "skill") return skillLabel(value);
  if (kind === "saving_throw") return abilityLabel(value);
  if (kind === "language") return LANGUAGE_LABELS[value] ?? value;
  return PROFICIENCY_VALUE_LABELS[value] ?? value;
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

  return (
    <article className="sheet character-view">
      <header className="sheet-header">
        <h1>{character.name}</h1>
        <p className="meta character-meta">
          {character.classes.map((item) => `${item.name_en} ${item.level}`).join(" / ")}
          {character.species ? ` · ${character.species.name_en}` : ""}
          {character.species?.subspecies ? ` (${character.species.subspecies})` : ""}
          {character.background ? ` · ${character.background.name_en}` : ""}
          {character.alignment ? ` · ${ALIGNMENT_LABELS[character.alignment] ?? character.alignment}` : ""}
        </p>
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
          <section className="combat-panel">
            <div className="stat">
              <span className="stat-label">Клас захисту</span>
              <span className="stat-value">
                {overrideNumber("armor_class", sheet.armor_class.value, "Клас захисту")}
              </span>
              <span className="stat-note">{partList(sheet.armor_class.parts)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Хіти</span>
              <span className="stat-value">
                <EditableNumber
                  value={sheet.hit_points.current}
                  title="Поточні хіти"
                  onSave={(value) => patch({ hp: { current: value } })}
                  min={0}
                  max={999}
                />
                {" / "}
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
            <div className="stat">
              <span className="stat-label">Майстерність</span>
              <span className="stat-value">{modifierLabel(sheet.proficiency_bonus)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Пасивна уважність</span>
              <span className="stat-value">
                {overrideNumber("passive_perception", sheet.passive_perception, "Пасивна уважність")}
              </span>
            </div>
          </section>

          <section className="wizard-block">
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
            <div className="button-row">
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

          <section className="wizard-block">
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
            <h2>Характеристики</h2>
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
                    <span className="skill-name">
                      {value.proficient ? "● " : "○ "}
                      {skillLabel(skill)}
                    </span>
                    <span className="skill-value">
                      {overrideNumber(key, value.value, `Навичка ${skillLabel(skill)}`)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      ) : null}

      {tab === "actions" ? (
        <section className="sheet-section">
          <h2>Атаки</h2>
          {sheet.attacks.length ? (
            <table className="ability-table">
              <thead>
                <tr>
                  <th>Зброя</th>
                  <th>Атака</th>
                  <th>Урон</th>
                  <th>Здібність</th>
                  <th>Властивості</th>
                </tr>
              </thead>
              <tbody>
                {sheet.attacks.map((attack) => (
                  <tr key={attack.name_en}>
                    <th scope="row">{attack.name_en}</th>
                    <td>{modifierLabel(attack.attack_bonus)}</td>
                    <td>{attack.damage}</td>
                    <td>{abilityLabel(attack.ability)}</td>
                    <td className="short">{attack.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="hint">
              Зброї немає. Додайте її в інвентар — бонус і урон порахуються з довідника.
            </p>
          )}
        </section>
      ) : null}

      {tab === "spells" ? (
        <>
          {casting.classes.length ? (
            <section className="sheet-section">
              <h2>Чарування</h2>
              <ul className="plain-list">
                {casting.classes.map((item) => (
                  <li key={item.key}>
                    {item.name_en}: опір {item.save_dc}, атака {modifierLabel(item.attack_bonus)} (від{" "}
                    {abilityLabel(item.ability)})
                    {item.prepares
                      ? `, готує до ${item.prepared_limit}`
                      : `, знає до ${item.spells_known_limit ?? 0}`}
                  </li>
                ))}
              </ul>
              <div className="resource-row">
                {Object.entries(sheet.resources.slots).map(([level, resource]) => (
                  <span key={level} className="resource">
                    {level} рівень
                    <Counter
                      used={resource.used}
                      total={resource.total}
                      title={`слоти ${level} рівня`}
                      onChange={(used) => {
                        const usedMap: Record<string, number> = {};
                        for (const [key, value] of Object.entries(sheet.resources.slots)) {
                          const next = key === level ? used : value.used;
                          if (next) usedMap[key] = next;
                        }
                        patch({ slots: usedMap });
                      }}
                    />
                  </span>
                ))}
                {sheet.resources.pact ? (
                  <span className="resource">
                    Pact Magic
                    <Counter
                      used={sheet.resources.pact.used}
                      total={sheet.resources.pact.total}
                      title="слоти Pact Magic"
                      onChange={(used) => patch({ pact_used: used })}
                    />
                  </span>
                ) : null}
              </div>
            </section>
          ) : (
            <p className="hint">Персонаж не чарує.</p>
          )}

          <section className="sheet-section">
            <h2>Відомі закляття</h2>
            {sheet.spells.length ? (
              <ul className="plain-list">
                {sheet.spells.map((spell) => (
                  <li key={`${spell.name_en}-${spell.source}`}>
                    {spell.level === 0 ? "заговір" : `${spell.level} рівня`} · {spell.name_en}
                    {spell.always_prepared
                      ? " · завжди підготовлене"
                      : spell.prepared
                        ? " · підготовлене"
                        : ""}
                    {spell.source === "species"
                      ? " · від виду"
                      : spell.source === "subclass"
                        ? " · від підкласу"
                        : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">—</p>
            )}
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
            <ul className="plain-list">
              {sheet.inventory.items.map((item) => (
                <li key={item.name_en}>
                  {item.name_en}
                  {item.quantity > 1 ? ` × ${item.quantity}` : ""} ·{" "}
                  {ITEM_KIND_LABELS[item.kind] ?? item.kind}
                  {item.armor_base ? ` · КЗ ${item.armor_base}` : ""}
                  {item.weight_lb ? ` · ${item.weight_lb} фнт` : ""}{" "}
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
        <section className="sheet-section">
          <h2>Уміння</h2>
          {sheet.features.length ? (
            <ul className="plain-list">
              {sheet.features.map((feature) => (
                <li key={`${feature.class_key}-${feature.name_en}`}>
                  <strong>{feature.name_en}</strong> · {feature.class_name}, {feature.level} рівень
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">—</p>
          )}
          <h3>Володіння</h3>
          <ul className="plain-list">
            {sheet.proficiencies.map((item, index) => (
              <li key={`${item.kind}-${item.value}-${index}`}>
                {PROFICIENCY_LABELS[item.kind] ?? item.kind}: {proficiencyValue(item.kind, item.value)}{" "}
                <span className="short">({item.source.kind}: {item.source.key})</span>
              </li>
            ))}
          </ul>
        </section>
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
