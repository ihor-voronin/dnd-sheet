import type { SheetDocument } from "./contract/sheetDocument";
import type {
  DraftView,
  FinishedCharacter,
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

export function spendHitDie(id: string, die: number, roll: number): Promise<SheetMutation> {
  return request<SheetMutation>(`/api/v1/characters/${id}/hit-dice`, {
    method: "POST",
    body: JSON.stringify({ die, roll }),
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
  data: Record<string, unknown>;
}

export function searchItems(
  query: string,
  limit = 8,
): Promise<{ items: ItemSearchResult[]; total: number }> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return getJson(`/api/v1/compendium/items?${params.toString()}`);
}
