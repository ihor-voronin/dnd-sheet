/** Експертиза плута й барда: вибір навичок із подвоєним бонусом майстерності.
 *
 * Скільки обирати і з чого — каже сервер (`sheet.expertise`): кількість рахується
 * з умінь класу («Expertise» плута на 1 і 6, барда на 3 і 10 рівнях), а
 * варіанти — це навички, якими персонаж уже володіє, і злодійські інструменти
 * плута. Тут лише вибір і збереження.
 */
import { useEffect, useState } from "react";

import { Term } from "../../components/Term";
import { skillLabel } from "../../labels";

const THIEVES_TOOLS = "thieves' tools";

function optionLabel(value: string): string {
  return value === THIEVES_TOOLS ? "Злодійські інструменти" : skillLabel(value);
}

export function ExpertisePicker({
  expertise,
  busy,
  onSave,
}: {
  expertise: { slots: number; chosen: string[]; options: string[] };
  busy: boolean;
  onSave: (values: string[]) => Promise<unknown>;
}) {
  const [picked, setPicked] = useState<string[]>(expertise.chosen);
  const [open, setOpen] = useState(expertise.chosen.length < expertise.slots);
  useEffect(() => setPicked(expertise.chosen), [expertise.chosen]);

  const pending = expertise.slots - expertise.chosen.length;
  const dirty = picked.join("|") !== expertise.chosen.join("|");

  function toggle(value: string) {
    setPicked((current) => {
      if (current.includes(value)) return current.filter((item) => item !== value);
      if (current.length >= expertise.slots) return current;
      return [...current, value];
    });
  }

  return (
    <div className={`expertise${pending > 0 ? " expertise--pending" : ""}`}>
      <p className="expertise__head">
        <Term k="expertise">Експертиза</Term>: {expertise.chosen.length} з {expertise.slots}
        {expertise.chosen.length ? ` — ${expertise.chosen.map(optionLabel).join(", ")}` : ""}
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
          Клас дає експертизу ще в {pending} {pending === 1 ? "навичці" : "навичках"}: бонус майстерності для них
          подвоюється. Оберіть серед навичок, якими ви володієте.
        </p>
      ) : null}
      {open ? (
        <>
          <div className="chip-row">
            {expertise.options.map((value) => (
              <button
                key={value}
                type="button"
                className={`chip ${picked.includes(value) ? "chip--active" : ""}`}
                aria-pressed={picked.includes(value)}
                disabled={!picked.includes(value) && picked.length >= expertise.slots}
                onClick={() => toggle(value)}
              >
                {optionLabel(value)}
              </button>
            ))}
          </div>
          {!expertise.options.length ? (
            <p className="hint">Немає навичок із володінням — спершу оберіть навички класу.</p>
          ) : null}
          <div className="inline-row">
            <button
              type="button"
              className="button button--primary"
              disabled={busy || !dirty}
              onClick={() =>
                void onSave(picked).then(() => {
                  if (picked.length >= expertise.slots) setOpen(false);
                })
              }
            >
              Зберегти експертизу ({picked.length} з {expertise.slots})
            </button>
            {expertise.chosen.length >= expertise.slots ? (
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
