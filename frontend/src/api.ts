import type { SheetDocument } from "./contract/sheetDocument";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Запит ${url} завершився зі статусом ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchDemoSheet(): Promise<SheetDocument> {
  return getJson<SheetDocument>("/api/v1/demo/sheet");
}
