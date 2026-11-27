/**
 * Картка персонажа у «Моїх персонажах» (головна сторінка й список).
 *
 * За столом гравець шукає свого героя не за іменем, а за «хто це»: гірський
 * дворф-маг 4 рівня. Тому картка — як шапка листа в мініатюрі: ініціали,
 * рівень у шестикутнику, вид і передісторія, класи з підкласами, і стан —
 * хіти смужкою (поранений герой видно ще до відкриття) та КЗ.
 */
import type { CharacterRosterEntry } from "../../api";
import { subclassLabel } from "../../labels";
import { initials } from "../character/sheetParts";
import { speciesLabel, termLabel, ukSubclass, withEnglish } from "../character/uk";

/** «Маг (Wizard)» → ["Маг", "Wizard"]: українська — головна, англійська — дрібно поруч. */
function splitLabel(label: string): [string, string | null] {
  const match = /^(.*?) [(—] ?(.+?)\)?$/.exec(label);
  if (!match || !/[а-яіїєґʼ]/i.test(match[1])) return [label, null];
  return [match[1], match[2]];
}

function hpState(current: number, maximum: number): "fine" | "bloodied" | "down" {
  if (current <= 0) return "down";
  return current * 2 <= maximum ? "bloodied" : "fine";
}

export function CharacterCard({ entry }: { entry: CharacterRosterEntry }) {
  const speciesKey = entry.species?.subspecies ?? entry.species?.name_en;
  const [speciesUk, speciesEn] = speciesKey ? splitLabel(speciesLabel(speciesKey)) : ["вид не вказано", null];
  const [backgroundUk] = entry.background ? splitLabel(termLabel(entry.background.name_en)) : [""];
  const hp = entry.hit_points;
  const state = hp ? hpState(hp.current, hp.maximum) : "fine";
  const share = hp && hp.maximum > 0 ? Math.max(0, Math.min(1, hp.current / hp.maximum)) : 0;

  return (
    <a className="roster-card" href={`#/character/${encodeURIComponent(entry.id)}`}>
      <span className="roster-card__portrait" aria-hidden="true">
        {initials(entry.name)}
      </span>

      <span className="roster-card__head">
        <span className="roster-card__name">{entry.name || "Без імені"}</span>
        <span className="roster-card__origin">
          {speciesUk}
          {speciesEn ? <span className="roster-card__en"> {speciesEn}</span> : null}
          {backgroundUk ? <> · {backgroundUk}</> : null}
        </span>
      </span>

      <span className="roster-card__level" aria-label={`Рівень ${entry.total_level}`}>
        <span className="roster-card__level-num">{entry.total_level}</span>
        <span className="roster-card__level-cap">рівень</span>
      </span>

      <span className="roster-card__classes">
        {entry.classes.length ? (
          entry.classes.map((item) => {
            const [classUk, classEn] = splitLabel(termLabel(item.name_en));
            const subclass = item.subclass
              ? splitLabel(
                  withEnglish(
                    item.subclass_name ?? subclassLabel(item.subclass),
                    item.subclass_name_uk ?? ukSubclass(item.subclass),
                  ),
                )[0]
              : null;
            return (
              <span key={item.key} className="roster-class">
                <span className="roster-class__name">
                  {classUk} {item.level}
                </span>
                {classEn ? <span className="roster-card__en">{classEn}</span> : null}
                {subclass ? <span className="roster-class__sub">{subclass}</span> : null}
              </span>
            );
          })
        ) : (
          <span className="roster-class roster-class__sub">клас не вказано</span>
        )}
      </span>

      {hp ? (
        <span className="roster-card__vitals">
          <span className={`roster-hp roster-hp--${state}`}>
            <span className="roster-hp__bar" aria-hidden="true">
              <span className="roster-hp__fill" style={{ width: `${share * 100}%` }} />
            </span>
            <span className="roster-hp__text">
              Хіти <strong>{hp.current}</strong>/{hp.maximum}
              {hp.temporary ? <span className="roster-hp__temp"> +{hp.temporary} тимч.</span> : null}
              {state === "down" ? " · без тями" : state === "bloodied" ? " · поранений" : ""}
            </span>
          </span>
          {entry.armor_class !== undefined ? (
            <span className="roster-ac" title="Клас захисту">
              КЗ <strong>{entry.armor_class}</strong>
            </span>
          ) : null}
        </span>
      ) : null}
    </a>
  );
}
