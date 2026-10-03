// Lane layout: which lanes exist, in what order, and at what angle around the spine.
// Pure functions, no three.js, so the rules are easy to test.
//
// Rules:
// - In thread mode each domain gets its own slice of the circle, with its threads inside it.
//   An item on threads from different domains sits between the slices, nearer the spine,
//   which then means "crosses domains".
// - When there are more threads than fit (maxLanes), domains collapse into one lane each.
//   Expanding a domain shows its threads; the others stay collapsed.
// - Within a group, lanes are ordered so that lanes sharing many items and links sit next
//   to each other. Averaging an item's lanes then puts it somewhere meaningful.

export const MAX_LANES = 16;
const GROUP_GAP = 0.6;  // empty slots between domain slices

// How strongly two lanes are related: items on both, plus links between them.
function affinity(items, links, lanesOfItem) {
  const w = new Map();
  const add = (a, b, n) => {
    if (a === b) return;
    const k = a < b ? `${a}|${b}` : `${b}|${a}`;
    w.set(k, (w.get(k) ?? 0) + n);
  };
  for (const it of items) {
    const ls = lanesOfItem(it);
    for (let i = 0; i < ls.length; i++) for (let j = i + 1; j < ls.length; j++) add(ls[i], ls[j], 2);
  }
  for (const l of links) {
    for (const a of lanesOfItem(l.a)) for (const b of lanesOfItem(l.b)) add(a, b, 1);
  }
  return (a, b) => w.get(a < b ? `${a}|${b}` : `${b}|${a}`) ?? 0;
}

// Greedy chain: start from the busiest lane, then keep appending the lane most related to
// the current end. Ties keep the curated order, so small datasets look as authored.
export function orderLanes(ids, weight, count) {
  const left = [...ids];
  if (left.length < 3) return left;
  left.sort((a, b) => count(b) - count(a) || ids.indexOf(a) - ids.indexOf(b));
  const out = [left.shift()];
  while (left.length) {
    const end = out[out.length - 1];
    let best = 0;
    for (let i = 1; i < left.length; i++) {
      const d = weight(end, left[i]) - weight(end, left[best]);
      if (d > 0 || (d === 0 && ids.indexOf(left[i]) < ids.indexOf(left[best]))) best = i;
    }
    out.push(left.splice(best, 1)[0]);
  }
  return out;
}

/**
 * Compute the lanes for a view.
 * @param data     indexed graph from data.js
 * @param mode     "threads" | "regions" | "domains"
 * @param expanded Set of domain ids to show as threads (thread mode, when collapsing)
 * @returns { lanes: [{id, name, color, angle, kind, domain?, threads?}], lanesOf(item), collapsed }
 */
export function computeLanes(data, mode, expanded = new Set(), maxLanes = MAX_LANES) {
  const items = data.nodes;
  const threadById = Object.fromEntries(data.graph.threads.map((t) => [t.id, t]));
  const usedThreads = data.graph.threads.filter((t) => items.some((n) => n.threads.includes(t.id)));
  const domainName = Object.fromEntries(data.graph.domains.map((d) => [d.id, d.name]));

  if (mode === "regions" || mode === "domains") {
    const vocab = mode === "regions" ? data.graph.regions : data.graph.domains;
    const key = mode === "regions" ? "regions" : "domains";
    const ids = vocab.map((v) => v.id).filter((id) => items.some((n) => n[key].includes(id)));
    const lanesOfItem = (it) => it[key].filter((id) => ids.includes(id));
    const w = affinity(items, data.links, lanesOfItem);
    const count = (id) => items.filter((n) => n[key].includes(id)).length;
    const ordered = orderLanes(ids, w, count);
    const name = Object.fromEntries(vocab.map((v) => [v.id, v.name]));
    const lanes = place([ordered]).map(({ id, angle }) => ({
      id, angle, name: name[id], kind: mode === "regions" ? "region" : "domain", color: null,
    }));
    return { lanes, lanesOf: lanesOfItem, collapsed: false };
  }

  // Thread mode, grouped by domain.
  const domainIds = data.graph.domains.map((d) => d.id)
    .filter((d) => usedThreads.some((t) => t.domain === d));
  const collapsed = usedThreads.length > maxLanes;
  const isOpen = (d) => !collapsed || expanded.has(d);
  const laneFor = (threadId) => {
    const d = threadById[threadId]?.domain;
    return isOpen(d) ? threadId : `domain:${d}`;
  };
  const lanesOfItem = (it) => [...new Set(it.threads.filter((t) => threadById[t]).map(laneFor))];
  const w = affinity(items, data.links, lanesOfItem);
  const count = (id) => items.filter((n) => lanesOfItem(n).includes(id)).length;

  const groups = domainIds.map((d) => {
    if (!isOpen(d)) return [`domain:${d}`];
    const ids = usedThreads.filter((t) => t.domain === d).map((t) => t.id);
    return orderLanes(ids, w, count);
  });
  const lanes = place(groups).map(({ id, angle }) => {
    if (id.startsWith("domain:")) {
      const d = id.slice(7);
      const threads = usedThreads.filter((t) => t.domain === d).map((t) => t.id);
      return { id, angle, kind: "domain", domain: d, threads, color: null,
               name: `${domainName[d] ?? d} · ${threads.length} thread${threads.length === 1 ? "" : "s"}` };
    }
    const t = threadById[id];
    return { id, angle, kind: "thread", domain: t.domain, name: t.name, color: t.color ?? null };
  });
  return { lanes, lanesOf: lanesOfItem, collapsed };
}

// Spread groups around the circle, one slot per lane plus a gap between groups.
function place(groups) {
  const gap = groups.length > 1 ? GROUP_GAP : 0;
  const slots = groups.reduce((n, g) => n + g.length + gap, 0);
  const unit = (Math.PI * 2) / slots;
  const out = [];
  let slot = gap / 2;
  for (const g of groups) {
    for (const id of g) {
      out.push({ id, angle: Math.PI / 2 + (slot + 0.5) * unit });
      slot += 1;
    }
    slot += gap;
  }
  return out;
}
