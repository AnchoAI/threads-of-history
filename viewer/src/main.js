import { LINK_TYPES, esc, loadGraph, yearLabel } from "./data.js";
import { renderDetail } from "./panel.js";
import { Timeline } from "./scene.js";
import { TimeBar } from "./timebar.js";

const $ = (id) => document.getElementById(id);

async function start() {
  let data;
  try {
    // ?graph=<file> loads another graph, e.g. the stress-test fixture during development.
    const alt = new URLSearchParams(location.search).get("graph");
    data = await loadGraph(alt && /^[\w./-]+\.json$/.test(alt) && !alt.includes("..") ? alt : "graph.json");
  } catch (err) {
    const box = $("error");
    box.innerHTML = `<b>No data to show.</b><br>${esc(err.message)}<br><br>
      Build it first from the <code>viewer/</code> folder with <code>npm run data</code>
      (or <code>python tools/build.py</code> from the repo root), then reload.`;
    box.hidden = false;
    $("count").textContent = "No data loaded";
    return;
  }

  let selected = null;
  let tour = null, tourI = 0;
  const hidden = new Set();
  let mode = "threads";
  let expanded = new Set();

  let bar = null;
  const legend = $("legend");
  const timeline = new Timeline($("stage"), $("labels"), data, {
    onPick: (id) => select(id),
    onLaneClick: (domain) => toggleDomain(domain),
    onWindow: () => bar?.draw(),
    onBuild: () => updateLaneHint(),
    leftInset: () => (legend.hidden || innerWidth <= 760 ? 8 : legend.getBoundingClientRect().right + 8),
  });

  // Open one domain into its threads (closing any other), or close it again.
  function toggleDomain(domain) {
    expanded = expanded.has(domain) ? new Set() : new Set([domain]);
    rebuild();
  }

  function rebuild() {
    timeline.build(mode, expanded);
  }

  // Lanes can collapse after a rebuild or after zooming changes which threads are in view.
  function updateLaneHint() {
    const collapsed = mode === "threads" && timeline.layout.collapsed;
    $("laneHint").hidden = !collapsed;
    document.querySelectorAll("#threadList .dom").forEach((h) => {
      h.classList.toggle("clickable", collapsed);
      h.setAttribute("aria-expanded", String(!collapsed || expanded.has(h.dataset.domain)));
    });
  }

  // ---- header counts and draft banner
  $("count").textContent = `${data.nodes.length} events · ${data.links.length} links`;
  const total = Object.values(data.reviewCounts).reduce((a, b) => a + b, 0);
  const unverified = data.reviewCounts.unverified ?? 0;
  if (unverified) {
    $("draft").textContent = `Draft data: ${unverified} of ${total} items and links are unverified. ` +
      "Open any item to see its review status and open questions.";
    $("draft").hidden = false;
  }

  // ---- thread toggles, grouped by domain
  for (const d of data.graph.domains) {
    const threads = data.graph.threads.filter((t) => t.domain === d.id && data.nodes.some((n) => n.threads.includes(t.id)));
    if (!threads.length) continue;
    const head = document.createElement("div");
    head.className = "dom";
    head.dataset.domain = d.id;
    head.tabIndex = 0;
    head.textContent = d.name;
    const open = () => { if (head.classList.contains("clickable")) toggleDomain(d.id); };
    head.onclick = open;
    head.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } };
    $("threadList").appendChild(head);
    for (const t of threads) {
      const row = document.createElement("div");
      row.className = "row";
      row.tabIndex = 0;
      row.dataset.thread = t.id;
      row.innerHTML = `<span class="sw" style="background:${data.threadColor[t.id]}"></span>${esc(t.name)}`;
      const toggle = () => {
        hidden.has(t.id) ? hidden.delete(t.id) : hidden.add(t.id);
        row.classList.toggle("off", hidden.has(t.id));
        timeline.setHidden(hidden);
      };
      row.onclick = toggle;
      row.onkeydown = (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); }
      };
      $("threadList").appendChild(row);
    }
  }

  // ---- link legend (only types that appear in the data), plus contested
  const used = new Set(data.links.map((l) => l.type));
  $("linkLegend").innerHTML = Object.entries(LINK_TYPES)
    .filter(([type]) => used.has(type))
    .map(([, t]) => `<div class="row static"><span class="ln" style="border-color:${t.color}"></span>${esc(t.label)}</div>`)
    .join("") + '<div class="row static"><span class="ln dash" style="border-color:#8A93A0"></span>Contested</div>';

  // ---- lane arrangement
  const modeButtons = document.querySelectorAll(".seg button[data-mode]");
  for (const b of modeButtons) {
    b.onclick = () => {
      modeButtons.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      mode = b.dataset.mode;
      rebuild();
      if (selected) timeline.focus(selected);
    };
  }

  // ---- 3D or 2D
  const viewButtons = document.querySelectorAll(".seg button[data-view]");
  for (const b of viewButtons) {
    b.onclick = () => {
      viewButtons.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      timeline.setView(b.dataset.view);
      $("hint").textContent = b.dataset.view === "2d"
        ? "drag to pan · scroll to zoom the camera · zoom time with the strip below or + and − · click a node"
        : "drag to orbit · scroll to zoom the camera · zoom time with the strip below or + and − · click a node";
      if (selected) timeline.focus(selected);
    };
  }

  // ---- selection and detail panel
  const detail = $("detail");
  function select(id, { fly = true } = {}) {
    selected = id && data.byId.has(id) && timeline.nodes.has(id) ? id : null;
    timeline.highlight(selected);
    try {
      history.replaceState(null, "", selected ? `#${selected}` : location.pathname + location.search);
    } catch {
      // Some embedded frames refuse URL changes; the viewer works without them.
    }
    if (!selected) { detail.hidden = true; return; }
    detail.innerHTML = renderDetail(data.byId.get(selected), data);
    detail.hidden = false;
    detail.scrollTop = 0;
    detail.querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => select(b.dataset.go); });
    $("closeD").onclick = () => select(null);
    if (fly) timeline.focus(selected);
  }

  $("resetBtn").onclick = () => { endTour(); select(null); timeline.reset(); };

  // ---- search
  const q = $("q"), results = $("results");
  q.addEventListener("input", () => {
    const s = q.value.trim().toLowerCase();
    results.innerHTML = "";
    if (!s) return;
    data.nodes
      .filter((n) => `${n.title} ${n.summary} ${n.occurred.start}`.toLowerCase().includes(s))
      .slice(0, 8)
      .forEach((n) => {
        const b = document.createElement("button");
        b.innerHTML = `<span class="y">${esc(yearLabel(n))}</span>${esc(n.title)}`;
        b.onclick = () => { select(n.id); results.innerHTML = ""; q.value = ""; };
        results.appendChild(b);
      });
  });

  // ---- guided paths
  const tourEl = $("tour");
  const nodeIds = new Set(data.nodes.map((n) => n.id));
  for (const path of data.paths) {
    const steps = path.steps.filter((id) => nodeIds.has(id));
    if (steps.length < 2) continue;
    const b = document.createElement("button");
    b.textContent = `Play: ${path.title}`;
    b.onclick = () => startTour(steps);
    $("tours").appendChild(b);
  }
  function startTour(steps) {
    hidden.clear();
    document.querySelectorAll("#threadList .row").forEach((r) => r.classList.remove("off"));
    timeline.setHidden(hidden);
    tour = steps;
    tourI = 0;
    tourEl.hidden = false;
    showTour();
  }
  function showTour() {
    const item = data.byId.get(tour[tourI]);
    timeline.setPinned([item.id]);
    $("tTxt").textContent = `${tourI + 1} / ${tour.length} · ${yearLabel(item)} ${item.title}`;
    select(item.id);
  }
  function endTour() { tour = null; tourEl.hidden = true; timeline.setPinned([]); }
  $("tNext").onclick = () => { tourI = Math.min(tour.length - 1, tourI + 1); showTour(); };
  $("tPrev").onclick = () => { tourI = Math.max(0, tourI - 1); showTour(); };
  $("tEnd").onclick = () => { endTour(); select(null); };
  addEventListener("keydown", (ev) => {
    if (ev.target === q || ev.defaultPrevented) return;
    if (tour) {
      if (ev.key === "ArrowRight") $("tNext").click();
      if (ev.key === "ArrowLeft") $("tPrev").click();
      return;
    }
    // Without a guided path running, the keyboard moves and zooms the time window.
    const w = timeline.window;
    if (ev.key === "ArrowLeft") w.pan(-w.span * 0.2);
    else if (ev.key === "ArrowRight") w.pan(w.span * 0.2);
    else if (ev.key === "+" || ev.key === "=") w.zoom(0.7);
    else if (ev.key === "-" || ev.key === "_") w.zoom(1 / 0.7);
    else if (ev.key === "0") w.reset();
    else return;
    timeline.setWindow(w.t0, w.t1);
    timeline.settle();
  });

  // ---- go
  rebuild();
  bar = new TimeBar($("timebar"), data, timeline);
  bar.draw();
  timeline.start();
  const fromHash = decodeURIComponent(location.hash.slice(1));
  if (fromHash) select(fromHash);
  window.__viewer = { data, timeline, select };  // handy in the browser console and in tests
}

start();
