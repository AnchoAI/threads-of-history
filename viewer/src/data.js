// Loading and indexing dist/graph.json. No three.js here, so this stays easy to test.

// Kinds drawn as nodes on the timeline. Actors appear in the side panel instead;
// series and scenarios get their own drawing later.
export const NODE_KINDS = new Set(["event", "signal", "decision"]);

export const LINK_TYPES = {
  led_to:    { label: "Led to",                        color: "#E6E1D6", out: "Led to",         in: "Came from" },
  revealed:  { label: "Revealed later (points back)",  color: "#FF7AD9", out: "Sheds light on", in: "Revealed by" },
  echo:      { label: "Echo / parallel",               color: "#8FD3FF", out: "Echoes",         in: "Echoed by" },
  signal_of: { label: "Signal of",                     color: "#F0D264", out: "Signal of",      in: "Signalled by" },
  part_of:   { label: "Part of",                       color: "#6FD08C", out: "Part of",        in: "Includes" },
};

export async function loadGraph(url = "graph.json") {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (HTTP ${res.status})`);
  return indexGraph(await res.json());
}

export function indexGraph(graph) {
  const byId = new Map(graph.items.map((it) => [it.id, it]));
  const nodes = graph.items.filter((it) => NODE_KINDS.has(it.kind) && it.occurred);
  const nodeIds = new Set(nodes.map((n) => n.id));
  const links = graph.links
    .filter((l) => nodeIds.has(l.from) && nodeIds.has(l.to))
    .map((l) => ({ ...l, a: byId.get(l.from), b: byId.get(l.to) }));
  const linksOf = new Map(nodes.map((n) => [n.id, []]));
  for (const l of links) {
    linksOf.get(l.from).push(l);
    linksOf.get(l.to).push(l);
  }
  const lanes = {
    threads: graph.threads,
    regions: graph.regions,
    domains: graph.domains.filter((d) => nodes.some((n) => n.domains.includes(d.id))),
  };
  const threadColor = Object.fromEntries(graph.threads.map((t) => [t.id, t.color || "#8A93A0"]));
  const reviewCounts = {};
  for (const it of [...graph.items, ...graph.links]) {
    const s = it.review?.status ?? "unverified";
    reviewCounts[s] = (reviewCounts[s] ?? 0) + 1;
  }
  return { graph, byId, nodes, links, linksOf, lanes, threadColor, paths: graph.paths, reviewCounts };
}

// Which lanes an item sits on for a given arrangement.
export function lanesOf(item, mode) {
  if (mode === "regions") return item.regions;
  if (mode === "domains") return item.domains;
  return item.threads;
}

// ---------------------------------------------------------------- display helpers

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];

function ordinal(n) {
  const teen = n % 100 >= 11 && n % 100 <= 13;
  return n + (teen ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[n % 10] ?? "th");
}

function formatDate(value, precision) {
  const neg = value.startsWith("-");
  const [datePart, time] = (neg ? value.slice(1) : value).split("T");
  const [y, m, d] = datePart.split("-").map(Number);
  const year = neg ? `${y} BCE` : String(y);
  if (precision === "century") return `${ordinal(Math.floor(y / 100) + 1)} century`;
  if (precision === "decade") return `${y - (y % 10)}s`;
  if (precision === "year" || !m) return year;
  if (precision === "month" || !d) return `${MONTHS[m - 1]} ${year}`;
  const day = `${d} ${MONTHS[m - 1]} ${year}`;
  return precision === "hour" && time ? `${day}, ${time}` : day;
}

export function formatSpan(span) {
  if (!span) return "";
  const start = formatDate(span.start, span.precision);
  let out = start;
  if (span.end && span.end !== span.start) out += ` – ${formatDate(span.end, span.precision)}`;
  else if (span.ongoing) out += " – present";
  return (span.approximate ? "c. " : "") + out;
}

export const yearLabel = (item) => item.occurred.start.replace(/^(-?\d{4}).*/, "$1");

// Item text comes from contributors, so it is always escaped before going into HTML.
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Only http(s) links are rendered as links.
export function safeUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
