import assert from "node:assert/strict";
import { test } from "node:test";

import {
  addDays, dayKey, dayRange, formatDay, formatPrice, formatTime, formatWhen, plural,
} from "../js/format.js";

globalThis.APP_CONFIG = { timezone: "Europe/Moscow" };

// Вторник, 29 сентября 2026, 15:00 по Москве
const NOW = new Date("2026-09-29T12:00:00Z");

test("время и день считаются в часовом поясе города, а не устройства", () => {
  assert.equal(formatTime("2026-09-29T16:00:00Z"), "19:00");
  // 22:30 UTC — уже следующий день в Москве
  assert.equal(dayKey("2026-09-29T22:30:00Z"), "2026-09-30");
});

test("относительные подписи дней", () => {
  assert.equal(formatDay("2026-09-29T18:00:00Z", NOW), "сегодня");
  assert.equal(formatDay("2026-09-30T08:00:00Z", NOW), "завтра");
  assert.equal(formatDay("2026-10-03T16:00:00Z", NOW), "сб, 3 окт");
  assert.equal(formatWhen("2026-10-03T16:00:00Z", NOW), "сб, 3 окт, 19:00");
});

test("цена", () => {
  assert.equal(formatPrice({ is_free: true }), "Бесплатно");
  assert.equal(formatPrice({ is_free: false, price_min: 300, price_max: null }), "от 300 ₽");
  assert.equal(formatPrice({ is_free: false, price_min: 300, price_max: 900 }), "300–900 ₽");
  assert.equal(formatPrice({ is_free: false, price_min: 300, price_max: 300 }), "от 300 ₽");
});

test("склонение", () => {
  const forms = ["голос", "голоса", "голосов"];
  const result = [0, 1, 2, 5, 11, 12, 21, 22, 111].map((n) => plural(n, forms));
  assert.deepEqual(result, [
    "голосов", "голос", "голоса", "голосов", "голосов", "голосов", "голос", "голоса", "голосов",
  ]);
});

test("addDays переходит через границу месяца и года", () => {
  assert.equal(addDays("2026-09-30", 1), "2026-10-01");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
});

test("диапазон «сегодня»: до конца дня по Москве", () => {
  assert.deepEqual(dayRange("today", NOW), { to: "2026-09-29T20:59:59.999Z" });
});

test("диапазон «завтра»", () => {
  assert.deepEqual(dayRange("tomorrow", NOW), {
    from: "2026-09-29T21:00:00.000Z",
    to: "2026-09-30T20:59:59.999Z",
  });
});

test("диапазон «выходные» из вторника: суббота 00:00 — конец воскресенья", () => {
  assert.deepEqual(dayRange("weekend", NOW), {
    from: "2026-10-02T21:00:00.000Z",
    to: "2026-10-04T20:59:59.999Z",
  });
});

test("«выходные» в субботу начинаются сейчас, в воскресенье — только сегодня", () => {
  const saturday = new Date("2026-10-03T09:00:00Z");
  assert.deepEqual(dayRange("weekend", saturday), { from: undefined, to: "2026-10-04T20:59:59.999Z" });
  const sunday = new Date("2026-10-04T09:00:00Z");
  assert.deepEqual(dayRange("weekend", sunday), { to: "2026-10-04T20:59:59.999Z" });
});

test("«неделя» — семь дней включая сегодня", () => {
  assert.deepEqual(dayRange("week", NOW), { to: "2026-10-05T20:59:59.999Z" });
});

test("без пресета фильтр не ограничивает даты", () => {
  assert.deepEqual(dayRange("", NOW), {});
});

test("работает и в поясе с переводом часов", () => {
  globalThis.APP_CONFIG = { timezone: "Europe/Berlin" };
  // 2026-10-25 — ночь перехода на зимнее время; полночь 26 октября уже UTC+1
  const range = dayRange("tomorrow", new Date("2026-10-25T12:00:00Z"));
  assert.equal(range.from, "2026-10-25T23:00:00.000Z");
  globalThis.APP_CONFIG = { timezone: "Europe/Moscow" };
});
