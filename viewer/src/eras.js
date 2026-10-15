// Era zones: faint bands along the time axis for the long, important events in view (the
// World Wars, the Reformation, the Cold War...). Derived from the data, no extra format:
// an era is an item with importance 5 that lasts long enough to read as a stretch of time
// at the current zoom. The best-connected eras win; a short era nested inside a long one
// (a war inside an age of empire) is kept, but two eras covering much the same years are not.
// Pure functions.
import { isKnown } from "./visibility.js";

export const MAX_ERAS = 5;
const MIN_SHARE = 0.04;   // an era must fill at least this share of the window
const MAX_OVERLAP = 0.5;  // skip an era that mostly repeats one already chosen of similar length

export function chooseEras(data, win, { max = MAX_ERAS, knowable = null } = {}) {
  const out = [];
  const links = (e) => data.linksOf.get(e.item.id)?.length ?? 0;
  const candidates = data.nodes
    .filter((n) => (n.importance ?? 3) >= 5 && Number.isFinite(n.occurred.range[1]) && isKnown(n, knowable))
    .map((n) => ({ item: n, a: n.occurred.range[0], b: n.occurred.range[1] }))
    .filter((e) => e.b - e.a >= Math.max(1, MIN_SHARE * win.span) && e.a < win.t1 && e.b > win.t0)
    .sort((p, q) => links(q) - links(p) || (q.b - q.a) - (p.b - p.a) || p.item.id.localeCompare(q.item.id));
  for (const e of candidates) {
    if (out.length >= max) break;
    const covered = out.some((o) => {
      const shared = Math.min(o.b, e.b) - Math.max(o.a, e.a);
      const ratio = Math.min(o.b - o.a, e.b - e.a) / Math.max(o.b - o.a, e.b - e.a);
      return shared > MAX_OVERLAP * Math.min(o.b - o.a, e.b - e.a) && ratio > 0.4;
    });
    if (!covered) out.push(e);
  }
  out.sort((p, q) => p.a - q.a);
  // Nesting depth, so a band inside another can be drawn thinner and labelled lower.
  for (const e of out) e.depth = out.filter((o) => o !== e && o.a <= e.a && o.b >= e.b && (o.b - o.a) > (e.b - e.a)).length;
  // Label row: eras that start close together get labels on different rows.
  const gap = 0.12 * win.span;
  for (const [i, e] of out.entries()) {
    e.row = 0;
    while (out.slice(0, i).some((o) => o.row === e.row && Math.max(o.a, win.t0) > Math.max(e.a, win.t0) - gap)) e.row++;
  }
  return out;
}
