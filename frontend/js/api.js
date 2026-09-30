import { initData } from "./bridge.js";

const config = () => globalThis.APP_CONFIG ?? {};
const base = () => config().apiBase ?? "/api/v1";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/**
 * Вне MAX для разработки можно открыть страницу как ?dev=<число>: тогда вместо подписанного
 * initData уходит X-Dev-User-Id (работает, только если сервер запущен с DEV_AUTH_ENABLED).
 */
function devUserId() {
  const fromUrl = new URLSearchParams(location.search).get("dev");
  if (fromUrl) localStorage.setItem("devUserId", fromUrl);
  return localStorage.getItem("devUserId");
}

function authHeaders() {
  const data = initData();
  if (data) return { "X-Max-Init-Data": data };
  const dev = devUserId();
  return dev ? { "X-Dev-User-Id": dev } : {};
}

function buildUrl(path, query = {}) {
  const url = new URL(base() + path, location.href);
  for (const [key, value] of Object.entries(query)) {
    for (const item of [].concat(value)) {
      if (item !== undefined && item !== null && item !== "" && item !== false) {
        url.searchParams.append(key, item);
      }
    }
  }
  return url;
}

async function request(method, path, { query, body } = {}) {
  let response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером. Проверьте интернет и повторите.");
  }
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, describeError(response.status, payload));
  return payload;
}

function describeError(status, payload) {
  if (typeof payload.detail === "string") return payload.detail;
  if (status === 401) return "Откройте приложение из MAX, чтобы войти.";
  if (status === 422) return "Проверьте введённые данные.";
  return "Что-то пошло не так. Попробуйте ещё раз.";
}

export const api = {
  categories: () => request("GET", "/categories"),
  events: {
    list: (query) => request("GET", "/events", { query }),
    get: (id) => request("GET", `/events/${id}`),
    ticketClick: (id) => request("POST", `/events/${id}/ticket-click`),
  },
  me: {
    get: () => request("GET", "/me"),
    update: (body) => request("PATCH", "/me", { body }),
  },
  favorites: {
    list: () => request("GET", "/me/favorites"),
    add: (eventId) => request("PUT", `/me/favorites/${eventId}`),
    remove: (eventId) => request("DELETE", `/me/favorites/${eventId}`),
  },
  reminders: {
    list: () => request("GET", "/me/reminders"),
    set: (eventId, minutesBefore) =>
      request("POST", "/me/reminders", { body: { event_id: eventId, minutes_before: minutesBefore } }),
    remove: (eventId) => request("DELETE", `/me/reminders/${eventId}`),
  },
  assistant: {
    say: (body) => request("POST", "/assistant/messages", { body }),
    reset: () => request("POST", "/assistant/reset"),
  },
  polls: {
    list: () => request("GET", "/polls"),
    create: (eventIds, title) => request("POST", "/polls", { body: { event_ids: eventIds, title } }),
    get: (id) => request("GET", `/polls/${id}`),
    vote: (id, optionId) => request("POST", `/polls/${id}/votes`, { body: { option_id: optionId } }),
  },
};
