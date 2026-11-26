/** Блоки листа, які показуються і в огляді, і у власній вкладці.
 *
 * Огляд у дусі DDB — це дашборд: ліва колонка з характеристиками й навичками,
 * права з боєм, атаками, чаруванням і уміннями. Щоб огляд не дублював розмітку
 * вкладок, спільні шматки живуть тут і приймають лише дані (та, де треба,
 * один колбек на зміну стану).
 */

import { Counter } from "./editing";
import {
  PROFICIENCY_LABELS,
  abilityLabel,
  modifierLabel,
  proficiencyValue,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";

export function AttacksTable({ attacks }: { attacks: SheetViewPayload["attacks"] }) {
  if (!attacks.length) {
    return (
      <p className="hint">
        Зброї немає. Додайте її в інвентар — бонус і урон порахуються з довідника.
      </p>
    );
  }
  return (
    <table className="ability-table ability-table--compact">
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
        {attacks.map((attack) => (
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
  );
}

export function CastingBlock({
  casting,
  resources,
  onSlotsUsed,
  onPactUsed,
}: {
  casting: SheetViewPayload["spellcasting"];
  resources: SheetViewPayload["resources"];
  onSlotsUsed: (level: string, used: number) => void;
  onPactUsed: (used: number) => void;
}) {
  if (!casting.classes.length) {
    return <p className="hint">Персонаж не чарує.</p>;
  }
  return (
    <>
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
        {Object.entries(resources.slots).map(([level, resource]) => (
          <span key={level} className="resource">
            {level} рівень
            <Counter
              used={resource.used}
              total={resource.total}
              title={`слоти ${level} рівня`}
              onChange={(used) => onSlotsUsed(level, used)}
            />
          </span>
        ))}
        {resources.pact ? (
          <span className="resource">
            Pact Magic
            <Counter
              used={resources.pact.used}
              total={resources.pact.total}
              title="слоти Pact Magic"
              onChange={onPactUsed}
            />
          </span>
        ) : null}
      </div>
    </>
  );
}

export function SpellsKnownList({ spells }: { spells: SheetViewPayload["spells"] }) {
  if (!spells.length) return <p className="hint">—</p>;
  return (
    <ul className="plain-list">
      {spells.map((spell) => (
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
  );
}

export function FeaturesList({ features }: { features: SheetViewPayload["features"] }) {
  if (!features.length) return <p className="hint">—</p>;
  return (
    <ul className="feature-list">
      {features.map((feature) => (
        <li key={`${feature.class_key}-${feature.name_en}`}>
          <span className="feature-name">{feature.name_en}</span>
          <span className="feature-meta">
            {feature.class_name}, {feature.level} рівень
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ProficienciesList({
  proficiencies,
  showSource = true,
}: {
  proficiencies: SheetViewPayload["proficiencies"];
  showSource?: boolean;
}) {
  if (!proficiencies.length) return <p className="hint">—</p>;
  return (
    <ul className="plain-list">
      {proficiencies.map((item, index) => (
        <li key={`${item.kind}-${item.value}-${index}`}>
          {PROFICIENCY_LABELS[item.kind] ?? item.kind}: {proficiencyValue(item.kind, item.value)}
          {showSource ? (
            <span className="short">
              {" "}
              ({item.source.kind}: {item.source.key})
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
