/**
 * Екран дозволу: застосунок (Claude чи інший клієнт MCP) просить доступ до персонажів.
 *
 * Сюди браузер приходить з `/authorize` (ADR 0005). Гравець бачить, хто просить,
 * що саме і куди повернеться браузер, і вирішує. Увійти тут можна лише в наявний
 * акаунт: застосунки не заводять нових гравців.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { decideOAuthRequest, fetchMe, fetchOAuthRequest } from "../../api";
import { LoginPanel } from "../auth/Login";

/** Куди перейти після рішення; у тестах підміняється. */
export const browser = {
  go(url: string) {
    window.location.assign(url);
  },
};

export function Consent({ requestId }: { requestId: string }) {
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const shown = useQuery({
    queryKey: ["oauth-request", requestId],
    queryFn: () => fetchOAuthRequest(requestId),
    retry: false,
  });
  const decision = useMutation({
    mutationFn: (approve: boolean) => decideOAuthRequest(requestId, approve),
    onSuccess: ({ redirect }) => browser.go(redirect),
  });

  if (shown.isPending || me.isPending) return <p className="status">Читаємо запит застосунку…</p>;
  if (shown.error) {
    return (
      <section className="login consent">
        <h2>Підключення застосунку</h2>
        <p className="status status--error" role="alert">
          {shown.error instanceof Error ? shown.error.message : String(shown.error)}
        </p>
      </section>
    );
  }

  const request = shown.data;
  const user = me.data?.user ?? null;
  const name = request.client.name;

  if (!user) {
    return (
      <LoginPanel
        existingOnly
        reason={`«${name}» просить доступ до ваших персонажів. Увійдіть через Telegram тим самим акаунтом, що й на сайті: новий акаунт тут не створюється.`}
      />
    );
  }

  const finished = decision.isSuccess;
  return (
    <section className="login consent" aria-labelledby="consent-title">
      <h2 id="consent-title">«{name}» просить доступ</h2>
      <p className="lead">
        До акаунта <strong>{user.name}</strong>. Застосунок зможе:
      </p>
      <ul className="plain-list consent__scopes">
        {request.scopes.map((scope) => (
          <li key={scope.key}>{scope.title}</li>
        ))}
      </ul>
      <p className="hint">
        Після рішення браузер повернеться на <strong>{request.redirect_host}</strong>.
        {request.client.uri ? (
          <>
            {" "}
            Сайт застосунку:{" "}
            <a href={request.client.uri} target="_blank" rel="noopener noreferrer">
              {request.client.uri}
            </a>
            .
          </>
        ) : null}
      </p>
      {request.client.local_only ? (
        <p className="hint hint--warn">
          Застосунок працює на цьому компʼютері (localhost). Дозволяйте, лише якщо ви самі його щойно запустили.
        </p>
      ) : null}
      {!request.client.verified_by_url ? (
        <p className="hint hint--warn">
          Застосунок назвав себе сам, під час реєстрації. Перевірте назву й адресу повернення.
        </p>
      ) : null}
      <div className="consent__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={decision.isPending || finished}
          onClick={() => decision.mutate(true)}
        >
          Дозволити
        </button>
        <button
          type="button"
          className="button"
          disabled={decision.isPending || finished}
          onClick={() => decision.mutate(false)}
        >
          Відмовити
        </button>
      </div>
      {decision.error ? (
        <p className="status status--error" role="alert">
          {decision.error instanceof Error ? decision.error.message : String(decision.error)}
        </p>
      ) : null}
      {finished ? <p className="hint">Повертаємося до застосунку…</p> : null}
      <p className="hint">Відключити застосунок можна будь-коли на головній, у розділі «Підключені застосунки».</p>
    </section>
  );
}
