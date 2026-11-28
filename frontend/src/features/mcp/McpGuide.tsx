/**
 * Як підключити ІІ-асистента (Claude чи інший клієнт MCP) до своїх персонажів.
 *
 * Адреса сервера береться з поточного сайту: на dnd.voronin.app це
 * https://dnd.voronin.app/mcp, локально — адреса розробницького сервера.
 */
import { useState } from "react";

import { LoginPanel } from "../auth/Login";

function CopyLine({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mcp-copy">
      <code>{text}</code>
      <button
        type="button"
        className="button"
        aria-label={label}
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(
            () => setCopied(true),
            () => setCopied(false),
          );
        }}
      >
        {copied ? "Скопійовано" : "Копіювати"}
      </button>
    </div>
  );
}

const EXAMPLES = [
  "Створи мені халфлінга-барда, колишнього контрабандиста",
  "Розбійник отримав 7 урону",
  "Ми зробили короткий відпочинок",
  "Додай Розбійнику мотузку й 20 стріл",
  "Що дасть Розбійнику 4-й рівень? Підніми з середніми хітами",
  "Дай посилання на лист для майстра",
];

export function McpGuide({ signedIn }: { signedIn: boolean }) {
  const server = `${window.location.origin}/mcp`;
  return (
    <article className="kb mcp-guide">
      <h2>Персонажі в ІІ-асистенті</h2>
      <p className="lead">
        Підключіть Claude (або інший застосунок із підтримкою MCP) — і просіть звичайними словами: створити персонажа,
        записати урон, відпочити, додати предмет, підняти рівень. Асистент працює лише з вашими персонажами й лише за
        правилами сайту: числа рахує сайт, а не модель.
      </p>

      <h3>Перш ніж почати</h3>
      {signedIn ? (
        <p>Ви вже увійшли на сайт — можна підключати.</p>
      ) : (
        <LoginPanel reason="Потрібен акаунт на сайті: увійдіть через Telegram хоча б раз. Застосунок не створює акаунтів сам." />
      )}

      <h3>Claude</h3>
      <p>
        Додайте конектор на claude.ai або в Claude для компʼютера. Він привʼязаний до акаунта Claude, тож потім працює й
        у застосунку на телефоні.
      </p>
      <ol className="mcp-steps">
        <li>Налаштування → «Конектори» (Connectors) → додати власний конектор (Add custom connector).</li>
        <li>
          Назва — будь-яка, наприклад <code>dnd-sheet</code>. Адреса:
          <CopyLine text={server} label="Копіювати адресу сервера" />
        </li>
        <li>
          Натисніть «Підключити» (Connect). Відкриється цей сайт: увійдіть через Telegram, перевірте назву застосунку й
          адресу повернення та натисніть «Дозволити».
        </li>
        <li>Перевірте: напишіть Claude «Покажи моїх персонажів» — у відповіді буде ваш список.</li>
      </ol>

      <h3>Claude Code</h3>
      <CopyLine text={`claude mcp add --transport http dnd-sheet ${server}`} label="Копіювати команду" />
      <p className="hint">
        Потім у Claude Code: <code>/mcp</code> → dnd-sheet → Authenticate.
      </p>

      <h3>Інші застосунки</h3>
      <p>
        Будь-який клієнт MCP із транспортом Streamable HTTP і входом через OAuth: вкажіть адресу сервера, решту він
        знайде сам.
      </p>

      <h3>Що можна просити</h3>
      <ul className="mcp-list">
        {EXAMPLES.map((example) => (
          <li key={example}>«{example}»</li>
        ))}
      </ul>

      <h3>Межі й безпека</h3>
      <ul className="mcp-list">
        <li>Лише ваші персонажі; чужих асистент не бачить.</li>
        <li>До 50 персонажів на гравця — так само, як на сайті.</li>
        <li>
          Видалення — лише на ваше пряме прохання: асистент мусить назвати точне імʼя персонажа, а застосунок спитає
          підтвердження.
        </li>
        <li>Доступ діє, доки ви його не відкличете: на головній, у розділі «Підключені застосунки» → «Відключити».</li>
      </ul>
    </article>
  );
}
