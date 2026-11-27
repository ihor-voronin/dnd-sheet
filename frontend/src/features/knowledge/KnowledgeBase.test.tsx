import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { body } from "../../test/tape";

const SECTIONS = ["species", "classes", "backgrounds", "feats", "spells", "options", "items"];

describe("knowledge base", () => {
  it("lists the sections and opens each one", async () => {
    const { user } = await renderApp("#/kb");
    for (const name of ["Види", "Класи", "Передісторії", "Риси", "Закляття", "Опційні вміння", "Предмети"]) {
      const [chip] = await screen.findAllByRole("button", { name: new RegExp(`^${name}`) });
      await user.click(chip);
      await waitFor(() => expect(chip).toHaveAttribute("aria-current", "page"));
    }
  });

  it.each(SECTIONS)("lets a guest browse %s", async (section) => {
    override("GET", "/api/v1/auth/me", { status: 200, body: { user: null } });
    const { user } = await renderApp(`#/kb/${section}`);
    await waitFor(() => expect(requests.length).toBeGreaterThan(2));
    await screen.findAllByRole("button");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 3, maxClicks: 120 });
    expect(document.querySelector("main")).toBeInTheDocument();
  });

  it.each([
    ["species", "human"],
    ["classes", "cleric"],
    ["backgrounds", "acolyte"],
  ])("opens a %s entry by link", async (section, key) => {
    await renderApp(`#/kb/${section}/${key}`);
    await waitFor(() => expect(requests.some((item) => item.url.startsWith("/api/v1/kb/"))).toBe(true));
    await screen.findAllByRole("button");
  });

  it("opens a compendium entry by link", async () => {
    const page = body<{ items: { id: string }[] }>(
      "GET",
      "/api/v1/compendium/entries?category=spell&limit=200&offset=0",
    );
    const { user } = await renderApp(`#/kb/spells/${encodeURIComponent(page.items[0].id)}`);
    await screen.findAllByRole("button");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2, maxClicks: 40 });
  });

  it("says when the compendium is unavailable", async () => {
    override("GET", "/api/v1/kb/", { status: 503, body: { detail: "Корпус не розблоковано" } });
    override("GET", "/api/v1/compendium/", { status: 503, body: { detail: "Корпус не розблоковано" } });
    for (const section of SECTIONS) {
      await renderApp(`#/kb/${section}`);
      await waitFor(() => expect(requests.length).toBeGreaterThan(1));
    }
  });
});
