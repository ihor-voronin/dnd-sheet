/** Інвентар: каталог предметів, додавання, правка й видалення.
 *
 * Додавання зроблено як у DDB: спершу каталог із фільтрами (тип, джерело,
 * магічність, пошук), у рядку — одна кнопка «Додати». Форма потрібна лише
 * тоді, коли треба щось довести руками — власний предмет або правка вже
 * доданого. Тому форма однакова для «додати свій» і «змінити».
 *
 * Каталог вантажиться один раз на весь застосунок: півтори тисячі записів у
 * короткому вигляді — це кількасот кілобайт, зате фільтри спрацьовують без
 * запиту на кожне натискання.
 *
 * Броня в корпусі не має числа КЗ (там лише група), тому базовий КЗ для
 * відомих назв береться з таблиці PHB — гравець усе одно може його змінити.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import {
  fetchBookTitles,
  fetchEntry,
  fetchItemCatalog,
  fetchItemsUk,
  searchItems,
} from "../../api";
import type { CompendiumEntry, ItemBody, ItemSearchResult } from "../../api";
import { ITEM_KIND_LABELS } from "../../labels";
import { itemKey, itemLabel, weaponDamage, weaponNotes } from "./uk";
import { RuleText } from "./panels";
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

/** Рідкість так, як її називає книга. */
const RARITY_LABELS: Record<string, string> = {
  common: "звичайний",
  uncommon: "незвичайний",
  rare: "рідкісний",
  "very rare": "дуже рідкісний",
  legendary: "легендарний",
  artifact: "артефакт",
  "rarity varies": "різна рідкість",
  varies: "різна рідкість",
  "unknown (magic)": "рідкість невідома",
};

/** Чипи типів: значення — те, що лежить у `data.item_type`. */
const TYPE_FILTERS: { value: string; label: string }[] = [
  { value: "armor", label: "Броня" },
  { value: "shield", label: "Щит" },
  { value: "weapon", label: "Зброя" },
  { value: "gear", label: "Спорядження" },
  { value: "tool", label: "Інструмент" },
  { value: "potion", label: "Зілля" },
  { value: "ring", label: "Перстень" },
  { value: "rod", label: "Жезл" },
  { value: "scroll", label: "Сувій" },
  { value: "staff", label: "Посох" },
  { value: "wand", label: "Паличка" },
  { value: "wondrous item", label: "Дивовижний" },
  { value: "mount", label: "Верхові" },
];

const KNOWN_TYPES = new Set(TYPE_FILTERS.map((filter) => filter.value));

/** «Інше» — те, що не потрапило в чипи (арт-обʼєкти, вибухівка, кораблі). */
const OTHER = "інше";

/** Скорочені назви джерел для чипів; решта показується кодом книги. */
const SOURCE_LABELS: Record<string, string> = {
  "basic-rules-2014": "Базові правила",
  "phb-2014": "Книга гравця",
  "dmg-2014": "Посібник Майстра",
  xgte: "Ксантар",
  tcoe: "Таша",
  egtw: "Уайлдмаунт",
  idrotf: "Крижаний пік",
  toa: "Гробниця",
  gotg: "Велетні",
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
    entry_id: item.entry_id ?? null,
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

function dataOf(entry: ItemSearchResult): Record<string, unknown> {
  return (entry.data ?? {}) as Record<string, unknown>;
}

/** Тип запису для чипів: «weapon (greataxe)» рахуємо як «weapon». */
function typeOf(entry: ItemSearchResult): string {
  const raw = String(dataOf(entry).item_type ?? "")
    .toLowerCase()
    .replace(/\s*\(.*$/, "")
    .trim();
  return KNOWN_TYPES.has(raw) ? raw : OTHER;
}

function weightOf(entry: ItemSearchResult): number {
  return Number(String(dataOf(entry).weight ?? "").replace(/[^\d.]/g, "")) || 0;
}

function draftFromEntry(entry: ItemSearchResult): Draft {
  const data = dataOf(entry);
  const itemType = String(data.item_type ?? "gear");
  const group = String(data.group ?? "");
  const kind = kindOf(entry, group, itemType);
  const damage = String(data.damage ?? "");
  // Власний урон лишаємо порожнім: інакше рядок із довідника став би
  // «виправленням» і з'їв би модифікатор здібності. Порожнє поле — це
  // «порахуй сам», а підказка показує, що саме буде.
  const notes = itemType === "weapon" ? String(data.properties ?? "") : "";
  return {
    ...EMPTY,
    name_en: entry.name_en,
    kind,
    weight_lb: weightOf(entry),
    damage: "",
    damageHint: damage,
    notes,
    armorBase: armorBaseFor(entry.name_en, group),
    dexCap: kind === "armor" ? (ARMOR_DEX_CAP[group] ?? null) : null,
    entry_id: entry.id,
  };
}

/** Предмет із каталогу — одразу в інвентар, без форми. */
function bodyFromEntry(entry: ItemSearchResult): ItemBody {
  const draft = draftFromEntry(entry);
  return {
    name_en: draft.name_en.trim(),
    kind: draft.kind,
    quantity: 1,
    weight_lb: draft.weight_lb,
    equipped: false,
    notes: draft.notes.trim() || null,
    damage: null,
    armor_base: draft.kind === "armor" ? draft.armorBase : null,
    dex_cap: draft.kind === "armor" ? draft.dexCap : null,
    entry_id: draft.entry_id,
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

/** Вага й ціна з довідника — англійські одиниці, показуємо свої. */
function weightLabel(raw: unknown): string {
  const text = String(raw ?? "").trim();
  if (!text) return "";
  //: У базових правилах вага буває дробом: «1/2 lb.» — інакше з нього
  //: виходить «12 фнт», бо скіс риска не цифра.
  const fraction = text.match(/(\d+)\s*\/\s*(\d+)/);
  const number = fraction
    ? String(Math.round((Number(fraction[1]) / Number(fraction[2])) * 100) / 100)
    : (text.match(/\d+(?:\.\d+)?/) ?? [""])[0];
  if (!number) return "";
  return `${number} фнт`;
}

function moneyLabel(raw: unknown): string {
  const text = String(raw ?? "");
  if (!text) return "";
  return text
    .replace(/\bgp\b/gi, "зм")
    .replace(/\bsp\b/gi, "см")
    .replace(/\bcp\b/gi, "мд")
    .replace(/\bpp\b/gi, "пл")
    .replace(/\bep\b/gi, "ел");
}

/** Короткий рядок про предмет для каталогу: «рідкість · ціна · вага · книга». */
function catalogMeta(entry: ItemSearchResult, titles: Record<string, string>): string {
  const data = dataOf(entry);
  return [
    RARITY_LABELS[String(data.rarity ?? "").toLowerCase()] ?? "",
    data.damage ? String(data.damage) : "",
    data.armor_class ? `КЗ ${data.armor_class}` : "",
    moneyLabel(data.cost),
    weightLabel(data.weight),
    SOURCE_LABELS[entry.source_id ?? ""] ?? titles[entry.source_id ?? ""] ?? entry.source_id ?? "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Що з запису довідника варто показати в розгорнутому рядку. */
function statsOf(data: Record<string, unknown>): [string, string][] {
  const rows: [string, string][] = [];
  const rarity = RARITY_LABELS[String(data.rarity ?? "").toLowerCase()];
  if (rarity) rows.push(["Рідкість", rarity]);
  if (data.armor_class) rows.push(["Клас захисту", String(data.armor_class)]);
  if (data.damage) rows.push(["Урон", weaponDamage(String(data.damage))]);
  if (data.properties) rows.push(["Властивості", weaponNotes(String(data.properties))]);
  if (data.cost) rows.push(["Ціна", moneyLabel(data.cost)]);
  if (data.weight) rows.push(["Вага", weightLabel(data.weight)]);
  if (data.attunement === true) rows.push(["Настроювання", "потрібне"]);
  return rows;
}

/** Рядок таблиці спорядження («Chain Mail · 75 gp · 55 lb. · AC 16») — це не
 * опис, а цифри: їх показує сітка характеристик, а не текст правила. */
function isStatLine(text: string): boolean {
  return text.length < 220 && (text.match(/ · /g)?.length ?? 0) >= 2;
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
  const [open, setOpen] = useState(false);
  const [catalog, setCatalog] = useState<ItemSearchResult[] | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [ukTexts, setUkTexts] = useState<Record<string, { name?: string; text?: string }>>({});
  const [query, setQuery] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [magical, setMagical] = useState<"any" | "yes" | "no">("any");
  const [source, setSource] = useState("");
  const [visible, setVisible] = useState(40);
  const [adding, setAdding] = useState<string | null>(null);
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [form, setForm] = useState<{ index: number | null; draft: Draft } | null>(null);
  const [confirmIndex, setConfirmIndex] = useState<number | null>(null);
  const [detail, setDetail] = useState<{
    index: number;
    text: string;
    english: string | null;
    showEnglish: boolean;
    loading: boolean;
    stats: [string, string][];
  } | null>(null);
  const loaded = useRef(false);

  //: Описи (українські) потрібні й без каталогу — коли розгортають предмет.
  useEffect(() => {
    let alive = true;
    void fetchItemsUk().then((texts) => {
      if (alive) setUkTexts(texts);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!open || loaded.current) return;
    loaded.current = true;
    let alive = true;
    void Promise.all([fetchItemCatalog(), fetchItemsUk(), fetchBookTitles()])
      .then(([rows, texts, books]) => {
        if (!alive) return;
        setCatalog(rows);
        setUkTexts(texts);
        setTitles(books);
      })
      .catch((error: unknown) => {
        if (alive) setCatalogError(error instanceof Error ? error.message : String(error));
      });
    return () => {
      alive = false;
    };
  }, [open]);

  /** Один предмет у кількох книгах: у списку він має бути один раз. */
  const entries = useMemo(() => {
    if (!catalog) return [];
    const seen = new Map<string, ItemSearchResult>();
    for (const entry of catalog) {
      const key = itemKey(entry.name_en);
      const previous = seen.get(key);
      if (!previous || entryScore(entry) > entryScore(previous)) seen.set(key, entry);
    }
    return Array.from(seen.values()).sort((left, right) =>
      left.name_en.localeCompare(right.name_en),
    );
  }, [catalog]);

  /** Джерела, яких у каталозі найбільше — саме їх і даємо чипами. */
  const sources = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entry of entries) {
      const id = entry.source_id ?? "";
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 6)
      .map(([id]) => id);
  }, [entries]);

  const byName = useMemo(() => {
    const map = new Map<string, ItemSearchResult>();
    for (const entry of entries) map.set(itemKey(entry.name_en), entry);
    return map;
  }, [entries]);

  const filtered = useMemo(() => {
    const wanted = itemKey(query);
    const picked = new Set(types);
    return entries.filter((entry) => {
      const data = dataOf(entry);
      if (picked.size && !picked.has(typeOf(entry))) return false;
      if (source && entry.source_id !== source) return false;
      if (magical !== "any" && Boolean(data.magical) !== (magical === "yes")) return false;
      if (!wanted) return true;
      const haystack = itemKey(`${entry.name_en} ${itemLabel(entry.name_en)}`);
      return haystack.includes(wanted);
    });
  }, [entries, magical, query, source, types]);

  const shown = filtered.slice(0, visible);

  function openAdd(entry?: ItemSearchResult) {
    setConfirmIndex(null);
    setForm({ index: null, draft: entry ? draftFromEntry(entry) : { ...EMPTY } });
  }

  function openEdit(index: number) {
    setConfirmIndex(null);
    setForm({ index, draft: draftFromItem(items[index]) });
  }

  async function addFromCatalog(entry: ItemSearchResult) {
    //: DDB-звичка: повторне «Додати» збільшує кількість, а не плодить рядки.
    const same = items.findIndex(
      (item) => itemKey(item.name_en) === itemKey(entry.name_en),
    );
    setAdding(entry.id);
    const ok =
      same >= 0
        ? await onUpdate(same, { quantity: items[same].quantity + 1 })
        : await onAdd(bodyFromEntry(entry));
    setAdding(null);
    if (ok) {
      setJustAdded(entry.id);
      window.setTimeout(() => setJustAdded((current) => (current === entry.id ? null : current)), 1600);
    }
  }

  async function remove(index: number) {
    const ok = await onRemove(index);
    if (!ok) return;
    setConfirmIndex(null);
    if (form?.index === index) setForm(null);
    if (detail?.index === index) setDetail(null);
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

  /** Повний запис довідника: у каталозі лише короткий, без тексту книги. */
  async function entryFor(item: SheetItem): Promise<CompendiumEntry | null> {
    const key = itemKey(item.name_en);
    const known = byName.get(key);
    if (item.entry_id) {
      try {
        return await fetchEntry(item.entry_id);
      } catch {
        /* запис могли перенести — пробуємо за назвою */
      }
    }
    if (known) {
      try {
        return await fetchEntry(known.id);
      } catch {
        /* далі пошук */
      }
    }
    try {
      const payload = await searchItems(item.name_en, 5);
      const hit = payload.items.find((row) => itemKey(row.name_en) === key);
      return hit ? await fetchEntry(hit.id) : null;
    } catch {
      return null;
    }
  }

  async function toggleDetail(index: number) {
    if (detail?.index === index) {
      setDetail(null);
      return;
    }
    const item = items[index];
    const translated = ukTexts[itemKey(item.name_en)]?.text ?? "";
    const known = byName.get(itemKey(item.name_en));
    setDetail({
      index,
      text: translated,
      english: null,
      showEnglish: false,
      loading: true,
      stats: known ? statsOf(dataOf(known)) : [],
    });
    const entry = await entryFor(item);
    const raw = entry?.text_en?.trim() ?? "";
    const english = raw && !isStatLine(raw) ? raw : null;
    const stats = entry ? statsOf((entry.data ?? {}) as Record<string, unknown>) : [];
    setDetail((current) =>
      current?.index === index
        ? {
            index,
            text: current.text || english || "",
            english,
            showEnglish: current.showEnglish,
            loading: false,
            stats: current.stats.length ? current.stats : stats,
          }
        : current,
    );
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
          placeholder="Пошук у довіднику: longsword, зілля, кольчуга…"
          onChange={(event) => {
            setQuery(event.target.value);
            setVisible(40);
            if (event.target.value.trim().length >= 2) setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setQuery("");
          }}
          aria-label="Пошук предмета в довіднику"
        />
        <button
          type="button"
          className={`button ${open ? "" : "button--primary"}`}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Згорнути каталог" : "Каталог"}
        </button>
        <button type="button" className="button" disabled={disabled} onClick={() => openAdd()}>
          Свій предмет
        </button>
      </div>

      {open ? (
        <section className="inv-catalog">
          <div className="chip-row inv-catalog__filters">
            {TYPE_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`chip ${types.includes(filter.value) ? "chip--active" : ""}`}
                onClick={() =>
                  setTypes((current) =>
                    current.includes(filter.value)
                      ? current.filter((value) => value !== filter.value)
                      : [...current, filter.value],
                  )
                }
              >
                {filter.label}
              </button>
            ))}
            <button
              type="button"
              className={`chip ${types.includes(OTHER) ? "chip--active" : ""}`}
              onClick={() =>
                setTypes((current) =>
                  current.includes(OTHER)
                    ? current.filter((value) => value !== OTHER)
                    : [...current, OTHER],
                )
              }
            >
              Інше
            </button>
          </div>

          <div className="chip-row inv-catalog__filters">
            <button
              type="button"
              className={`chip ${magical === "any" ? "chip--active" : ""}`}
              onClick={() => setMagical("any")}
            >
              усі
            </button>
            <button
              type="button"
              className={`chip ${magical === "yes" ? "chip--active" : ""}`}
              onClick={() => setMagical("yes")}
            >
              магічні
            </button>
            <button
              type="button"
              className={`chip ${magical === "no" ? "chip--active" : ""}`}
              onClick={() => setMagical("no")}
            >
              звичайні
            </button>
          </div>

          <div className="chip-row inv-catalog__filters">
            <button
              type="button"
              className={`chip ${source === "" ? "chip--active" : ""}`}
              onClick={() => setSource("")}
            >
              усі джерела
            </button>
            {sources.map((id) => (
              <button
                key={id}
                type="button"
                className={`chip ${source === id ? "chip--active" : ""}`}
                onClick={() => setSource(source === id ? "" : id)}
              >
                {SOURCE_LABELS[id] ?? titles[id] ?? id}
              </button>
            ))}
          </div>

          {catalogError ? <p className="hint hint--warn">Каталог не завантажився: {catalogError}</p> : null}
          {!catalog && !catalogError ? <p className="hint">Завантажуємо каталог…</p> : null}
          {catalog ? (
            <p className="hint">
              {filtered.length} з {entries.length} предметів
              {types.length || source || magical !== "any" || query.trim() ? " за фільтром" : ""}
            </p>
          ) : null}

          {shown.length ? (
            <ul className="inv-catalog__list">
              {shown.map((entry) => {
                const busy = adding === entry.id;
                const added = justAdded === entry.id;
                return (
                  <li key={entry.id} className="inv-catalog__row">
                    <span className="inv-catalog__main">
                      <span className="inv-catalog__name">{itemLabel(entry.name_en)}</span>
                      <span className="inv-catalog__meta">{catalogMeta(entry, titles) || "—"}</span>
                    </span>
                    <button
                      type="button"
                      className="button button--primary inv-catalog__add"
                      disabled={disabled || busy}
                      onClick={() => void addFromCatalog(entry)}
                    >
                      {busy ? "…" : added ? "Додано" : "Додати"}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {filtered.length > shown.length ? (
            <button
              type="button"
              className="button inv-catalog__more"
              onClick={() => setVisible((value) => value + 60)}
            >
              Показати ще ({filtered.length - shown.length})
            </button>
          ) : null}
        </section>
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
            const entry = byName.get(itemKey(item.name_en));
            const data = entry ? dataOf(entry) : {};
            const rarity = RARITY_LABELS[String(data.rarity ?? "").toLowerCase()] ?? "";
            const meta = [
              ITEM_KIND_LABELS[item.kind] ?? item.kind,
              rarity,
              data.attunement === true ? "настроювання" : "",
              item.damage,
              item.armor_base ? `КЗ ${item.armor_base}` : "",
              item.dex_cap !== null && item.armor_base ? `СПР ≤ ${item.dex_cap}` : "",
              item.weight_lb ? `${item.weight_lb} фнт` : "",
              item.notes,
            ].filter(Boolean);
            const isOpen = detail?.index === index;
            const stats = detail?.index === index && detail.stats.length
              ? detail.stats
              : entry
                ? statsOf(data)
                : [];
            return (
              <li
                key={`${item.name_en}-${index}`}
                className={`item-row ${form?.index === index ? "is-editing" : ""} ${
                  isOpen ? "is-open" : ""
                }`}
              >
                <span className="item-row__line">
                  <span className="item-main">
                    <button
                      type="button"
                      className="item-name item-name--button"
                      onClick={() => void toggleDetail(index)}
                      title={isOpen ? "Згорнути опис" : "Показати опис"}
                    >
                      {itemLabel(item.name_en)}
                      {item.quantity > 1 ? ` × ${item.quantity}` : ""}
                      <span className="item-name__caret">{isOpen ? "▴" : "▾"}</span>
                    </button>
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
                </span>

                {isOpen ? (
                  <div className="item-detail">
                    {stats.length ? (
                      <dl className="item-detail__stats">
                        {stats.map(([label, value]) => (
                          <div key={label} className="item-detail__stat">
                            <dt>{label}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                    {detail.loading && !detail.text ? (
                      <p className="hint">Шукаємо опис…</p>
                    ) : detail.text ? (
                      <RuleText text={detail.showEnglish && detail.english ? detail.english : detail.text} />
                    ) : (
                      <p className="hint">
                        Опису в книзі немає — лише цифри вище. Свої нотатки можна
                        дописати кнопкою ✎.
                      </p>
                    )}
                    {detail.english && detail.text ? (
                      <button
                        type="button"
                        className="link-button item-detail__toggle"
                        onClick={() =>
                          setDetail({ ...detail, showEnglish: !detail.showEnglish })
                        }
                      >
                        {detail.showEnglish ? "показати українською" : "показати оригінал"}
                      </button>
                    ) : null}
                    {!detail.text && detail.english ? (
                      <p className="hint">Перекладу ще немає — показуємо оригінал.</p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="hint">Порожньо. Відкрийте каталог і додайте предмет.</p>
      )}
    </>
  );
}
