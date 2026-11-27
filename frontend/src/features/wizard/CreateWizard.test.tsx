import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { explore } from "../../test/explore";
import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";
import { body, ids } from "../../test/tape";

const DRAFT = "drf_test";
const STEPS = ["species", "class", "abilities", "background", "equipment", "spells"] as const;

/** Open the wizard on a saved draft (a recorded one, or a stand-in) whose next step is `step`. */
async function openStep(step: (typeof STEPS)[number], draftId = DRAFT) {
  const draft = body<{ draft: Record<string, unknown> }>("GET", `/api/v1/characters/wizard/${DRAFT}`);
  override("GET", `/api/v1/characters/wizard/${draftId}$`, {
    status: 200,
    body: { draft: { ...draft.draft, id: draftId, next_step: step } },
  });
  window.localStorage.setItem("dndsheet.draft", draftId);
  const app = await renderApp("#/create");
  await waitFor(() =>
    expect(requests.some((item) => item.url === `/api/v1/characters/wizard/${draftId}/steps/${step}`)).toBe(true),
  );
  await screen.findAllByRole("button");
  return app;
}

describe("character creation wizard", () => {
  it("starts a new draft and walks every step to the sheet", async () => {
    const { user } = await renderApp("#/create");
    await waitFor(() => expect(requests.some((item) => item.url === "/api/v1/characters/wizard")).toBe(true));
    await screen.findAllByRole("button", { name: /^Далі/ });
    // Picking options enables "Next"; every PUT answers with the next recorded step.
    // "Start over" would throw the walk back to the first step.
    await explore(user, document.querySelector("main") as HTMLElement, {
      rounds: 10,
      maxClicks: 300,
      skip: /^(← до|Мої персонажі|Довідник|Знайшли помилку|Світла тема|Темна тема|Почати)/,
    });
    expect(requests.some((item) => item.method === "PUT")).toBe(true);
  });

  it.each(STEPS)("lets the player work through the %s step", async (step) => {
    const { user } = await openStep(step);
    await explore(
      user,
      document.querySelector<HTMLElement>(".wizard-step") ?? (document.querySelector("main") as HTMLElement),
      {
        rounds: 3,
      },
    );
    expect(requests.some((item) => item.url.includes("/steps/"))).toBe(true);
  });

  it.each(STEPS.flatMap((step) => [["draft-gnome-wizard", step] as const, ["draft-elf-fighter", step] as const]))(
    "works through %s at the %s step",
    async (draft, step) => {
      const { user } = await openStep(step, ids[draft]);
      await explore(
        user,
        document.querySelector<HTMLElement>(".wizard-step") ?? (document.querySelector("main") as HTMLElement),
        {
          rounds: 4,
          skip: /^(← до|Мої персонажі|Довідник|Знайшли помилку|Світла тема|Темна тема|Почати)/,
        },
      );
      expect(document.querySelector("main")).toBeInTheDocument();
    },
  );

  it("shows why a step was rejected", async () => {
    override("PUT", `/api/v1/characters/wizard/${DRAFT}/steps/`, { status: 422, body: { detail: "Оберіть вид" } });
    const { user } = await openStep("species");
    await explore(user, document.querySelector("main") as HTMLElement, { rounds: 2, maxClicks: 60 });
    expect(document.querySelector("main")).toBeInTheDocument();
  });

  it("finishes the draft and opens the new sheet", async () => {
    const { user } = await openStep("spells");
    const create = await screen.findAllByRole("button", { name: /Створити персонажа/ });
    await user.click(create[create.length - 1]);
    await waitFor(() => expect(requests.some((item) => item.url.endsWith("/finish"))).toBe(true));
  });

  it("starts over when the saved draft is gone", async () => {
    override("GET", `/api/v1/characters/wizard/${DRAFT}`, { status: 404, body: { detail: "немає" } });
    window.localStorage.setItem("dndsheet.draft", DRAFT);
    await renderApp("#/create");
    await waitFor(() =>
      expect(requests.some((item) => item.method === "POST" && item.url === "/api/v1/characters/wizard")).toBe(true),
    );
  });
});
