/** Вкладка «Дії»: атаки, закляття й ресурси, згруповані за типом дії.
 *
 * D&D Beyond показує тут не один список, а групи «Дії / Бонусні дії /
 * Реакції / Інше» і фільтри над ними. Ми робимо те саме, але компактними
 * рядками: назва й тип, дистанція, атака/ОС, урон, нотатки. Зброя, Удар без
 * зброї, доступні закляття й обмежені класові ресурси живуть в одній моделі,
 * тому фільтр «Обмежене» чи «Бонусна дія» просто відсіює рядки. Унизу
 * вкладки — згортваний довідник «Дії в бою»: загальні дії ходу, які не
 * залежать від арсеналу персонажа.
 */

import { useState } from "react";

import { damageTypeLabel, modifierLabel, rangeLabel, schoolLabel } from "../../labels";
import type { SheetFeatureResource, SheetSpell, SheetViewPayload } from "../wizard/types";
import { Counter } from "./editing";
import { RuleText } from "./panels";
import {
  componentsLabel,
  featureLabel,
  featureText,
  itemLabel,
  spellLabel,
  weaponDamage,
  weaponNotes,
} from "./uk";

type ActionType = "action" | "bonus" | "reaction" | "other";
type Filter = "all" | "attack" | ActionType | "limited";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Усі" },
  { id: "attack", label: "Атака" },
  { id: "action", label: "Дія" },
  { id: "bonus", label: "Бонусна дія" },
  { id: "reaction", label: "Реакція" },
  { id: "other", label: "Інше" },
  { id: "limited", label: "Обмежене" },
];

const GROUP_LABELS: Record<ActionType, string> = {
  action: "Дії",
  bonus: "Бонусні дії",
  reaction: "Реакції",
  other: "Інше",
};

/** Стандартні дії ходу: короткий переказ правила для памʼятки. */
const COMBAT: Record<ActionType, { name: string; hint: string }[]> = {
  action: [
    {
      name: "Атака",
      hint: "Одна атака зброєю або без неї; риси можуть давати більше. Замість атаки — Захват чи Штовханина.",
    },
    { name: "Ривок", hint: "Додатковий рух на відстань, що дорівнює швидкості, цього ходу." },
    {
      name: "Відхід",
      hint: "Рух без атак можливості від істот, яких ви покидаєте, до кінця ходу.",
    },
    {
      name: "Ухиляння",
      hint: "Атаки по вас — із завадою, рятівні кидки СПР — з перевагою; втрачається, якщо не можете діяти.",
    },
    {
      name: "Захват",
      hint: "Особлива атака: ціль рятується СИЛ або СПР; утримуєте її, доки не вивільниться.",
    },
    {
      name: "Допомога",
      hint: "Союзник дістає перевагу на атаку по цілі поруч або на перевірку чи рятівний кидок.",
    },
    {
      name: "Сховатися",
      hint: "Перевірка Скритності проти пасивної Спостережливості; потрібне укриття.",
    },
    {
      name: "Імпровізація",
      hint: "Будь-яка дія поза списком; чи можлива вона й що коштує — вирішує майстер.",
    },
    { name: "Вплив", hint: "Спроба переконати, обманути, залякати чи розважити істоту." },
    {
      name: "Магія",
      hint: "Чарування закляття з часом «1 дія»; бонусні дії та реакції — окремо.",
    },
    {
      name: "Готовність",
      hint: "Підготувати дію з умовою-тригером; виконується реакцією до початку вашого наступного ходу.",
    },
    {
      name: "Пошук",
      hint: "Перевірка МУД (Спостережливість) або ІНТ (Розслідування), щоб щось знайти.",
    },
    {
      name: "Штовханина",
      hint: "Особлива атака: ціль рятується СИЛ або СПР; відсуваєте на 5 фт або збиваєте з ніг.",
    },
    {
      name: "Вивчення",
      hint: "Перевірка ІНТ (Магія, Історія, Природа чи Релігія), щоб пригадати знання.",
    },
    {
      name: "Використання",
      hint: "Взаємодія з предметом; зазвичай раз за хід безкоштовно, далі — дія.",
    },
  ],
  bonus: [
    {
      name: "Двобійний бій",
      hint: "Легка зброя в одній руці й інша легка — додаткова атака бонусною дією.",
    },
  ],
  reaction: [
    {
      name: "Атака нагоди",
      hint: "Коли ворог виходить із вашої досяжності, ви можете вдарити його реакцією.",
    },
  ],
  other: [
    {
      name: "Взаємодія з предметом",
      hint: "Витягнути, покласти, відкрити — раз за хід безкоштовно; складніше — дією.",
    },
  ],
};

interface ActionRow {
  id: string;
  name: string;
  typeLabel: string;
  range: string;
  hit: string;
  damage: string;
  notes: string;
  actionType: ActionType;
  attack: boolean;
  limited?: boolean;
  description?: string;
  resource?: SheetFeatureResource;
}

function spellTime(spell: SheetSpell): ActionType {
  const text = (spell.casting_time ?? "").toLowerCase();
  if (text.includes("bonus action")) return "bonus";
  if (text.includes("reaction")) return "reaction";
  if (text.includes("action")) return "action";
  return "other";
}

function availableSpells(sheet: SheetViewPayload): SheetSpell[] {
  const prepares = new Map(sheet.spellcasting.classes.map((item) => [item.key, item.prepares]));
  return sheet.spells.filter(
    (spell) =>
      spell.level === 0 ||
      spell.prepared ||
      spell.always_prepared ||
      (spell.class_key ? prepares.get(spell.class_key) === false : false),
  );
}

function buildRows(sheet: SheetViewPayload): ActionRow[] {
  const rows: ActionRow[] = [];
  for (const [index, attack] of sheet.attacks.entries()) {
    rows.push({
      id: `weapon-${index}`,
      name: itemLabel(attack.name_en),
      typeLabel: "Зброя",
      range: rangeLabel(attack.range) || "—",
      hit: modifierLabel(attack.attack_bonus),
      damage: weaponDamage(attack.damage),
      notes: weaponNotes(attack.notes),
      actionType: "action",
      attack: true,
    });
  }

  const strength = sheet.abilities.str?.modifier ?? 0;
  const unarmedDamage =
    strength === 0
      ? "1 дробляча"
      : `1 ${strength > 0 ? "+" : "−"} ${Math.abs(strength)} дробляча`;
  rows.push({
    id: "unarmed",
    name: "Удар без зброї",
    typeLabel: "Дія",
    range: "5 фт",
    hit: modifierLabel(strength + sheet.proficiency_bonus),
    damage: unarmedDamage,
    notes: "захват або штовханина: рятунок СИЛ/СПР",
    actionType: "action",
    attack: true,
    description:
      "Можна вдарити (1 + модифікатор СИЛИ дроблячого урону), захопити ціль або " +
      "штовхнути її на 5 фт чи збити з ніг. Для захвату й штовханини ціль " +
      "рятується СИЛ або СПР (ОС 8 + бонус майстерності + СИЛ).",
  });

  const casters = sheet.spellcasting.classes;
  for (const spell of availableSpells(sheet)) {
    const caster = casters.find((item) => item.key === spell.class_key) ?? casters[0];
    const hit = spell.save
      ? `ОС ${caster?.save_dc ?? "—"}`
      : spell.attack_roll
        ? modifierLabel(caster?.attack_bonus ?? 0)
        : "—";
    const notes = [
      spell.components ? `компоненти ${componentsLabel(spell.components)}` : "",
      spell.concentration ? "концентрація" : "",
      spell.ritual ? "ритуал" : "",
      spell.school ? schoolLabel(spell.school) : "",
    ]
      .filter(Boolean)
      .join(" · ");
    rows.push({
      id: `spell-${spell.name_en}-${spell.source}`,
      name: spellLabel(spell.name_en),
      typeLabel: spell.level === 0 ? "Заговір" : `Закляття ${spell.level} рівня`,
      range: rangeLabel(spell.range) || "—",
      hit,
      damage: spell.damage
        ? `${spell.damage.dice} ${damageTypeLabel(spell.damage.type)}`
        : "—",
      notes,
      actionType: spellTime(spell),
      attack: Boolean(spell.attack_roll),
    });
  }

  for (const resource of sheet.feature_resources) {
    const feature = sheet.features.find((item) => item.name_en === resource.name_en);
    rows.push({
      id: `resource-${resource.key}`,
      name: featureLabel(resource.name_en, resource.name_uk ?? feature?.name_uk),
      typeLabel: "Обмежене",
      range: "—",
      hit: "—",
      damage: "—",
      notes: `відновлення: ${
        resource.recharge === "short" ? "короткий або тривалий" : "тривалий"
      } відпочинок`,
      actionType: resource.action,
      attack: false,
      limited: true,
      resource,
      description: featureText(
        resource.name_en,
        feature?.description,
        feature?.text_uk,
      ),
    });
  }

  return rows;
}

export function ActionPanel({
  sheet,
  onUseFeature,
}: {
  sheet: SheetViewPayload;
  onUseFeature: (key: string, used: number) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const rows = buildRows(sheet);

  const visible = (() => {
    if (filter === "all") return rows;
    if (filter === "attack") return rows.filter((row) => row.attack);
    if (filter === "limited") return rows.filter((row) => row.limited);
    return rows.filter((row) => row.actionType === filter);
  })();

  return (
    <div className="action-panel">
      <div className="action-panel__bar">
        <span className="action-panel__per">
          Атак за дію: <strong>{sheet.attacks_per_action}</strong>
        </span>
        <span className="action-panel__source">
          {sheet.attacks.length ? `${sheet.attacks.length} зброї` : "зброї немає"}
        </span>
      </div>

      <div className="action-filters" role="group" aria-label="Фільтр дій">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`action-filter ${filter === item.id ? "is-active" : ""}`}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {filter === "limited" ? (
        <section className="action-group">
          <h4 className="action-group__head">
            <span>Обмежені використання</span>
            <span className="action-group__count">{visible.length}</span>
          </h4>
          {visible.length ? (
            <ul className="action-list">
              {visible.map((row) => (
                <ActionRowView key={row.id} row={row} onUseFeature={onUseFeature} />
              ))}
            </ul>
          ) : (
            <p className="hint">У персонажа немає класових ресурсів.</p>
          )}
        </section>
      ) : (
        (Object.keys(GROUP_LABELS) as ActionType[]).map((type) => {
          const groupRows = visible.filter((row) => row.actionType === type);
          if (!groupRows.length) return null;
          return (
            <section key={type} className="action-group">
              <h4 className="action-group__head">
                <span>{GROUP_LABELS[type]}</span>
                <span className="action-group__count">{groupRows.length}</span>
              </h4>
              <ul className="action-list">
                {groupRows.map((row) => (
                  <ActionRowView key={row.id} row={row} onUseFeature={onUseFeature} />
                ))}
              </ul>
            </section>
          );
        })
      )}

      {filter !== "limited" && !visible.length ? (
        <p className="hint">
          За цим фільтром у персонажа нічого немає — загальні дії бою є в довіднику нижче.
        </p>
      ) : null}

      <details className="combat-ref">
        <summary className="combat-ref__head">
          <span className="combat-ref__title">Дії в бою</span>
          <span className="combat-ref__hint">
            загальний довідник: що взагалі можна робити в бою
          </span>
        </summary>
        <div className="combat-ref__body">
          {(Object.keys(GROUP_LABELS) as ActionType[]).map((type) => (
            <div key={type} className="combat-ref__group">
              <p className="combat-ref__label">{GROUP_LABELS[type]}</p>
              <ul className="combat-actions">
                {COMBAT[type].map((hint) => (
                  <li key={hint.name} className="combat-action">
                    <span className="combat-action__name">{hint.name}</span>
                    <span className="combat-action__hint">{hint.hint}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function ActionRowView({
  row,
  onUseFeature,
}: {
  row: ActionRow;
  onUseFeature: (key: string, used: number) => void;
}) {
  return (
    <li className={`action-row ${row.limited ? "is-limited" : ""}`}>
      <div className="action-row__head">
        <span className="action-row__name">{row.name}</span>
        <span className="action-row__type">{row.typeLabel}</span>
      </div>
      {row.resource ? (
        <div className="action-row__resource">
          <span className="action-row__recharge">{row.notes}</span>
          <Counter
            used={row.resource.used}
            total={row.resource.total}
            title={row.name}
            onChange={(used) => onUseFeature(row.resource!.key, used)}
          />
        </div>
      ) : (
        <div className="action-row__stats">
          <span>
            <em>Дистанція</em>
            {row.range}
          </span>
          <span>
            <em>Атака / ОС</em>
            {row.hit}
          </span>
          <span>
            <em>Урон</em>
            {row.damage}
          </span>
        </div>
      )}
      {row.resource ? null : row.notes ? (
        <p className="action-row__notes">{row.notes}</p>
      ) : null}
      {row.description ? (
        <details className="action-row__more">
          <summary>як працює</summary>
          <RuleText text={row.description} />
        </details>
      ) : null}
    </li>
  );
}
