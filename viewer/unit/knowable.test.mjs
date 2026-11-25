// Unit tests for "knowable on": what was known by a date, to the public or to one party.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { indexGraph } from "../src/data.js";
import { TimeWindow } from "../src/timescale.js";
import { chooseVisible, isKnown, knownParties, knownSince } from "../src/visibility.js";

const real = indexGraph(JSON.parse(readFileSync(new URL("../../dist/graph.json", import.meta.url))));

// A tiny made-up graph: a secret event the government knew about before the public did.
const span = (a, b) => ({ start: String(a), precision: "year", range: [a, b] });
const item = (id, occurred, known, extra = {}) => ({
  kind: "event", id, title: id, summary: "", occurred, known, threads: ["t"], regions: ["r"], domains: ["d"],
  importance: 3, sources: [], review: { status: "unverified" }, ...extra,
});
const tiny = indexGraph({
  domains: [{ id: "d", name: "D" }], threads: [{ id: "t", name: "T", domain: "d" }], regions: [{ id: "r", name: "R" }],
  items: [
    item("secret", span(2000, 2001), {
      public: span(2010, 2011),
      by: [{ party: "Government", when: span(2002, 2003) }],
    }),
    item("open", span(2005, 2006), { public: span(2005, 2006) }),
  ],
  links: [{ id: "secret--led_to--open", from: "secret", to: "open", type: "led_to", confidence: "documented", note: "",
            sources: [], review: { status: "unverified" } }],
  paths: [],
});

test("an item is known from its public date, or earlier to a party that knew first", () => {
  const secret = tiny.byId.get("secret");
  assert.equal(knownSince(secret), 2010);
  assert.equal(knownSince(secret, "Government"), 2002);
  assert.equal(knownSince(secret, "Someone else"), 2010);
  assert.equal(isKnown(secret, { t: 2005, party: null }), false);
  assert.equal(isKnown(secret, { t: 2005, party: "Government" }), true);
  assert.equal(isKnown(secret, null), true);
  assert.deepEqual(knownParties(tiny), ["Government"]);
});

test("a secret agreement stays hidden until it was published", () => {
  // Sykes–Picot: signed May 1916, published November 1917 (both still unverified in the data).
  const w = new TimeWindow(1910, 1925, [1900, 2030]);
  const at = (t) => chooseVisible(real, w, { knowable: { t, party: null } }).visible.has("sykes-picot-agreement-1916");
  assert.equal(at(1917.0), false);
  assert.equal(at(1918.0), true);
  assert.equal(chooseVisible(real, w).visible.has("sykes-picot-agreement-1916"), true);
});

test("hindsight does not leak through the selection or its connections", () => {
  const w = new TimeWindow(2000, 2015, [2000, 2015]);
  // Selecting "open" in 2006: its cause "secret" was not public yet, so it stays hidden.
  const pub = chooseVisible(tiny, w, { selected: "open", knowable: { t: 2006, party: null } });
  assert.deepEqual([...pub.visible], ["open"]);
  // The government did know by then.
  const gov = chooseVisible(tiny, w, { selected: "open", knowable: { t: 2006, party: "Government" } });
  assert.deepEqual(new Set(gov.visible), new Set(["open", "secret"]));
  // A selection that was not known yet is not drawn either.
  const early = chooseVisible(tiny, w, { selected: "secret", knowable: { t: 2004, party: null } });
  assert.equal(early.visible.has("secret"), false);
});

test("nothing that happened after the date is shown", () => {
  const w = new TimeWindow(1900, 2030, [1900, 2030]);
  const { visible } = chooseVisible(real, w, { knowable: { t: 1962.0, party: null } });
  assert.ok(visible.size > 0);
  for (const id of visible) assert.ok(knownSince(real.byId.get(id)) <= 1962.0, id);
});
