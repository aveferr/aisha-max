import { api } from "../api.js";
import { h, replaceContent } from "../dom.js";
import { formatDay, plural } from "../format.js";

const VOTE_FORMS = ["голос", "голоса", "голосов"];

/**
 * Раздел «Мои голосования»: созданные пользователем и те, где он голосовал.
 * Пока голосований нет, раздел скрыт; сбой загрузки его тоже прячет — это дополнение к экрану.
 */
export function pollList() {
  const node = h("section", { class: "polls", hidden: true });

  async function load() {
    try {
      const polls = await api.polls.list();
      node.hidden = polls.length === 0;
      if (polls.length > 0) {
        replaceContent(
          node,
          h("h2", { class: "section-title" }, "Мои голосования"),
          h("div", {}, polls.map(pollRow)),
        );
      }
    } catch {
      node.hidden = true;
    }
  }

  return { node, load };
}

function pollRow(poll) {
  const events = poll.events_preview.join(" · ");
  const more = poll.options_count > poll.events_preview.length ? " …" : "";
  const role = poll.is_mine ? "вы создали" : "вы проголосовали";
  const waiting = !poll.voted ? " · ждёт вашего голоса" : "";

  return h(
    "article",
    { class: "row" },
    h(
      "a",
      { class: "row-main", href: `#/poll/${poll.id}` },
      h(
        "span",
        { class: "row-body" },
        h("span", { class: "row-title" }, poll.title),
        h("span", { class: "row-meta" }, events + more),
        h(
          "span",
          { class: "row-meta" },
          `${poll.total_votes} ${plural(poll.total_votes, VOTE_FORMS)} · ${role} ${formatDay(poll.created_at)}${waiting}`,
        ),
      ),
    ),
  );
}
