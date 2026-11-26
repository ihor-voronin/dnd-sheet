/** Блоки листа, які показуються і в огляді, і у власній вкладці.
 *
 * Огляд у дусі DDB — це дашборд: ліва колонка з характеристиками й навичками,
 * права з боєм, атаками, чаруванням і уміннями. Щоб огляд не дублював розмітку
 * вкладок, спільні шматки живуть тут і приймають лише дані (та, де треба,
 * один колбек на зміну стану).
 */

import { Counter } from "./editing";
import {
  ABILITY_SHORT,
  PROFICIENCY_LABELS,
  abilityLabel,
  castingTimeLabel,
  damageTypeLabel,
  durationLabel,
  modifierLabel,
  proficiencyValue,
  rangeLabel,
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

/** Закляття, доступні просто зараз: заговори й підготовлені (або всі знані,
 * якщо клас не готує). Саме цього бракувало вкладці «Дії»: атаки були, а
 * чарування — ні. */
export function ActionSpells({
  spells,
  casting,
}: {
  spells: SheetViewPayload["spells"];
  casting: SheetViewPayload["spellcasting"];
}) {
  if (!casting.classes.length) return <p className="hint">Персонаж не чарує.</p>;

  const prepares = new Map(casting.classes.map((item) => [item.key, item.prepares]));
  const available = spells
    .filter(
      (spell) =>
        spell.level === 0 ||
        spell.prepared ||
        spell.always_prepared ||
        (spell.class_key ? prepares.get(spell.class_key) === false : false),
    )
    .sort((left, right) => left.level - right.level || left.name_en.localeCompare(right.name_en));

  if (!available.length) {
    return (
      <p className="hint">
        Немає доступних закляттів: оберіть їх у візарді або підготуйте після відпочинку.
      </p>
    );
  }

  const groups = new Map<number, typeof available>();
  for (const spell of available) {
    const bucket = groups.get(spell.level);
    if (bucket) bucket.push(spell);
    else groups.set(spell.level, [spell]);
  }

  return (
    <div className="action-spells">
      {Array.from(groups.entries()).map(([level, list]) => (
        <div key={level} className="action-spells__group">
          <h4 className="action-spells__head">
            {level === 0 ? "Заговори" : `${level} рівень`}
            <span>{list.length}</span>
          </h4>
          <ul className="action-spells__list">
            {list.map((spell) => {
              const meta = [
                castingTimeLabel(spell.casting_time),
                rangeLabel(spell.range),
                durationLabel(spell.duration),
              ].filter(Boolean);
              return (
                <li key={`${spell.name_en}-${spell.source}`} className="action-spell">
                  <span className="action-spell__name">{spell.name_en}</span>
                  {spell.always_prepared ? (
                    <span className="action-spell__tag">завжди</span>
                  ) : null}
                  {meta.length ? (
                    <span className="action-spell__meta">{meta.join(" · ")}</span>
                  ) : null}
                  <span className="action-spell__effects">
                    {spell.damage ? (
                      <span className="action-chip action-chip--damage">
                        {spell.damage.dice} {damageTypeLabel(spell.damage.type)}
                      </span>
                    ) : null}
                    {spell.save ? (
                      <span className="action-chip">
                        рятунок {ABILITY_SHORT[spell.save] ?? spell.save}
                      </span>
                    ) : null}
                    {spell.attack_roll ? <span className="action-chip">атака закляттям</span> : null}
                    {spell.concentration ? (
                      <span className="action-chip action-chip--quiet">концентрація</span>
                    ) : null}
                    {spell.ritual ? (
                      <span className="action-chip action-chip--quiet">ритуал</span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
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
