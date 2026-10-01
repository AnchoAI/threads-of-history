// The zoom strip along the bottom: how many items fall in each period across the whole
// timeline, with the current window highlighted.
//   drag across it      pick a period
//   drag the window     move it
//   scroll over it      zoom in or out around the pointer
//   double-click        show everything
//   keyboard (focused)  ← → move, + − zoom, 0 show everything
import { fromYear } from "./timescale.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export class TimeBar {
  constructor(el, data, timeline) {
    this.el = el;
    this.timeline = timeline;
    this.win = timeline.window;
    this.canvas = el.querySelector("canvas");
    this.label = el.querySelector(".range");
    this.starts = data.nodes.map((n) => n.occurred.range[0]);
    this.#bind();
    new ResizeObserver(() => this.draw()).observe(this.canvas);
  }

  // time <-> x within the canvas, across the full limits
  #tx(t) {
    const [lo, hi] = this.win.limits;
    return ((t - lo) / (hi - lo)) * this.canvas.clientWidth;
  }

  #xt(x) {
    const [lo, hi] = this.win.limits;
    return lo + (x / this.canvas.clientWidth) * (hi - lo);
  }

  draw() {
    const c = this.canvas, dpr = Math.min(devicePixelRatio, 2);
    const w = c.clientWidth, h = c.clientHeight;
    if (!w) return;
    c.width = w * dpr;
    c.height = h * dpr;
    const g = c.getContext("2d");
    g.scale(dpr, dpr);
    const css = getComputedStyle(this.el);
    const ink = css.getPropertyValue("--ink").trim() || "#E6E1D6";
    const muted = css.getPropertyValue("--muted").trim() || "#8A93A0";
    const accent = css.getPropertyValue("--accent").trim() || "#F08A3E";

    // Histogram of item start dates.
    const bins = Math.max(20, Math.floor(w / 4));
    const counts = new Array(bins).fill(0);
    const [lo, hi] = this.win.limits;
    for (const t of this.starts) counts[Math.min(bins - 1, Math.floor(((t - lo) / (hi - lo)) * bins))]++;
    const max = Math.max(...counts, 1);
    g.fillStyle = muted;
    g.globalAlpha = 0.55;
    const bw = w / bins;
    counts.forEach((n, i) => {
      if (!n) return;
      const bh = Math.max(1.5, (n / max) * (h - 6));
      g.fillRect(i * bw + 0.5, h - bh, Math.max(1, bw - 1), bh);
    });

    // The current window.
    const x0 = this.#tx(this.win.t0), x1 = Math.max(this.#tx(this.win.t1), x0 + 2);
    g.globalAlpha = 0.16;
    g.fillStyle = accent;
    g.fillRect(x0, 0, x1 - x0, h);
    g.globalAlpha = 1;
    g.strokeStyle = accent;
    g.lineWidth = 1.5;
    g.strokeRect(x0 + 0.75, 0.75, x1 - x0 - 1.5, h - 1.5);

    // The "knowable on" date, when the slider is on.
    const k = this.timeline.knowable;
    if (k) {
      const xk = this.#tx(k.t);
      g.strokeStyle = css.getPropertyValue("--known").trim() || "#8FD3FF";
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(xk, 0);
      g.lineTo(xk, h);
      g.stroke();
    }

    // Decade marks.
    g.fillStyle = ink;
    g.globalAlpha = 0.5;
    g.font = "10px 'IBM Plex Mono', ui-monospace, monospace";
    const step = (hi - lo) > 80 ? 20 : 10;
    for (let y = Math.ceil(lo / step) * step; y < hi; y += step) {
      g.fillText(String(y), this.#tx(y) + 2, 10);
    }
    g.globalAlpha = 1;
    this.label.textContent = describe(this.win);
  }

  #bind() {
    const c = this.canvas;
    let drag = null;
    const at = (ev) => ev.clientX - c.getBoundingClientRect().left;
    c.addEventListener("pointerdown", (ev) => {
      c.setPointerCapture(ev.pointerId);
      const x = at(ev);
      const inside = x >= this.#tx(this.win.t0) && x <= this.#tx(this.win.t1);
      drag = inside && this.win.span < this.win.limits[1] - this.win.limits[0]
        ? { kind: "move", x, t0: this.win.t0 }
        : { kind: "brush", x };
    });
    c.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const x = at(ev);
      if (drag.kind === "move") {
        const dt = this.#xt(x) - this.#xt(drag.x);
        this.timeline.setWindow(drag.t0 + dt, drag.t0 + dt + this.win.span);
      } else if (Math.abs(x - drag.x) > 3) {
        const [a, b] = [this.#xt(drag.x), this.#xt(x)].sort((p, q) => p - q);
        this.timeline.setWindow(a, b);
      }
    });
    const end = () => { if (drag) { drag = null; this.timeline.settle(); } };
    c.addEventListener("pointerup", end);
    c.addEventListener("pointercancel", end);
    c.addEventListener("dblclick", () => { this.timeline.setWindow(...this.win.limits); this.timeline.settle(); });

    let settleTimer = null;
    c.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const factor = Math.exp(ev.deltaY * 0.0015);
      this.win.zoom(factor, this.#xt(at(ev)));
      this.timeline.setWindow(this.win.t0, this.win.t1);
      clearTimeout(settleTimer);
      settleTimer = setTimeout(() => this.timeline.settle(), 250);
    }, { passive: false });

    c.addEventListener("keydown", (ev) => {
      const w = this.win;
      if (ev.key === "ArrowLeft") w.pan(-w.span * 0.2);
      else if (ev.key === "ArrowRight") w.pan(w.span * 0.2);
      else if (ev.key === "+" || ev.key === "=") w.zoom(0.7);
      else if (ev.key === "-" || ev.key === "_") w.zoom(1 / 0.7);
      else if (ev.key === "0") w.reset();
      else return;
      ev.preventDefault();
      ev.stopPropagation();
      this.timeline.setWindow(w.t0, w.t1);
      this.timeline.settle();
    });
  }
}

// "1914 – 2026", "Mar 1962 – Jan 1963", "14 Oct – 28 Oct 1962", "24 Feb 1962, 03:00 – 21:00"
export function describe(win) {
  const a = fromYear(win.t0), b = fromYear(win.t1);
  const y = (d) => d.getUTCFullYear();
  const m = (d) => MONTHS[d.getUTCMonth()];
  if (win.span >= 8) return `${y(a)} – ${y(b)}`;
  if (win.span >= 60 / 365) return `${m(a)} ${y(a)} – ${m(b)} ${y(b)}`;
  if (win.span >= 2 / 365) return `${a.getUTCDate()} ${m(a)} – ${b.getUTCDate()} ${m(b)} ${y(b)}`;
  const hh = (d) => `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  return `${a.getUTCDate()} ${m(a)} ${y(a)}, ${hh(a)} – ${hh(b)}`;
}
