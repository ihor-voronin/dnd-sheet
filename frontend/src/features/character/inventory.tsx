/** Інвентар: пошук у довіднику, додавання, правка й видалення.
 *
 * DDB-звичка: предмет додають із каталогу, а потім доводять руками — назву,
 * урон, вагу, КЗ. Тому форма однакова для «додати» й «змінити»: довідник
 * лише підставляє те, що знає, а решту гравець править як хоче.
 *
 * Броня в корпусі не має числа КЗ (там лише група), тому базовий КЗ для
 * відомих назв береться з таблиці PHB — гравець усе одно може його змінити.
 */

import { useEffect, useState } from "react";

import { searchItems } from "../../api";
import type { ItemBody, ItemSearchResult } from "../../api";
import { ITEM_KIND_LABELS } from "../../labels";
import { itemLabel } from "./uk";
import type { SheetItem } from "../wizard/types";
import { NumberField } from "./editing";

/** Таблиця броні PHB: назва → базовий КЗ. */
const ARMOR_BASE: Record<string, number> = {
  padded: 11,
  leather: 11,
  "studded leather": 12,
  hide: 12,
  "chain shirt": 13,
  "scale mail": 14,
  breastplate: 14,
  "half plate": 15,
  "ring mail": 14,
  "chain mail": 16,
  splint: 17,
  plate: 18,
};

/** Група броні → межа бонусу Спритності (легка — без межі). */
const ARMOR_DEX_CAP: Record<string, number | null> = {
  "Light Armor": null,
  "Medium Armor": 2,
  "Heavy Armor": 0,
};

interface Draft {
  name_en: string;
  kind: string;
  quantity: number;
  weight_lb: number;
  equipped: boolean;
  armorBase: number;
  dexCap: number | null;
  notes: string;
  damage: string;
  /** Підказка з довідника: що буде, якщо урон не вписувати вручну. */
  damageHint: string;
  entry_id: string | null;
}

const EMPTY: Draft = {
  name_en: "",
  kind: "gear",
  quantity: 1,
  weight_lb: 0,
  equipped: false,
  armorBase: 11,
  dexCap: null,
  notes: "",
  damage: "",
  damageHint: "",
  entry_id: null,
};

function draftFromItem(item: SheetItem): Draft {
  return {
    name_en: item.name_en,
    kind: item.kind,
    quantity: item.quantity,
    weight_lb: item.weight_lb,
    equipped: item.equipped,
    armorBase: item.armor_base ?? 11,
    dexCap: item.dex_cap,
    notes: item.notes ?? "",
    damage: item.damage ?? "",
    damageHint: item.damage ?? "",
    entry_id: null,
  };
}

/** Наскільки повні дані запису: чим більше заповнених полів, тим краще. */
function entryScore(entry: ItemSearchResult): number {
  const values = Object.values(entry.data ?? {});
  const filled = values.filter(
    (value) => value !== null && value !== undefined && value !== "",
  ).length;
  return filled + (entry.id.startsWith("basic-rules-2014/") ? 0 : 1);
}

function kindOf(entry: ItemSearchResult, group: string, itemType: string): string {
  if (
    itemType === "shield" ||
    group === "Shield" ||
    (itemType === "armor" && /(^|\s)shield\b/i.test(entry.name_en))
  ) {
    return "shield";
  }
  if (itemType === "weapon") return "weapon";
  if (itemType === "armor") return "armor";
  if (itemType === "tool") return "tool";
  return "gear";
}

/** Базовий КЗ: відома назва з таблиці PHB, інакше — типове для групи. */
function armorBaseFor(name: string, group: string): number {
  const known = ARMOR_BASE[name.trim().toLowerCase()];
  if (known) return known;
  if (group === "Medium Armor") return 13;
  if (group === "Heavy Armor") return 16;
  return 11;
}

function draftFromEntry(entry: ItemSearchResult): Draft {
  const data = entry.data as Record<string, unknown>;
  const itemType = String(data.item_type ?? "gear");
  const group = String(data.group ?? "");
  const kind = kindOf(entry, group, itemType);
  const weight = Number(String(data.weight ?? "").replace(/[^\d.]/g, "")) || 0;
  const damage = String(data.damage ?? "");
  // Власний урон лишаємо порожнім: інакше рядок із довідника став би
  // «виправленням» і з'їв би модифікатор здібності. Порожнє поле — це
  // «порахуй сам», а підказка показує, що саме буде.
  const notes = itemType === "weapon" ? String(data.properties ?? "") : "";
  return {
    ...EMPTY,
    name_en: entry.name_en,
    kind,
    weight_lb: weight,
    damage: "",
    damageHint: damage,
    notes,
    armorBase: armorBaseFor(entry.name_en, group),
    dexCap: kind === "armor" ? (ARMOR_DEX_CAP[group] ?? null) : null,
    entry_id: entry.id,
  };
}

function bodyFromDraft(draft: Draft, withEntry: boolean): ItemBody {
  return {
    name_en: draft.name_en.trim(),
    kind: draft.kind,
    quantity: draft.quantity,
    weight_lb: draft.weight_lb,
    equipped: draft.equipped,
    notes: draft.notes.trim() || null,
    damage: draft.kind === "weapon" ? draft.damage.trim() || null : null,
    armor_base: draft.kind === "armor" ? draft.armorBase : null,
    dex_cap: draft.kind === "armor" ? draft.dexCap : null,
    ...(withEntry ? { entry_id: draft.entry_id } : {}),
  };
}

export function InventoryPanel({
  items,
  money,
  carrying,
  disabled = false,
  onAdd,
  onUpdate,
  onRemove,
}: {
  items: SheetItem[];
  money: Record<string, number>;
  carrying: { capacity: number; weight: number };
  disabled?: boolean;
  onAdd: (item: ItemBody) => Promise<boolean>;
  onUpdate: (index: number, fields: Partial<ItemBody>) => Promise<boolean>;
  onRemove: (index: number) => Promise<boolean>;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ItemSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [form, setForm] = useState<{ index: number | null; draft: Draft } | null>(null);
  const [confirmIndex, setConfirmIndex] = useState<number | null>(null);

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    let alive = true;
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const payload = await searchItems(text, 20);
        if (!alive) return;
        // Довідник містить той самий предмет у кількох книгах (PHB, базові
        // правила, DMG) — у списку вибору він має бути один. Порядок —
        // спершу точний збіг, далі початок назви, далі решта.
        const wanted = text.toLocaleLowerCase();
        const rank = (name: string) => {
          const value = name.toLocaleLowerCase();
          if (value === wanted) return 0;
          if (value.startsWith(wanted)) return 1;
          return 2;
        };
        const seen = new Map<string, ItemSearchResult>();
        for (const item of payload.items) {
          const key = item.name_en.trim().toLocaleLowerCase();
          const previous = seen.get(key);
          // У «базових правилах» той самий предмет бідніший (немає групи
          // броні) — лишаємо варіант із повнішими даними.
          if (!previous || entryScore(item) > entryScore(previous)) seen.set(key, item);
        }
        const unique = Array.from(seen.values());
        unique.sort(
          (left, right) =>
            rank(left.name_en) - rank(right.name_en) ||
            left.name_en.localeCompare(right.name_en),
        );
        setResults(unique.slice(0, 12));
      } catch {
        if (alive) setResults([]);
      } finally {
        if (alive) setSearching(false);
      }
    }, 250);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [query]);

  function openAdd(entry?: ItemSearchResult) {
    setConfirmIndex(null);
    setForm({ index: null, draft: entry ? draftFromEntry(entry) : { ...EMPTY } });
    setResults([]);
    setQuery("");
  }

  function openEdit(index: number) {
    setConfirmIndex(null);
    setForm({ index, draft: draftFromItem(items[index]) });
  }

  async function remove(index: number) {
    const ok = await onRemove(index);
    if (!ok) return;
    setConfirmIndex(null);
    if (form?.index === index) setForm(null);
  }

  async function submit() {
    if (!form) return;
    if (!form.draft.name_en.trim()) return;
    const ok =
      form.index === null
        ? await onAdd(bodyFromDraft(form.draft, true))
        : await onUpdate(form.index, bodyFromDraft(form.draft, false));
    if (ok) setForm(null);
  }

  return (
    <>
      <h3 className="ddb-work__title">
        <span>Інвентар</span>
        <span className="short">
          вага {carrying.weight} з {carrying.capacity} фнт
        </span>
      </h3>

      <div className="money-row">
        {Object.entries({ gp: "золото", sp: "срібло", cp: "мідь" }).map(([coin, label]) => (
          <span key={coin} className="resource">
            {label}: {money[coin] ?? 0}
          </span>
        ))}
      </div>

      <div className="inv-search">
        <input
          className="inv-search__input"
          value={query}
          placeholder="Пошук у довіднику: longsword, chain mail…"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setQuery("");
          }}
          aria-label="Пошук предмета в довіднику"
        />
        <button
          type="button"
          className="button button--primary"
          disabled={disabled}
          onClick={() => openAdd()}
        >
          Додати
        </button>
      </div>

      {searching ? <p className="hint">Шукаємо…</p> : null}
      {!searching && query.trim().length >= 2 && !results.length ? (
        <p className="hint">Нічого не знайдено — додайте предмет вручну кнопкою «Додати».</p>
      ) : null}
      {results.length ? (
        <ul className="inv-results">
          {results.map((entry) => {
            const data = entry.data as Record<string, unknown>;
            const group = String(data.group ?? "");
            const itemType = String(data.item_type ?? "");
            const kind = kindOf(entry, group, itemType);
            const label = ITEM_KIND_LABELS[kind] ?? kind;
            const meta = [label, String(data.damage ?? ""), String(data.weight ?? ""), group].filter(
              Boolean,
            );
            return (
              <li key={entry.id}>
                <button type="button" className="inv-results__row" onClick={() => openAdd(entry)}>
                  <span className="inv-results__name">{itemLabel(entry.name_en)}</span>
                  <span className="inv-results__meta">{meta.join(" · ")}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {form ? (
        <div className="inv-form">
          <p className="inv-form__title">
            {form.index === null ? "Новий предмет" : "Змінити предмет"}
          </p>
          <div className="inv-form__grid">
            <label className="field inv-form__wide">
              <span>Назва</span>
              <input
                value={form.draft.name_en}
                onChange={(event) =>
                  setForm({ ...form, draft: { ...form.draft, name_en: event.target.value } })
                }
              />
            </label>
            <label className="field">
              <span>Тип</span>
              <select
                value={form.draft.kind}
                onChange={(event) =>
                  setForm({ ...form, draft: { ...form.draft, kind: event.target.value } })
                }
              >
                {Object.entries(ITEM_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field inv-form__num">
              <span>Кількість</span>
              <NumberField
                value={form.draft.quantity}
                min={0}
                max={99}
                size="sm"
                title="Кількість"
                onChange={(value) => setForm({ ...form, draft: { ...form.draft, quantity: value } })}
              />
            </label>
            <label className="field inv-form__num">
              <span>Вага, фнт</span>
              <NumberField
                value={form.draft.weight_lb}
                min={0}
                max={999}
                size="sm"
                title="Вага предмета"
                onChange={(value) => setForm({ ...form, draft: { ...form.draft, weight_lb: value } })}
              />
            </label>
            {form.draft.kind === "weapon" ? (
              <label className="field inv-form__wide">
                <span>Урон (порожньо — рахуємо з довідника й модифікатора)</span>
                <input
                  value={form.draft.damage}
                  placeholder={form.draft.damageHint || "напр. 1d8+3 slashing"}
                  onChange={(event) =>
                    setForm({ ...form, draft: { ...form.draft, damage: event.target.value } })
                  }
                />
              </label>
            ) : null}
            {form.draft.kind === "armor" ? (
              <>
                <label className="field inv-form__num">
                  <span>Базовий КЗ</span>
                  <NumberField
                    value={form.draft.armorBase}
                    min={10}
                    max={20}
                    size="sm"
                    title="Базовий КЗ броні"
                    onChange={(value) =>
                      setForm({ ...form, draft: { ...form.draft, armorBase: value } })
                    }
                  />
                </label>
                <label className="field inv-form__num">
                  <span>Межа СПР</span>
                  <NumberField
                    value={form.draft.dexCap ?? 0}
                    min={0}
                    max={10}
                    size="sm"
                    disabled={form.draft.dexCap === null}
                    title="Межа бонусу Спритності"
                    onChange={(value) =>
                      setForm({ ...form, draft: { ...form.draft, dexCap: value } })
                    }
                  />
                </label>
                <label className="field inv-form__check">
                  <input
                    type="checkbox"
                    checked={form.draft.dexCap === null}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        draft: { ...form.draft, dexCap: event.target.checked ? null : 0 },
                      })
                    }
                  />
                  <span>без межі СПР</span>
                </label>
              </>
            ) : null}
            <label className="field inv-form__wide">
              <span>Властивості / нотатки</span>
              <input
                value={form.draft.notes}
                placeholder="напр. Versatile (1d10), Light"
                onChange={(event) =>
                  setForm({ ...form, draft: { ...form.draft, notes: event.target.value } })
                }
              />
            </label>
            <label className="field inv-form__check">
              <input
                type="checkbox"
                checked={form.draft.equipped}
                onChange={(event) =>
                  setForm({ ...form, draft: { ...form.draft, equipped: event.target.checked } })
                }
              />
              <span>споряджено</span>
            </label>
          </div>
          <div className="inv-form__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={disabled || !form.draft.name_en.trim()}
              onClick={() => void submit()}
            >
              {form.index === null ? "Додати в інвентар" : "Зберегти"}
            </button>
            <button type="button" className="button" onClick={() => setForm(null)}>
              Скасувати
            </button>
          </div>
        </div>
      ) : null}

      {items.length ? (
        <ul className="item-list">
          {items.map((item, index) => {
            const meta = [
              ITEM_KIND_LABELS[item.kind] ?? item.kind,
              item.damage,
              item.armor_base ? `КЗ ${item.armor_base}` : "",
              item.dex_cap !== null && item.armor_base ? `СПР ≤ ${item.dex_cap}` : "",
              item.weight_lb ? `${item.weight_lb} фнт` : "",
              item.notes,
            ].filter(Boolean);
            return (
              <li
                key={`${item.name_en}-${index}`}
                className={`item-row ${form?.index === index ? "is-editing" : ""}`}
              >
                <span className="item-main">
                  <span className="item-name">
                    {itemLabel(item.name_en)}
                    {item.quantity > 1 ? ` × ${item.quantity}` : ""}
                  </span>
                  <span className="item-meta">{meta.join(" · ")}</span>
                </span>
                <span className="inv-row__actions">
                  <button
                    type="button"
                    className={`chip ${item.equipped ? "chip--active" : ""}`}
                    disabled={disabled}
                    onClick={() => void onUpdate(index, { equipped: !item.equipped })}
                    title={item.equipped ? "Зняти" : "Спорядити"}
                  >
                    {item.equipped ? "споряджено" : "не споряджено"}
                  </button>
                  <button
                    type="button"
                    className="inv-icon"
                    disabled={disabled}
                    onClick={() => openEdit(index)}
                    title="Змінити предмет"
                  >
                    ✎
                  </button>
                  {confirmIndex === index ? (
                    <>
                      <button
                        type="button"
                        className="chip chip--danger"
                        disabled={disabled}
                        onClick={() => void remove(index)}
                        title="Підтвердити"
                      >
                        прибрати?
                      </button>
                      <button
                        type="button"
                        className="inv-icon"
                        onClick={() => setConfirmIndex(null)}
                        title="Скасувати"
                      >
                        ×
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="inv-icon inv-icon--danger"
                      disabled={disabled}
                      onClick={() => setConfirmIndex(index)}
                      title="Прибрати з інвентаря"
                    >
                      ×
                    </button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="hint">Порожньо. Знайдіть предмет у довіднику або додайте свій.</p>
      )}
    </>
  );
}
