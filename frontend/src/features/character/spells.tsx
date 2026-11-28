/** Закляття під час гри: денна підготовка й додавання поза рівнем.

 * Дві різні дії, які й у книзі різні:
 *
 * * **підготувати** (PHB, p. 201) — на день вибрати набір зі списку класу,
 *   не більше ніж «модифікатор + рівень»; учорашній набір замінюється;
 * * **додати** — взяти закляття в лист (зі списку класу) або вписати своє,
 *   якого немає в книзі. Власне позначається словом «власне» і не вдає
 *   книжкове: довідник його не знає, текст дав гравець.
 *
 * Числа не рахуються тут: ліміт і найвищий рівень прийшли з сервера
 * (`spellcasting.classes`), а перевірку все одно робить агрегат.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { OTHER_SPELL_CLASS, fetchClassSpells } from "../../api";
import type { CustomSpellFields as CustomSpellFieldsBody, SpellBody } from "../../api";
import type { SheetSpell, SheetSpellcasting } from "../wizard/types";

import { spellLabel, termLabel } from "./uk";

type CastingClass = SheetSpellcasting["classes"][number];

type Pick = { name_en: string; level: number; entry_id: string | null };

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function levelLabel(level: number): string {
  return level === 0 ? "заговір" : `${level} рівень`;
}

function spellLevelOf(entry: { data: Record<string, unknown> }): number {
  return Number(entry.data.level ?? 0);
}

/** Ліміт і найвищий рівень — з сервера, не з клієнта. */
function preparedLimit(item: CastingClass): number {
  return item.prepared_limit ?? 0;
}

// ---------------------------------------------------------------------------
// денна підготовка
// ---------------------------------------------------------------------------

export function SpellsPreparePanel({
  casting,
  spells,
  busy,
  onSave,
}: {
  casting: SheetSpellcasting;
  spells: SheetSpell[];
  busy: boolean;
  onSave: (classKey: string, picks: Pick[]) => Promise<boolean>;
}) {
  const preparing = casting.classes.filter((item) => item.prepares && item.prepared_limit !== null);
  if (!preparing.length) return null;

  return (
    <>
      <h3 className="sheet-work__title">
        <span>Підготовка на день</span>
        <span className="short">зі списку класу</span>
      </h3>
      {preparing.map((item) => (
        <PreparedClass key={item.key} casting={item} spells={spells} busy={busy} onSave={onSave} />
      ))}
    </>
  );
}

function PreparedClass({
  casting,
  spells,
  busy,
  onSave,
}: {
  casting: CastingClass;
  spells: SheetSpell[];
  busy: boolean;
  onSave: (classKey: string, picks: Pick[]) => Promise<boolean>;
}) {
  // Лише закляття, обрані цим класом: доменні (підклас) мають той самий
  // class_key, але завжди підготовлені й у ліміт не входять.
  const own = spells.filter((spell) => spell.class_key === casting.key && spell.source === "class");
  const learned = own.filter((spell) => spell.level > 0 && !spell.custom);
  const cantrips = own.filter((spell) => spell.level === 0);
  const custom = own.filter((spell) => spell.custom);
  const preparedNames = learned.filter((spell) => spell.prepared).map((spell) => spell.name_en);
  const signature = preparedNames.slice().sort().join("|");

  const [selected, setSelected] = useState<string[]>(preparedNames);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Після збереження сервер повертає новий лист — підтягуємо його набір.
  useEffect(() => {
    setSelected(signature ? signature.split("|") : []);
  }, [signature]);

  const list = useQuery({
    queryKey: ["class-spells", casting.key, casting.max_spell_level],
    queryFn: () => fetchClassSpells(casting.key, casting.max_spell_level),
  });

  const options = useMemo(() => {
    const map = new Map<string, Pick>();
    // Маг готує лише з книги заклять (PHB, p. 114), а не з усього списку класу.
    for (const entry of casting.key === "wizard" ? [] : (list.data?.items ?? [])) {
      const level = spellLevelOf(entry);
      // Заговори не готують: вони змінюються лише з рівнем.
      if (level === 0) continue;
      map.set(entry.name_en.toLocaleLowerCase(), {
        name_en: entry.name_en,
        level,
        entry_id: entry.id,
      });
    }
    // Те, що вже є в листі (підклас, давній вибір), теж має бути у списку.
    for (const spell of learned) {
      map.set(spell.name_en.toLocaleLowerCase(), {
        name_en: spell.name_en,
        level: spell.level,
        entry_id: spell.entry_id,
      });
    }
    return Array.from(map.values()).sort(
      (left, right) => left.level - right.level || left.name_en.localeCompare(right.name_en),
    );
  }, [list.data, learned, casting.key]);

  const needle = query.trim().toLocaleLowerCase();
  const visible = needle
    ? options.filter(
        (option) =>
          option.name_en.toLocaleLowerCase().includes(needle) ||
          spellLabel(option.name_en).toLocaleLowerCase().includes(needle),
      )
    : options;

  const limit = preparedLimit(casting);
  // Власні закляття теж займають місце в ліміті — рахуємо їх одразу, інакше
  // «обрано 0/1» дозволяло б зберегти набір, який сервер відхилить.
  const occupiedByCustom = custom.filter((item) => item.prepared).length;
  const used = selected.length + occupiedByCustom;
  const over = used > limit;

  function toggle(nameEn: string) {
    setError(null);
    setSelected((current) =>
      current.includes(nameEn) ? current.filter((item) => item !== nameEn) : [...current, nameEn],
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const picks = selected
        .map((name) => options.find((option) => option.name_en === name))
        .filter((option): option is Pick => Boolean(option));
      const ok = await onSave(casting.key, picks);
      if (!ok) setError("Не вдалося зберегти підготовку");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="spell-prep">
      <header className="spell-prep__head">
        <span className="spell-prep__class">{termLabel(casting.name_en)}</span>
        <span className={`spell-prep__count ${over ? "is-over" : ""}`}>
          {occupiedByCustom
            ? `обрано ${selected.length} + власних ${occupiedByCustom} / ${limit}`
            : `обрано ${selected.length} / ${limit}`}
        </span>
      </header>

      <div className="spell-prep__tools">
        <input
          className="inv-search__input"
          type="search"
          value={query}
          placeholder={`Пошук у списку ${termLabel(casting.name_en)}…`}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy || over}
          onClick={() => void save()}
        >
          {saving ? "Зберігаємо…" : "Зберегти підготовку"}
        </button>
      </div>

      {error ? <p className="status status--error">{error}</p> : null}
      {list.isPending ? <p className="hint">Читаємо список класу…</p> : null}
      {list.error ? <p className="hint hint--warn">Список не завантажився: {messageOf(list.error)}</p> : null}

      <div className="spell-prep__list">
        {visible.map((option) => (
          <label
            key={option.name_en}
            className={`chip chip--row ${selected.includes(option.name_en) ? "chip--active" : ""}`}
          >
            <input
              type="checkbox"
              checked={selected.includes(option.name_en)}
              onChange={() => toggle(option.name_en)}
            />
            <span>{spellLabel(option.name_en)}</span>
            <span className="meta">{levelLabel(option.level)}</span>
          </label>
        ))}
        {!visible.length && !list.isPending ? <p className="hint">Нічого не знайшли — змініть пошук.</p> : null}
      </div>

      {over ? (
        <p className="hint hint--warn">
          Більше, ніж клас готує на день: приберіть {used - limit} — сервер інакше відмовить.
        </p>
      ) : null}

      {cantrips.length ? (
        <p className="hint">
          Заговори не змінюються підготовкою: {cantrips.map((item) => spellLabel(item.name_en)).join(", ")}.
        </p>
      ) : null}
      {custom.length ? (
        <p className="hint">
          Власні закляття завжди доступні й займають місце в ліміті: {custom.map((item) => item.name_en).join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// власне закляття: поля, спільні для додавання й редагування
// ---------------------------------------------------------------------------

/** Чернетка власного закляття у формі (рядки — як у полях вводу). */
type CustomDraft = {
  name: string;
  level: number;
  description: string;
  school: string;
  casting_time: string;
  range: string;
  duration: string;
  components: string;
  concentration: boolean;
  ritual: boolean;
};

const EMPTY_DRAFT: CustomDraft = {
  name: "",
  level: 1,
  description: "",
  school: "",
  casting_time: "",
  range: "",
  duration: "",
  components: "",
  concentration: false,
  ritual: false,
};

function draftOf(spell: SheetSpell): CustomDraft {
  return {
    name: spell.name_en,
    level: spell.level,
    description: spell.description ?? "",
    school: spell.school ?? "",
    casting_time: spell.casting_time ?? "",
    range: spell.range ?? "",
    duration: spell.duration ?? "",
    components: spell.components ?? "",
    concentration: Boolean(spell.concentration),
    ritual: Boolean(spell.ritual),
  };
}

/** Поля чернетки для сервера: порожні рядки — `null`. */
function draftBody(draft: CustomDraft): Omit<SpellBody, "class_key" | "name_en"> {
  const text = (value: string) => value.trim() || null;
  return {
    level: draft.level,
    description: text(draft.description),
    school: text(draft.school),
    casting_time: text(draft.casting_time),
    range: text(draft.range),
    duration: text(draft.duration),
    components: text(draft.components),
    concentration: draft.concentration,
    ritual: draft.ritual,
  };
}

const META_FIELDS: {
  key: "school" | "casting_time" | "range" | "duration" | "components";
  label: string;
  hint: string;
}[] = [
  { key: "school", label: "Школа", hint: "втілення, ілюзія…" },
  { key: "casting_time", label: "Час", hint: "1 дія" },
  { key: "range", label: "Дистанція", hint: "18 м, дотик" },
  { key: "duration", label: "Тривалість", hint: "1 хвилина" },
  { key: "components", label: "Компоненти", hint: "В, С, М (перо)" },
];

function CustomSpellFields({ draft, onChange }: { draft: CustomDraft; onChange: (draft: CustomDraft) => void }) {
  const set = <K extends keyof CustomDraft>(key: K, value: CustomDraft[K]) => onChange({ ...draft, [key]: value });
  return (
    <>
      <label className="field inv-form__wide">
        Назва
        <input
          className="inv-search__input"
          value={draft.name}
          maxLength={120}
          placeholder="Наприклад, «Благословення столу»"
          onChange={(event) => set("name", event.target.value)}
        />
      </label>
      <label className="field">
        Рівень
        <select className="select" value={draft.level} onChange={(event) => set("level", Number(event.target.value))}>
          <option value={0}>заговір</option>
          {Array.from({ length: 9 }, (_, index) => index + 1).map((value) => (
            <option key={value} value={value}>
              {value} рівень
            </option>
          ))}
        </select>
      </label>
      {META_FIELDS.map((item) => (
        <label key={item.key} className="field">
          {item.label}
          <input
            className="inv-search__input"
            value={draft[item.key]}
            maxLength={120}
            placeholder={item.hint}
            onChange={(event) => set(item.key, event.target.value)}
          />
        </label>
      ))}
      <label className="field inv-form__check">
        <input
          type="checkbox"
          checked={draft.concentration}
          onChange={(event) => set("concentration", event.target.checked)}
        />
        концентрація
      </label>
      <label className="field inv-form__check">
        <input type="checkbox" checked={draft.ritual} onChange={(event) => set("ritual", event.target.checked)} />
        ритуал
      </label>
      <label className="field inv-form__wide">
        Текст (що робить)
        <textarea
          className="spell-add__text"
          rows={3}
          maxLength={4000}
          value={draft.description}
          placeholder="Своїми словами: ефект, урон, рятунок. Це побачить лист і PDF."
          onChange={(event) => set("description", event.target.value)}
        />
      </label>
    </>
  );
}

/** Клас власного закляття: клас персонажа або «поза класом» (дар майстра, предмет). */
function CustomClassSelect({
  classes,
  value,
  onChange,
}: {
  classes: CastingClass[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      Чий
      <select className="select" value={value} onChange={(event) => onChange(event.target.value)}>
        {classes.map((item) => (
          <option key={item.key} value={item.key}>
            {termLabel(item.name_en)}
          </option>
        ))}
        <option value={OTHER_SPELL_CLASS}>поза класом</option>
      </select>
    </label>
  );
}

function customHint(classKey: string): string {
  return classKey === OTHER_SPELL_CLASS
    ? "Поза класом — дар майстра чи сила предмета: місця в лімітах не займає, КС і атаки класу не має (впишіть їх у текст)."
    : "Власне закляття класу завжди підготовлене й займає місце в денному ліміті — якщо місця немає, спершу зніміть підготовку з іншого.";
}

// ---------------------------------------------------------------------------
// додати закляття
// ---------------------------------------------------------------------------

export function AddSpellForm({
  casting,
  busy,
  onAdd,
}: {
  casting: SheetSpellcasting;
  busy: boolean;
  onAdd: (spell: SpellBody) => Promise<boolean>;
}) {
  const classes = casting.classes;
  // Без класу, що чарує, лишається тільки власне закляття поза класом.
  const onlyCustom = !classes.length;
  const [open, setOpen] = useState(false);
  const [classKey, setClassKey] = useState(classes[0]?.key ?? OTHER_SPELL_CLASS);
  const [custom, setCustom] = useState(onlyCustom);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Pick | null>(null);
  const [draft, setDraft] = useState<CustomDraft>(EMPTY_DRAFT);
  const [prepared, setPrepared] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const current = classes.find((item) => item.key === classKey) ?? classes[0];
  const list = useQuery({
    queryKey: ["class-spells", current?.key ?? "", current?.max_spell_level ?? 0],
    queryFn: () => fetchClassSpells(current?.key ?? "", current?.max_spell_level ?? 0),
    enabled: open && !custom && Boolean(current),
  });

  function reset() {
    setPicked(null);
    setDraft(EMPTY_DRAFT);
    setQuery("");
    setError(null);
    setPrepared(Boolean(current?.prepares));
  }

  function openForm() {
    reset();
    setCustom(onlyCustom);
    setOpen(true);
  }

  const needle = query.trim().toLocaleLowerCase();
  const options = (list.data?.items ?? [])
    .map((entry) => ({
      name_en: entry.name_en,
      level: spellLevelOf(entry),
      entry_id: entry.id,
    }))
    .filter(
      (entry) =>
        !needle ||
        spellLabel(entry.name_en).toLocaleLowerCase().includes(needle) ||
        entry.name_en.toLocaleLowerCase().includes(needle),
    )
    .slice(0, 40);

  async function submit() {
    const finalName = custom ? draft.name.trim() : (picked?.name_en ?? "");
    if (!finalName) {
      setError(custom ? "Впишіть назву власного закляття" : "Оберіть закляття зі списку");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body: SpellBody = custom
        ? { class_key: classKey, name_en: finalName, custom: true, prepared: true, ...draftBody(draft) }
        : {
            class_key: current?.key ?? classKey,
            name_en: finalName,
            level: picked?.level ?? 0,
            entry_id: picked?.entry_id ?? null,
            prepared,
            custom: false,
            description: null,
          };
      const ok = await onAdd(body);
      if (!ok) {
        setError("Не вдалося додати закляття");
        return;
      }
      setOpen(false);
      reset();
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="button spell-add__open" disabled={busy} onClick={openForm}>
        {onlyCustom ? "+ Додати власне закляття" : "+ закляття"}
      </button>
    );
  }

  return (
    <section className="inv-form spell-add">
      <p className="inv-form__title">{onlyCustom ? "Власне закляття" : "Додати закляття"}</p>
      <div className="inv-form__grid">
        {custom ? (
          <CustomClassSelect classes={classes} value={classKey} onChange={setClassKey} />
        ) : classes.length > 1 ? (
          <label className="field">
            Клас
            <select
              className="select"
              value={current?.key ?? ""}
              onChange={(event) => {
                setClassKey(event.target.value);
                setPicked(null);
                setQuery("");
              }}
            >
              {classes.map((item) => (
                <option key={item.key} value={item.key}>
                  {termLabel(item.name_en)}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {onlyCustom ? null : (
          <label className="field inv-form__check inv-form__wide">
            <input
              type="checkbox"
              checked={custom}
              onChange={(event) => {
                setCustom(event.target.checked);
                // Назад до книжкового — клас мусить бути класом персонажа.
                if (!event.target.checked && classKey === OTHER_SPELL_CLASS) setClassKey(classes[0]?.key ?? "");
                setPicked(null);
                setError(null);
              }}
            />
            власне закляття (немає в книзі)
          </label>
        )}

        {custom ? (
          <CustomSpellFields draft={draft} onChange={setDraft} />
        ) : (
          <>
            <label className="field inv-form__wide">
              Пошук у списку класу
              <input
                className="inv-search__input"
                type="search"
                value={query}
                placeholder="Частина назви…"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="spell-add__results">
              {list.isPending ? <p className="hint">Читаємо список класу…</p> : null}
              {list.error ? <p className="hint hint--warn">Список не завантажився: {messageOf(list.error)}</p> : null}
              {options.map((option) => (
                <button
                  key={option.name_en}
                  type="button"
                  className={`chip ${picked?.name_en === option.name_en ? "chip--active" : ""}`}
                  onClick={() => {
                    setPicked(option);
                    setError(null);
                  }}
                >
                  {spellLabel(option.name_en)} · {levelLabel(option.level)}
                </button>
              ))}
              {!options.length && !list.isPending ? (
                <p className="hint">У списку нічого не знайшли. Якщо це ваше закляття — увімкніть «власне».</p>
              ) : null}
            </div>
          </>
        )}

        {custom ? (
          <p className="hint inv-form__wide">{customHint(classKey)}</p>
        ) : (
          <label className="field inv-form__check inv-form__wide">
            <input type="checkbox" checked={prepared} onChange={(event) => setPrepared(event.target.checked)} />
            підготовлене зараз
          </label>
        )}
      </div>

      {error ? <p className="status status--error">{error}</p> : null}

      <div className="inv-form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy}
          onClick={() => void submit()}
        >
          {saving ? "Додаємо…" : "Додати"}
        </button>
        <button type="button" className="button" onClick={() => setOpen(false)}>
          Скасувати
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// змінити власне закляття
// ---------------------------------------------------------------------------

export function EditCustomSpellForm({
  spell,
  casting,
  busy,
  onSave,
  onCancel,
}: {
  spell: SheetSpell;
  casting: SheetSpellcasting;
  busy: boolean;
  onSave: (fields: CustomSpellFieldsBody) => Promise<boolean>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<CustomDraft>(() => draftOf(spell));
  const [classKey, setClassKey] = useState(spell.class_key ?? OTHER_SPELL_CLASS);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!draft.name.trim()) {
      setError("Впишіть назву власного закляття");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const ok = await onSave({ name_en: draft.name.trim(), class_key: classKey, ...draftBody(draft) });
      if (!ok) setError("Не вдалося зберегти закляття");
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="inv-form spell-add spell-edit">
      <p className="inv-form__title">Змінити власне закляття</p>
      <div className="inv-form__grid">
        <CustomClassSelect classes={casting.classes} value={classKey} onChange={setClassKey} />
        <CustomSpellFields draft={draft} onChange={setDraft} />
        <p className="hint inv-form__wide">{customHint(classKey)}</p>
      </div>
      {error ? <p className="status status--error">{error}</p> : null}
      <div className="inv-form__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={saving || busy}
          onClick={() => void submit()}
        >
          {saving ? "Зберігаємо…" : "Зберегти"}
        </button>
        <button type="button" className="button" onClick={onCancel}>
          Скасувати
        </button>
      </div>
    </section>
  );
}
