import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp } from "../../test/render";
import { override, requests } from "../../test/setup";

const PLAYER = { status: 200, body: { user: { id: "u1", name: "Ігор", username: null, photo_url: null } } };
const GUEST = { status: 200, body: { user: null } };

function request(client: Record<string, unknown> = {}) {
  return {
    status: 200,
    body: {
      client: {
        client_id: "https://claude.example/client.json",
        name: "Claude",
        uri: "https://claude.example",
        redirect_hosts: ["claude.example"],
        local_only: false,
        verified_by_url: true,
        ...client,
      },
      redirect_host: "claude.example",
      scopes: [{ key: "characters", title: "Бачити й змінювати ваших персонажів" }],
      expires_at: 0,
      signed_in: true,
    },
  };
}

async function consentModule() {
  return import("./Consent");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("app consent screen", () => {
  it("shows who asks, what for and where the browser returns, then approves", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/requests/r1", request());
    override("POST", "/api/v1/oauth/requests/r1", {
      status: 200,
      body: { redirect: "https://claude.example/cb?code=c" },
    });
    const { user } = await renderApp("#/oauth/r1");
    expect(await screen.findByRole("heading", { name: "«Claude» просить доступ" })).toBeInTheDocument();
    expect(screen.getByText("Бачити й змінювати ваших персонажів")).toBeInTheDocument();
    expect(screen.getAllByText("claude.example").length).toBeGreaterThan(0);
    expect(screen.queryByText(/localhost/)).not.toBeInTheDocument();
    expect(screen.getByText(/підключення застосунку/)).toBeInTheDocument();

    const { browser } = await consentModule();
    const go = vi.spyOn(browser, "go").mockImplementation(() => undefined);
    await user.click(screen.getByRole("button", { name: "Дозволити" }));
    await waitFor(() => expect(go).toHaveBeenCalledWith("https://claude.example/cb?code=c"));
    expect(requests.find((item) => item.method === "POST" && item.url === "/api/v1/oauth/requests/r1")?.body).toEqual({
      approve: true,
    });
    expect(await screen.findByText("Повертаємося до застосунку…")).toBeInTheDocument();
  });

  it("denies and warns about local, self-registered apps", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/requests/r2", request({ local_only: true, verified_by_url: false, uri: null }));
    override("POST", "/api/v1/oauth/requests/r2", { status: 200, body: { redirect: "http://localhost:1/cb?error=x" } });
    const { user } = await renderApp("#/oauth/r2");
    expect(await screen.findByText(/працює на цьому компʼютері/)).toBeInTheDocument();
    expect(screen.getByText(/назвав себе сам/)).toBeInTheDocument();
    const { browser } = await consentModule();
    const go = vi.spyOn(browser, "go").mockImplementation(() => undefined);
    await user.click(screen.getByRole("button", { name: "Відмовити" }));
    await waitFor(() => expect(go).toHaveBeenCalled());
    expect(requests.find((item) => item.url === "/api/v1/oauth/requests/r2" && item.method === "POST")?.body).toEqual({
      approve: false,
    });
  });

  it("asks a guest to sign in to an existing account only", async () => {
    override("GET", "/api/v1/auth/me", GUEST);
    override("GET", "/api/v1/auth/config", {
      status: 200,
      body: { auth_enabled: true, telegram_bot: null, telegram_ready: false, dev_login: true },
    });
    override("GET", "/api/v1/oauth/requests/r3", request());
    override("POST", "/api/v1/auth/dev", { status: 422, body: { detail: "спершу увійдіть на сайті" } });
    const { user } = await renderApp("#/oauth/r3");
    expect(await screen.findByText(/новий акаунт тут не створюється/)).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("напр. Ігор"), "Новенький");
    const submit = screen
      .getAllByRole("button", { name: "Увійти" })
      .find((item) => item.getAttribute("type") === "submit")!;
    await user.click(submit);
    expect(await screen.findByText("спершу увійдіть на сайті")).toBeInTheDocument();
    expect(requests.some((item) => item.url === "/api/v1/auth/dev?existing_only=1")).toBe(true);
  });

  it("explains an expired request and a failed decision", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/requests/old", { status: 404, body: { detail: "запит на дозвіл застарів" } });
    await renderApp("#/oauth/old");
    expect(await screen.findByRole("alert")).toHaveTextContent("запит на дозвіл застарів");
  });

  it("shows why the decision didn't go through", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/requests/r4", request());
    override("POST", "/api/v1/oauth/requests/r4", { status: 404, body: { detail: "почніть підключення ще раз" } });
    const { user } = await renderApp("#/oauth/r4");
    await user.click(await screen.findByRole("button", { name: "Дозволити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("почніть підключення ще раз");
  });
});

describe("connected apps", () => {
  it("lists apps on the home page and disconnects one", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/grants", {
      status: 200,
      body: {
        items: [
          {
            client_id: "c1",
            name: "Claude",
            scopes: ["characters"],
            connected_at: 1_790_000_000,
            last_used_at: 1_790_100_000,
          },
        ],
      },
    });
    override("DELETE", "/api/v1/oauth/grants", { status: 200, body: { items: [] } });
    const { user } = await renderApp("#/");
    expect(await screen.findByRole("heading", { name: "Підключені застосунки" })).toBeInTheDocument();
    expect(screen.getByText("Claude")).toBeInTheDocument();
    expect(screen.getByText(/востаннє/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Відключити" }));
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Підключені застосунки" })).not.toBeInTheDocument(),
    );
    expect(requests.some((item) => item.method === "DELETE" && item.url === "/api/v1/oauth/grants?client_id=c1")).toBe(
      true,
    );
  });

  it("stays hidden without connected apps and reports a failed disconnect", async () => {
    override("GET", "/api/v1/auth/me", PLAYER);
    override("GET", "/api/v1/oauth/grants", {
      status: 200,
      body: {
        items: [{ client_id: "c1", name: "Claude", scopes: [], connected_at: 1_790_000_000, last_used_at: null }],
      },
    });
    override("DELETE", "/api/v1/oauth/grants", { status: 404, body: { detail: "такого застосунку немає" } });
    const { user } = await renderApp("#/");
    await user.click(await screen.findByRole("button", { name: "Відключити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("такого застосунку немає");
  });
});
