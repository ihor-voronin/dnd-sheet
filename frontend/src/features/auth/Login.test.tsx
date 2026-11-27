import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";

/** The form's submit button (the top bar has its own «Увійти» link-button). */
function submitButton(): HTMLElement {
  return screen.getAllByRole("button", { name: "Увійти" }).find((button) => button.getAttribute("type") === "submit")!;
}

const GUEST = { status: 200, body: { user: null } };

function config(fields: Record<string, unknown>) {
  return {
    status: 200,
    body: { auth_enabled: true, telegram_bot: null, telegram_ready: false, dev_login: false, ...fields },
  };
}

describe("sign-in panel", () => {
  it("loads the Telegram widget and signs in through it", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", config({ telegram_bot: "dnd_bot", telegram_ready: true }));
    override("POST", "/api/v1/auth/telegram", { status: 200, body: { user: { id: "1", name: "Т" } } });
    await renderApp("#/");
    await waitFor(() => expect(document.querySelector("script[data-telegram-login='dnd_bot']")).not.toBeNull());
    window.onTelegramAuth?.({ id: 1, hash: "x" });
    await waitFor(() => expect(requests.some((item) => item.url === "/api/v1/auth/telegram")).toBe(true));
  });

  it("shows why a Telegram sign-in failed", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", config({ telegram_bot: "dnd_bot", telegram_ready: true }));
    override("POST", "/api/v1/auth/telegram", { status: 401, body: { detail: "Застарілий підпис" } });
    await renderApp("#/");
    await waitFor(() => expect(window.onTelegramAuth).toBeTypeOf("function"));
    window.onTelegramAuth?.({ id: 1 });
    expect(await screen.findByText("Застарілий підпис")).toBeInTheDocument();
  });

  it("says when Telegram isn't configured", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", config({}));
    await renderApp("#/");
    expect(await screen.findByText(/ще не налаштовано/)).toBeInTheDocument();
  });

  it("signs in by name in development", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", config({ dev_login: true }));
    override("POST", "/api/v1/auth/dev", { status: 200, body: { user: { id: "1", name: "Ігор" } } });
    const { user } = await renderApp("#/");
    await user.type(await screen.findByPlaceholderText("напр. Ігор"), "Ігор");
    await user.click(submitButton());
    await waitFor(() =>
      expect(requests.find((item) => item.url === "/api/v1/auth/dev")?.body).toEqual({ name: "Ігор" }),
    );
  });

  it("shows a refused development sign-in", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", config({ dev_login: true }));
    override("POST", "/api/v1/auth/dev", { status: 403, body: { detail: "Вимкнено" } });
    const { user } = await renderApp("#/");
    await user.type(await screen.findByPlaceholderText("напр. Ігор"), "X");
    await user.click(submitButton());
    expect(await screen.findByText("Вимкнено")).toBeInTheDocument();
  });
});
