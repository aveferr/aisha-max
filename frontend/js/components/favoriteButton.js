import { bookmarkIcon, h } from "../dom.js";
import { isFavorite, toggleFavorite } from "../store.js";
import { attempt } from "../ui.js";

/** Кнопка избранного; сама обновляет вид после ответа сервера. */
export function favoriteButton(eventId, { withLabel = false } = {}) {
  const button = h("button", { type: "button", class: withLabel ? "button" : "icon-button" });

  const paint = () => {
    const active = isFavorite(eventId);
    button.setAttribute("aria-pressed", String(active));
    button.setAttribute("aria-label", active ? "Убрать из избранного" : "Добавить в избранное");
    button.replaceChildren(
      bookmarkIcon(active),
      ...(withLabel ? [document.createTextNode(active ? " В избранном" : " В избранное")] : []),
    );
  };

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    button.disabled = true;
    await attempt(() => toggleFavorite(eventId));
    button.disabled = false;
    paint();
  });

  paint();
  return button;
}
