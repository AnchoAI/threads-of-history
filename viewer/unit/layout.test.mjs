// Unit tests for the lane layout. Run: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { indexGraph } from "../src/data.js";
import { computeLanes, orderLanes, MAX_LANES } from "../src/layout.js";

const load = (path) => indexGraph(JSON.parse(readFileSync(new URL(path, import.meta.url))));
const real = load("../../dist/graph.json");
const stress = load("../tests/fixtures/stress-graph.json");

// Lanes of one domain should form one unbroken run around the circle.
function contiguous(lanes) {
  const runs = lanes.map((l) => l.domain).filter((d, i, a) => i === 0 || d !== a[i - 1]);
  return new Set(runs).size === runs.length;
}

test("few threads: every thread gets its own lane, grouped by domain", () => {
  const { lanes, collapsed } = computeLanes(real, "threads");
  assert.equal(collapsed, false);
  assert.ok(lanes.every((l) => l.kind === "thread"));
  assert.equal(lanes.length, new Set(real.nodes.flatMap((n) => n.threads)).size);
  assert.ok(contiguous(lanes));
});

test("many threads: domains collapse to one lane each", () => {
  const { lanes, collapsed, lanesOf } = computeLanes(stress, "threads");
  assert.equal(collapsed, true);
  assert.equal(lanes.length, 6);
  assert.ok(lanes.every((l) => l.kind === "domain" && l.name.includes("thread")));
  const item = stress.nodes[0];
  assert.deepEqual(new Set(lanesOf(item)), new Set(item.domains.map((d) => `domain:${d}`)));
});

test("opening a domain shows its threads and keeps the others collapsed", () => {
  const { lanes } = computeLanes(stress, "threads", new Set(["economy"]));
  const open = lanes.filter((l) => l.kind === "thread");
  assert.equal(open.length, 8);
  assert.ok(open.every((l) => l.domain === "economy"));
  assert.equal(lanes.filter((l) => l.kind === "domain").length, 5);
  assert.ok(contiguous(lanes));
  assert.ok(lanes.length <= MAX_LANES + 1);
});

test("lanes get distinct angles around the full circle", () => {
  for (const [data, mode] of [[real, "threads"], [real, "regions"], [stress, "domains"]]) {
    const angles = computeLanes(data, mode).lanes.map((l) => l.angle);
    assert.equal(new Set(angles.map((a) => a.toFixed(6))).size, angles.length);
    assert.ok(Math.max(...angles) - Math.min(...angles) < Math.PI * 2);
  }
});

test("related lanes are placed next to each other", () => {
  const ids = ["a", "b", "c", "d"];
  const pairs = { "a|c": 10, "b|d": 10, "a|b": 1 };
  const weight = (x, y) => pairs[[x, y].sort().join("|")] ?? 0;
  const order = orderLanes(ids, weight, () => 1);
  const pos = Object.fromEntries(order.map((id, i) => [id, i]));
  assert.equal(Math.abs(pos.a - pos.c), 1);
  assert.equal(Math.abs(pos.b - pos.d), 1);
});
