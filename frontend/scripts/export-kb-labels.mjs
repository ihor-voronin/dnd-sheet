/**
 * Writes dist/kb-labels.json: the Ukrainian dictionaries of the SPA (species, class and
 * item names, skill and ability labels, the player glossary) for the server-rendered
 * compendium pages (`/kb/...`). The backend reads the file from the SPA folder, so the
 * dictionaries have one home — src/ — and the pages never drift from the app.
 *
 * Runs after `vite build` (see package.json). The module is loaded through Vite, so it
 * reads the same TypeScript as the bundle.
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outPath = resolve(root, "dist/kb-labels.json");

const server = await createServer({
  root,
  configFile: false,
  logLevel: "error",
  appType: "custom",
  server: { middlewareMode: true, hmr: false, watch: null },
  optimizeDeps: { noDiscovery: true, include: [] },
});
try {
  const { kbLabels } = await server.ssrLoadModule("/src/seo/kbLabels.ts");
  const labels = kbLabels();
  // Empty dictionaries mean a broken import, not "no translation": fail the build.
  for (const key of ["species", "terms", "items", "skills", "glossary"]) {
    if (!Object.keys(labels[key] ?? {}).length) throw new Error(`kb-labels: "${key}" is empty`);
  }
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, JSON.stringify(labels));
  console.warn(`kb-labels: ${Object.keys(labels.items).length} items, ${Object.keys(labels.terms).length} terms`);
} finally {
  await server.close();
}
