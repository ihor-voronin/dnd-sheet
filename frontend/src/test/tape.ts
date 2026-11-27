/// <reference types="node" />

/**
 * The API tape: responses recorded from the real backend by
 * scripts/record_frontend_tape.py (book text scrubbed). Tests answer `fetch`
 * from it, so components get real-shaped data without a server.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

interface TapeEntry {
  method: string;
  url: string;
  status: number;
  body: string;
  request?: unknown;
}

interface TapeFile {
  ids: Record<string, string>;
  bodies: Record<string, unknown>;
  tape: TapeEntry[];
}

const here = dirname(fileURLToPath(import.meta.url));
const file = JSON.parse(gunzipSync(readFileSync(join(here, "tape.json.gz"))).toString("utf-8")) as TapeFile;

export const ids = file.ids;

export interface Reply {
  status: number;
  body: unknown;
}

/** A deep copy: components and React Query must not share mutable recorded objects. */
function reply(entry: TapeEntry): Reply {
  return { status: entry.status, body: structuredClone(file.bodies[entry.body]) };
}

/** `/api/v1/characters/<id>/…` and wizard drafts compared without their ids. */
function shape(url: string): string {
  return url
    .split("?")[0]
    .replace(/\/characters\/wizard\/drf_[^/]+/, "/characters/wizard/:draft")
    .replace(/\/characters\/(?!wizard\b)[^/]+/, "/characters/:id")
    .replace(/\/shared\/[^/]+/, "/shared/:token");
}

function withoutVersion(value: unknown): string {
  if (!value || typeof value !== "object") return JSON.stringify(value ?? null);
  const { version: _version, ...rest } = value as Record<string, unknown>;
  return JSON.stringify(rest, Object.keys(rest).sort());
}

/** Among matches, the one recorded with the same request (a long rest, not the short one). */
function pick(matches: TapeEntry[], request: unknown): TapeEntry | undefined {
  if (request !== undefined && matches.length > 1) {
    const wanted = withoutVersion(request);
    const same = matches.find((entry) => entry.request !== undefined && withoutVersion(entry.request) === wanted);
    if (same) return same;
  }
  return matches[0];
}

/** The recorded body of a matching call: by exact URL, then path, then path shape. */
export function lookup(method: string, url: string, request?: unknown): Reply | null {
  const ok = file.tape.filter((entry) => entry.method === method && entry.status < 400);
  const path = url.split("?")[0];
  const wanted = shape(url);
  for (const matches of [
    ok.filter((entry) => entry.url === url),
    ok.filter((entry) => entry.url.split("?")[0] === path),
    ok.filter((entry) => shape(entry.url) === wanted),
  ]) {
    const found = pick(matches, request);
    if (found) return reply(found);
  }
  return null;
}

/** The recorded body for a URL, as a typed object (for unit tests and overrides). */
export function body<T = unknown>(method: string, url: string): T {
  const found = lookup(method, url);
  if (!found) throw new Error(`not in the tape: ${method} ${url}`);
  return found.body as T;
}
