import type { ClassChoiceGroup } from "./features/wizard/types";
import type { SheetDocument } from "./contract/sheetDocument";
import type {
  BackgroundView,
  ClassView,
  SpeciesView,
  ClassSpell,
  DraftView,
  FeatEntry,
  FinishedCharacter,
  LevelUpReport,
  LevelUpView,
  RestReport,
  SheetViewPayload,
  StepView,
} from "./features/wizard/types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let detail = `Запит ${url} завершився зі статусом ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = String(payload.detail);
    } catch {
      /* тіло не JSON — лишаємо статус */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function getJson<T>(url: string): Promise<T> {
  return request<T>(url, { method: "GET" });
}

// --- вхід -----------------------------------------------------------------

export interface AuthUser {
  id: string;
  name: string;
  username: string | null;
  photo_url: string | null;
}

export interface AuthConfig {
  auth_enabled: boolean;
  telegram_bot: string | null;
  telegram_ready: boolean;
  dev_login: boolean;
}

export function fetchAuthConfig(): Promise<AuthConfig> {
  return getJson<AuthConfig>("/api/v1/auth/config");
}

export function fetchMe(): Promise<{ user: AuthUser | null }> {
  return getJson<{ user: AuthUser | null }>("/api/v1/auth/me");
}

/** Дані з віджета Telegram як є: сервер сам перевіряє підпис. */
export function loginTelegram(payload: Record<string, unknown>): Promise<{ user: AuthUser }> {
  return request<{ user: AuthUser }>("/api/v1/auth/telegram", { method: "POST", body: JSON.stringify(payload) });
}

export function loginDev(name: string): Promise<{ user: AuthUser }> {
  return request<{ user: AuthUser }>("/api/v1/auth/dev", { method: "POST", body: JSON.stringify({ name }) });
}

export function logout(): Promise<{ user: null }> {
  return request<{ user: null }>("/api/v1/auth/logout", { method: "POST", body: "{}" });
}

// --- демо-документ (PDF-контракт) ----------------------------------------

export function fetchDemoSheet(): Promise<SheetDocument> {
  return getJson<SheetDocument>("/api/v1/demo/sheet");
}

// --- візард ---------------------------------------------------------------

export function startWizard(): Promise<StepView> {
  return request<StepView>("/api/v1/characters/wizard", { method: "POST", body: "{}" });
}

export function readDraft(draftId: string): Promise<{ draft: DraftView }> {
  return getJson<{ draft: DraftView }>(`/api/v1/characters/wizard/${draftId}`);
}

export function readStep<T>(draftId: string, step: string): Promise<StepView<T>> {
  return getJson<StepView<T>>(`/api/v1/characters/wizard/${draftId}/steps/${step}`);
}

export function writeStep<T>(
  draftId: string,
  step: string,
  payload: Record<string, unknown>,
): Promise<StepView<T>> {
  return request<StepView<T>>(
    `/api/v1/characters/wizard/${draftId}/steps/${step}`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function finishDraft(draftId: string): Promise<FinishedCharacter> {
  return request<FinishedCharacter>(`/api/v1/characters/wizard/${draftId}/finish`, {
    method: "POST",
    body: "{}",
  });
}

// --- збережені персонажі --------------------------------------------------

export function fetchCharacter(id: string): Promise<{ sheet: SheetViewPayload }> {
  return getJson<{ sheet: SheetViewPayload }>(`/api/v1/characters/${id}`);
}

/** Лише номер версії листа — для опитування «чи не змінили його з іншого пристрою». */
export function fetchCharacterVersion(id: string): Promise<{ version: number }> {
  return getJson<{ version: number }>(`/api/v1/characters/${id}/version`);
}

export interface SheetMutation {
  sheet: SheetViewPayload;
  version: number;
}

export interface RestMutation extends SheetMutation {
  rest: RestReport;
}

export function patchCharacter(
  id: string,
  body: Record<string, unknown>,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function restCharacter(id: string, kind: "short" | "long"): Promise<RestMutation> {
  return request<RestMutation>(`/api/v1/characters/${id}/rest`, {
    method: "POST",
    body: JSON.stringify({ kind }),
  });
}

// --- підвищення рівня -----------------------------------------------------

export function fetchLevelUp(id: string): Promise<LevelUpView> {
  return getJson<LevelUpView>(`/api/v1/characters/${id}/level-up`);
}

export interface LevelUpMutation extends SheetMutation {
  level_up: LevelUpReport;
}

export function levelUpCharacter(
  id: string,
  body: Record<string, unknown>,
): Promise<LevelUpMutation> {
  return request<LevelUpMutation>(`/api/v1/characters/${id}/level-up`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Один рядок «усіх умінь класу за рівнями»: назва, рівень, текст правила. */
export interface ClassFeatureRow {
  name_en: string;
  level: number;
  name_uk?: string;
  text?: string;
  text_uk?: string;
}

/** Усі вміння класу з текстами — вантажиться, коли список розгорнули. */
export function fetchClassFeatures(
  classKey: string,
): Promise<{ class_key: string; features: ClassFeatureRow[] }> {
  return getJson(
    `/api/v1/characters/wizard/class-features/${encodeURIComponent(classKey)}`,
  );
}

/** Підклас цілком: назва, опис-вступ і всі вміння з текстами. */
export interface SubclassBriefPayload {
  id: string;
  name_en: string;
  name_uk: string | null;
  description: string;
  description_uk: string | null;
  /** Запис у корпусі пошкоджений (чужий текст без структури) — показуємо примітку. */
  corrupt?: boolean;
  features: {
    name_en: string;
    level: number;
    name_uk?: string;
    description: string;
    text_uk?: string;
    subclass_name: string;
    subclass_name_uk?: string | null;
  }[];
}

export function fetchSubclassDetails(subclassKey: string): Promise<SubclassBriefPayload> {
  return getJson(
    `/api/v1/characters/wizard/subclass/${subclassKey
      .split("/")
      .map(encodeURIComponent)
      .join("/")}`,
  );
}

/** Закляття класу до рівня включно — зі «Spell Lists» книг. */
export function fetchClassSpells(
  classKey: string,
  maxLevel: number,
): Promise<{ items: ClassSpell[]; total: number }> {
  const params = new URLSearchParams({ max_level: String(maxLevel) });
  // Воїн і плут чарують лише як містичний лицар / таємний пройдисвіт — зі списку мага.
  const listKey = classKey === "fighter" || classKey === "rogue" ? "wizard" : classKey;
  return getJson(`/api/v1/compendium/classes/${encodeURIComponent(listKey)}/spells?${params}`);
}

/** Усі риси корпусу — для вибору на рівні покращення характеристик. */
export function fetchFeats(): Promise<FeatEntry[]> {
  return (async () => {
    const all: FeatEntry[] = [];
    for (let offset = 0; ; offset += CATALOG_PAGE) {
      const page = await getJson<{ items: FeatEntry[]; total: number }>(
        `/api/v1/compendium/entries?category=feat&limit=${CATALOG_PAGE}&offset=${offset}`,
      );
      all.push(...(page.items ?? []));
      if (!page.items?.length || all.length >= page.total) break;
    }
    return all;
  })();
}

export function spendHitDie(id: string, die: number, roll: number): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/hit-dice`, {
    method: "POST",
    body: JSON.stringify({ die, roll }),
  });
}

// --- закляття -------------------------------------------------------------

export interface SpellBody {
  class_key: string;
  name_en: string;
  level: number;
  entry_id?: string | null;
  prepared?: boolean;
  /** Власне закляття: його немає в книзі, текст дав гравець. */
  custom?: boolean;
  description?: string | null;
}

export function addCharacterSpell(
  id: string,
  spell: SpellBody,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/spells`, {
    method: "POST",
    body: JSON.stringify({ ...spell, version }),
  });
}

export function removeCharacterSpell(
  id: string,
  nameEn: string,
  classKey: string,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/spells`, {
    method: "DELETE",
    body: JSON.stringify({ name_en: nameEn, class_key: classKey, version }),
  });
}

export function prepareCharacterSpells(
  id: string,
  classKey: string,
  spells: { name_en: string; level: number; entry_id?: string | null }[],
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/spells/prepare`, {
    method: "POST",
    body: JSON.stringify({ class_key: classKey, spells, version }),
  });
}

/** Експертиза: навички (або злодійські інструменти) з подвоєним бонусом. */
export function setCharacterExpertise(
  id: string,
  expertise: string[],
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/expertise`, {
    method: "POST",
    body: JSON.stringify({ expertise, version }),
  });
}

export function setCharacterClassChoice(
  id: string,
  group: string,
  values: string[],
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/class-choices`, {
    method: "POST",
    body: JSON.stringify({ group, values, version }),
  });
}

/** Групи виборів риси виду для візарда (навички Умілого, закляття Учня магії…). */
export function fetchWizardFeatChoices(body: {
  feat: string;
  species_key: string;
  subspecies_key: string | null;
  choices: Record<string, string[]>;
}): Promise<{ groups: ClassChoiceGroup[] }> {
  return request<{ groups: ClassChoiceGroup[] }>(`/api/v1/characters/wizard/feat-choices`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Книга виду (VGM чи MPMM): від неї залежить кістка природної зброї. */
export function setCharacterSpeciesSource(id: string, source: string | null, version: number): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/species-source`, {
    method: "POST",
    body: JSON.stringify({ source, version }),
  });
}

/** Риса виду на 1 рівні (варіантна людина, власна лінія). */
export function setCharacterSpeciesFeat(
  id: string,
  featKey: string,
  featAbility: string | null,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/species-feat`, {
    method: "POST",
    body: JSON.stringify({ feat_key: featKey, feat_ability: featAbility, version }),
  });
}

// --- інвентар -------------------------------------------------------------

export interface ItemBody {
  name_en: string;
  kind: string;
  quantity?: number;
  weight_lb?: number;
  equipped?: boolean;
  attuned?: boolean;
  entry_id?: string | null;
  armor_base?: number | null;
  dex_cap?: number | null;
  notes?: string | null;
  damage?: string | null;
  /** Зброя угоди (Pact of the Blade) — лише одна. */
  pact_weapon?: boolean;
  /** Зброя Хекс-воїна (Hex Warrior) — лише одна. */
  hex_weapon?: boolean;
  /** Зброя кенсея (Path of the Kensei) — кілька, ліміт за рівнем. */
  kensei_weapon?: boolean;
}

export function addCharacterItem(
  id: string,
  item: ItemBody,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/items`, {
    method: "POST",
    body: JSON.stringify({ item, version }),
  });
}

export function updateCharacterItem(
  id: string,
  index: number,
  fields: Partial<ItemBody>,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/items/${index}`, {
    method: "PATCH",
    body: JSON.stringify({ fields, version }),
  });
}

export function removeCharacterItem(
  id: string,
  index: number,
  version: number,
): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/items/${index}`, {
    method: "DELETE",
    body: JSON.stringify({ version }),
  });
}

export function fetchCharacters(): Promise<{
  items: { id: string; name: string; total_level: number }[];
  total: number;
  /** Незавершена чернетка гравця — продовжити з будь-якого пристрою. */
  draft_id?: string | null;
}> {
  return getJson("/api/v1/characters");
}

// --- експорт --------------------------------------------------------------

export type ExportFormat = "pdf" | "markdown";

/** Адреса файлу листа. Це не fetch: браузер сам віддасть вкладення. */
export function exportUrl(id: string, format: ExportFormat): string {
  return `/api/v1/characters/${encodeURIComponent(id)}/export/${format}`;
}

export function demoExportUrl(format: ExportFormat): string {
  return `/api/v1/demo/export/${format}`;
}

export function fetchRenderers(): Promise<{ formats: ExportFormat[]; available: ExportFormat[] }> {
  return getJson("/api/v1/renderers");
}

// --- довідник (пошук предметів у кроці спорядження) ----------------------

export interface ItemSearchResult {
  id: string;
  name_en: string;
  name_uk?: string | null;
  source_id?: string;
  category?: string;
  data: Record<string, unknown>;
}

export function searchItems(
  query: string,
  limit = 8,
): Promise<{ items: ItemSearchResult[]; total: number }> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return getJson(`/api/v1/compendium/items?${params.toString()}`);
}

/** Скільки записів віддає довідник за один запит (стеля API). */
const CATALOG_PAGE = 200;

let catalog: Promise<ItemSearchResult[]> | null = null;

/** Весь каталог предметів одним махом.
 *
 * Фільтри в панелі (тип, джерело, магічність, пошук) мають спрацьовувати
 * одразу, без запиту на кожне натискання. Записів півтори тисячі, у
 * «короткому» вигляді це кількасот кілобайт — тож вантажимо один раз і
 * тримаємо в памʼяті до перезавантаження сторінки.
 */
export function fetchItemCatalog(): Promise<ItemSearchResult[]> {
  if (catalog) return catalog;
  catalog = (async () => {
    const all: ItemSearchResult[] = [];
    for (let offset = 0; ; offset += CATALOG_PAGE) {
      const page = await getJson<{
        items: ItemSearchResult[];
        total: number;
      }>(`/api/v1/compendium/items?limit=${CATALOG_PAGE}&offset=${offset}`);
      all.push(...page.items);
      if (!page.items.length || all.length >= page.total) break;
    }
    return all;
  })();
  return catalog;
}

/** Повний запис довідника: у «короткому» немає тексту книги. */
export interface CompendiumEntry {
  id: string;
  name_en: string;
  name_uk?: string | null;
  text_en?: string | null;
  text_uk?: string | null;
  data: Record<string, unknown>;
}

// --- база знань (без входу) ------------------------------------------------

export function fetchKbSpecies(): Promise<{ items: SpeciesView[] }> {
  return getJson("/api/v1/kb/species");
}

export function fetchKbClasses(): Promise<{ items: ClassView[] }> {
  return getJson("/api/v1/kb/classes");
}

export function fetchKbBackgrounds(): Promise<{ items: BackgroundView[] }> {
  return getJson("/api/v1/kb/backgrounds");
}

const categoryCache = new Map<string, Promise<ItemSearchResult[]>>();

/** Усі записи категорії довідника (закляття, риси, опційні вміння) — для пошуку українською на клієнті. */
export function fetchCategory(category: string): Promise<ItemSearchResult[]> {
  const cached = categoryCache.get(category);
  if (cached) return cached;
  const loading = (async () => {
    const all: ItemSearchResult[] = [];
    for (let offset = 0; ; offset += CATALOG_PAGE) {
      const page = await getJson<{ items: ItemSearchResult[]; total: number }>(
        `/api/v1/compendium/entries?category=${encodeURIComponent(category)}&limit=${CATALOG_PAGE}&offset=${offset}`,
      );
      all.push(...page.items);
      if (!page.items.length || all.length >= page.total) break;
    }
    return all;
  })();
  categoryCache.set(category, loading);
  loading.catch(() => categoryCache.delete(category));
  return loading;
}

export function fetchEntry(entryId: string): Promise<CompendiumEntry> {
  return getJson<CompendiumEntry>(`/api/v1/compendium/entries/${entryId}`);
}

let bookTitles: Promise<Record<string, string>> | null = null;

/** Коди книг → назви («phb-2014» → «Player's Handbook (2014)»). */
export function fetchBookTitles(): Promise<Record<string, string>> {
  if (bookTitles) return bookTitles;
  bookTitles = (async () => {
    try {
      const payload = await getJson<{
        books: { source_id: string; title: string }[];
      }>("/api/v1/compendium/summary");
      const map: Record<string, string> = {};
      for (const book of payload.books ?? []) map[book.source_id] = book.title;
      return map;
    } catch {
      return {};
    }
  })();
  return bookTitles;
}

/** Переклади предметів (назви в бандлі, описи — окремим файлом). */
export interface ItemUkPayload {
  items: Record<string, { name?: string; text?: string }>;
}

let itemsUk: Promise<ItemUkPayload["items"]> | null = null;

export function fetchItemsUk(): Promise<ItemUkPayload["items"]> {
  if (itemsUk) return itemsUk;
  itemsUk = (async () => {
    try {
      const response = await fetch("/items-uk.json");
      if (!response.ok) return {};
      const payload = (await response.json()) as ItemUkPayload;
      return payload.items ?? {};
    } catch {
      return {};
    }
  })();
  return itemsUk;
}
