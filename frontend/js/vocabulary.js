// Справочники интерфейса. Слаги категорий и тегов совпадают с backend/app/assistant/vocabulary.py.

export const TAG_TITLES = {
  calm: "спокойное",
  active: "активное",
  romantic: "романтичное",
  unusual: "необычное",
  educational: "познавательное",
  outdoor: "на открытом воздухе",
  company: "для компании",
  family: "для всей семьи",
};

export const WHEN_OPTIONS = [
  { value: "", label: "Любая дата" },
  { value: "today", label: "Сегодня" },
  { value: "tomorrow", label: "Завтра" },
  { value: "weekend", label: "Выходные" },
  { value: "week", label: "Ближайшая неделя" },
];

export const REMINDER_OPTIONS = [
  { minutes: 30, label: "За 30 минут" },
  { minutes: 120, label: "За 2 часа" },
  { minutes: 1440, label: "За сутки" },
];

export const DEFAULT_REMINDER_MINUTES = 120;
export const POLL_MIN_OPTIONS = 2;
export const POLL_MAX_OPTIONS = 5;
