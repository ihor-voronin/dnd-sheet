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
  abilityGenitive,
  abilityLabel,
  castingTimeLabel,
  damageTypeLabel,
  durationLabel,
  modifierLabel,
  proficiencyValue,
  rangeLabel,
  schoolLabel,
} from "../../labels";
import type { SheetViewPayload } from "../wizard/types";
import {
  componentsLabel,
  featureLabel,
  featureText,
  itemLabel,
  proficiencySourceLabel,
  spellHigher,
  spellLabel,
  spellText,
  termLabel,
  weaponDamage,
  weaponNotes,
} from "./uk";

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
            <th scope="row">{itemLabel(attack.name_en)}</th>
            <td>{modifierLabel(attack.attack_bonus)}</td>
            <td>{weaponDamage(attack.damage)}</td>
            <td>{abilityLabel(attack.ability)}</td>
            <td className="short">{weaponNotes(attack.notes) || "—"}</td>
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
                  <span className="action-spell__name">{spellLabel(spell.name_en)}</span>
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

/** Ячейки заклять: заповнена клітинка = доступна, натиск гасить/повертає одну. */
function SlotTrack({
  label,
  title,
  used,
  total,
  onChange,
}: {
  label: string;
  title: string;
  used: number;
  total: number;
  onChange: (used: number) => void;
}) {
  const remaining = total - used;
  return (
    <div className="slot-track">
      <span className="slot-track__label">{label}</span>
      <span className="slot-track__boxes" role="group" aria-label={title}>
        {Array.from({ length: total }, (_, index) => {
          const spent = index < used;
          return (
            <button
              key={index}
              type="button"
              className={`slot-track__box ${spent ? "is-spent" : "is-ready"}`}
              aria-pressed={!spent}
              aria-label={`${title}: ячейка ${index + 1} — ${
                spent ? "витрачена" : "доступна"
              }`}
              title={spent ? `${title}: повернути ячейку` : `${title}: витратити ячейку`}
              onClick={() => onChange(spent ? used - 1 : used + 1)}
            />
          );
        })}
      </span>
      <span className="slot-track__count">
        {remaining} / {total}
      </span>
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
            {termLabel(item.name_en)}: ОС порятунку {item.save_dc}, атака{" "}
            {modifierLabel(item.attack_bonus)} (від {abilityGenitive(item.ability)})
            {item.prepares
              ? `, готує до ${item.prepared_limit}`
              : `, знає до ${item.spells_known_limit ?? 0}`}
          </li>
        ))}
      </ul>
      <div className="spell-slots">
        {Object.entries(resources.slots)
          .filter(([, resource]) => resource.total > 0)
          .map(([level, resource]) => (
            <SlotTrack
              key={level}
              label={`${level} рівень`}
              title={`слоти ${level} рівня`}
              used={resource.used}
              total={resource.total}
              onChange={(used) => onSlotsUsed(level, used)}
            />
          ))}
        {resources.pact ? (
          <SlotTrack
            label="Pact Magic"
            title="слоти Pact Magic"
            used={resources.pact.used}
            total={resources.pact.total}
            onChange={onPactUsed}
          />
        ) : null}
        {Object.values(resources.slots).some((resource) => resource.total > 0) ||
        resources.pact ? (
          <p className="slot-hint">клік по ячейці витрачає слот, повторний — повертає</p>
        ) : null}
      </div>
    </>
  );
}

export function SpellsKnownList({ spells }: { spells: SheetViewPayload["spells"] }) {
  if (!spells.length) return <p className="hint">—</p>;

  const sorted = [...spells].sort(
    (left, right) => left.level - right.level || left.name_en.localeCompare(right.name_en),
  );
  const groups = new Map<number, typeof sorted>();
  for (const spell of sorted) {
    const bucket = groups.get(spell.level);
    if (bucket) bucket.push(spell);
    else groups.set(spell.level, [spell]);
  }

  return (
    <div className="spell-known">
      {Array.from(groups.entries()).map(([level, list]) => (
        <section key={level} className="spell-group">
          <h4 className="spell-group__head">
            <span>{level === 0 ? "Заговори" : `${level} рівень`}</span>
            <span className="spell-group__count">{list.length}</span>
          </h4>
          <ul className="spell-group__list">
            {list.map((spell) => {
              const meta = [
                castingTimeLabel(spell.casting_time),
                rangeLabel(spell.range),
                durationLabel(spell.duration),
              ].filter(Boolean);
              return (
                <li key={`${spell.name_en}-${spell.source}`}>
                  <details className="spell">
                    <summary className="spell__summary">
                      <span className="spell__name">{spellLabel(spell.name_en)}</span>
                      <span className="spell__tags">
                        {spell.school ? (
                          <span className="spell-tag">{schoolLabel(spell.school)}</span>
                        ) : null}
                        {spell.always_prepared ? (
                          <span className="spell-tag spell-tag--gold">завжди</span>
                        ) : spell.prepared ? (
                          <span className="spell-tag">підготовлене</span>
                        ) : null}
                        {spell.source === "species" ? (
                          <span className="spell-tag">від виду</span>
                        ) : spell.source === "subclass" ? (
                          <span className="spell-tag">від підкласу</span>
                        ) : null}
                      </span>
                      <span className="spell__chevron" aria-hidden>
                        ▾
                      </span>
                    </summary>
                    <div className="spell__body">
                      {meta.length ? <p className="spell__meta">{meta.join(" · ")}</p> : null}
                      {spell.components ? (
                        <p className="spell__components">Компоненти: {componentsLabel(spell.components)}</p>
                      ) : null}
                      <div className="spell__effects">
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
                        {spell.attack_roll ? (
                          <span className="action-chip">атака закляттям</span>
                        ) : null}
                        {spell.concentration ? (
                          <span className="action-chip action-chip--quiet">концентрація</span>
                        ) : null}
                        {spell.ritual ? (
                          <span className="action-chip action-chip--quiet">ритуал</span>
                        ) : null}
                      </div>
                      <RuleText text={spellText(spell.name_en, spell.description)} />
                      {spell.at_higher_levels ? (
                        <div className="spell__higher">
                          <span className="spell__higher-label">На вищих рівнях</span>
                          <RuleText text={spellHigher(spell.name_en, spell.at_higher_levels)} />
                        </div>
                      ) : null}
                    </div>
                  </details>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function FeaturesList({ features }: { features: SheetViewPayload["features"] }) {
  if (!features.length) return <p className="hint">—</p>;
  return (
    <ul className="feature-list feature-list--rich">
      {features.map((feature) => (
        <li key={`${feature.class_key}-${feature.name_en}-${feature.source ?? "class"}`}>
          <details className="feature">
            <summary className="feature__summary">
              <span className="feature-name">{featureLabel(feature.name_en)}</span>
              <span className="feature-meta">
                {feature.source === "subclass" && feature.subclass_name
                  ? `${termLabel(feature.subclass_name)} · `
                  : ""}
                {termLabel(feature.class_name)}, {feature.level} рівень
              </span>
              <span className="feature__chevron" aria-hidden>
                ▾
              </span>
            </summary>
            <RuleText text={featureText(feature.name_en, feature.description)} />
          </details>
        </li>
      ))}
    </ul>
  );
}

/** Риси (feats): не клас і не підклас, тому окремим списком. */
export function FeatsList({
  feats,
}: {
  feats: NonNullable<SheetViewPayload["feat_details"]>;
}) {
  if (!feats.length) return null;
  return (
    <ul className="feature-list feature-list--rich">
      {feats.map((feat) => (
        <li key={feat.key}>
          <details className="feature">
            <summary className="feature__summary">
              <span className="feature-name">{feat.name_uk || feat.name_en}</span>
              <span className="feature-meta">
                риса{feat.source_id ? ` · ${feat.source_id}` : ""}
              </span>
              <span className="feature__chevron" aria-hidden>
                ▾
              </span>
            </summary>
            <RuleText text={feat.description} />
          </details>
        </li>
      ))}
    </ul>
  );
}

/** Текст правила як є: абзаци, списки, курсивний підпис рівня. */
export function RuleText({ text }: { text: string }) {
  if (!text.trim()) return <p className="hint">Опис недоступний.</p>;
  const blocks = text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
  return (
    <div className="feature-text">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim());
        const heading = block.match(/^#{3,5}\s+(.+)$/);
        if (heading) {
          return (
            <h4 key={index} className="feature-text__head">
              {cleanMarkdown(heading[1])}
            </h4>
          );
        }
        const table = markdownTable(lines);
        if (table) {
          return (
            <table key={index} className="feature-table">
              <thead>
                <tr>
                  {table.header.map((cell, position) => (
                    <th key={position}>{cleanMarkdown(cell)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row, position) => (
                  <tr key={position}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cleanMarkdown(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }
        if (lines.every((line) => line.startsWith("- "))) {
          return (
            <ul key={index}>
              {lines.map((line, position) => (
                <li key={position}>{cleanMarkdown(line.slice(2))}</li>
              ))}
            </ul>
          );
        }
        if (/^\*\d+(?:st|nd|rd|th)-level .*\*$/i.test(block)) {
          return (
            <p key={index} className="feature-text__level">
              {cleanMarkdown(block)}
            </p>
          );
        }
        return <p key={index}>{cleanMarkdown(block)}</p>;
      })}
    </div>
  );
}

function cleanMarkdown(text: string): string {
  return text.replace(/\*\*/g, "").replace(/\*/g, "");
}

/** Markdown-таблиця: рядки з `|`, другий рядок — роздільник `| --- |`. */
function markdownTable(
  lines: string[],
): { header: string[]; rows: string[][] } | null {
  const pipes = lines.filter(Boolean);
  if (pipes.length < 2) return null;
  if (!pipes.every((line) => line.startsWith("|") && line.endsWith("|"))) return null;
  const cells = pipes.map((line) =>
    line
      .slice(1, -1)
      .split("|")
      .map((cell) => cell.trim()),
  );
  const separator = cells[1]?.every((cell) => /^:?-{2,}:?$/.test(cell));
  if (!separator) return null;
  return { header: cells[0], rows: cells.slice(2) };
}

/** Обмежені класові ресурси: Друге дихання, Кі, Канал божественності. */
export function FeatureResources({
  resources,
  disabled = false,
  onChange,
}: {
  resources: SheetViewPayload["feature_resources"];
  disabled?: boolean;
  onChange: (key: string, used: number) => void;
}) {
  if (!resources.length) return null;
  return (
    <div className="feature-resources">
      {resources.map((resource) => (
        <div key={resource.key} className="feature-resource">
          <span className="feature-resource__main">
            <span className="feature-resource__name">{featureLabel(resource.name_en)}</span>
            <span className="feature-resource__meta">
              {termLabel(resource.class_name)} ·{" "}
              {resource.recharge === "short"
                ? "короткий або довгий відпочинок"
                : "довгий відпочинок"}
            </span>
          </span>
          <Counter
            used={resource.used}
            total={resource.total}
            title={featureLabel(resource.name_en)}
            onChange={(used) => {
              if (disabled) return;
              onChange(resource.key, used);
            }}
          />
        </div>
      ))}
    </div>
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
              ({proficiencySourceLabel(item.source.kind, item.source.key)})
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
