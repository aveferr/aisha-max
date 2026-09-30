import { api } from "../api.js";
import { openLink } from "../bridge.js";
import { favoriteButton } from "../components/favoriteButton.js";
import { h, replaceContent } from "../dom.js";
import { formatDayLong, formatPrice, formatTime, formatWhen } from "../format.js";
import { clearReminder, setReminder, store } from "../store.js";
import { attempt, errorBlock, loading } from "../ui.js";
import { DEFAULT_REMINDER_MINUTES, REMINDER_OPTIONS, TAG_TITLES } from "../vocabulary.js";

const SOURCE_TITLES = {
  demo: "демонстрационный набор данных",
  "kultura.rf": "Культура.РФ",
  manual: "добавлено вручную",
};

export default function eventView([id]) {
  const node = h("section", { class: "view" }, loading());

  async function load() {
    replaceContent(node, loading());
    try {
      replaceContent(node, draw(await api.events.get(Number(id))));
    } catch (error) {
      replaceContent(node, errorBlock(error, load));
    }
  }

  load();
  return node;
}

function draw(event) {
  const cancelled = event.status === "cancelled";
  const facts = [
    ["Когда", `${formatDayLong(event.starts_at)}, ${formatTime(event.starts_at)}`],
    ["Где", [event.venue.name, event.venue.address, event.venue.city.name].filter(Boolean).join(", ")],
    ["Цена", formatPrice(event)],
    ["Возраст", `${event.age_limit}+`],
    event.pushkin_card && ["Оплата", "принимается Пушкинская карта"],
  ].filter(Boolean);

  return [
    h("a", { class: "back", href: "#/" }, "← Афиша"),
    h("p", { class: "eyebrow" }, event.category.title),
    h("h1", {}, event.title),
    cancelled && h("p", { class: "banner" }, "Событие отменено."),
    h(
      "dl",
      { class: "facts" },
      facts.map(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]),
    ),
    event.description && h("p", { class: "description" }, event.description),
    event.tags.length > 0 &&
      h("p", { class: "tags" }, event.tags.map((tag) => h("span", { class: "tag" }, TAG_TITLES[tag] ?? tag))),
    !cancelled && actions(event),
    provenance(event),
  ];
}

function actions(event) {
  const reminderBox = h("div", { class: "reminder" });
  drawReminder(reminderBox, event);

  return h(
    "div",
    { class: "actions" },
    event.ticket_url
      ? h(
          "button",
          { class: "button button-primary", onclick: () => buyTicket(event) },
          "Купить билет",
        )
      : h("p", { class: "note" }, event.is_free ? "Вход свободный." : ""),
    favoriteButton(event.id, { withLabel: true }),
    reminderBox,
  );
}

async function buyTicket(event) {
  const { ok } = await attempt(() => api.events.ticketClick(event.id));
  if (ok) openLink(event.ticket_url);
}

function drawReminder(box, event) {
  const remindAt = store.reminders.get(event.id);
  if (remindAt) {
    replaceContent(
      box,
      h("p", { class: "note" }, `Напомним: ${formatWhen(remindAt)}`),
      h(
        "button",
        {
          class: "button",
          onclick: async () => {
            const { ok } = await attempt(() => clearReminder(event.id), { success: "Напоминание отменено" });
            if (ok) drawReminder(box, event);
          },
        },
        "Отменить напоминание",
      ),
    );
    return;
  }

  const select = h(
    "select",
    { class: "input", "aria-label": "Когда напомнить" },
    REMINDER_OPTIONS.map(({ minutes, label }) =>
      h("option", { value: minutes, selected: minutes === DEFAULT_REMINDER_MINUTES }, label),
    ),
  );
  replaceContent(
    box,
    select,
    h(
      "button",
      {
        class: "button",
        onclick: async () => {
          const { ok } = await attempt(() => setReminder(event.id, Number(select.value)), {
            success: "Напоминание поставлено",
          });
          if (ok) drawReminder(box, event);
        },
      },
      "Напомнить",
    ),
  );
}

/** Происхождение данных: пользователь должен видеть, откуда сведения и насколько они свежие. */
function provenance(event) {
  const source = SOURCE_TITLES[event.source] ?? event.source;
  const updated = formatWhen(event.data_updated_at);
  return h(
    "footer",
    { class: "provenance" },
    h("p", {}, `Источник: ${source}. Данные актуальны на ${updated}.`),
    event.is_test_data && h("p", {}, "Это демонстрационные данные, такого события в действительности нет."),
    event.source_url && h("a", { href: event.source_url, target: "_blank", rel: "noopener" }, "Первоисточник"),
  );
}
