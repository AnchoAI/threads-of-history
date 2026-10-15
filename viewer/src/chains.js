// "Why did this happen?" and "What did it lead to?": follow led_to links from an item,
// backward to its causes or forward to its effects, a few steps deep. Pure functions.
//
// A sub-event shares its parent's causes and effects, so the trace also starts from the
// events an item is part_of. Each item appears once; a second route to it is not expanded
// again. With a "knowable on" date, items not yet known are left out.
import { isKnown } from "./visibility.js";

export const TRACE_DEPTH = 4;
const MAX_ITEMS = 40;

// Returns { tree, ids, links }:
//   tree   [{ item, link, contested, children }] in date order
//   ids    every item in the trace, including the start
//   links  every link id used
export function trace(data, id, dir = "back", { depth = TRACE_DEPTH, knowable = null } = {}) {
  const start = data.byId.get(id);
  const ids = new Set([id]);
  const links = new Set();
  if (!start) return { tree: [], ids, links };

  const step = (itemId) => (data.linksOf.get(itemId) ?? []).filter((l) =>
    l.type === "led_to" && (dir === "back" ? l.to === itemId : l.from === itemId));
  const next = (l) => data.byId.get(dir === "back" ? l.from : l.to);

  // Start from the item and the larger events it is part of.
  const roots = [id];
  for (let cur = id, guard = 0; guard < 6; guard++) {
    const up = (data.linksOf.get(cur) ?? []).find((l) => l.type === "part_of" && l.from === cur);
    if (!up) break;
    roots.push(up.to);
    links.add(up.id);
    ids.add(up.to);
    cur = up.to;
  }

  const expand = (itemId, level) => {
    if (level > depth) return [];
    const out = [];
    for (const l of step(itemId)) {
      const o = next(l);
      if (!o || ids.size >= MAX_ITEMS || !isKnown(o, knowable)) continue;
      if (ids.has(o.id)) continue;
      ids.add(o.id);
      links.add(l.id);
      out.push({ item: o, link: l, contested: l.confidence === "contested", children: [] });
    }
    out.sort((a, b) => a.item.occurred.range[0] - b.item.occurred.range[0]);
    for (const node of out) node.children = expand(node.item.id, level + 1);
    return out;
  };

  const tree = roots.flatMap((r) => expand(r, 1));
  return { tree, ids, links };
}

// The time span a trace covers, for fitting the window to it.
export function traceSpan(data, ids) {
  let lo = Infinity, hi = -Infinity;
  for (const id of ids) {
    const [a, b] = data.byId.get(id).occurred.range;
    lo = Math.min(lo, a);
    hi = Math.max(hi, Number.isFinite(b) ? b : a);
  }
  return [lo, hi];
}
