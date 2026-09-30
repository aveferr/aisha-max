import { api } from "../api.js";
import { dayList } from "../components/dayList.js";
import { eventRow } from "../components/eventRow.js";
import { pollList } from "../components/pollList.js";
import { h, replaceContent } from "../dom.js";
import { store } from "../store.js";
import { attempt, emptyBlock, errorBlock, loading } from "../ui.js";
import { POLL_MAX_OPTIONS, POLL_MIN_OPTIONS } from "../vocabulary.js";

export default function favoritesView() {
  const node = h("section", { class: "view" });
  let events = [];
  let choosing = false;
  const chosen = new Set();
  const polls = pollList();

  async function load() {
    replaceContent(node, h("h1", {}, "Избранное"), loading());
    polls.load();
    try {
      events = await api.favorites.list();
      draw();
    } catch (error) {
      replaceContent(node, h("h1", {}, "Избранное"), errorBlock(error, load));
    }
  }

  function draw() {
    // Событие могли убрать из избранного прямо в списке — показываем актуальное состояние.
    events = events.filter((event) => store.favoriteIds.has(event.id));
    if (events.length === 0) {
      replaceContent(
        node,
        h("h1", {}, "Избранное"),
        emptyBlock("Пока пусто", "Добавляйте события закладкой, чтобы вернуться к ним позже."),
        h("a", { class: "button", href: "#/" }, "Открыть афишу"),
        polls.node,
      );
      return;
    }

    const canPoll = events.length >= POLL_MIN_OPTIONS;
    replaceContent(
      node,
      h("h1", {}, "Избранное"),
      canPoll &&
        h(
          "button",
          {
            class: "button",
            onclick: () => {
              choosing = !choosing;
              chosen.clear();
              draw();
            },
          },
          choosing ? "Отмена" : "Выбрать вместе с друзьями",
        ),
      choosing &&
        h(
          "p",
          { class: "note" },
          `Отметьте от ${POLL_MIN_OPTIONS} до ${POLL_MAX_OPTIONS} событий — друзья смогут проголосовать.`,
        ),
      dayList(events, (event) => eventRow(event, { leading: choosing ? checkbox(event) : null })),
      choosing && pollBar(),
      polls.node,
    );
  }

  function checkbox(event) {
    return h("input", {
      type: "checkbox",
      class: "check",
      "aria-label": `Выбрать: ${event.title}`,
      checked: chosen.has(event.id),
      onchange: (change) => {
        if (change.target.checked && chosen.size >= POLL_MAX_OPTIONS) {
          change.target.checked = false;
          return;
        }
        change.target.checked ? chosen.add(event.id) : chosen.delete(event.id);
        draw();
      },
    });
  }

  function pollBar() {
    const enough = chosen.size >= POLL_MIN_OPTIONS;
    return h(
      "div",
      { class: "sticky-bar" },
      h(
        "button",
        {
          class: "button button-primary button-wide",
          disabled: !enough,
          onclick: async () => {
            const { ok, result } = await attempt(() => api.polls.create([...chosen]));
            if (ok) location.hash = `#/poll/${result.id}`;
          },
        },
        `Создать голосование (${chosen.size})`,
      ),
    );
  }

  load();
  return node;
}
