// Generates stress-graph.json: a FAKE graph with many threads, for testing the viewer's layout
// at scale. Nothing in it is history. Run: node tests/fixtures/make-stress-graph.mjs
// Open it in the viewer with ?graph=tests/fixtures/stress-graph.json (dev server only).
import { writeFileSync } from "node:fs";

let seed = 42;
const rand = () => ((seed = (seed * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32);
const pick = (xs) => xs[Math.floor(rand() * xs.length)];

const DOMAINS = [
  ["politics", "Politics & conflict", 12], ["economy", "Economy & resources", 8],
  ["society", "Society & migration", 7], ["science", "Science & technology", 5],
  ["culture", "Culture & media", 5], ["sports", "Sports", 3],
];
const REGIONS = [["americas", "Americas"], ["western-europe", "Western Europe"],
  ["russia-eastern-europe", "Russia & Eastern Europe"], ["middle-east-north-africa", "Middle East & N. Africa"],
  ["south-central-asia", "South & Central Asia"], ["east-asia", "East Asia"], ["africa", "Sub-Saharan Africa"]];

const threads = [];
DOMAINS.forEach(([d, , n], di) => {
  for (let i = 0; i < n; i++) {
    const hue = (di * 60 + i * (50 / n)) % 360;
    threads.push({ id: `${d}-thread-${i + 1}`, name: `Test ${d} thread ${i + 1}`, domain: d,
                   color: hslHex(hue, 55, 62) });
  }
});
const byDomain = Object.fromEntries(DOMAINS.map(([d]) => [d, threads.filter((t) => t.domain === d)]));

const items = [];
for (let i = 0; i < 400; i++) {
  const year = 1900 + Math.floor(rand() * 126);
  const month = 1 + Math.floor(rand() * 12);
  const start = `${year}-${String(month).padStart(2, "0")}`;
  const home = pick(DOMAINS)[0];
  const ts = new Set([pick(byDomain[home]).id]);
  if (rand() < 0.5) ts.add(pick(byDomain[rand() < 0.7 ? home : pick(DOMAINS)[0]]).id);
  const tList = [...ts];
  const range = [year + (month - 1) / 12, year + month / 12];
  items.push({
    kind: rand() < 0.1 ? "signal" : "event",
    id: `test-event-${i + 1}`, title: `Test event ${i + 1} (fake)`,
    summary: "Generated test data for the viewer's layout. Not a real event.",
    occurred: { start, precision: "month", range },
    known: { public: { start, precision: "month", range } },
    threads: tList, regions: [pick(REGIONS)[0]],
    domains: [...new Set(tList.map((t) => threads.find((x) => x.id === t).domain))].sort(),
    importance: 1 + Math.floor(rand() * 5), sources: [],
    review: { status: "unverified", notes: ["Fake test data."] },
  });
}
// One parent event with day-level parts, for testing that zooming opens events into sub-events.
const dayRange = (m, d) => {
  const doy = Math.round((Date.UTC(1962, m - 1, d) - Date.UTC(1962, 0, 1)) / 86400000);
  return [1962 + doy / 365, 1962 + (doy + 1) / 365];
};
const crisisThreads = [byDomain.politics[0].id];
items.push({
  kind: "event", id: "test-crisis", title: "Test crisis (fake)",
  summary: "Generated parent event with day-level parts. Not a real event.",
  occurred: { start: "1962-10", end: "1962-11", precision: "month", range: [1962 + 9 / 12, 1962 + 11 / 12] },
  known: { public: { start: "1962-10", precision: "month", range: [1962 + 9 / 12, 1962 + 10 / 12] } },
  threads: crisisThreads, regions: ["americas"], domains: ["politics"], importance: 5, sources: [],
  review: { status: "unverified", notes: ["Fake test data."] },
});
const parts = [];
for (let d = 0; d < 6; d++) {
  const day = 14 + d * 2;
  const start = `1962-10-${day}`;
  parts.push({
    kind: "event", id: `test-crisis-day-${d + 1}`, title: `Test crisis, day ${day} (fake)`,
    summary: "Generated sub-event. Not a real event.",
    occurred: { start, precision: "day", range: dayRange(10, day) },
    known: { public: { start, precision: "day", range: dayRange(10, day) } },
    threads: crisisThreads, regions: ["americas"], domains: ["politics"], importance: 2, sources: [],
    review: { status: "unverified", notes: ["Fake test data."] },
  });
}
items.push(...parts);
items.sort((a, b) => a.occurred.range[0] - b.occurred.range[0]);

const links = [];
const seen = new Set();
while (links.length < 500) {
  const a = pick(items), b = pick(items);
  if (a === b || a.occurred.range[0] > b.occurred.range[0]) continue;
  const share = a.threads.some((t) => b.threads.includes(t)) || a.domains.some((d) => b.domains.includes(d));
  if (!share && rand() < 0.8) continue;  // most links stay within a domain, as in real data
  const type = rand() < 0.8 ? "led_to" : "echo";
  const id = `${a.id}--${type}--${b.id}`;
  if (seen.has(id)) continue;
  seen.add(id);
  links.push({ id, from: a.id, to: b.id, type, confidence: rand() < 0.1 ? "contested" : "documented",
               note: "Fake test link.", sources: [], review: { status: "unverified" } });
}

for (const p of parts) {
  links.push({ id: `${p.id}--part_of--test-crisis`, from: p.id, to: "test-crisis", type: "part_of",
               confidence: "documented", note: "Fake test link.", sources: [], review: { status: "unverified" } });
}

const graph = {
  format_version: 1,
  domains: DOMAINS.map(([id, name]) => ({ id, name })),
  threads, regions: REGIONS.map(([id, name]) => ({ id, name })),
  items, links,
  paths: [{ id: "test-path", title: "Test path", steps: items.slice(0, 6).map((i) => i.id) }],
  datasets: [], stats: {},
};
writeFileSync(new URL("./stress-graph.json", import.meta.url), JSON.stringify(graph) + "\n");
console.log(`stress-graph.json: ${threads.length} threads, ${items.length} items, ${links.length} links`);

function hslHex(h, s, l) {
  s /= 100; l /= 100;
  const f = (n) => {
    const k = (n + h / 30) % 12;
    const c = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(c * 255).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}
