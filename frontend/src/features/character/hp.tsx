/** Хіти й кістки хитів: те, що найчастіше змінюється за столом.
 *
 * Хіти — це не «поле числа», а дві дії: отримати шкоду й полікуватися. Тому
 * зверху великі поточні/максимум/тимчасові (клік по числу — вписати), а під
 * ними — поле кількості з двома кнопками й швидкі кнопки −1/−5/−10 і
 * +1/+5/+10: на дошці це швидше, ніж відкривати поле.
 *
 * Кістки хитів показуються кісткою, кількістю вільних і «намистинами»
 * витрачених. Кидок можна зробити одразу (випадкове число, як у DDB) або
 * вписати те, що випало на реальному кубику.
 */

import { useState } from "react";
import type { ReactNode } from "react";

import type { SheetViewPayload } from "../wizard/types";
import { EditableNumber, NumberField } from "./editing";

export function HitPointsBlock({
  hitPoints,
  maxField,
  disabled = false,
  onSet,
  onDamage,
  onHeal,
}: {
  hitPoints: SheetViewPayload["hit_points"];
  maxField: ReactNode;
  disabled?: boolean;
  onSet: (patch: { current?: number; temporary?: number }) => void;
  onDamage: (amount: number) => void;
  onHeal: (amount: number) => void;
}) {
  const [amount, setAmount] = useState(1);
  const down = hitPoints.current === 0;

  return (
    <section className="ddb-hp" aria-label="Хіти">
      <div className="ddb-hp__values">
        <div className="ddb-hp__cell">
          <span className="ddb-hp__cap">Поточні</span>
          <EditableNumber
            size="lg"
            value={hitPoints.current}
            title="Поточні хіти"
            min={0}
            max={999}
            onSave={(value) => onSet({ current: value })}
          />
        </div>
        <span className="ddb-hp__slash" aria-hidden>
          /
        </span>
        <div className="ddb-hp__cell ddb-hp__cell--max">
          <span className="ddb-hp__cap">Максимум</span>
          <span className="ddb-hp__max">{maxField}</span>
        </div>
        <div
          className={`ddb-hp__cell ddb-hp__cell--temp ${
            hitPoints.temporary > 0 ? "is-on" : ""
          }`}
        >
          <span className="ddb-hp__cap">Тимч.</span>
          <EditableNumber
            value={hitPoints.temporary}
            title="Тимчасові хіти"
            min={0}
            max={999}
            onSave={(value) => onSet({ temporary: value })}
          />
        </div>
        <span className="ddb-hp__flags">
          {down ? (
            <span className="ddb-hp__flag ddb-hp__flag--down">непритомний</span>
          ) : hitPoints.bloodied ? (
            <span className="ddb-hp__flag">поранений</span>
          ) : null}
        </span>
      </div>

      <div className="ddb-hp__apply">
        <NumberField
          value={amount}
          live
          min={1}
          max={999}
          disabled={disabled}
          title="Скільки хітів"
          suffix="хп"
          size="sm"
          onChange={setAmount}
        />
        <button
          type="button"
          className="ddb-hp__act ddb-hp__act--damage"
          disabled={disabled}
          onClick={() => onDamage(amount)}
          title="Зняти хіти: спершу тимчасові, як у правилах"
        >
          Шкода
        </button>
        <button
          type="button"
          className="ddb-hp__act ddb-hp__act--heal"
          disabled={disabled}
          onClick={() => onHeal(amount)}
          title="Додати хіти, не вище максимуму"
        >
          Лікування
        </button>
      </div>

      <div className="ddb-hp__quick" aria-label="Швидка зміна хітів">
        {[-10, -5, -1].map((step) => (
          <button
            key={step}
            type="button"
            className="ddb-hp__quick-btn ddb-hp__quick-btn--damage"
            disabled={disabled}
            onClick={() => onDamage(-step)}
          >
            {step}
          </button>
        ))}
        {[1, 5, 10].map((step) => (
          <button
            key={step}
            type="button"
            className="ddb-hp__quick-btn ddb-hp__quick-btn--heal"
            disabled={disabled}
            onClick={() => onHeal(step)}
          >
            +{step}
          </button>
        ))}
      </div>
    </section>
  );
}

export function HitDiceBlock({
  resources,
  conModifier,
  disabled = false,
  onSpend,
}: {
  resources: SheetViewPayload["resources"];
  conModifier: number;
  disabled?: boolean;
  onSpend: (die: number, roll: number) => Promise<boolean>;
}) {
  const entries = Object.entries(resources.hit_dice);
  const [open, setOpen] = useState<string | null>(null);
  const [rolls, setRolls] = useState<Record<string, number>>({});
  const [last, setLast] = useState<{ die: number; roll: number } | null>(null);

  if (!entries.length) return <p className="hint">—</p>;

  async function spend(die: number, roll: number) {
    const ok = await onSpend(die, roll);
    if (ok) {
      setLast({ die, roll });
      setOpen(null);
    }
  }

  return (
    <div className="hitdice">
      {entries.map(([name, resource]) => {
        const size = Number(name.replace("d", ""));
        const free = resource.total - resource.used;
        return (
          <div key={name} className={`hitdie ${free === 0 ? "is-empty" : ""}`}>
            <span className="hitdie__face" title={`Кістка хиту ${name}`}>
              {name}
            </span>
            <div className="hitdie__body">
              <span className="hitdie__count">
                <strong>{free}</strong>
                <span>з {resource.total} вільних</span>
              </span>
              {resource.total > 1 ? (
                <span className="hitdie__pips" aria-hidden>
                  {Array.from({ length: resource.total }, (_, index) => (
                    <span key={index} className={`hitdie__pip ${index < free ? "is-free" : ""}`} />
                  ))}
                </span>
              ) : null}
            </div>
            <div className="hitdie__actions">
              <button
                type="button"
                className="hitdie__roll"
                disabled={disabled || free === 0}
                onClick={() => void spend(size, 1 + Math.floor(Math.random() * size))}
                title={`Кинути ${name} і полікуватися на кидок + мод. Статури`}
              >
                Кинути {name}
              </button>
              <button
                type="button"
                className="hitdie__manual-toggle"
                disabled={disabled || free === 0}
                onClick={() => setOpen(open === name ? null : name)}
                title="Вписати кидок з реального кубика"
              >
                {open === name ? "згорнути" : "ввести"}
              </button>
            </div>
            {open === name ? (
              <div className="hitdie__manual">
                <NumberField
                  value={rolls[name] ?? 1}
                  live
                  min={1}
                  max={size}
                  disabled={disabled || free === 0}
                  title={`Кидок ${name}`}
                  size="sm"
                  onChange={(value) => setRolls({ ...rolls, [name]: value })}
                />
                <button
                  type="button"
                  className="hitdie__apply"
                  disabled={disabled || free === 0}
                  onClick={() => void spend(size, rolls[name] ?? 1)}
                >
                  Витратити
                </button>
              </div>
            ) : null}
          </div>
        );
      })}
      {last ? (
        <p className="hitdie__result">
          Кидок {last.roll} + Статура {conModifier >= 0 ? `+${conModifier}` : conModifier} →{" "}
          <strong>+{Math.max(0, last.roll + conModifier)} хітів</strong>
        </p>
      ) : null}
    </div>
  );
}
