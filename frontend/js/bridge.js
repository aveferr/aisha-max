// Обёртка над MAX Bridge (window.WebApp). Вне MAX (обычный браузер) все вызовы безопасно
// превращаются в «ничего не делать» или в разумный запасной вариант.

const webApp = () => window.WebApp ?? null;

export const isInsideMax = () => Boolean(webApp()?.initData);

export const initData = () => webApp()?.initData ?? "";

export function startParam() {
  return (
    webApp()?.initDataUnsafe?.start_param ??
    new URLSearchParams(location.search).get("start_param")
  );
}

export function ready() {
  webApp()?.ready?.();
}

export function openLink(url) {
  if (webApp()?.openLink) webApp().openLink(url);
  else window.open(url, "_blank", "noopener");
}

export function haptic(kind = "success") {
  try {
    webApp()?.HapticFeedback?.notificationOccurred?.(kind);
  } catch {
    /* вибрация — приятное дополнение, а не обязательная часть */
  }
}

/** Системная кнопка «назад» MAX: показываем на вложенных экранах. */
export function setBackButton(visible, onClick) {
  const button = webApp()?.BackButton;
  if (!button) return;
  if (setBackButton.handler) button.offClick?.(setBackButton.handler);
  setBackButton.handler = onClick;
  if (visible) {
    button.onClick?.(onClick);
    button.show?.();
  } else {
    button.hide?.();
  }
}
