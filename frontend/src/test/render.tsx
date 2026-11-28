import { render } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

/**
 * Render the whole app at a route. Modules are reloaded for every test: App keeps
 * its QueryClient and api.ts its catalogs at module level, and a cache from the
 * previous test would answer instead of the tape.
 */
export async function renderApp(route = "#/"): Promise<RenderResult & { user: ReturnType<typeof userEvent.setup> }> {
  // `#/…` — маршрут застосунку, `/bugs` — справжня адреса; шлях попереднього тесту не лишається.
  window.history.replaceState(null, "", route.startsWith("/") ? route : `/${route}`);
  vi.resetModules();
  const { default: App } = await import("../App");
  const user = userEvent.setup({ delay: null });
  return { ...render(<App />), user };
}
