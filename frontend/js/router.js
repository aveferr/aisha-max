// Маршрутизация по location.hash. Мини-приложение открывается по одному адресу,
// поэтому хэш-маршруты не требуют настройки сервера.

const ROUTES = [
  { name: "catalog", pattern: /^\/?$/, tab: "catalog" },
  { name: "event", pattern: /^\/event\/(\d+)$/, tab: "catalog" },
  { name: "assistant", pattern: /^\/assistant$/, tab: "assistant" },
  { name: "favorites", pattern: /^\/favorites$/, tab: "favorites" },
  { name: "poll", pattern: /^\/poll\/(\d+)$/, tab: "favorites" },
  { name: "profile", pattern: /^\/profile$/, tab: "profile" },
];

const ROOT_TABS = new Set(["catalog", "assistant", "favorites", "profile"]);

/** '#/event/12' → { name: 'event', params: ['12'], tab: 'catalog', isRoot: false } */
export function matchRoute(hash) {
  const path = hash.replace(/^#/, "") || "/";
  for (const route of ROUTES) {
    const match = path.match(route.pattern);
    if (match) {
      return {
        name: route.name,
        params: match.slice(1),
        tab: route.tab,
        isRoot: ROOT_TABS.has(route.name),
      };
    }
  }
  return { name: "notfound", params: [], tab: null, isRoot: false };
}

/** Параметр запуска из ссылки (start_param) → хэш-маршрут. */
export function routeFromStartParam(param) {
  if (!param) return null;
  if (param === "catalog") return "#/";
  const match = param.match(/^(event|poll)_(\d+)$/);
  return match ? `#/${match[1]}/${match[2]}` : null;
}
