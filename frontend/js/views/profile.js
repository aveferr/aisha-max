import { api } from "../api.js";
import { h, replaceContent } from "../dom.js";
import { formatWhen } from "../format.js";
import { clearReminder, store } from "../store.js";
import { attempt, emptyBlock } from "../ui.js";

export default function profileView() {
  const interests = h("div", { class: "chips", role: "group", "aria-label": "Интересы" });
  const reminders = h("div");

  function drawInterests() {
    const selected = new Set(store.user.interests.map((category) => category.slug));
    replaceContent(
      interests,
      store.categories.map(({ slug, title }) =>
        h(
          "button",
          {
            type: "button",
            class: "chip",
            "aria-pressed": String(selected.has(slug)),
            onclick: async () => {
              const next = new Set(selected);
              next.has(slug) ? next.delete(slug) : next.add(slug);
              const { ok, result } = await attempt(() => api.me.update({ interests: [...next] }));
              if (ok) store.user = result;
              drawInterests();
            },
          },
          title,
        ),
      ),
    );
  }

  async function drawReminders() {
    const { ok, result } = await attempt(() => api.reminders.list());
    if (!ok) return;
    if (result.length === 0) {
      replaceContent(reminders, emptyBlock("Напоминаний нет", "Поставить можно на странице события."));
      return;
    }
    replaceContent(
      reminders,
      h(
        "ul",
        { class: "plain-list" },
        result.map(({ event, remind_at: remindAt }) =>
          h(
            "li",
            { class: "plain-item" },
            h(
              "div",
              {},
              h("a", { href: `#/event/${event.id}` }, event.title),
              h("p", { class: "row-meta" }, `Напомним: ${formatWhen(remindAt)}`),
            ),
            h(
              "button",
              {
                class: "button",
                onclick: async () => {
                  const done = await attempt(() => clearReminder(event.id));
                  if (done.ok) drawReminders();
                },
              },
              "Отменить",
            ),
          ),
        ),
      ),
    );
  }

  drawInterests();
  drawReminders();

  return h(
    "section",
    { class: "view" },
    h("h1", {}, "Профиль"),
    h("p", { class: "lead" }, [store.user.first_name, store.user.city?.name].filter(Boolean).join(" · ")),
    h("h2", { class: "section-title" }, "Интересы"),
    h("p", { class: "note" }, "Учитываются при подборе: события этих категорий поднимаются выше."),
    interests,
    h("h2", { class: "section-title" }, "Напоминания"),
    reminders,
  );
}
