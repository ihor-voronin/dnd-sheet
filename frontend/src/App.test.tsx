import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "./test/render";
import { override, requests } from "./test/setup";
import { ids } from "./test/tape";

describe("App shell", () => {
  it("shows the home page with the player's characters", async () => {
    const { user } = await renderApp("#/");
    expect(await screen.findByRole("heading", { name: "Мої персонажі" })).toBeInTheDocument();
    await screen.findAllByRole("link", { name: /рівень|рівня/i });
    await user.click(screen.getByRole("button", { name: "Мої персонажі" }));
    await user.click(screen.getByRole("button", { name: /Світла тема/ }));
    expect(document.documentElement.dataset.theme).toBe("day");
    await user.click(screen.getByRole("button", { name: /Темна тема/ }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("asks a guest to sign in before opening a character", async () => {
    override("GET", "/api/v1/auth/me", { status: 200, body: { user: null } });
    await renderApp(`#/character/${ids["fighter-1"]}`);
    expect(await screen.findByText(/після входу через Telegram/)).toBeInTheDocument();
  });

  it("shows the guest home page with a login panel", async () => {
    override("GET", "/api/v1/auth/me", { status: 200, body: { user: null } });
    const { user } = await renderApp("#/");
    const enter = await screen.findByRole("button", { name: "Увійти й створити персонажа" });
    await user.click(enter);
    await user.click(screen.getByRole("button", { name: "Головна" }));
  });

  it("opens a character sheet and goes back to the list", async () => {
    const { user } = await renderApp(`#/character/${ids["fighter-1"]}`);
    await user.click(await screen.findByRole("button", { name: "← до списку" }));
    await waitFor(() => expect(window.location.hash).toBe("#/"));
  });

  it("explains a missing character", async () => {
    override("GET", "/api/v1/characters/nobody", { status: 404, body: { detail: "Персонажа немає" } });
    await renderApp("#/character/nobody");
    expect(await screen.findByText(/Не вдалося прочитати персонажа: Персонажа немає/)).toBeInTheDocument();
  });

  it("opens a shared sheet without signing in", async () => {
    override("GET", "/api/v1/auth/me", { status: 200, body: { user: null } });
    await renderApp("#/s/some-token");
    await waitFor(() => expect(requests.some((item) => item.url.startsWith("/api/v1/shared/some-token"))).toBe(true));
  });

  it("says when a shared link is revoked", async () => {
    override("GET", "/api/v1/shared/", { status: 404, body: { detail: "немає" } });
    await renderApp("#/s/dead");
    expect(await screen.findByText(/Посилання недійсне/)).toBeInTheDocument();
  });

  it("shows the bug report page", async () => {
    await renderApp("#/bugs");
    expect(await screen.findAllByText(/github\.com|GitHub/)).not.toHaveLength(0);
  });

  it("signs out", async () => {
    override("GET", "/api/v1/auth/config", {
      status: 200,
      body: { auth_enabled: true, telegram_bot: "bot", telegram_ready: true, dev_login: false },
    });
    override("POST", "/api/v1/auth/logout", { status: 200, body: { user: null } });
    const { user } = await renderApp("#/");
    await user.click(await screen.findByRole("button", { name: "Вийти" }));
    await waitFor(() => expect(requests.some((item) => item.url === "/api/v1/auth/logout")).toBe(true));
  });

  it("continues an unfinished draft from the list", async () => {
    const { user } = await renderApp("#/");
    const resume = await screen.findByRole("button", { name: "Продовжити" });
    await user.click(resume);
    await waitFor(() => expect(window.location.hash).toBe("#/create"));
  });
});
