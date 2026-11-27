/**
 * «Поділитися»: посилання на лист лише для перегляду.
 *
 * За посиланням лист відкривається без входу: його видно, можна надрукувати чи
 * завантажити PDF, але змінити нічого не можна. Нове посилання замінює старе
 * (старе перестає працювати), «Вимкнути» відкликає його зовсім.
 *
 * Якщо є бот Telegram — ще й посилання `t.me/<бот>?startapp=s_<токен>`: воно
 * відкриває той самий лист одразу в Mini App. У самому Telegram — кнопка
 * «Надіслати в Telegram» з вибором чату.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { createShare, fetchAuthConfig, fetchShare, revokeShare } from "../../api";
import { inTelegram, shareToTelegram, telegramShareLink } from "../../telegram";

export function SharePanel({ characterId, onClose }: { characterId: string; onClose: () => void }) {
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchShare(characterId)
      .then((share) => alive && setToken(share.token))
      .catch((failure: unknown) => alive && setError(failure instanceof Error ? failure.message : String(failure)));
    return () => {
      alive = false;
    };
  }, [characterId]);

  const config = useQuery({ queryKey: ["auth-config"], queryFn: fetchAuthConfig, staleTime: Infinity });
  const bot = config.data?.telegram_ready ? config.data.telegram_bot : null;
  const link = token ? `${window.location.origin}/#/s/${token}` : "";
  const telegramLink = token && bot ? telegramShareLink(bot, token) : "";

  async function act(action: () => Promise<{ token: string | null }>) {
    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      setToken((await action()).token);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string = link) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setError("Не вдалося скопіювати — виділіть посилання й скопіюйте вручну.");
    }
  }

  return (
    <section className="share-panel" aria-label="Поділитися листом">
      <header className="share-panel__head">
        <h2 className="share-panel__title">Поділитися листом</h2>
        <button type="button" className="link-button" onClick={onClose}>
          закрити
        </button>
      </header>
      <p className="share-panel__lead">
        За посиланням лист видно без входу: його можна переглянути, надрукувати й завантажити PDF, але не змінити. Видно
        все, що на листі, разом із нотатками.
      </p>
      {token === undefined && !error ? <p className="meta">Перевіряємо…</p> : null}
      {token === null ? (
        <button
          type="button"
          className="button button--primary"
          disabled={busy}
          onClick={() => void act(() => createShare(characterId))}
        >
          Створити посилання
        </button>
      ) : null}
      {token ? (
        <>
          <div className="share-panel__link">
            <input
              readOnly
              value={link}
              aria-label="Посилання на лист лише для перегляду"
              onFocus={(event) => event.currentTarget.select()}
            />
            <button type="button" className="button button--primary" onClick={() => void copy()}>
              {copied ? "Скопійовано" : "Копіювати"}
            </button>
          </div>
          {telegramLink ? (
            <div className="share-panel__telegram">
              <p className="meta">У Telegram лист відкриється одразу в застосунку:</p>
              <div className="share-panel__link">
                <input
                  readOnly
                  value={telegramLink}
                  aria-label="Посилання на лист у Telegram"
                  onFocus={(event) => event.currentTarget.select()}
                />
                {inTelegram ? (
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => shareToTelegram(telegramLink, "Мій персонаж D&D")}
                  >
                    Надіслати в Telegram
                  </button>
                ) : (
                  <button type="button" className="button" onClick={() => void copy(telegramLink)}>
                    Копіювати
                  </button>
                )}
              </div>
            </div>
          ) : null}
          <div className="share-panel__actions">
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => void act(() => createShare(characterId))}
              title="Старе посилання перестане працювати"
            >
              Нове посилання
            </button>
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => void act(() => revokeShare(characterId))}
            >
              Вимкнути посилання
            </button>
          </div>
        </>
      ) : null}
      {error ? <p className="status status--error">{error}</p> : null}
    </section>
  );
}
