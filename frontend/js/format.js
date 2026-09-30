// Форматирование дат и цен. Чистые функции без обращения к DOM — покрыты тестами (tests/).

const timeZone = () => globalThis.APP_CONFIG?.timezone ?? "Europe/Moscow";

const part = (iso, options) =>
  new Intl.DateTimeFormat("ru-RU", { timeZone: timeZone(), ...options })
    .format(new Date(iso))
    .replace(/\.$/, "");

/** Ключ дня «ГГГГ-ММ-ДД» в часовом поясе города. */
export const dayKey = (iso) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: timeZone() }).format(new Date(iso));

export const formatTime = (iso) => part(iso, { hour: "2-digit", minute: "2-digit", hour12: false });

export function dayParts(iso) {
  return {
    day: part(iso, { day: "numeric" }),
    month: part(iso, { month: "short" }),
    weekday: part(iso, { weekday: "short" }),
  };
}

export function formatDayLong(iso) {
  return part(iso, { weekday: "long", day: "numeric", month: "long" });
}

/** «сегодня» / «завтра» / «сб, 3 окт» */
export function formatDay(iso, now = new Date()) {
  const key = dayKey(iso);
  const today = dayKey(now.toISOString());
  if (key === today) return "сегодня";
  if (key === addDays(today, 1)) return "завтра";
  const { weekday, day, month } = dayParts(iso);
  return `${weekday}, ${day} ${month}`;
}

export const formatWhen = (iso, now = new Date()) => `${formatDay(iso, now)}, ${formatTime(iso)}`;

export function formatPrice(event) {
  if (event.is_free) return "Бесплатно";
  if (event.price_max && event.price_max !== event.price_min) {
    return `${event.price_min}–${event.price_max} ₽`;
  }
  return `от ${event.price_min} ₽`;
}

export function plural(n, [one, few, many]) {
  const tail = n % 100;
  if (tail >= 11 && tail <= 14) return many;
  const last = n % 10;
  if (last === 1) return one;
  return last >= 2 && last <= 4 ? few : many;
}

// --- Диапазоны дат для фильтра каталога -----------------------------------------------------

export function addDays(key, days) {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

const weekdayOf = (key) => new Date(`${key}T00:00:00Z`).getUTCDay(); // 0 — воскресенье

function offsetMinutes(date) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone(),
      hourCycle: "h23",
      year: "numeric", month: "numeric", day: "numeric",
      hour: "numeric", minute: "numeric", second: "numeric",
    })
      .formatToParts(date)
      .map(({ type, value }) => [type, Number(value)]),
  );
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
  return Math.round((asUtc - Math.floor(date.getTime() / 1000) * 1000) / 60000);
}

/** Момент 00:00 указанного дня в часовом поясе города. */
function startOfDay(key) {
  const guess = new Date(`${key}T00:00:00Z`);
  return new Date(guess.getTime() - offsetMinutes(guess) * 60000);
}

const endOfDay = (key) => new Date(startOfDay(addDays(key, 1)).getTime() - 1);

/**
 * Пресет фильтра → {from, to} в ISO. Без from сервер берёт «сейчас», так что уже
 * начавшиеся события не попадают в выдачу.
 */
export function dayRange(preset, now = new Date()) {
  const today = dayKey(now.toISOString());
  const iso = (date) => date?.toISOString();
  switch (preset) {
    case "today":
      return { to: iso(endOfDay(today)) };
    case "tomorrow": {
      const tomorrow = addDays(today, 1);
      return { from: iso(startOfDay(tomorrow)), to: iso(endOfDay(tomorrow)) };
    }
    case "weekend": {
      const dow = weekdayOf(today);
      if (dow === 0) return { to: iso(endOfDay(today)) }; // воскресенье — только сегодня
      const saturday = addDays(today, 6 - dow);
      return {
        from: dow === 6 ? undefined : iso(startOfDay(saturday)),
        to: iso(endOfDay(addDays(saturday, 1))),
      };
    }
    case "week":
      return { to: iso(endOfDay(addDays(today, 6))) };
    default:
      return {};
  }
}
