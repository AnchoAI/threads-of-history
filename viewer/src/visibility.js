// Which items to draw for a time window, and which of them get labels.
// Pure functions, no three.js.
//
// Rules:
// - An item is a candidate if its time span overlaps the window and one of its threads is shown.
// - A sub-event (the `from` of a part_of link) only appears once its parent fills at least a
//   quarter of the window, so zooming in opens events into their parts. A sub-event at least
//   as important as its parent is never folded away (e.g. an invasion that ends a buildup).
// - Of the candidates, the most important are drawn (importance first, then number of links),
//   up to maxNodes. The selected item, its connections and pinned items (e.g. the current step
//   of a guided path) are always drawn if they are in the window.
// - Only the top maxLabels get labels, plus the selected item and its connections.
// - With a "knowable on" date, only items that were known by then are candidates at all:
//   known to the public, or to a chosen party (e.g. "US government") if that came first.
//   This applies even to the selection and its connections, so nothing leaks from hindsight.

export const MAX_NODES = 120;
export const MAX_LABELS = 30;
const PART_SHARE = 0.25;

export function span(item) {
  const [a, b] = item.occurred.range;
  return [a, b ?? Infinity];
}

export function inWindow(item, win) {
  const [a, b] = span(item);
  return a <= win.t1 && b >= win.t0;
}

// parent id for each sub-event
export function parents(data) {
  const out = new Map();
  for (const l of data.links) if (l.type === "part_of") out.set(l.from, l.to);
  return out;
}

// The earliest time an item was known: to the public, or to `party` if given and earlier.
export function knownSince(item, party = null) {
  let t = (item.known?.public ?? item.occurred).range[0];
  if (party) {
    for (const k of item.known?.by ?? []) if (k.party === party) t = Math.min(t, k.when.range[0]);
  }
  return t;
}

// knowable: null, or { t: decimal year, party: string | null }
export function isKnown(item, knowable) {
  return !knowable || knownSince(item, knowable.party) <= knowable.t;
}

// Every party named in known.by, for the "known to" picker.
export function knownParties(data) {
  return [...new Set(data.nodes.flatMap((n) => (n.known?.by ?? []).map((k) => k.party)))].sort();
}

export function score(item, data) {
  return (item.importance ?? 3) * 100 + Math.min(data.linksOf.get(item.id)?.length ?? 0, 99);
}

export function chooseVisible(data, win, {
  hiddenThreads = new Set(), selected = null, pinned = [], maxNodes = MAX_NODES, maxLabels = MAX_LABELS,
  parentOf = parents(data), knowable = null,
} = {}) {
  const known = (id) => isKnown(data.byId.get(id), knowable);
  const neighbours = new Set();
  if (selected) {
    for (const l of data.linksOf.get(selected) ?? []) neighbours.add(l.from === selected ? l.to : l.from);
  }
  const forced = new Set([selected, ...pinned, ...neighbours].filter((id) => id && known(id)));

  const partOpen = (item) => {
    const p = parentOf.get(item.id);
    if (!p || forced.has(item.id) || p === selected) return true;
    const parent = data.byId.get(p);
    if ((item.importance ?? 3) >= (parent.importance ?? 3)) return true;
    const [a, b] = span(parent);
    return (Math.min(b, win.t1) - Math.max(a, win.t0)) >= PART_SHARE * win.span || (b - a) >= PART_SHARE * win.span;
  };

  const candidates = data.nodes.filter((n) =>
    inWindow(n, win) && n.threads.some((t) => !hiddenThreads.has(t)) && partOpen(n) && isKnown(n, knowable));
  const ranked = candidates.sort((a, b) => score(b, data) - score(a, data) || a.id.localeCompare(b.id));

  const visible = new Set();
  for (const n of ranked) if (forced.has(n.id)) visible.add(n.id);
  for (const n of ranked) {
    if (visible.size >= Math.max(maxNodes, forced.size)) break;
    visible.add(n.id);
  }

  const labelled = new Set([...forced].filter((id) => visible.has(id)));
  for (const n of ranked) {
    if (labelled.size >= maxLabels + forced.size) break;
    if (visible.has(n.id)) labelled.add(n.id);
  }
  return { visible, labelled, candidates: candidates.length };
}
