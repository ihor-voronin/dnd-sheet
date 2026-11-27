/** Вибори класу: бойовий стиль, втаємничення, метамагія, прийоми, улюблений ворог.
 *
 * Скільки обирати і з чого — каже сервер (`sheet.class_choices`): слоти — з
 * рівнів класу й підкласу, варіанти — з довідника. Тут лише вибір і збереження.
 */

import { useEffect, useState } from "react";

import type { ClassChoiceGroup } from "../wizard/types";

const GROUP_LABELS: Record<string, string> = {
  "Fighting Style": "Бойовий стиль",
  "Eldritch Invocations": "Таємні втаємничення",
  "Pact Boon": "Дар пакту",
  Metamagic: "Метамагія",
  Maneuvers: "Прийоми майстра битви",
  Infusions: "Вливання",
  "Favored Enemy": "Улюблений ворог",
  "Natural Explorer": "Улюблена місцевість",
};

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
  const [open, setOpen] = useState(group.chosen.length < group.slots);
  useEffect(() => setPicked(group.chosen), [group.chosen]);

  const pending = group.slots - group.chosen.length;
  const dirty = picked.join("|") !== group.chosen.join("|");
  const label = GROUP_LABELS[group.group] ?? group.group;
  const text = new Map(group.options.map((option) => [option.name_en, option]));

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
        {label}: {group.chosen.length} з {group.slots}
        {group.chosen.length ? ` — ${group.chosen.join(", ")}` : ""}
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
          Рівні класу дають ще {pending} на вибір. Наведіть на варіант, щоб прочитати опис.
        </p>
      ) : null}
      {open ? (
        <>
          <div className="chip-row">
            {group.options.map((option) => (
              <button
                key={option.name_en}
                type="button"
                className={`chip ${picked.includes(option.name_en) ? "chip--active" : ""}`}
                aria-pressed={picked.includes(option.name_en)}
                title={[option.prerequisite ? `Передумова: ${option.prerequisite}` : "", option.text_en]
                  .filter(Boolean)
                  .join("\n\n")}
                disabled={!picked.includes(option.name_en) && picked.length >= group.slots}
                onClick={() => toggle(option.name_en)}
              >
                {option.name_en}
              </button>
            ))}
          </div>
          {picked.map((name) =>
            text.get(name)?.text_en ? (
              <p key={name} className="hint">
                <strong>{name}.</strong> {text.get(name)?.text_en}
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
                  if (picked.length >= group.slots) setOpen(false);
                })
              }
            >
              Зберегти ({picked.length} з {group.slots})
            </button>
            {group.chosen.length >= group.slots ? (
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
