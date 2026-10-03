// Unit tests for the time window, ticks and importance-based visibility.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { indexGraph } from "../src/data.js";
import { TimeWindow, MIN_SPAN, WORLD_LENGTH, ticks, fromYear, toYear } from "../src/timescale.js";
import { chooseVisible, MAX_NODES, MAX_LABELS } from "../src/visibility.js";

const load = (path) => indexGraph(JSON.parse(readFileSync(new URL(path, import.meta.url))));
const real = load("../../dist/graph.json");
const stress = load("../tests/fixtures/stress-graph.json");

test("the window maps its span onto the full world length", () => {
  const w = new TimeWindow(1900, 2000);
  assert.equal(w.x(1900), -WORLD_LENGTH / 2);
  assert.equal(w.x(2000), WORLD_LENGTH / 2);
  assert.equal(w.x(1950), 0);
});

test("the window stays inside its limits and above the minimum span", () => {
  const w = new TimeWindow(1900, 2000);
  w.set(1850, 1860);
  assert.deepEqual([w.t0, w.t1], [1900, 1910]);
  w.set(1950, 1950);
  assert.ok(Math.abs(w.span - MIN_SPAN) < 1e-12);
  w.set(1800, 2100);
  assert.deepEqual([w.t0, w.t1], [1900, 2000]);
});

test("zooming keeps the point under the pointer fixed", () => {
  const w = new TimeWindow(1900, 2000);
  const before = w.x(1962);
  w.zoom(0.5, 1962);
  assert.ok(Math.abs(w.x(1962) - before) < 1e-9);
  assert.equal(w.span, 50);
});

test("ticks adapt from decades down to hours", () => {
  const labels = (t0, t1) => ticks(new TimeWindow(t0, t1, [1900, 2030])).map((t) => t.label);
  assert.ok(labels(1900, 2030).includes("1960"));
  const month = labels(1962.7, 1963.0);
  assert.ok(month.some((l) => /^Oct 1962$/.test(l)), month.join(","));
  const day = labels(toYear(new Date(Date.UTC(1962, 9, 14))), toYear(new Date(Date.UTC(1962, 9, 28))));
  assert.ok(day.some((l) => /^\d+ Oct 1962$/.test(l)), day.join(","));
  const hour = labels(toYear(new Date(Date.UTC(1962, 9, 22, 0))), toYear(new Date(Date.UTC(1962, 9, 22, 12))));
  assert.ok(hour.some((l) => /22 Oct \d\d:00/.test(l)), hour.join(","));
  for (const [a, b] of [[1900, 2030], [1962.7, 1963], [1962.8, 1962.81]]) {
    const n = ticks(new TimeWindow(a, b, [1900, 2030])).length;
    assert.ok(n >= 3 && n <= 16, `${n} ticks for ${a}-${b}`);
  }
});

test("year fractions and dates convert both ways", () => {
  const d = new Date(Date.UTC(1962, 9, 22, 19));
  assert.equal(fromYear(toYear(d)).getTime(), d.getTime());
});

test("zoomed out, only the most important items are drawn and labelled", () => {
  const w = new TimeWindow(1900, 2030);
  const { visible, labelled, candidates } = chooseVisible(stress, w);
  assert.ok(candidates > MAX_NODES);
  assert.equal(visible.size, MAX_NODES);
  assert.equal(labelled.size, MAX_LABELS);
  const minShown = Math.min(...[...visible].map((id) => stress.byId.get(id).importance));
  const maxHidden = Math.max(...stress.nodes.filter((n) => !visible.has(n.id) && !n.id.startsWith("test-crisis-"))
    .map((n) => n.importance));
  assert.ok(minShown >= maxHidden - 1, "hidden items are never much more important than shown ones");
});

test("the selection and its connections are always drawn", () => {
  const w = new TimeWindow(1900, 2030);
  const low = stress.nodes.find((n) => n.importance === 1 && stress.linksOf.get(n.id).length > 0);
  const { visible, labelled } = chooseVisible(stress, w, { selected: low.id });
  assert.ok(visible.has(low.id) && labelled.has(low.id));
  for (const l of stress.linksOf.get(low.id)) assert.ok(visible.has(l.from === low.id ? l.to : l.from));
});

test("sub-events appear only when zoomed in on their parent", () => {
  const parts = stress.nodes.filter((n) => n.id.startsWith("test-crisis-day-")).map((n) => n.id);
  const out = chooseVisible(stress, new TimeWindow(1900, 2030)).visible;
  assert.ok(parts.every((id) => !out.has(id)));
  const zoomed = chooseVisible(stress, new TimeWindow(1962.7, 1963.0, [1900, 2030])).visible;
  assert.ok(parts.every((id) => zoomed.has(id)));
});

test("items outside the window and on hidden threads are not drawn", () => {
  const w = new TimeWindow(1960, 1970, [1900, 2030]);
  const { visible } = chooseVisible(real, w, { hiddenThreads: new Set(["cuba"]) });
  for (const id of visible) {
    const n = real.byId.get(id);
    assert.ok(n.occurred.range[0] <= 1970 && (n.occurred.range[1] ?? 1970) >= 1960);
    assert.ok(n.threads.some((t) => t !== "cuba"));
  }
  assert.ok(!visible.has("bay-of-pigs-invasion-1961") || real.byId.get("bay-of-pigs-invasion-1961").threads.some((t) => t !== "cuba"));
});

test("a sub-event at least as important as its parent is never folded away", () => {
  const parent = stress.byId.get("test-crisis");
  const part = stress.byId.get("test-crisis-day-1");
  const w = new TimeWindow(1900, 2030);
  const saved = part.importance;
  try {
    part.importance = parent.importance;
    assert.ok(chooseVisible(stress, w).visible.has(part.id));
    part.importance = parent.importance - 1;
    assert.ok(!chooseVisible(stress, w).visible.has(part.id));
  } finally {
    part.importance = saved;
  }
});
