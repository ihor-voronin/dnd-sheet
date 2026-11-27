/** Коротка картка підкласу: «що це таке» і що дає на вищих рівнях.
 *
 * Потрібна у двох місцях — на кроці «Клас» (коли обирають спеціалізацію на
 * 1 рівні) і на кроці підвищення рівня (коли вона зʼявляється на 3/10).
 * Опис і вміння приходять окремим запитом: вбудовувати їх у крок означало б
 * віддавати тексти всіх підкласів класу ще до вибору.
 */

import { useEffect, useState } from "react";

import { fetchSubclassDetails } from "../../api";
import type { SubclassBriefPayload } from "../../api";
import { RuleText } from "../character/panels";
import { featureLabel, withEnglish } from "../character/uk";

export function SubclassBrief({
  subclassKey,
  highlightLevel,
}: {
  subclassKey: string;
  /** Рівень, який дають цим вибором — його позначимо «отримуєте зараз». */
  highlightLevel?: number;
}) {
  const [data, setData] = useState<SubclassBriefPayload | "loading" | null>(null);

  useEffect(() => {
    if (!subclassKey) {
      setData(null);
      return;
    }
    let alive = true;
    setData("loading");
    void fetchSubclassDetails(subclassKey)
      .then((payload) => {
        if (alive) setData(payload);
      })
      .catch(() => {
        if (alive) setData(null);
      });
    return () => {
      alive = false;
    };
  }, [subclassKey]);

  if (!subclassKey) return null;
  if (data === "loading") return <p className="meta">Читаємо опис підкласу…</p>;
  if (!data) return null;

  const description = data.description_uk || data.description;
  return (
    <div className="subclass-brief">
      {data.corrupt ? (
        <p className="hint hint--warn">
          У корпусі текст цього підкласу пошкоджений: чужа мова й жодного
          поділу на вміння. Показуємо лише назву — правило беріть із книги.
        </p>
      ) : null}
      {description ? (
        <div className="subclass-brief__text">
          <RuleText text={description} />
        </div>
      ) : null}

      {data.features.length ? (
        <>
          <h4 className="species-card__h4">Що дає на вищих рівнях</h4>
          <ul className="plain-list">
            {data.features.map((feature) => (
              <li key={`${feature.level}-${feature.name_en}`}>
                <details className="reckoning">
                  <summary>
                    {feature.level} рівень ·{" "}
                    {feature.name_uk
                      ? withEnglish(feature.name_en, feature.name_uk)
                      : featureLabel(feature.name_en)}
                    {feature.level === highlightLevel ? (
                      <span className="meta"> · отримуєте зараз</span>
                    ) : null}
                  </summary>
                  {feature.text_uk || feature.description ? (
                    <RuleText text={feature.text_uk || feature.description} />
                  ) : (
                    <p className="hint">Тексту цього вміння в корпусі немає.</p>
                  )}
                </details>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
