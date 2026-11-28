/// <reference types="node" />
import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, vi } from "vitest";

import { lookup } from "./tape";
import type { Reply } from "./tape";

// Довідник — серверні сторінки: перехід туди в jsdom не працює, тож тести бачать лише виклик.
vi.mock("../seo/kbLinks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../seo/kbLinks")>()),
  openServerPage: vi.fn(),
}));

const here = dirname(fileURLToPath(import.meta.url));
const itemsUk = readFileSync(join(here, "..", "..", "public", "items-uk.json"), "utf-8");

type Override = { method: string; prefix: string; reply: Reply | ((body: unknown) => Reply) };
const overrides: Override[] = [];

/** All requests the app made in the current test: `METHOD url`. */
export const requests: { method: string; url: string; body: unknown }[] = [];

/** Answer a request differently in this test (e.g. a guest, an error). Later overrides win. */
export function override(method: string, prefix: string, replyOrFn: Override["reply"]): void {
  overrides.unshift({ method, prefix, reply: replyOrFn });
}

function respond(status: number, payload: unknown): Response {
  return new Response(typeof payload === "string" ? payload : JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.pathname + input.search : input.url;
  const method = (init?.method ?? "GET").toUpperCase();
  let payload: unknown = undefined;
  if (typeof init?.body === "string" && init.body) {
    try {
      payload = JSON.parse(init.body);
    } catch {
      payload = init.body;
    }
  }
  requests.push({ method, url, body: payload });
  if (url === "/items-uk.json") return respond(200, itemsUk);
  // A prefix ending with "$" matches the whole URL only.
  const custom = overrides.find(
    (item) =>
      item.method === method &&
      (item.prefix.endsWith("$") ? url === item.prefix.slice(0, -1) : url.startsWith(item.prefix)),
  );
  if (custom) {
    const result = typeof custom.reply === "function" ? custom.reply(payload) : custom.reply;
    return respond(result.status, result.body);
  }
  const recorded = lookup(method, url, payload);
  if (recorded) return respond(recorded.status, recorded.body);
  return respond(404, { detail: `not in the tape: ${method} ${url}` });
}

// React Query retries a failed request once (a second later): errors need more than 1 s.
configure({ asyncUtilTimeout: 5000 });

// jsdom lacks these; the app calls them when switching pages.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
// The player agrees to every confirmation; printing and new tabs do nothing.
window.confirm = vi.fn(() => true);
window.alert = vi.fn();
window.print = vi.fn();
window.open = vi.fn(() => null) as unknown as typeof window.open;
Element.prototype.scrollIntoView = vi.fn();
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(fakeFetch));
  requests.length = 0;
});

afterEach(() => {
  cleanup();
  overrides.length = 0;
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.location.hash = "";
  vi.unstubAllGlobals();
});
