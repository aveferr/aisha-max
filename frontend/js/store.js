// Общее состояние, которое нужно нескольким экранам: справочники, профиль, избранное, напоминания.
// Источник правды — сервер; здесь только кэш, чтобы отметки в списках совпадали между экранами.

import { api } from "./api.js";

export const store = {
  categories: [],
  user: null,
  favoriteIds: new Set(),
  reminders: new Map(), // id события → ISO время напоминания
};

export async function bootstrap() {
  const [categories, user, favorites, reminders] = await Promise.all([
    api.categories(),
    api.me.get(),
    api.favorites.list(),
    api.reminders.list(),
  ]);
  store.categories = categories;
  store.user = user;
  store.favoriteIds = new Set(favorites.map((event) => event.id));
  store.reminders = new Map(reminders.map((r) => [r.event.id, r.remind_at]));
}

export const isFavorite = (eventId) => store.favoriteIds.has(eventId);

/** Переключает избранное и возвращает новое состояние. */
export async function toggleFavorite(eventId) {
  if (isFavorite(eventId)) {
    await api.favorites.remove(eventId);
    store.favoriteIds.delete(eventId);
    return false;
  }
  await api.favorites.add(eventId);
  store.favoriteIds.add(eventId);
  return true;
}

export async function setReminder(eventId, minutesBefore) {
  const reminder = await api.reminders.set(eventId, minutesBefore);
  store.reminders.set(eventId, reminder.remind_at);
  return reminder;
}

export async function clearReminder(eventId) {
  await api.reminders.remove(eventId);
  store.reminders.delete(eventId);
}
