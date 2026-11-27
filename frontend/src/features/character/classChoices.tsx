/** Вибори класу: бойовий стиль, втаємничення, метамагія, прийоми, улюблений ворог.
 *
 * Скільки обирати і з чого — каже сервер (`sheet.class_choices`): кількість — з
 * рівнів класу й підкласу, варіанти — з довідника. Тут лише вибір і збереження.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { fetchFeats } from "../../api";
import { ABILITY_LABELS, DAMAGE_TYPE_LABELS, LANGUAGE_LABELS, TOOL_LABELS } from "../../labels";
import type { ClassChoiceGroup, SheetViewPayload } from "../wizard/types";

import { FeatPicker } from "./LevelUp";
import { featLabel, itemLabel, withEnglish } from "./uk";

const GROUP_LABELS: Record<string, string> = {
  "Fighting Style": "Бойовий стиль",
  "Eldritch Invocations": "Містичні виклики",
  "Pact Boon": "Дар угоди",
  Metamagic: "Метамагія",
  Maneuvers: "Маневри",
  Infusions: "Наповнення",
  "Favored Enemy": "Улюблений ворог",
  "Natural Explorer": "Природжений дослідник",
  "Circle Terrain": "Місцевість кола",
  // вибори рис і бойових стилів
  "Skills or Tools": "Навички або інструменти",
  Skill: "Навичка",
  Tool: "Інструмент",
  Language: "Мова",
  Languages: "Мови",
  Weapons: "Зброя",
  "Spell Class": "Клас заклять",
  Cantrips: "Заговори",
  Cantrip: "Заговір",
  "1st-level Spell": "Закляття 1 рівня",
  Rituals: "Ритуали",
  "Damage Type": "Тип урону",
  "Copied Rituals": "Переписані ритуали",
  Skills: "Навички",
  "Skill or Language": "Навичка або мова",
  "Magical Secrets": "Магічні таємниці",
  "Mystic Arcanum (6th level)": "Містичний арканум (6 рівень)",
  "Mystic Arcanum (7th level)": "Містичний арканум (7 рівень)",
  "Mystic Arcanum (8th level)": "Містичний арканум (8 рівень)",
  "Mystic Arcanum (9th level)": "Містичний арканум (9 рівень)",
  "Spell Mastery (1st level)": "Майстерність заклять (1 рівень)",
  "Spell Mastery (2nd level)": "Майстерність заклять (2 рівень)",
  "Signature Spells": "Фірмові закляття",
  "Additional Magical Secrets": "Додаткові магічні таємниці",
  "Hunter's Prey": "Здобич мисливця",
  "Defensive Tactics": "Захисна тактика",
  Multiattack: "Мультиатака",
  "Superior Hunter's Defense": "Вищий захист мисливця",
  "Totem Spirit": "Тотемний дух",
  "Aspect of the Beast": "Аспект звіра",
  "Totemic Attunement": "Тотемне налаштування",
  "Dragon Ancestor": "Драконячий предок",
  "Storm Aura": "Аура бурі",
  "Elemental Disciplines": "Стихійні дисципліни",
  "Arcane Shot": "Арканний постріл",
  Runes: "Руни",
};

/** Хто дав вибір — для підказки «… дає ще N на вибір». */
const ORIGIN_GIVES: Record<string, string> = {
  feat: "Риса дає",
  style: "Бойовий стиль дає",
  sub: "Підклас дає",
  boon: "Дар угоди дає",
  feature: "Вміння класу дає",
  inv: "Виклик дає",
};

/** Класи, з яких риси беруть закляття. */
const CLASS_LABELS: Record<string, string> = {
  artificer: "Артифіцер",
  bard: "Бард",
  cleric: "Жрець",
  druid: "Друїд",
  sorcerer: "Чародій",
  warlock: "Чаклун",
  wizard: "Маг",
};

/** Книги поза PHB: опційні варіанти, ведучий може їх не дозволяти. */
const SOURCE_TAGS: Record<string, string> = { tcoe: "Таша", xgte: "Ксанатар" };

type Option = ClassChoiceGroup["options"][number];
/** Назва варіанта: переклад із сервера, далі словники інтерфейсу (інструменти, мови, зброя). */
const optionLabel = (option: Option) => {
  if (option.name_uk) return withEnglish(option.name_en, option.name_uk);
  const key = option.name_en.toLowerCase();
  const local = TOOL_LABELS[key] ?? LANGUAGE_LABELS[key] ?? DAMAGE_TYPE_LABELS[key] ?? CLASS_LABELS[key];
  return local ? withEnglish(option.name_en, local) : itemLabel(option.name_en);
};

/** Підпис групи: «Бойовий стиль», а для риси — «Умілий (Skilled): Навички або інструменти». */
function groupLabel(group: ClassChoiceGroup): string {
  const label = withEnglish(group.group, GROUP_LABELS[group.group]);
  return group.origin ? `${group.origin.name_uk}: ${label}` : label;
}

function ChoiceGroup({
  group,
  busy,
  onSave,
}: {
  group: ClassChoiceGroup;
  busy: boolean;
  onSave: (key: string, values: string[]) => Promise<unknown>;
}) {
  const [picked, setPicked] = useState<string[]>(group.chosen);
  const [open, setOpen] = useState(!group.open_ended && group.chosen.length < group.slots);
  const [query, setQuery] = useState("");
  useEffect(() => setPicked(group.chosen), [group.chosen]);

  const pending = group.open_ended ? 0 : group.slots - group.chosen.length;
  const dirty = picked.join("|") !== group.chosen.join("|");
  const label = groupLabel(group);
  const text = new Map(group.options.map((option) => [option.name_en, option]));
  // Довгі списки (Магічні таємниці — сотні заклять): пошук і перші 40 збігів.
  const searchable = group.options.length > 30;
  const needle = query.trim().toLocaleLowerCase();
  const matching = group.options.filter(
    (option) =>
      !needle ||
      option.name_en.toLocaleLowerCase().includes(needle) ||
      (option.name_uk ?? "").toLocaleLowerCase().includes(needle),
  );
  const shown = searchable
    ? [
        ...group.options.filter((option) => picked.includes(option.name_en)),
        ...matching.filter((option) => !picked.includes(option.name_en)).slice(0, 40),
      ]
    : group.options;

  function toggle(value: string) {
    setPicked((current) => {
      if (current.includes(value)) return current.filter((item) => item !== value);
      if (current.length >= group.slots) return current;
      return [...current, value];
    });
  }

  return (
    <div className={`expertise${pending > 0 ? " expertise--pending" : ""}`}>
      <p className="expertise__head">
        {label}: {group.open_ended ? `обрано ${group.chosen.length}` : `${group.chosen.length} з ${group.slots}`}
        {group.chosen.length
          ? ` — ${group.chosen.map((name) => (text.get(name) ? optionLabel(text.get(name)!) : name)).join(", ")}`
          : ""}
        {!open ? (
          <>
            {" "}
            <button type="button" className="link-button" onClick={() => setOpen(true)}>
              змінити
            </button>
          </>
        ) : null}
      </p>
      {pending > 0 ? (
        <p className="hint hint--warn">
          {group.origin ? (ORIGIN_GIVES[group.origin.kind] ?? "Дає") : "Рівні класу дають"} ще {pending} на вибір.
          Наведіть на варіант, щоб прочитати опис; сірі варіанти потребують передумови або вже є у персонажа.
        </p>
      ) : null}
      {open && !group.options.length ? (
        <p className="hint">Спершу оберіть клас заклять цієї риси — тоді тут з’явиться його список.</p>
      ) : null}
      {open && group.options.length ? (
        <>
          {searchable ? (
            <label className="search-field">
              <span className="visually-hidden">Пошук варіанта</span>
              <input
                type="search"
                value={query}
                placeholder={`Пошук серед ${group.options.length}: «Fireball», «Вогняна куля»…`}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          ) : null}
          <div className="chip-row">
            {shown.map((option) => (
              <button
                key={option.name_en}
                type="button"
                className={`chip ${picked.includes(option.name_en) ? "chip--active" : ""}`}
                aria-pressed={picked.includes(option.name_en)}
                title={[
                  option.locked ? `Недоступно: ${option.locked}` : "",
                  option.prerequisite ? `Передумова (prerequisite): ${option.prerequisite}` : "",
                  option.text_uk || option.text_en,
                ]
                  .filter(Boolean)
                  .join("\n\n")}
                disabled={
                  (!picked.includes(option.name_en) && picked.length >= group.slots) ||
                  (Boolean(option.locked) && !picked.includes(option.name_en))
                }
                onClick={() => toggle(option.name_en)}
              >
                {optionLabel(option)}
                {option.source && SOURCE_TAGS[option.source] ? (
                  <small className="chip__tag"> {SOURCE_TAGS[option.source]}</small>
                ) : null}
              </button>
            ))}
          </div>
          {searchable && matching.length > 40 ? (
            <p className="hint">Показано 40 з {matching.length} — уточніть пошук.</p>
          ) : null}
          {picked.map((name) =>
            text.get(name)?.text_en ? (
              <p key={name} className="hint">
                <strong>{optionLabel(text.get(name)!)}.</strong> {text.get(name)?.text_uk || text.get(name)?.text_en}
              </p>
            ) : null,
          )}
          <div className="inline-row">
            <button
              type="button"
              className="button button--primary"
              disabled={busy || !dirty}
              onClick={() =>
                void onSave(group.key, picked).then(() => {
                  if (group.open_ended || picked.length >= group.slots) setOpen(false);
                })
              }
            >
              Зберегти ({group.open_ended ? picked.length : `${picked.length} з ${group.slots}`})
            </button>
            {group.open_ended || group.chosen.length >= group.slots ? (
              <button type="button" className="link-button" onClick={() => setOpen(false)}>
                Скасувати
              </button>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

export function ClassChoices({
  groups,
  busy,
  onSave,
}: {
  groups: ClassChoiceGroup[];
  busy: boolean;
  onSave: (key: string, values: string[]) => Promise<unknown>;
}) {
  return (
    <>
      {groups.map((group) => (
        <ChoiceGroup key={group.key} group={group} busy={busy} onSave={onSave} />
      ))}
    </>
  );
}

/** Книга виду: від неї залежить кістка природної зброї (табаксі VGM 1d4, MPMM 1d6). */
export function SpeciesSource({
  value,
  busy,
  onSave,
}: {
  value: NonNullable<SheetViewPayload["species_source"]>;
  busy: boolean;
  onSave: (source: string | null) => Promise<unknown>;
}) {
  const current = value.chosen ?? value.default;
  return (
    <div className="expertise">
      <p className="expertise__head">Книга виду: {current}</p>
      <p className="hint">Від книги залежить кістка природної зброї ({value.weapon}).</p>
      <div className="chip-row">
        {value.options.map((option) => (
          <button
            key={option.source}
            type="button"
            className={`chip ${current === option.source ? "chip--active" : ""}`}
            aria-pressed={current === option.source}
            disabled={busy || current === option.source}
            onClick={() => void onSave(option.source === value.default ? null : option.source)}
          >
            {option.source} — {option.die}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Риса виду на 1 рівні: варіантна людина й власна лінія (PHB, p. 31; TCoE, p. 8). */
export function SpeciesFeat({
  value,
  busy,
  onSave,
}: {
  value: NonNullable<SheetViewPayload["species_feat"]>;
  busy: boolean;
  onSave: (featKey: string, ability: string | null) => Promise<unknown>;
}) {
  const [open, setOpen] = useState(!value.chosen);
  const [featId, setFeatId] = useState<string | null>(value.chosen);
  const [ability, setAbility] = useState<string | null>(value.ability);
  const feats = useQuery({ queryKey: ["feats"], queryFn: fetchFeats, enabled: open || Boolean(value.chosen) });
  useEffect(() => {
    setFeatId(value.chosen);
    setAbility(value.ability);
  }, [value.chosen, value.ability]);

  const chosenName = (() => {
    if (!value.chosen) return null;
    const entry = feats.data?.find((feat) => feat.id === value.chosen);
    return entry ? withEnglish(entry.name_en, entry.name_uk ?? featLabel(entry.name_en)) : value.chosen;
  })();
  const abilities = featId ? (value.feat_abilities[featId] ?? []) : [];

  return (
    <div className={`expertise${value.chosen ? "" : " expertise--pending"}`}>
      <p className="expertise__head">
        Риса виду: {chosenName ?? "не обрано"}
        {value.ability ? ` (+1 ${ABILITY_LABELS[value.ability] ?? value.ability})` : ""}
        {!open ? (
          <>
            {" "}
            <button type="button" className="link-button" onClick={() => setOpen(true)}>
              змінити
            </button>
          </>
        ) : null}
      </p>
      {!value.chosen ? (
        <p className="hint hint--warn">
          Варіантна людина й власна лінія беруть рису на 1 рівні. Вибори риси (навички, закляття) з’являться нижче,
          щойно її оберете.
        </p>
      ) : null}
      {open ? (
        <>
          {feats.isPending ? <p className="meta">Читаємо риси…</p> : null}
          <FeatPicker
            feats={feats.data ?? []}
            value={featId}
            onChange={(id) => {
              setFeatId(id);
              setAbility(value.feat_abilities[id]?.[0] ?? null);
            }}
          />
          {abilities.length > 1 ? (
            <label className="field">
              <span>Риса дає +1 до характеристики — оберіть яку</span>
              <select className="select" value={ability ?? ""} onChange={(event) => setAbility(event.target.value)}>
                {abilities.map((code) => (
                  <option key={code} value={code}>
                    {ABILITY_LABELS[code] ?? code}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="inline-row">
            <button
              type="button"
              className="button button--primary"
              disabled={busy || !featId || (featId === value.chosen && ability === value.ability)}
              onClick={() =>
                featId && void onSave(featId, abilities.length ? ability : null).then(() => setOpen(false))
              }
            >
              Зберегти рису
            </button>
            {value.chosen ? (
              <button type="button" className="link-button" onClick={() => setOpen(false)}>
                Скасувати
              </button>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
