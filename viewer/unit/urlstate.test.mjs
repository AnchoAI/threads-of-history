import { test } from "node:test";
import assert from "node:assert/strict";
import { formatState, parseState } from "../src/urlstate.js";

const ctx = { items: new Set(["a-1962", "b-1990"]), threads: new Set(["cuba", "ww1"]), parties: new Set(["US government"]), limits: [0, 2027] };

test("the old #item-id links still work", () => {
  assert.deepEqual(parseState("#a-1962", ctx), { item: "a-1962" });
  assert.deepEqual(parseState("#no-such-item", ctx), {});
});

test("state round-trips through the hash", () => {
  const s = { item: "a-1962", window: [1950, 1980], view: "3d", lanes: "regions", hidden: ["ww1", "cuba"], scale: "even",
              knowable: { t: 1962.81, party: "US government" } };
  const back = parseState(formatState(s, { view: "2d", lanes: "threads", scale: "compressed" }), ctx);
  assert.equal(back.item, "a-1962");
  assert.deepEqual(back.window, [1950, 1980]);
  assert.equal(back.view, "3d");
  assert.equal(back.lanes, "regions");
  assert.deepEqual(back.hidden, ["cuba", "ww1"]);
  assert.equal(back.scale, "even");
  assert.deepEqual(back.knowable, { t: 1962.81, party: "US government" });
});

test("invalid parts are dropped, the rest kept", () => {
  const back = parseState("#e=zzz&t=1990,1950&v=hologram&l=threads&h=cuba,nope&k=abc&p=KGB", ctx);
  assert.deepEqual(back, { lanes: "threads", hidden: ["cuba"] });
  assert.deepEqual(parseState("#t=-500,3000", ctx).window, [0, 2027]);
});

test("defaults are left out of the link", () => {
  assert.equal(formatState({ view: "2d", lanes: "threads", scale: "compressed" }, { view: "2d", lanes: "threads", scale: "compressed" }), "");
});
