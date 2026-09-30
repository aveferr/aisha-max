import { ApiError } from "./api.js";
import { isInsideMax, ready, setBackButton, startParam } from "./bridge.js";
import { h, replaceContent } from "./dom.js";
import { matchRoute, routeFromStartParam } from "./router.js";
import { bootstrap } from "./store.js";
import { errorBlock, loading } from "./ui.js";
import assistantView from "./views/assistant.js";
import catalogView from "./views/catalog.js";
import eventView from "./views/event.js";
import favoritesView from "./views/favorites.js";
import pollView from "./views/poll.js";
import profileView from "./views/profile.js";

const VIEWS = {
  catalog: catalogView,
  event: eventView,
  assistant: assistantView,
  favorites: favoritesView,
  poll: pollView,
  profile: profileView,
};

const app = document.getElementById("app");
const tabs = document.querySelectorAll("#tabs a");
let disposeCurrent = null;
let renderId = 0;

function render() {
  const route = matchRoute(location.hash);
  const current = ++renderId;

  disposeCurrent?.();
  disposeCurrent = null;

  for (const tab of tabs) {
    if (tab.dataset.tab === route.tab) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  setBackButton(!route.isRoot, () => history.back());

  const view = VIEWS[route.name];
  if (!view) {
    replaceContent(app, h("p", { class: "status" }, "Такой страницы нет."), h("a", { class: "button", href: "#/" }, "К афише"));
    return;
  }

  // Экран может вернуть узел или { node, dispose } (например, если он обновляется по таймеру).
  const result = view(route.params);
  if (current !== renderId) return;
  const { node, dispose } = result.node ? result : { node: result, dispose: null };
  disposeCurrent = dispose;
  replaceContent(app, node);
  window.scrollTo(0, 0);
}

function loginProblem(error) {
  const unauthorized = error instanceof ApiError && error.status === 401;
  const hint = isInsideMax()
    ? "Не удалось подтвердить вход. Закройте приложение и откройте его заново."
    : "Откройте приложение из чата с ботом в MAX.";
  return unauthorized
    ? h("div", { class: "status" }, h("p", { class: "status-title" }, "Нужен вход через MAX"), h("p", {}, hint))
    : errorBlock(error, start);
}

async function start() {
  replaceContent(app, loading());
  ready();
  try {
    await bootstrap();
  } catch (error) {
    replaceContent(app, loginProblem(error));
    return;
  }
  window.addEventListener("hashchange", render);
  // MAX открывает приложение с данными запуска в хэше (#WebAppData=...), это не маршрут.
  // Такой хэш заменяем на экран из ссылки бота (start_param) или на каталог.
  if (!location.hash.startsWith("#/")) {
    const target = routeFromStartParam(startParam()) ?? "#/";
    history.replaceState(null, "", location.pathname + location.search + target);
  }
  render();
}

start();
