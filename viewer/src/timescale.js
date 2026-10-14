// The time window: which slice of time fills the timeline, and the tick marks for it.
// Zooming changes the window, not the camera, so the view can go from a century to a
// few hours without the scene becoming enormous. Pure functions, no three.js.

export const WORLD_LENGTH = 450;          // world units the window always spans
export const MIN_SPAN = 6 / (24 * 365.25); // six hours, in years
export const DEEP_SPAN = 300;              // with more years than this, the past is compressed by default

const DAY = 1 / 365.25;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// "Compressed past": with a long timeline, x follows the square root of the time before the
// end of the limits, so the last century gets a fair share of the axis next to the first
// millennium. Zooming and panning still work in years; only the drawing is warped, and a
// narrow window is nearly linear.
export class TimeWindow {
  constructor(t0, t1, limits = [t0, t1], { compressed = false } = {}) {
    this.limits = limits;
    this.compressed = compressed;
    this.set(t0, t1);
  }

  warp(t) {
    return this.compressed ? -Math.sqrt(Math.max(this.limits[1] + 1 - t, 0)) : t;
  }

  unwarp(u) {
    return this.compressed ? this.limits[1] + 1 - u * u : u;
  }

  // Where t falls across the full limits, 0..1, on the current scale (for the time strip).
  share(t) {
    const [lo, hi] = this.limits;
    return (this.warp(t) - this.warp(lo)) / (this.warp(hi) - this.warp(lo));
  }

  fromShare(f) {
    const [lo, hi] = this.limits;
    return this.unwarp(this.warp(lo) + f * (this.warp(hi) - this.warp(lo)));
  }

  get span() {
    return this.t1 - this.t0;
  }

  // Keep the window inside the limits and no narrower than MIN_SPAN.
  set(t0, t1) {
    const [lo, hi] = this.limits;
    let span = Math.min(Math.max(t1 - t0, MIN_SPAN), hi - lo);
    let start = Math.min(Math.max(t0, lo), hi - span);
    this.t0 = start;
    this.t1 = start + span;
    return this;
  }

  reset() {
    return this.set(...this.limits);
  }

  // Zoom by `factor` (<1 zooms in) keeping time `at` fixed on screen.
  zoom(factor, at = (this.t0 + this.t1) / 2) {
    const f = (at - this.t0) / this.span;
    const span = this.span * factor;
    return this.set(at - f * span, at - f * span + span);
  }

  pan(years) {
    return this.set(this.t0 + years, this.t1 + years);
  }

  // Centre the window on `t`, keeping the span.
  centre(t) {
    return this.set(t - this.span / 2, t + this.span / 2);
  }

  x(t) {
    const a = this.warp(this.t0), b = this.warp(this.t1);
    return ((this.warp(t) - a) / (b - a) - 0.5) * WORLD_LENGTH;
  }

  contains(t0, t1 = t0) {
    return t1 >= this.t0 && t0 <= this.t1;
  }
}

// Tick marks for a window: roughly 8–16 of them, at calendar-friendly steps.
const STEPS = [
  [100, "year"], [50, "year"], [20, "year"], [10, "year"], [5, "year"], [2, "year"], [1, "year"],
  [6, "month"], [3, "month"], [1, "month"],
  [7, "day"], [2, "day"], [1, "day"], [6, "hour"], [1, "hour"],
];

export function ticks(win, target = 12) {
  if (win.compressed) return warpedTicks(win, target);
  // The finest step that still gives no more than `target` ticks.
  let [n, unit] = STEPS[0];
  for (const [sn, su] of [...STEPS].reverse()) {
    if (win.span / (sn * APPROX[su]) <= target) { n = sn; unit = su; break; }
  }
  return stepTicks(win, n, unit);
}

const APPROX = { year: 1, month: 1 / 12, day: DAY, hour: DAY / 24 };

// With a compressed past one step doesn't fit everywhere: centuries suit the far past and
// years the recent end. Take ticks from coarse to fine steps, keeping each one only if it
// is far enough on screen from the ticks already kept.
function warpedTicks(win, target) {
  const gap = WORLD_LENGTH / (target * 1.15);
  const kept = [];
  for (const [n, unit] of STEPS) {
    if (win.span / (n * APPROX[unit]) > 3000) break;
    for (const tk of stepTicks(win, n, unit, 3000)) {
      const x = win.x(tk.t);
      if (kept.every((k) => Math.abs(k.x - x) >= gap)) kept.push({ ...tk, x });
    }
  }
  return kept.sort((a, b) => a.t - b.t).map(({ x, ...tk }) => tk);
}

function stepTicks(win, n, unit, max = 400) {
  const out = [];
  let d = floorTo(fromYear(win.t0), n, unit);
  for (let guard = 0; guard < max; guard++) {
    const t = toYear(d);
    if (t > win.t1) break;
    if (t >= win.t0) out.push({ t, label: label(d, unit), major: isMajor(d, n, unit) });
    d = add(d, n, unit);
  }
  return out;
}

// ---------------------------------------------------------------- calendar helpers

function yearLength(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 366 : 365;
}

export function toYear(d) {
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  return d.getUTCFullYear() + (d.getTime() - start) / (yearLength(d.getUTCFullYear()) * 86400000);
}

export function fromYear(t) {
  const y = Math.floor(t);
  return new Date(Math.round(Date.UTC(y, 0, 1) + (t - y) * yearLength(y) * 86400000));
}

function floorTo(d, n, unit) {
  const y = d.getUTCFullYear(), m = d.getUTCMonth(), day = d.getUTCDate();
  if (unit === "year") return new Date(Date.UTC(Math.floor(y / n) * n, 0, 1));
  if (unit === "month") return new Date(Date.UTC(y, Math.floor(m / n) * n, 1));
  if (unit === "day") return new Date(Date.UTC(y, m, n === 7 ? day - ((day - 1) % 7) : day));
  return new Date(Date.UTC(y, m, day, Math.floor(d.getUTCHours() / n) * n));
}

function add(d, n, unit) {
  const r = new Date(d);
  if (unit === "year") r.setUTCFullYear(r.getUTCFullYear() + n);
  else if (unit === "month") r.setUTCMonth(r.getUTCMonth() + n);
  else if (unit === "day") r.setUTCDate(r.getUTCDate() + n);
  else r.setUTCHours(r.getUTCHours() + n);
  return r;
}

function isMajor(d, n, unit) {
  if (unit === "year") return d.getUTCFullYear() % (n * 5 >= 10 ? n * 5 : 10) === 0;
  if (unit === "month") return d.getUTCMonth() === 0;
  if (unit === "day") return d.getUTCDate() === 1;
  return d.getUTCHours() === 0;
}

function label(d, unit) {
  const y = d.getUTCFullYear(), m = MONTHS[d.getUTCMonth()];
  if (unit === "year") return String(y);
  if (unit === "month") return d.getUTCMonth() === 0 ? String(y) : `${m} ${y}`;
  if (unit === "day") return `${d.getUTCDate()} ${m} ${y}`;
  return `${d.getUTCDate()} ${m} ${String(d.getUTCHours()).padStart(2, "0")}:00`;
}
