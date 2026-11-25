// Shareable view state in the URL hash. No three.js or DOM here, so it is easy to test.
//
//   #cuban-missile-crisis-1962                      an item (the original link format, still read)
//   #e=cuban-missile-crisis-1962&t=1950.00,1990.00&v=2d&l=threads&h=cuba,ww1&s=even&k=1962.81&p=US%20government
//
// e: selected item · t: time window (decimal years) · v: view (2d, 3d, list) · l: lanes
// (threads, regions, domains) · h: hidden threads · s: time scale (compressed, even)
// · k: "knowable on" date (decimal year) · p: the party it is known to.
// Anything unknown or invalid is dropped, so an old or edited link still opens something sensible.

const VIEWS = new Set(["2d", "3d", "list"]);
const LANES = new Set(["threads", "regions", "domains"]);
const SCALES = new Set(["compressed", "even"]);

export function parseState(hash, { items = new Set(), threads = new Set(), parties = new Set(), limits = [-Infinity, Infinity] } = {}) {
  const raw = (hash || "").replace(/^#/, "");
  if (!raw) return {};
  if (!raw.includes("=")) {
    const id = safeDecode(raw);
    return items.has(id) ? { item: id } : {};
  }
  const q = new URLSearchParams(raw);
  const out = {};
  const item = q.get("e");
  if (item && items.has(item)) out.item = item;
  const t = (q.get("t") || "").split(",").map(Number);
  if (t.length === 2 && t.every(Number.isFinite) && t[0] < t[1]) {
    out.window = [Math.max(t[0], limits[0]), Math.min(t[1], limits[1])];
    if (!(out.window[0] < out.window[1])) delete out.window;
  }
  if (VIEWS.has(q.get("v"))) out.view = q.get("v");
  if (LANES.has(q.get("l"))) out.lanes = q.get("l");
  if (SCALES.has(q.get("s"))) out.scale = q.get("s");
  const hidden = (q.get("h") || "").split(",").filter((x) => threads.has(x));
  if (hidden.length) out.hidden = hidden;
  const k = Number(q.get("k"));
  if (q.has("k") && Number.isFinite(k)) {
    out.knowable = { t: Math.min(Math.max(k, limits[0]), limits[1]), party: parties.has(q.get("p")) ? q.get("p") : null };
  }
  return out;
}

export function formatState({ item = null, window = null, view = null, lanes = null, hidden = [], scale = null, knowable = null } = {},
  defaults = {}) {
  const q = new URLSearchParams();
  if (item) q.set("e", item);
  if (window) q.set("t", window.map((x) => x.toFixed(2)).join(","));
  if (view && view !== defaults.view) q.set("v", view);
  if (lanes && lanes !== defaults.lanes) q.set("l", lanes);
  if (hidden.length) q.set("h", [...hidden].sort().join(","));
  if (scale && scale !== defaults.scale) q.set("s", scale);
  if (knowable) {
    q.set("k", knowable.t.toFixed(4));
    if (knowable.party) q.set("p", knowable.party);
  }
  const s = q.toString();
  return s ? `#${s}` : "";
}

function safeDecode(s) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}
