/// <reference types="node" />
import { screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { renderApp } from "./test/render";
import { ids } from "./test/tape";

const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "index.html"), "utf-8");

function meta(attribute: "name" | "property", key: string): string | undefined {
  const tag = html.match(new RegExp(`<meta\\s+${attribute}="${key}"\\s+content="([^"]*)"`, "s"));
  return tag?.[1];
}

describe("what search engines and link previews see (index.html)", () => {
  it("has a title and a description of the right length", () => {
    const title = html.match(/<title>(.*?)<\/title>/)?.[1].replace(/&amp;/g, "&") ?? "";
    expect(title).toContain("Лист персонажа D&D 5e");
    expect(title.length).toBeLessThanOrEqual(60);
    const description = html.match(/name="description"\s+content="([^"]*)"/s)?.[1] ?? "";
    expect(description.length).toBeGreaterThan(80);
    expect(description.length).toBeLessThanOrEqual(160);
  });

  it("has a canonical URL, Open Graph and structured data", () => {
    expect(html).toContain('<link rel="canonical" href="https://dnd.voronin.app/" />');
    expect(meta("property", "og:image")).toBe("https://dnd.voronin.app/og-image.png");
    expect(meta("property", "og:locale")).toBe("uk_UA");
    expect(meta("name", "twitter:card")).toBe("summary_large_image");
    const jsonLd = html.match(/<script type="application\/ld\+json">(.*?)<\/script>/s)?.[1] ?? "";
    expect(JSON.parse(jsonLd)).toMatchObject({
      "@type": "WebApplication",
      inLanguage: "uk",
      isAccessibleForFree: true,
    });
  });

  it("tells crawlers without JavaScript what the site is", () => {
    const noscript = html.match(/<noscript>(.*?)<\/noscript>/s)?.[1] ?? "";
    expect(noscript).toContain("<h1>");
    expect(noscript).toContain("довідник");
    // Сторінки довідника — справжні адреси, які пошуковик знайде й без JavaScript.
    expect(noscript).toContain('href="/kb/spells"');
  });
});

describe("tab titles", () => {
  it("names each page", async () => {
    await renderApp("#/mcp");
    await waitFor(() => expect(document.title).toBe("ІІ-асистент (MCP) для листа персонажа D&D 5e"));
  });

  it("names the character on its sheet", async () => {
    await renderApp(`#/character/${ids["fighter-1"]}`);
    await screen.findByRole("button", { name: "Дії" });
    await waitFor(() => expect(document.title).toMatch(/ — лист персонажа D&D 5e$/));
    expect(document.title).not.toMatch(/^Персонаж —/);
  });
});
