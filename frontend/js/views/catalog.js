import { api } from "../api.js";
import { dayList } from "../components/dayList.js";
import { eventRow } from "../components/eventRow.js";
import { h, replaceContent } from "../dom.js";
import { dayRange } from "../format.js";
import { store } from "../store.js";
import { emptyBlock, errorBlock, loading } from "../ui.js";
import { WHEN_OPTIONS } from "../vocabulary.js";

const PAGE_SIZE = 20;
const SEARCH_DELAY_MS = 300;

const blankFilters = () => ({ category: "", when: "", free: false, pushkin: false, priceMax: "", q: "" });

// Фильтры переживают переходы между экранами: вернувшись из карточки, пользователь видит тот же список.
let filters = blankFilters();

function toQuery({ category, when, free, pushkin, priceMax, q }) {
  const { from, to } = dayRange(when);
  return {
    category,
    date_from: from,
    date_to: to,
    free,
    pushkin_card: pushkin,
    price_max: priceMax,
    q: q.trim(),
  };
}

export default function catalogView() {
  const results = h("div", { class: "results" });
  const notice = h("p", { class: "notice", hidden: true });
  let items = [];
  let total = 0;
  let generation = 0; // отсекает ответы устаревших запросов

  async function load({ append = false } = {}) {
    const current = ++generation;
    if (!append) replaceContent(results, loading());
    try {
      const page = await api.events.list({
        ...toQuery(filters),
        limit: PAGE_SIZE,
        offset: append ? items.length : 0,
      });
      if (current !== generation) return;
      items = append ? [...items, ...page.items] : page.items;
      total = page.total;
      notice.hidden = !items.some((event) => event.is_test_data);
      draw();
    } catch (error) {
      if (current === generation) replaceContent(results, errorBlock(error, () => load()));
    }
  }

  function draw() {
    if (items.length === 0) {
      replaceContent(
        results,
        emptyBlock("Ничего не нашлось", "Попробуйте снять часть фильтров."),
        h("button", { class: "button", onclick: resetFilters }, "Сбросить фильтры"),
      );
      return;
    }
    replaceContent(
      results,
      dayList(items, (event) => eventRow(event)),
      items.length < total &&
        h(
          "button",
          { class: "button button-wide", onclick: () => load({ append: true }) },
          `Показать ещё (${total - items.length})`,
        ),
    );
  }

  function resetFilters() {
    filters = blankFilters();
    search.value = "";
    when.value = "";
    price.value = "";
    refreshControls();
    load();
  }

  function change(patch) {
    filters = { ...filters, ...patch };
    refreshControls();
    load();
  }

  // --- элементы управления ---------------------------------------------------------------

  let searchTimer;
  const search = h("input", {
    type: "search",
    class: "input",
    placeholder: "Название или описание",
    "aria-label": "Поиск по афише",
    value: filters.q,
    oninput: (event) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => change({ q: event.target.value }), SEARCH_DELAY_MS);
    },
  });

  const categoryBar = h("div", { class: "chips", role: "group", "aria-label": "Категории" });
  const when = h(
    "select",
    { class: "input", "aria-label": "Дата", onchange: (event) => change({ when: event.target.value }) },
    WHEN_OPTIONS.map(({ value, label }) => h("option", { value, selected: value === filters.when }, label)),
  );
  const price = h("input", {
    type: "number",
    class: "input",
    min: "0",
    step: "50",
    inputmode: "numeric",
    placeholder: "Цена до, ₽",
    "aria-label": "Максимальная цена",
    value: filters.priceMax,
    oninput: (event) => change({ priceMax: event.target.value }),
  });
  const free = toggle("Бесплатно", () => filters.free, (value) => change({ free: value }));
  const pushkin = toggle("Пушкинская карта", () => filters.pushkin, (value) => change({ pushkin: value }));

  function refreshControls() {
    const options = [{ slug: "", title: "Все" }, ...store.categories];
    replaceContent(
      categoryBar,
      options.map(({ slug, title }) =>
        h(
          "button",
          {
            type: "button",
            class: "chip",
            "aria-pressed": String(filters.category === slug),
            onclick: () => change({ category: slug }),
          },
          title,
        ),
      ),
    );
    free.paint();
    pushkin.paint();
  }

  function build() {
    refreshControls();
    return h(
      "section",
      { class: "view" },
      h("h1", {}, "Афиша"),
      h("p", { class: "lead" }, store.user?.city?.name ?? ""),
      notice,
      search,
      categoryBar,
      h("div", { class: "filters" }, when, price),
      h("div", { class: "filters" }, free.button, pushkin.button),
      results,
    );
  }

  const node = build();
  notice.textContent = "Показаны демонстрационные данные: события вымышлены.";
  load();
  return node;
}

/** Кнопка-переключатель с состоянием aria-pressed. */
function toggle(label, get, set) {
  const button = h("button", { type: "button", class: "chip", onclick: () => set(!get()) }, label);
  return {
    button,
    paint: () => button.setAttribute("aria-pressed", String(get())),
  };
}
