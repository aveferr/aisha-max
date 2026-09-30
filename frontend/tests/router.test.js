import assert from "node:assert/strict";
import { test } from "node:test";

import { matchRoute, routeFromStartParam } from "../js/router.js";

test("корневые разделы", () => {
  assert.deepEqual(matchRoute(""), { name: "catalog", params: [], tab: "catalog", isRoot: true });
  assert.equal(matchRoute("#/").name, "catalog");
  assert.equal(matchRoute("#/assistant").tab, "assistant");
  assert.equal(matchRoute("#/favorites").isRoot, true);
});

test("вложенные экраны не считаются корневыми и подсвечивают свой раздел", () => {
  const event = matchRoute("#/event/12");
  assert.deepEqual([event.name, event.params, event.tab, event.isRoot], ["event", ["12"], "catalog", false]);
  assert.equal(matchRoute("#/poll/5").tab, "favorites");
});

test("неизвестные и некорректные адреса", () => {
  assert.equal(matchRoute("#/nope").name, "notfound");
  assert.equal(matchRoute("#/event/abc").name, "notfound");
  assert.equal(matchRoute("#/event/1/extra").name, "notfound");
});

test("параметр запуска из ссылки бота", () => {
  assert.equal(routeFromStartParam("catalog"), "#/");
  assert.equal(routeFromStartParam("event_7"), "#/event/7");
  assert.equal(routeFromStartParam("poll_3"), "#/poll/3");
  assert.equal(routeFromStartParam("poll_x"), null);
  assert.equal(routeFromStartParam(""), null);
  assert.equal(routeFromStartParam(null), null);
});
