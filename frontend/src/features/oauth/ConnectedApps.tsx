/**
 * «Підключені застосунки»: кому гравець дозволив керувати персонажами (MCP).
 *
 * Порожній список не показується зовсім — більшість гравців застосунків не
 * підключає, і зайвий розділ на головній їм ні до чого.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { disconnectApp, fetchConnectedApps } from "../../api";

function day(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString("uk-UA", { day: "numeric", month: "long", year: "numeric" });
}

export function ConnectedApps() {
  const client = useQueryClient();
  const apps = useQuery({ queryKey: ["connected-apps"], queryFn: fetchConnectedApps, retry: false });
  const disconnect = useMutation({
    mutationFn: disconnectApp,
    onSuccess: (data) => client.setQueryData(["connected-apps"], data),
  });

  const items = apps.data?.items ?? [];
  if (!items.length) return null;
  return (
    <section className="saved connected-apps" aria-labelledby="connected-apps-title">
      <div className="saved-head">
        <h2 id="connected-apps-title">Підключені застосунки</h2>
      </div>
      <p className="hint">Ці застосунки можуть бачити й змінювати ваших персонажів. Відключення діє одразу.</p>
      <ul className="connected-apps__list">
        {items.map((app) => (
          <li key={app.client_id}>
            <span>
              <strong>{app.name}</strong>
              <span className="hint">
                {" "}
                · з {day(app.connected_at)}
                {app.last_used_at ? ` · востаннє ${day(app.last_used_at)}` : ""}
              </span>
            </span>
            <button
              type="button"
              className="button"
              disabled={disconnect.isPending}
              onClick={() => {
                if (window.confirm(`Відключити «${app.name}»? Він більше не матиме доступу до персонажів.`)) {
                  disconnect.mutate(app.client_id);
                }
              }}
            >
              Відключити
            </button>
          </li>
        ))}
      </ul>
      {disconnect.error ? (
        <p className="status status--error" role="alert">
          {disconnect.error instanceof Error ? disconnect.error.message : String(disconnect.error)}
        </p>
      ) : null}
    </section>
  );
}
