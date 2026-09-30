import { api } from "../api.js";
import { h, replaceContent } from "../dom.js";
import { formatPrice, formatWhen, plural } from "../format.js";
import { attempt, errorBlock, loading, toast } from "../ui.js";

const REFRESH_MS = 8000;
const VOTE_FORMS = ["голос", "голоса", "голосов"];

export default function pollView([id]) {
  const node = h("section", { class: "view" }, loading());
  const share = () => {
    const bot = globalThis.APP_CONFIG?.botUsername;
    return bot ? `https://max.ru/${bot}?startapp=poll_${id}` : null;
  };

  async function vote(optionId) {
    const { ok, result } = await attempt(() => api.polls.vote(id, optionId), { success: "Голос учтён" });
    if (ok) draw(result);
  }

  function draw(poll) {
    replaceContent(
      node,
      h("a", { class: "back", href: "#/favorites" }, "← Избранное"),
      h("h1", {}, poll.title),
      h("p", { class: "lead" }, `${poll.total_votes} ${plural(poll.total_votes, VOTE_FORMS)}`),
      h(
        "ol",
        { class: "options" },
        poll.options.map((option) => optionItem(option, poll)),
      ),
      shareBlock(),
    );
  }

  function optionItem({ id: optionId, event, votes }, poll) {
    const mine = poll.my_option_id === optionId;
    const percent = poll.total_votes ? Math.round((votes / poll.total_votes) * 100) : 0;
    const bar = h("div", { class: "bar" }, h("div", { class: "bar-fill" }));
    bar.firstChild.style.width = `${percent}%`;

    return h(
      "li",
      { class: "option" },
      h("a", { class: "option-title", href: `#/event/${event.id}` }, event.title),
      h("p", { class: "row-meta" }, `${formatWhen(event.starts_at)} · ${event.venue.name} · ${formatPrice(event)}`),
      bar,
      h("p", { class: "row-meta" }, `${votes} ${plural(votes, VOTE_FORMS)} · ${percent}%`),
      h(
        "button",
        {
          class: mine ? "button button-primary" : "button",
          "aria-pressed": String(mine),
          onclick: () => vote(optionId),
        },
        mine ? "Ваш выбор" : "Голосовать",
      ),
    );
  }

  function shareBlock() {
    const link = share();
    if (!link) return h("p", { class: "note" }, "Чтобы позвать друзей, перешлите им эту страницу из MAX.");
    return h(
      "div",
      { class: "share" },
      h("p", { class: "note" }, "Ссылка для друзей:"),
      h("code", { class: "link" }, link),
      h(
        "button",
        {
          class: "button",
          onclick: async () => {
            try {
              await navigator.clipboard.writeText(link);
              toast("Ссылка скопирована");
            } catch {
              toast("Не удалось скопировать — выделите ссылку вручную");
            }
          },
        },
        "Скопировать",
      ),
    );
  }

  async function refresh(first = false) {
    try {
      draw(await api.polls.get(id));
    } catch (error) {
      if (first) replaceContent(node, errorBlock(error, () => refresh(true)));
    }
  }

  refresh(true);
  const timer = setInterval(refresh, REFRESH_MS);
  return { node, dispose: () => clearInterval(timer) };
}
