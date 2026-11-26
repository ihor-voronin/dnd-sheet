/**
 * ЗГЕНЕРОВАНО з contract/sheet-document.schema.json
 * Не редагувати руками. Перегенерація: pnpm run contract
 */

/**
 * Канонічний документ листка персонажа. Єдине джерело правди для всіх рендерів.
 */
export interface SheetDocument {
  schemaVersion: string;
  edition: "2014";
  title: LocalizedText;
  /**
   * @minItems 1
   */
  pages: [Page, ...Page[]];
  fields: {
    [k: string]: Field;
  };
}
export interface LocalizedText {
  uk: string;
  en: string;
  glossaryId?: string | null;
}
export interface Page {
  size: "A4" | "A4-landscape" | "A5";
  /**
   * @minItems 1
   */
  sections: [Section, ...Section[]];
}
export interface Section {
  id: string;
  title: LocalizedText;
  columns: number;
  /**
   * @minItems 1
   */
  fields: [string, ...string[]];
}
export interface Field {
  id: string;
  type: "text" | "number" | "longtext" | "checkbox" | "list" | "counter" | "formula" | "dice";
  value: string | number | boolean | null | unknown[];
  origin: "input" | "computed" | "override";
  label: LocalizedText;
  hint?: LocalizedText | null;
  editable?: boolean;
  formula?: Formula | null;
}
export interface Formula {
  expr: string;
  deps?: string[];
}
