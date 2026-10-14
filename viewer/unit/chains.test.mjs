// Unit tests for "why did this happen?" chains. Run: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import { indexGraph } from "../src/data.js";
import { trace, traceSpan } from "../src/chains.js";

// A → B → C → D (led_to), E part_of D, and a cycle back from D to B that must not loop.
const item = (id, y, known) => ({ id, kind: "event", title: id, summary: "", threads: ["t"], regions: ["r"], importance: 3,
  occurred: { start: String(y), precision: "year", range: [y, y + 1] },
  ...(known ? { known: { public: { start: String(known), precision: "year", range: [known, known + 1] } } } : {}) });
const link = (from, type, to, extra = {}) => ({ id: `${from}--${type}--${to}`, from, to, type, confidence: "documented", note: "", sources: [], ...extra });
const g = indexGraph({
  items: [item("a", 1054), item("b", 1517), item("c", 1648, 1900), item("d", 1998), item("e", 1999)],
  links: [link("a", "led_to", "b"), link("b", "led_to", "c", { confidence: "contested" }), link("c", "led_to", "d"),
          link("e", "part_of", "d"), link("d", "led_to", "b")],
  threads: [{ id: "t", name: "T", domain: "politics" }], regions: [{ id: "r", name: "R" }], domains: [], paths: [],
});

test("causes go back several steps, in order, and don't loop", () => {
  const t = trace(g, "d", "back");
  assert.deepEqual([...t.ids].sort(), ["a", "b", "c", "d"]);
  assert.equal(t.tree[0].item.id, "c");
  assert.equal(t.tree[0].children[0].item.id, "b");
  assert.equal(t.tree[0].children[0].contested, true);
  assert.equal(t.tree[0].children[0].children[0].item.id, "a");
});

test("a sub-event inherits its parent's causes", () => {
  const t = trace(g, "e", "back");
  assert.ok(t.ids.has("d") && t.ids.has("a"));
  assert.ok(t.links.has("e--part_of--d"));
});

test("effects go forward, depth is capped, and the knowable date hides later items", () => {
  assert.deepEqual([...trace(g, "a", "forward").ids].sort(), ["a", "b", "c", "d"]);
  assert.deepEqual([...trace(g, "a", "forward", { depth: 1 }).ids].sort(), ["a", "b"]);
  // c only became known in 1900, so in 1800 the chain stops at b.
  assert.deepEqual([...trace(g, "a", "forward", { knowable: { t: 1800, party: null } }).ids].sort(), ["a", "b"]);
  assert.deepEqual(traceSpan(g, new Set(["a", "d"])), [1054, 1999]);
});
