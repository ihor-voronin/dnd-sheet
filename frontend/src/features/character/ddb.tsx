/** Блоки листа в дусі D&D Beyond.
 *
 * Тут лише розмітка й підписи: жодних обчислень правил і жодного стану.
 * Числа приходять готовими з сервера, а редаговані поля вставляються ззовні
 * через `render` — так само, як у CharacterView.
 *
 * Оформлення наслідує загальний вигляд аркуша D&D Beyond (темні панелі,
 * гексагони характеристик, рядки навичок), але жодних їхніх файлів чи
 * зображень не використовує.
 */

import type { ReactNode } from "react";

import {
  ABILITY_LABELS,
  ABILITY_SHORT,
  SKILL_ABILITY,
  SKILL_LABELS,
  abilityLabel,
  modifierLabel,
  proficiencyValue,
  skillLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";

const ABILITIES = ["str", "dex", "con", "int", "wis", "cha"];
const SKILL_ORDER = Object.keys(SKILL_LABELS);

/** Редагування числа в місці: підставляється з CharacterView. */
export type RenderValue = (
  key: string,
  value: number,
  title: string,
  suffix?: string,
) => ReactNode;

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.slice(0, 2).map((word) => Array.from(word)[0] ?? "");
  return letters.join("").toUpperCase() || "?";
}

export function AbilityHex({
  code,
  ability,
}: {
  code: string;
  ability: SheetViewPayload["abilities"][string];
}) {
  const basis = `База ${ability.base}${ability.bonus ? `, бонус ${modifierLabel(ability.bonus)}` : ""}`;
  return (
    <li className="ddb-ability">
      <span className="ddb-ability__label">{ABILITY_LABELS[code] ?? code}</span>
      <div className="ddb-hex" title={`${ABILITY_LABELS[code] ?? code}: ${ability.total} (${basis})`}>
        <div className="ddb-hex__inner">
          <span className="ddb-hex__mod">{modifierLabel(ability.modifier)}</span>
          <span className="ddb-hex__score">{ability.total}</span>
        </div>
      </div>
    </li>
  );
}

export function HexStat({
  label,
  value,
  note,
  title,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  title?: string;
}) {
  return (
    <div className="ddb-hexstat">
      <span className="ddb-hexstat__label">{label}</span>
      <div className="ddb-hex ddb-hex--small" title={title}>
        <div className="ddb-hex__inner">
          <span className="ddb-hexstat__value">{value}</span>
          {note ? <span className="ddb-hex__note">{note}</span> : null}
        </div>
      </div>
    </div>
  );
}

export function SavePills({
  saves,
  render,
}: {
  saves: SheetViewPayload["saving_throws"];
  render: RenderValue;
}) {
  return (
    <ul className="ddb-saves">
      {ABILITIES.map((code) => {
        const save = saves[code];
        if (!save) return null;
        return (
          <li key={code} className={`ddb-save${save.proficient ? " is-prof" : ""}`}>
            <span
              className="ddb-save__dot"
              title={save.proficient ? "володіє кидком порятунку" : "без володіння"}
            />
            <span className="ddb-save__name">{ABILITY_SHORT[code]}</span>
            <span className="ddb-save__value">
              {render(`save:${code}`, save.value, `Порятунок ${abilityLabel(code)}`)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function PassiveList({
  items,
}: {
  items: { label: string; value: number; note?: string }[];
}) {
  return (
    <ul className="ddb-passives">
      {items.map((item) => (
        <li key={item.label} className="ddb-passive">
          <span className="ddb-passive__value">{item.value}</span>
          <span className="ddb-passive__label">{item.label}</span>
          {item.note ? <span className="ddb-passive__note">{item.note}</span> : null}
        </li>
      ))}
    </ul>
  );
}

export function SkillTable({
  skills,
  render,
}: {
  skills: SheetViewPayload["skills"];
  render: RenderValue;
}) {
  return (
    <ul className="ddb-skills">
      {SKILL_ORDER.map((skill) => {
        const value = skills[skill];
        if (!value) return null;
        return (
          <li
            key={skill}
            className={`ddb-skill${value.proficient ? " is-prof" : ""}${value.expertise ? " is-expert" : ""}`}
            title={value.expertise ? "Експертність: бонус майстерності подвоєно" : undefined}
          >
            <span className="ddb-skill__abil">{ABILITY_SHORT[SKILL_ABILITY[skill]] ?? ""}</span>
            <span className="ddb-skill__dot" aria-hidden />
            <span className="ddb-skill__name">{skillLabel(skill)}</span>
            <span className="ddb-skill__value">
              {render(`skill:${skill}`, value.value, `Навичка ${skillLabel(skill)}`)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Володіння, згруповані як в аркуші: броня, зброя, інструменти, мови. */
const PROFICIENCY_GROUPS: { kind: string; title: string }[] = [
  { kind: "armor", title: "Броня" },
  { kind: "weapon", title: "Зброя" },
  { kind: "tool", title: "Інструменти" },
  { kind: "language", title: "Мови" },
];

export function ProficiencyGroups({
  proficiencies,
}: {
  proficiencies: SheetViewPayload["proficiencies"];
}) {
  const groups = PROFICIENCY_GROUPS.map((group) => {
    const values: string[] = [];
    for (const item of proficiencies) {
      if (item.kind !== group.kind) continue;
      // Джерела бувають різні, значення — те саме: «легка броня» з класу
      // та з передісторії не має друкуватись двічі.
      if (values.includes(item.value)) continue;
      values.push(item.value);
    }
    return { ...group, values };
  }).filter((group) => group.values.length);

  if (!groups.length) return <p className="hint">—</p>;

  return (
    <div className="ddb-prof">
      {groups.map((group) => (
        <div key={group.kind} className="ddb-prof__group">
          <span className="ddb-prof__title">{group.title}</span>
          <span className="ddb-prof__values">
            {group.values.map((value) => proficiencyValue(group.kind, value)).join(" · ")}
          </span>
        </div>
      ))}
    </div>
  );
}
