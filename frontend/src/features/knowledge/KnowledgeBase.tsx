/**
 * Довідник для всіх, навіть без входу: види, класи, передісторії, риси,
 * закляття, опційні вміння, предмети.
 *
 * Картки видів, класів і передісторій — ті самі, що у візарді (`SpeciesSummary`,
 * `classFacts`, `backgroundFacts`): довідник і створення персонажа показують
 * одне й те саме. Пошук — українською й англійською, на клієнті: записів
 * сотні, а не мільйони, і фільтр має спрацьовувати на кожну літеру.
 */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  fetchCategory,
  fetchClassFeatures,
  fetchEntry,
  fetchKbBackgrounds,
  fetchKbClasses,
  fetchKbSpecies,
  fetchSubclassDetails,
} from "../../api";
import type { ItemSearchResult } from "../../api";
import { castingTimeLabel, durationLabel, rangeLabel, schoolLabel } from "../../labels";
import { ItemCatalogBrowser } from "../character/inventory";
import { RuleText } from "../character/panels";
import { featureLabel, featureText, itemLabel, speciesLabel, termLabel, withEnglish } from "../character/uk";
import { FactList, SpeciesSummary, TraitList, backgroundFacts, classFacts, speciesFacts } from "../wizard/steps";
import type { BackgroundView, ClassView, SpeciesView } from "../wizard/types";

export type KbSection = "species" | "classes" | "backgrounds" | "feats" | "spells" | "options" | "items";

const SECTIONS: { id: KbSection; label: string; hint: string }[] = [
  { id: "species", label: "Види", hint: "раси й підраси: швидкість, темний зір, особливості" },
  { id: "classes", label: "Класи", hint: "хіти, володіння, уміння за рівнями, підкласи" },
  { id: "backgrounds", label: "Передісторії", hint: "навички, інструменти, риса, спорядження" },
  { id: "feats", label: "Риси", hint: "замість підвищення характеристик" },
  { id: "spells", label: "Закляття", hint: "рівень, школа, час, дистанція, опис" },
  { id: "options", label: "Опційні вміння", hint: "виклики, бойові стилі, маневри, інфузії" },
  { id: "items", label: "Предмети", hint: "зброя, броня, спорядження, магічні предмети" },
];

const CATEGORY: Partial<Record<KbSection, string>> = {
  feats: "feat",
  spells: "spell",
  options: "optionalfeature",
};

export function isKbSection(value: string | undefined): value is KbSection {
  return SECTIONS.some((section) => section.id === value);
}

function norm(value: string): string {
  return value.toLocaleLowerCase("uk").replace(/[’ʼ']/g, "'").trim();
}

function matches(query: string, ...values: (string | null | undefined)[]): boolean {
  const wanted = norm(query);
  if (!wanted) return true;
  return values.some((value) => value && norm(value).includes(wanted));
}

export function KnowledgeBase({
  section,
  entryKey,
  go,
}: {
  section?: KbSection;
  entryKey?: string;
  go: (section?: KbSection, key?: string) => void;
}) {
  return (
    <section className="kb">
      <header className="kb__head">
        <h2>Довідник</h2>
        <p className="lead">
          Правила Книги гравця 2014 і доповнень українською. Назви — «Українська (English)»; там, де переклад ще не
          готовий, показано текст книги англійською.
        </p>
      </header>
      <nav className="chip-row kb__nav" aria-label="Розділи довідника">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`chip ${section === item.id ? "chip--active" : ""}`}
            aria-current={section === item.id ? "page" : undefined}
            onClick={() => go(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      {!section ? (
        <ul className="kb__sections">
          {SECTIONS.map((item) => (
            <li key={item.id}>
              <button type="button" className="kb__section-card" onClick={() => go(item.id)}>
                <strong>{item.label}</strong>
                <span className="meta">{item.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {section === "species" ? <SpeciesSection entryKey={entryKey} go={go} /> : null}
      {section === "classes" ? <ClassesSection entryKey={entryKey} go={go} /> : null}
      {section === "backgrounds" ? <BackgroundsSection entryKey={entryKey} go={go} /> : null}
      {section && CATEGORY[section] ? (
        <EntriesSection key={section} section={section} category={CATEGORY[section]!} entryKey={entryKey} go={go} />
      ) : null}
      {section === "items" ? (
        <div className="kb__items">
          <ItemCatalogBrowser initialOpen />
        </div>
      ) : null}
    </section>
  );
}

// --- спільне -----------------------------------------------------------------

function Status({ pending, error }: { pending: boolean; error: unknown }) {
  if (pending) return <p className="status">Читаємо довідник…</p>;
  if (error) {
    return (
      <p className="status status--error">
        Не вдалося прочитати: {error instanceof Error ? error.message : String(error)}
      </p>
    );
  }
  return null;
}

/** Список із пошуком і карткою вибраного запису під ним. */
function Browser<T>({
  items,
  keyOf,
  labelOf,
  metaOf,
  searchOf,
  selected,
  onSelect,
  placeholder,
  children,
}: {
  items: T[];
  keyOf: (item: T) => string;
  labelOf: (item: T) => string;
  metaOf?: (item: T) => string;
  searchOf: (item: T) => (string | null | undefined)[];
  selected?: string;
  onSelect: (key?: string) => void;
  placeholder: string;
  children?: ReactNode;
}) {
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(120);
  const filtered = useMemo(
    () => items.filter((item) => matches(query, ...searchOf(item))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, query],
  );
  const shown = filtered.slice(0, visible);

  return (
    <div className="kb__browser">
      {children ? <div className="kb__detail">{children}</div> : null}
      <input
        type="search"
        className="kb__search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={placeholder}
        aria-label="Пошук у розділі"
      />
      <p className="hint">
        {filtered.length} з {items.length}
      </p>
      <ul className="kb__list">
        {shown.map((item) => {
          const key = keyOf(item);
          return (
            <li key={key}>
              <button
                type="button"
                className={`kb__item ${selected === key ? "kb__item--active" : ""}`}
                aria-current={selected === key ? "true" : undefined}
                onClick={() => {
                  onSelect(selected === key ? undefined : key);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                <span>{labelOf(item)}</span>
                {metaOf ? <span className="meta">{metaOf(item)}</span> : null}
              </button>
            </li>
          );
        })}
      </ul>
      {filtered.length > shown.length ? (
        <button type="button" className="button" onClick={() => setVisible((value) => value + 200)}>
          Показати ще ({filtered.length - shown.length})
        </button>
      ) : null}
    </div>
  );
}

function DetailHead({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <header className="kb__detail-head">
      <h3>{title}</h3>
      <button type="button" className="link-button" onClick={onClose}>
        закрити
      </button>
    </header>
  );
}

// --- види --------------------------------------------------------------------

function SpeciesSection({ entryKey, go }: { entryKey?: string; go: (section?: KbSection, key?: string) => void }) {
  const query = useQuery({ queryKey: ["kb", "species"], queryFn: fetchKbSpecies, staleTime: Infinity });
  const items = query.data?.items ?? [];
  const selected = items.find((item) => item.key === entryKey);
  return (
    <>
      <Status pending={query.isPending} error={query.error} />
      <Browser<SpeciesView>
        items={items}
        keyOf={(item) => item.key}
        labelOf={(item) => speciesLabel(item.name_en)}
        metaOf={(item) => (item.subspecies?.length ? `підрас: ${item.subspecies.length}` : "")}
        searchOf={(item) => [
          item.name_en,
          speciesLabel(item.name_en),
          ...(item.subspecies ?? []).map((sub) => speciesLabel(sub.name_en)),
        ]}
        selected={entryKey}
        onSelect={(key) => go("species", key)}
        placeholder="Пошук: «дворф», «elf», «тифлінг»…"
      >
        {selected ? <SpeciesDetail item={selected} onClose={() => go("species")} /> : null}
      </Browser>
    </>
  );
}

function SpeciesDetail({ item, onClose }: { item: SpeciesView; onClose: () => void }) {
  return (
    <article className="species-card kb__card">
      <DetailHead title={speciesLabel(item.name_en)} onClose={onClose} />
      <SpeciesSummary base={item} effective={item} />
      {item.subspecies?.length ? (
        <>
          <h4 className="species-card__h4">Підраси</h4>
          {item.subspecies.map((sub) => (
            <details key={sub.key} className="reckoning">
              <summary>{speciesLabel(sub.name_en)}</summary>
              <FactList facts={speciesFacts(sub)} />
              {sub.description ? <RuleText text={sub.description_uk || sub.description} /> : null}
              {sub.traits?.length ? <TraitList title="Додає підраса" traits={sub.traits} /> : null}
            </details>
          ))}
        </>
      ) : null}
    </article>
  );
}

// --- класи -------------------------------------------------------------------

function ClassesSection({ entryKey, go }: { entryKey?: string; go: (section?: KbSection, key?: string) => void }) {
  const query = useQuery({ queryKey: ["kb", "classes"], queryFn: fetchKbClasses, staleTime: Infinity });
  const items = query.data?.items ?? [];
  const selected = items.find((item) => item.key === entryKey);
  return (
    <>
      <Status pending={query.isPending} error={query.error} />
      <Browser<ClassView>
        items={items}
        keyOf={(item) => item.key}
        labelOf={(item) => termLabel(item.name_en)}
        metaOf={(item) => `d${item.hit_die}`}
        searchOf={(item) => [item.name_en, termLabel(item.name_en)]}
        selected={entryKey}
        onSelect={(key) => go("classes", key)}
        placeholder="Пошук: «паладин», «wizard»…"
      >
        {selected ? <ClassDetail item={selected} onClose={() => go("classes")} /> : null}
      </Browser>
    </>
  );
}

function ClassDetail({ item, onClose }: { item: ClassView; onClose: () => void }) {
  const features = useQuery({
    queryKey: ["kb", "class-features", item.key],
    queryFn: () => fetchClassFeatures(item.key),
    staleTime: Infinity,
  });
  return (
    <article className="species-card kb__card">
      <DetailHead title={termLabel(item.name_en)} onClose={onClose} />
      <FactList facts={classFacts(item)} />
      {item.description ? (
        <details className="reckoning species-description" open>
          <summary>Опис класу</summary>
          <RuleText text={item.description_uk || item.description} />
        </details>
      ) : null}
      <h4 className="species-card__h4">Уміння за рівнями</h4>
      {features.isPending ? <p className="meta">Читаємо тексти вмінь…</p> : null}
      <ul className="plain-list">
        {(features.data?.features ?? []).map((feature) => (
          <li key={`${feature.level}-${feature.name_en}`}>
            <details className="reckoning">
              <summary>
                {feature.level} рівень · {featureLabel(feature.name_en, feature.name_uk)}
              </summary>
              <RuleText text={feature.text_uk || feature.text || ""} />
            </details>
          </li>
        ))}
      </ul>
      {item.subclasses_all?.length ? (
        <>
          <h4 className="species-card__h4">Підкласи — {item.subclasses_all.length}</h4>
          <ul className="plain-list">
            {item.subclasses_all.map((sub) => (
              <li key={sub.id}>
                <SubclassDetails id={sub.id} title={withEnglish(sub.name_en, sub.name_uk)} />
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}

function SubclassDetails({ id, title }: { id: string; title: string }) {
  const [open, setOpen] = useState(false);
  const details = useQuery({
    queryKey: ["kb", "subclass", id],
    queryFn: () => fetchSubclassDetails(id),
    enabled: open,
    staleTime: Infinity,
  });
  return (
    <details className="reckoning" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>{title}</summary>
      {details.isPending && open ? <p className="meta">Читаємо…</p> : null}
      {details.data ? (
        <>
          {details.data.description ? (
            <RuleText text={details.data.description_uk || details.data.description} />
          ) : null}
          <ul className="plain-list">
            {details.data.features.map((feature) => (
              <li key={`${feature.level}-${feature.name_en}`}>
                <details className="reckoning">
                  <summary>
                    {feature.level} рівень · {featureLabel(feature.name_en, feature.name_uk)}
                  </summary>
                  <RuleText text={feature.text_uk || feature.description} />
                </details>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </details>
  );
}

// --- передісторії ------------------------------------------------------------

function BackgroundsSection({ entryKey, go }: { entryKey?: string; go: (section?: KbSection, key?: string) => void }) {
  const query = useQuery({ queryKey: ["kb", "backgrounds"], queryFn: fetchKbBackgrounds, staleTime: Infinity });
  const items = query.data?.items ?? [];
  const selected = items.find((item) => item.key === entryKey);
  return (
    <>
      <Status pending={query.isPending} error={query.error} />
      <Browser<BackgroundView>
        items={items}
        keyOf={(item) => item.key}
        labelOf={(item) => termLabel(item.name_en)}
        metaOf={(item) => item.source_id}
        searchOf={(item) => [item.name_en, termLabel(item.name_en)]}
        selected={entryKey}
        onSelect={(key) => go("backgrounds", key)}
        placeholder="Пошук: «солдат», «sage»…"
      >
        {selected ? <BackgroundDetail item={selected} onClose={() => go("backgrounds")} /> : null}
      </Browser>
    </>
  );
}

function BackgroundDetail({ item, onClose }: { item: BackgroundView; onClose: () => void }) {
  return (
    <article className="species-card kb__card">
      <DetailHead title={termLabel(item.name_en)} onClose={onClose} />
      <FactList facts={backgroundFacts(item)} />
      {item.description ? (
        <details className="reckoning species-description" open>
          <summary>Опис передісторії</summary>
          <RuleText text={item.description_uk || item.description} />
        </details>
      ) : null}
      {item.feature_en ? (
        <details className="reckoning" open>
          <summary>Риса: {featureLabel(item.feature_en, item.feature_uk)}</summary>
          {item.feature_text ? (
            <RuleText text={featureText(item.feature_en, item.feature_text, item.feature_text_uk)} />
          ) : (
            <p className="hint">Опису риси в довіднику немає.</p>
          )}
        </details>
      ) : null}
      {item.equipment?.length ? (
        <>
          <h4 className="species-card__h4">Спорядження</h4>
          <ul className="plain-list">
            {item.equipment.map((row) => (
              <li key={row.text}>{row.text_uk || itemLabel(row.text)}</li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}

// --- риси, закляття, опційні вміння -------------------------------------------

/** Один запис на назву: те саме закляття є в кількох книгах (PHB і базові правила). */
function unique(rows: ItemSearchResult[]): ItemSearchResult[] {
  const seen = new Map<string, ItemSearchResult>();
  for (const row of rows) {
    const key = row.name_en.toLowerCase();
    if (!seen.has(key)) seen.set(key, row);
  }
  return [...seen.values()].sort((left, right) =>
    (left.name_uk || left.name_en).localeCompare(right.name_uk || right.name_en, "uk"),
  );
}

function spellMeta(data: Record<string, unknown>): string {
  const level = Number(data.level ?? 0);
  const parts = [level ? `${level} рівень` : "заговір"];
  if (typeof data.school === "string") parts.push(schoolLabel(data.school));
  if (data.ritual) parts.push("ритуал");
  return parts.join(" · ");
}

function EntriesSection({
  section,
  category,
  entryKey,
  go,
}: {
  section: KbSection;
  category: string;
  entryKey?: string;
  go: (section?: KbSection, key?: string) => void;
}) {
  const query = useQuery({
    queryKey: ["kb", "category", category],
    queryFn: () => fetchCategory(category),
    staleTime: Infinity,
  });
  const items = useMemo(() => unique(query.data ?? []), [query.data]);
  const [level, setLevel] = useState<number | null>(null);
  const shownItems =
    section === "spells" && level !== null ? items.filter((item) => Number(item.data.level ?? 0) === level) : items;
  const selected = items.find((item) => item.id === entryKey);

  return (
    <>
      <Status pending={query.isPending} error={query.error} />
      {section === "spells" ? (
        <div className="chip-row kb__levels" role="group" aria-label="Рівень закляття">
          <button
            type="button"
            className={`chip ${level === null ? "chip--active" : ""}`}
            onClick={() => setLevel(null)}
          >
            усі
          </button>
          {Array.from({ length: 10 }, (_, value) => (
            <button
              key={value}
              type="button"
              className={`chip ${level === value ? "chip--active" : ""}`}
              onClick={() => setLevel(level === value ? null : value)}
            >
              {value === 0 ? "заговори" : value}
            </button>
          ))}
        </div>
      ) : null}
      <Browser<ItemSearchResult>
        items={shownItems}
        keyOf={(item) => item.id}
        labelOf={(item) => withEnglish(item.name_en, item.name_uk)}
        metaOf={(item) =>
          section === "spells"
            ? spellMeta(item.data)
            : typeof item.data.prerequisite === "string"
              ? `умова: ${item.data.prerequisite}`
              : ""
        }
        searchOf={(item) => [item.name_en, item.name_uk]}
        selected={entryKey}
        onSelect={(key) => go(section, key)}
        placeholder={section === "spells" ? "Пошук: «вогняна куля», «shield»…" : "Пошук українською чи англійською…"}
      >
        {selected ? <EntryDetail entry={selected} section={section} onClose={() => go(section)} /> : null}
      </Browser>
    </>
  );
}

function EntryDetail({
  entry,
  section,
  onClose,
}: {
  entry: ItemSearchResult;
  section: KbSection;
  onClose: () => void;
}) {
  const full = useQuery({
    queryKey: ["kb", "entry", entry.id],
    queryFn: () => fetchEntry(entry.id),
    staleTime: Infinity,
  });
  const data = entry.data;
  const facts: [string, string][] = [];
  if (section === "spells") {
    facts.push(["Рівень", spellMeta(data)]);
    if (data.casting_time) facts.push(["Час накладання", castingTimeLabel(String(data.casting_time))]);
    if (data.range) facts.push(["Дистанція", rangeLabel(String(data.range))]);
    if (data.components) facts.push(["Компоненти", String(data.components)]);
    if (data.duration) facts.push(["Тривалість", durationLabel(String(data.duration))]);
  }
  if (typeof data.prerequisite === "string" && data.prerequisite) facts.push(["Умова", data.prerequisite]);
  const text = full.data?.text_uk || full.data?.text_en || "";
  return (
    <article className="species-card kb__card">
      <DetailHead title={withEnglish(entry.name_en, entry.name_uk)} onClose={onClose} />
      {facts.length ? <FactList facts={facts} /> : null}
      {full.isPending ? <p className="meta">Читаємо текст…</p> : <RuleText text={text} />}
      {full.data && !full.data.text_uk && full.data.text_en ? (
        <p className="hint">Перекладу ще немає — текст книги англійською.</p>
      ) : null}
    </article>
  );
}
