import * as Tooltip from "@radix-ui/react-tooltip";

/**
 * Значок підказки: показує ОРИГІНАЛЬНИЙ англійський текст.
 * Доступність: кнопка з aria-label, Radix дає aria-describedby і клавіатуру.
 */
export function Hint({ original }: { original: string }) {
  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>
        <button type="button" className="hint-trigger" aria-label={`Оригінал: ${original}`}>
          ?
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="hint-content" sideOffset={6} collisionPadding={8}>
          <span className="hint-original">{original}</span>
          <Tooltip.Arrow className="hint-arrow" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
