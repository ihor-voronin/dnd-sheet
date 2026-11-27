/**
 * Generates TS types from the contract.
 * Run: npm run contract (needed once after npm install).
 */
import { compileFromFile } from "json-schema-to-typescript";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(here, "../../contract/sheet-document.schema.json");
const outPath = resolve(here, "../src/contract/sheetDocument.ts");

const banner = `/**
 * GENERATED from contract/sheet-document.schema.json
 * Do not edit by hand. Regenerate: npm run contract
 */
`;

const typescript = await compileFromFile(schemaPath, {
  bannerComment: banner,
  additionalProperties: false,
  style: { singleQuote: false, semi: true },
});

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, typescript, "utf8");

console.log(`Contract generated: ${outPath}`);
