/**
 * Кодогенерація TS-типів з контракту.
 * Запуск: pnpm run contract (потрібен один раз після npm install).
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { compileFromFile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(here, "../../contract/sheet-document.schema.json");
const outPath = resolve(here, "../src/contract/sheetDocument.ts");

const banner = `/**
 * ЗГЕНЕРОВАНО з contract/sheet-document.schema.json
 * Не редагувати руками. Перегенерація: pnpm run contract
 */
`;

const typescript = await compileFromFile(schemaPath, {
  bannerComment: banner,
  additionalProperties: false,
  style: { singleQuote: false, semi: true },
});

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, typescript, "utf8");

console.log(`Контракт згенеровано: ${outPath}`);
