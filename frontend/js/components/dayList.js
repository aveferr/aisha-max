import { h } from "../dom.js";
import { dayKey, dayParts } from "../format.js";

/** Группирует события по дням (порядок уже задан сервером) и рисует строки под заголовком дня. */
export function dayList(events, renderRow) {
  const groups = [];
  for (const event of events) {
    const key = dayKey(event.starts_at);
    const last = groups[groups.length - 1];
    if (last?.key === key) last.events.push(event);
    else groups.push({ key, events: [event] });
  }

  return h(
    "div",
    { class: "day-list" },
    groups.map(({ events: dayEvents }) => {
      const { day, month, weekday } = dayParts(dayEvents[0].starts_at);
      return h(
        "section",
        { class: "day" },
        h(
          "h2",
          { class: "day-heading" },
          h("span", { class: "day-number" }, day),
          h("span", { class: "day-name" }, `${month}, ${weekday}`),
        ),
        dayEvents.map(renderRow),
      );
    }),
  );
}
