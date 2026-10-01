// The time window: which slice of time fills the timeline, and the tick marks for it.
// Zooming changes the window, not the camera, so the view can go from a century to a
// few hours without the scene becoming enormous. Pure functions, no three.js.

export const WORLD_LENGTH = 450;          // world units the window always spans
export const MIN_SPAN = 6 / (24 * 365.25); // six hours, in years

const DAY = 1 / 365.25;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export class TimeWindow {
  constructor(t0, t1, limits = [t0, t1]) {
    this.limits = limits;
    this.set(t0, t1);
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
    return ((t - this.t0) / this.span - 0.5) * WORLD_LENGTH;
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
  const approx = { year: 1, month: 1 / 12, day: DAY, hour: DAY / 24 };
  // The finest step that still gives no more than `target` ticks.
  let [n, unit] = STEPS[0];
  for (const [sn, su] of [...STEPS].reverse()) {
    if (win.span / (sn * approx[su]) <= target) { n = sn; unit = su; break; }
  }
  const out = [];
  let d = floorTo(fromYear(win.t0), n, unit);
  for (let guard = 0; guard < 400; guard++) {
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
