/** Екран збереженого персонажа: усе, що порахував сервер, без власних правил.
 *
 * Числа тут не перераховуються: якщо лист показав 16, то 16 і прийшло з
 * сервера. Компонент лише групує їх так, як їх читають за столом.
 */

import {
  ALIGNMENT_LABELS,
  ABILITY_SHORT,
  ITEM_KIND_LABELS,
  PROFICIENCY_LABELS,
  SKILL_LABELS,
  abilityLabel,
  modifierLabel,
  skillLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];
const SKILL_ORDER = Object.keys(SKILL_LABELS);

/** Підписи складників приходять ключами (`armor:Chain mail`), не текстом. */
function partLabel(raw: string): string {
  if (raw.startsWith("armor:")) return `броня ${raw.slice("armor:".length)}`;
  if (raw === "unarmored") return "без броні";
  if (raw === "dexterity") return "Спритність";
  if (raw === "shield") return "щит";
  if (raw === "bonus") return "бонус";
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

function proficiencyValue(kind: string, value: string): string {
  if (kind === "skill") return skillLabel(value);
  if (kind === "saving_throw") return abilityLabel(value);
  if (kind === "language") return LANGUAGE_LABELS[value] ?? value;
  return PROFICIENCY_VALUE_LABELS[value] ?? value;
}

export function CharacterView({ sheet }: { sheet: SheetViewPayload }) {
  const { character } = sheet;
  const casting = sheet.spellcasting;
  const money = Object.entries(sheet.inventory.money)
    .filter(([, amount]) => amount > 0)
    .map(([coin, amount]) => `${amount} ${coin}`)
    .join(", ");

  const groupedProficiencies = sheet.proficiencies.reduce<Record<string, typeof sheet.proficiencies>>(
    (groups, item) => {
      groups[item.kind] = [...(groups[item.kind] ?? []), item];
      return groups;
    },
    {},
  );

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

      <section className="combat-panel">
        <div className="stat">
          <span className="stat-label">Клас захисту</span>
          <span className="stat-value">{sheet.armor_class.value}</span>
          <span className="stat-note">{partList(sheet.armor_class.parts)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Хіти</span>
          <span className="stat-value">
            {sheet.hit_points.current} / {sheet.hit_points.maximum}
          </span>
          <span className="stat-note">{partList(sheet.hit_points.parts)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Ініціатива</span>
          <span className="stat-value">{modifierLabel(sheet.initiative)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Швидкість</span>
          <span className="stat-value">{sheet.speed} фт</span>
        </div>
        <div className="stat">
          <span className="stat-label">Майстерність</span>
          <span className="stat-value">{modifierLabel(sheet.proficiency_bonus)}</span>
        </div>
        <div className="stat">
          <span className="stat-label">Хіт-дайси</span>
          <span className="stat-value">
            {Object.entries(sheet.hit_dice)
              .map(([die, count]) => `${count}${die}`)
              .join(" + ")}
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Пасивна уважність</span>
          <span className="stat-value">{sheet.passive_perception}</span>
        </div>
        {sheet.darkvision ? (
          <div className="stat">
            <span className="stat-label">Темний зір</span>
            <span className="stat-value">{sheet.darkvision} фт</span>
          </div>
        ) : null}
        {sheet.resistances.length ? (
          <div className="stat">
            <span className="stat-label">Опір</span>
            <span className="stat-value">{sheet.resistances.join(", ")}</span>
          </div>
        ) : null}
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
                    {modifierLabel(save.value)} {save.proficient ? <span className="dot" title="володіє" /> : null}
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
            return (
              <li key={skill} className={value.proficient ? "skill skill--proficient" : "skill"}>
                <span className="skill-name">
                  {value.proficient ? "● " : "○ "}
                  {skillLabel(skill)}
                </span>
                <span className="skill-value">{modifierLabel(value.value)}</span>
              </li>
            );
          })}
        </ul>
      </section>

      {casting.classes.length ? (
        <section className="sheet-section">
          <h2>Закляття</h2>
          <ul className="plain-list">
            {casting.classes.map((item) => (
              <li key={item.key}>
                {item.name_en}: опір {item.save_dc}, атака {modifierLabel(item.attack_bonus)} (від{" "}
                {abilityLabel(item.ability)})
                {item.prepares ? `, готує до ${item.prepared_limit}` : `, знає до ${item.spells_known_limit ?? 0}`}
              </li>
            ))}
          </ul>
          <p className="hint">
            Слоти:{" "}
            {Object.entries(casting.slots.by_level)
              .map(([level, count]) => `${count} × ${level} рівня`)
              .join(", ") || "—"}
            {casting.slots.pact ? ` · Pact Magic: ${casting.slots.pact.slots} × ${casting.slots.pact.level} рівня` : ""}
          </p>
        </section>
      ) : null}

      <section className="sheet-section">
        <h2>Володіння</h2>
        {Object.keys(groupedProficiencies).length ? (
          <ul className="plain-list">
            {Object.entries(groupedProficiencies).map(([kind, items]) => (
              <li key={kind}>
                <strong>{PROFICIENCY_LABELS[kind] ?? kind}:</strong>{" "}
                {items
                  .map(
                    (item) =>
                      `${proficiencyValue(kind, item.value)} (${item.source.kind}: ${item.source.key})`,
                  )
                  .join(", ")}
              </li>
            ))}
          </ul>
        ) : (
          <p className="hint">—</p>
        )}
      </section>

      <section className="sheet-section">
        <h2>Інвентар</h2>
        <p className="hint">
          Вага {sheet.carrying.weight} з {sheet.carrying.capacity} фнт
          {money ? ` · гроші: ${money}` : " · грошей немає"}
        </p>
        {sheet.inventory.items.length ? (
          <ul className="plain-list">
            {sheet.inventory.items.map((item) => (
              <li key={item.name_en}>
                {item.name_en}
                {item.quantity > 1 ? ` × ${item.quantity}` : ""} · {ITEM_KIND_LABELS[item.kind] ?? item.kind}
                {item.armor_base ? ` · КЗ ${item.armor_base}` : ""}
                {item.weight_lb ? ` · ${item.weight_lb} фнт` : ""}
                {item.equipped ? " · споряджено" : ""}
                {item.attuned ? " · налаштовано" : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="hint">Порожньо — предмети можна додати на листі (етап 4).</p>
        )}
      </section>

      {sheet.warnings.length ? (
        <section className="sheet-section">
          <h2>Зауваження</h2>
          <ul className="plain-list">
            {sheet.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
