/** Вкладка «Передісторія»: хто персонаж до пригод і що це йому дало.
 *
 * У листі були лише назва передісторії в шапці й володіння в загальному
 * списку. Тут — опис із довідника, риса передісторії, конкретні навички,
 * інструменти, мови й спорядження, які вона дала. Зовнішність переїхала сюди
 * з нотаток: це частина «хто я», а не замітки під час гри.
 */

import { ALIGNMENT_LABELS, proficiencyValue } from "../../labels";
import type { BackgroundDetails } from "../wizard/types";
import { NoteArea, notesStatusText } from "./notes";
import type { NoteStatus } from "./notes";
import { RuleText } from "./panels";
import { itemLabel, ukBackground, withEnglish } from "./uk";

function joinOrDash(values: string[], kind: string, any: number): string {
  const labels = values.map((value) => proficiencyValue(kind, value));
  if (any > 0) {
    labels.push(`${any} на вибір`);
  }
  return labels.length ? labels.join(" · ") : "—";
}

export function BackgroundPanel({
  details,
  alignment,
  appearance,
  status,
  savedAt,
  onAppearanceChange,
}: {
  details: BackgroundDetails | null;
  alignment: string | null;
  appearance: string;
  status: NoteStatus;
  savedAt: string | null;
  onAppearanceChange: (value: string) => void;
}) {
  if (!details) {
    return (
      <>
        <h3 className="ddb-work__title">
          <span>Передісторія</span>
        </h3>
        <p className="hint">
          Передісторію не вибрано — її обирають у візарді на кроці «Передісторія».
        </p>
      </>
    );
  }

  const uk = ukBackground(details.key);
  const nameUk = details.name_uk ?? uk?.name;
  const featureUk = details.feature_uk ?? uk?.feature;
  const featureTextUk = details.feature_text_uk ?? uk?.featureText;
  const equipmentUk = details.equipment_uk ?? uk?.equipment;
  const descriptionUk = details.description_uk ?? uk?.description;

  return (
    <div className="background-panel">
      <h3 className="ddb-work__title">
        <span>Передісторія</span>
        <span className="short">{details.source_id === "custom" ? "власна" : details.source_id || "2014"}</span>
      </h3>

      <section className="bg-card">
        <div className="bg-card__head">
          <span className="bg-card__name">{withEnglish(details.name_en, nameUk)}</span>
          {alignment ? (
            <span className="bg-card__align">
              {ALIGNMENT_LABELS[alignment] ?? alignment}
            </span>
          ) : null}
        </div>
        <ul className="bg-grants">
          <li>
            <span>Навички</span>
            <span>{joinOrDash(details.skills, "skill", 0)}</span>
          </li>
          <li>
            <span>Інструменти</span>
            <span>{joinOrDash(details.tools, "tool", details.tools_any)}</span>
          </li>
          <li>
            <span>Мови</span>
            <span>{joinOrDash(details.languages, "language", details.languages_any)}</span>
          </li>
          <li>
            <span>Риса</span>
            <span>{details.feature_en ? withEnglish(details.feature_en, featureUk) : "—"}</span>
          </li>
        </ul>
        {details.equipment ? (
          <p className="bg-equipment">
            <span>Спорядження </span>
            {equipmentUk ??
              (details.source_id === "custom"
                ? details.equipment
                    .split(", ")
                    .map((name) => itemLabel(name))
                    .join(", ")
                : details.equipment)}
          </p>
        ) : null}
      </section>

      {details.feature_text ? (
        <details className="feature">
          <summary className="feature__summary">
            <span className="feature-name">
              {details.feature_en ? withEnglish(details.feature_en, featureUk) : "Риса передісторії"}
            </span>
            <span className="feature-meta">риса передісторії</span>
            <span className="feature__chevron" aria-hidden>
              ▾
            </span>
          </summary>
          <RuleText text={featureTextUk ?? details.feature_text} />
        </details>
      ) : null}

      {details.description ? (
        <details className="feature">
          <summary className="feature__summary">
            <span className="feature-name">Опис передісторії</span>
            <span className="feature-meta">з довідника</span>
            <span className="feature__chevron" aria-hidden>
              ▾
            </span>
          </summary>
          <RuleText text={descriptionUk ?? details.description} />
        </details>
      ) : null}

      <h3 className="ddb-work__title">
        <span>Зовнішність</span>
        <span className="short">зберігається автоматично</span>
      </h3>
      <NoteArea
        label="Зовнішність"
        value={appearance}
        minHeight={130}
        placeholder="зріст, статура, шрам, одяг, манери, голос…"
        onChange={onAppearanceChange}
      />
      <p className={`notes-status notes-status--${status}`} role="status">
        {notesStatusText(status, savedAt)}
      </p>
    </div>
  );
}
