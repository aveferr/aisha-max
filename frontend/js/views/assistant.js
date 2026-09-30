import { api } from "../api.js";
import { openLink } from "../bridge.js";
import { favoriteButton } from "../components/favoriteButton.js";
import { h, replaceContent } from "../dom.js";
import { formatPrice, formatWhen } from "../format.js";
import { setReminder } from "../store.js";
import { attempt } from "../ui.js";
import { DEFAULT_REMINDER_MINUTES, POLL_MIN_OPTIONS } from "../vocabulary.js";

// Подписи быстрых ответов приходят с эмодзи (для чата MAX); в интерфейсе приложения они не нужны.
const plainLabel = (label) => label.replace(/^[\p{Extended_Pictographic}\uFE0F\s]+/u, "");

// История диалога живёт, пока открыто приложение: при переключении вкладок она не теряется.
const thread = [];
let started = false;

export default function assistantView() {
  const log = h("div", { class: "chat-log" });
  const status = h("p", { class: "status", hidden: true }, "Подбираю…");
  const input = h("input", {
    class: "input",
    type: "text",
    name: "message",
    autocomplete: "off",
    maxlength: "1000",
    placeholder: "Например: спокойное и недорого в субботу вечером",
    "aria-label": "Сообщение",
  });
  const submit = h("button", { class: "button button-primary", type: "submit" }, "Отправить");
  let busy = false;

  function setBusy(value) {
    busy = value;
    input.disabled = submit.disabled = value;
    status.hidden = !value;
    if (!value) input.focus({ preventScroll: true });
  }

  function draw() {
    replaceContent(
      log,
      thread.map((message, index) => renderMessage(message, index === thread.length - 1)),
    );
    log.lastElementChild?.scrollIntoView({ block: "nearest" });
  }

  function renderMessage(message, isLast) {
    if (message.role === "user") return h("p", { class: "bubble bubble-user" }, message.text);
    return h(
      "div",
      { class: "bubble bubble-bot" },
      h("p", { class: "bubble-text" }, message.text),
      message.cards.map((card, index) => pick(card, index + 1)),
      isLast && message.cards.length >= POLL_MIN_OPTIONS && pollButton(message.cards),
      isLast &&
        message.quickReplies.length > 0 &&
        h(
          "div",
          { class: "quick" },
          message.quickReplies.map(({ label, payload }) =>
            h(
              "button",
              { type: "button", class: "chip", onclick: () => send({ payload }, plainLabel(label)) },
              plainLabel(label),
            ),
          ),
        ),
    );
  }

  async function send(body, shownText) {
    if (busy) return;
    if (shownText) thread.push({ role: "user", text: shownText });
    draw();
    setBusy(true);
    const { ok, result } = await attempt(() => (body ? api.assistant.say(body) : api.assistant.reset()));
    setBusy(false);
    if (ok) {
      thread.push({
        role: "assistant",
        text: result.text,
        cards: result.cards,
        quickReplies: result.quick_replies,
      });
    }
    draw();
  }

  const form = h(
    "form",
    {
      class: "composer",
      onsubmit: (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        send({ text }, text);
      },
    },
    input,
    submit,
  );

  if (started) draw();
  else {
    started = true;
    send(null, null); // первое открытие: приветствие и первый вопрос
  }

  return h(
    "section",
    { class: "view view-chat" },
    h("h1", {}, "Подбор"),
    h("p", { class: "lead" }, "Напишите, что хочется, или отвечайте кнопками."),
    log,
    status,
    form,
  );
}

/** Карточка предложенного события с причинами выбора и источником. */
function pick({ event, reasons, source_note: sourceNote }, number) {
  return h(
    "article",
    { class: "pick" },
    h("h3", {}, h("a", { href: `#/event/${event.id}` }, `${number}. ${event.title}`)),
    h("p", { class: "row-meta" }, `${formatWhen(event.starts_at)} · ${event.venue.name}`),
    h("p", { class: "row-meta" }, `${formatPrice(event)} · ${event.age_limit}+`),
    reasons.length > 0 && h("p", { class: "why" }, `Почему подходит: ${reasons.join("; ")}`),
    h("p", { class: "source" }, sourceNote.replace(/\s*\u26A0\s*/u, " · ")),
    h(
      "div",
      { class: "actions actions-inline" },
      favoriteButton(event.id, { withLabel: true }),
      h(
        "button",
        {
          type: "button",
          class: "button",
          onclick: () =>
            attempt(() => setReminder(event.id, DEFAULT_REMINDER_MINUTES), {
              success: "Напомним за 2 часа",
            }),
        },
        "Напомнить",
      ),
      event.ticket_url &&
        h(
          "button",
          {
            type: "button",
            class: "button",
            onclick: async () => {
              const { ok } = await attempt(() => api.events.ticketClick(event.id));
              if (ok) openLink(event.ticket_url);
            },
          },
          "Билеты",
        ),
    ),
  );
}

function pollButton(cards) {
  return h(
    "button",
    {
      type: "button",
      class: "button button-wide",
      onclick: async () => {
        const { ok, result } = await attempt(() => api.polls.create(cards.map((card) => card.event.id)));
        if (ok) location.hash = `#/poll/${result.id}`;
      },
    },
    "Выбрать вместе с друзьями",
  );
}
