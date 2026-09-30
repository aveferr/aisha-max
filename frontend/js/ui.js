import { haptic } from "./bridge.js";
import { h } from "./dom.js";

let toastTimer;

export function toast(message) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("visible"), 3200);
}

/** Выполняет действие; ошибку показывает уведомлением, а не роняет экран. */
export async function attempt(action, { success } = {}) {
  try {
    const result = await action();
    if (success) {
      toast(success);
      haptic("success");
    }
    return { ok: true, result };
  } catch (error) {
    toast(error.message);
    haptic("error");
    return { ok: false, error };
  }
}

export const loading = () => h("p", { class: "status" }, "Загрузка…");

export function errorBlock(error, retry) {
  return h(
    "div",
    { class: "status status-error" },
    h("p", {}, error.message),
    retry && h("button", { class: "button", onclick: retry }, "Повторить"),
  );
}

export const emptyBlock = (title, hint) =>
  h("div", { class: "status" }, h("p", { class: "status-title" }, title), hint && h("p", {}, hint));
