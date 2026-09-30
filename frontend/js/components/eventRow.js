import { h } from "../dom.js";
import { formatPrice, formatTime } from "../format.js";
import { favoriteButton } from "./favoriteButton.js";

/** Строка афиши: время слева, название и подробности, закладка справа. */
export function eventRow(event, { leading = null } = {}) {
  const details = [formatPrice(event), `${event.age_limit}+`];
  if (event.pushkin_card) details.push("Пушкинская карта");

  return h(
    "article",
    { class: "row" },
    leading,
    h(
      "a",
      { class: "row-main", href: `#/event/${event.id}` },
      h("span", { class: "row-time" }, formatTime(event.starts_at)),
      h(
        "span",
        { class: "row-body" },
        h("span", { class: "row-title" }, event.title),
        h("span", { class: "row-meta" }, `${event.category.title} · ${event.venue.name}`),
        h("span", { class: "row-meta" }, details.join(" · ")),
      ),
    ),
    favoriteButton(event.id),
  );
}
