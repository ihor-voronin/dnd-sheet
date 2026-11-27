/**
 * Вхід через Telegram.
 *
 * Віджет Telegram (https://core.telegram.org/widgets/login) — це скрипт, який
 * сам малює кнопку й після підтвердження в Telegram викликає нашу функцію з
 * даними користувача й підписом. Підпис перевіряє сервер; браузер лише
 * передає дані як є. Віджет працює тільки на домені, прив'язаному до бота
 * через BotFather (`/setdomain`), тому на localhost є вхід для розробки —
 * якщо сервер його дозволив.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { fetchAuthConfig, loginDev, loginTelegram } from "../../api";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

function TelegramButton({ bot, onDone }: { bot: string; onDone: (error: string | null) => void }) {
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.onTelegramAuth = (user) => {
      loginTelegram(user)
        .then(() => onDone(null))
        .catch((failure: unknown) => onDone(failure instanceof Error ? failure.message : String(failure)));
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", bot);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "6");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    holder.current?.appendChild(script);
    const target = holder.current;
    return () => {
      delete window.onTelegramAuth;
      if (target) target.innerHTML = "";
    };
  }, [bot, onDone]);

  return <div ref={holder} className="login-telegram" />;
}

export function LoginPanel({ reason }: { reason?: string }) {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["auth-config"], queryFn: fetchAuthConfig, staleTime: Infinity });
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  function done(failure: string | null) {
    setError(failure);
    if (!failure) void queryClient.invalidateQueries();
  }

  async function devLogin() {
    setBusy(true);
    try {
      await loginDev(name);
      done(null);
    } catch (failure) {
      done(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  const data = config.data;
  return (
    <section className="login">
      <h2>Вхід</h2>
      <p className="lead">
        {reason ??
          "Увійдіть через Telegram, щоб створювати персонажів. Вони зберігаються на сервері й доступні з будь-якого пристрою."}
      </p>
      {data?.telegram_ready && data.telegram_bot ? (
        <TelegramButton bot={data.telegram_bot} onDone={done} />
      ) : data && !data.dev_login ? (
        <p className="hint">
          Вхід через Telegram ще не налаштовано: адміністратор має вказати бота (<code>DNDSHEET_TELEGRAM_BOT</code> і{" "}
          <code>DNDSHEET_TELEGRAM_BOT_TOKEN</code>).
        </p>
      ) : null}
      {data?.dev_login ? (
        <form
          className="login-dev"
          onSubmit={(event) => {
            event.preventDefault();
            void devLogin();
          }}
        >
          <label>
            <span className="meta">Вхід для розробки (без Telegram) — імʼя гравця</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="напр. Ігор" />
          </label>
          <button type="submit" className="button" disabled={busy || !name.trim()}>
            Увійти
          </button>
        </form>
      ) : null}
      {error ? <p className="status status--error">{error}</p> : null}
      <p className="hint">
        Без входу доступний <a href="#/kb">довідник</a>: види, класи, передісторії, риси, закляття, предмети.
      </p>
    </section>
  );
}
