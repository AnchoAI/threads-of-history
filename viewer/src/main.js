import { LINK_TYPES, esc, loadGraph, yearLabel } from "./data.js";
import { renderDetail } from "./panel.js";
import { trace, traceSpan } from "./chains.js";
import { Timeline } from "./scene.js";
import { TimeBar } from "./timebar.js";
import { fromYear, toYear } from "./timescale.js";
import { isKnown, knownParties, knownSince, span } from "./visibility.js";
import { formatState, parseState } from "./urlstate.js";

const $ = (id) => document.getElementById(id);
const narrow = () => innerWidth <= 760;
// Three paths offered on the start screen, by id; any others are listed under "All guided paths".
const FEATURED = ["cuba-to-nord-stream", "opium-wars-to-hong-kong-2020", "great-schism-to-ukraine-church"];
const SEEN_KEY = "threads-of-history:seen-start";

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

  const legend = $("legend"), detail = $("detail");
  const threadIds = new Set(data.graph.threads.map((t) => t.id));
  const parties = new Set(knownParties(data));

  let selected = null;
  let tour = null, tourI = 0, beforeTour = null;
  const hidden = new Set();
  let mode = "threads";
  let view = narrow() ? "list" : "2d";
  let expanded = new Set();

  let bar = null;
  const timeline = new Timeline($("stage"), $("labels"), data, {
    view: "2d",
    onPick: (id) => select(id),
    onLaneClick: (domain) => toggleDomain(domain),
    onWindow: () => { bar?.draw(); updateSubset(); renderList(); saveState(); },
    onBuild: () => updateLaneHint(),
    leftInset: () => (legend.hidden || narrow() ? 8 : legend.getBoundingClientRect().right + 8),
    rightInset: () => (detail.hidden || narrow() ? 16 : innerWidth - detail.getBoundingClientRect().left + 8),
    topInset: () => $("topbar").getBoundingClientRect().bottom,
    bottomInset: () => innerHeight - $("timebar").getBoundingClientRect().top,
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

  // ---- filters panel: collapsible; its controls keep their state while it is closed
  const filtersBtn = $("filtersBtn");
  function setFilters(open) {
    legend.hidden = !open;
    filtersBtn.setAttribute("aria-expanded", String(open));
    filtersBtn.classList.toggle("on", open);
    timeline.resize();
  }
  filtersBtn.onclick = () => setFilters(legend.hidden);

  // ---- thread toggles, grouped by domain
  const threadRows = new Map();
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
        applyHidden();
      };
      row.onclick = toggle;
      row.onkeydown = (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); }
      };
      threadRows.set(t.id, row);
      $("threadList").appendChild(row);
    }
  }
  function applyHidden() {
    for (const [id, row] of threadRows) row.classList.toggle("off", hidden.has(id));
    timeline.setHidden(hidden);
    updateStatus();
    renderList();
    saveState();
  }

  // ---- relationship legend (only types that appear in the data), plus contested
  const used = new Set(data.links.map((l) => l.type));
  $("linkLegend").innerHTML = Object.entries(LINK_TYPES)
    .filter(([type]) => used.has(type))
    .map(([, t]) => `<div class="row static"><span class="ln" style="border-color:${t.color}"></span>${esc(t.label)}</div>`)
    .join("") + '<div class="row static"><span class="ln dash" style="border-color:#8A93A0"></span>Contested</div>';

  // ---- lane arrangement
  const modeButtons = document.querySelectorAll(".seg button[data-mode]");
  function setMode(m) {
    mode = m;
    modeButtons.forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.mode === m)));
    rebuild();
    if (selected) timeline.focus(selected);
    saveState();
  }
  for (const b of modeButtons) b.onclick = () => setMode(b.dataset.mode);

  // ---- time scale: compressed past or even time (only offered for long timelines)
  const timeButtons = document.querySelectorAll(".seg button[data-time]");
  const syncTime = () => timeButtons.forEach((x) =>
    x.setAttribute("aria-pressed", String((x.dataset.time === "compressed") === timeline.window.compressed)));
  $("timeScale").hidden = !timeline.window.compressed;
  syncTime();
  function setScale(compressed) {
    timeline.setCompressed(compressed);
    syncTime();
    bar?.draw();
    if (selected) timeline.focus(selected);
    saveState();
  }
  for (const b of timeButtons) b.onclick = () => setScale(b.dataset.time === "compressed");

  // ---- 2D, 3D, or a plain list (the list is the fallback for small screens)
  const viewButtons = document.querySelectorAll(".seg button[data-view]");
  function setView(v) {
    view = v;
    viewButtons.forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.view === v)));
    $("list").hidden = v !== "list";
    document.body.classList.toggle("listview", v === "list");
    if (v !== "list") timeline.setView(v);
    renderList();
    if (selected && v !== "list") timeline.focus(selected);
    saveState();
  }
  for (const b of viewButtons) b.onclick = () => setView(b.dataset.view);

  // ---- "knowable on": show only what was known by a date, to the public or to one party
  const knowOn = $("knowOn"), knowRange = $("knowRange"), knowDate = $("knowDate"), knowParty = $("knowParty");
  const [lo, hi] = timeline.window.limits;
  // step "any": a fixed day step drifts from the calendar over a long timeline.
  Object.assign(knowRange, { min: lo, max: hi, step: "any" });
  const iso = (t) => fromYear(t).toISOString().slice(0, 10);
  Object.assign(knowDate, { min: iso(Math.max(lo, 1)), max: iso(hi) });
  for (const party of parties) {
    const o = document.createElement("option");
    o.value = party;
    o.textContent = `to ${party}`;
    knowParty.appendChild(o);
  }
  const DAY_MS = 86400000;
  // A date means "by the end of that day".
  const endOfDay = (dateStr) => toYear(new Date(Date.parse(`${dateStr}T00:00:00Z`) + DAY_MS - 1));

  function knowable() {
    if (!knowOn.checked) return null;
    const d = fromYear(Number(knowRange.value));
    const label = `${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })} ${d.getUTCFullYear()}`;
    return { t: endOfDay(iso(Number(knowRange.value))), party: knowParty.value || null, label };
  }

  function applyKnowable() {
    const k = knowable();
    $("knowControls").hidden = !k;
    $("knowNote").hidden = !k;
    knowDate.value = iso(Number(knowRange.value));
    timeline.setKnowable(k);
    if (k) {
      const n = data.nodes.filter((item) => isKnown(item, k)).length;
      $("knowCount").textContent = `${n} of ${data.nodes.length} events known ${k.party ? `to ${k.party}` : "publicly"} by ${k.label}.`;
    }
    // Drop a selection that was not yet known; otherwise refresh its panel without hindsight.
    if (selected && !isKnown(data.byId.get(selected), k)) select(null);
    else if (selected) select(selected, { fly: false });
    updateStatus();
    renderList();
    saveState();
  }

  knowOn.addEventListener("change", () => {
    if (knowOn.checked) {
      // Start from when the selected item became known ("what was knowable then?"), else the window's end.
      // Its known date, not its occurred date: an item that became public later would hide itself.
      const start = selected ? knownSince(data.byId.get(selected), knowParty.value || null) : Math.min(timeline.window.t1, hi);
      knowRange.value = String(start);
    }
    applyKnowable();
  });
  knowRange.addEventListener("input", applyKnowable);
  knowDate.addEventListener("change", () => {
    if (!knowDate.value) return;
    knowRange.value = String(Math.min(Math.max(toYear(new Date(`${knowDate.value}T00:00:00Z`)), lo), hi));
    applyKnowable();
  });
  knowParty.addEventListener("change", applyKnowable);

  // ---- selection and the inspector
  function select(id, { fly = true } = {}) {
    selected = id && data.byId.has(id) && timeline.nodes.has(id) && isKnown(data.byId.get(id), knowable()) ? id : null;
    if (timeline.trace) timeline.trace = null;
    timeline.highlight(selected);
    const wasHidden = detail.hidden;
    if (!selected) {
      detail.hidden = true;
    } else {
      detail.innerHTML = renderDetail(data.byId.get(selected), data, { knowable: knowable() });
      detail.hidden = false;
      detail.scrollTop = 0;
      detail.querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => select(b.dataset.go); });
      $("closeD").onclick = () => select(null);
      $("closeX").onclick = () => select(null);
      detail.querySelectorAll("[data-trace]").forEach((b) => {
        b.onclick = () => {
          const t = trace(data, selected, b.dataset.trace, { knowable: knowable() });
          timeline.setTrace({ ids: t.ids, links: t.links, span: traceSpan(data, t.ids) });
        };
      });
    }
    if (wasHidden !== detail.hidden) timeline.resize();  // the 2D view fits beside the inspector
    if (selected && fly && view !== "list") timeline.focus(selected);
    renderList();
    saveState();
  }

  $("resetBtn").onclick = () => { endTour({ restore: false }); select(null); timeline.reset(); };

  // ---- search
  const q = $("q"), results = $("results");
  q.addEventListener("input", () => {
    const s = q.value.trim().toLowerCase();
    results.innerHTML = "";
    if (!s) return;
    const k = knowable();
    data.nodes
      .filter((n) => isKnown(n, k) && `${n.title} ${n.summary} ${n.occurred.start}`.toLowerCase().includes(s))
      .slice(0, 8)
      .forEach((n) => {
        const b = document.createElement("button");
        b.innerHTML = `<span class="y">${esc(yearLabel(n))}</span>${esc(n.title)}`;
        b.onclick = () => { select(n.id); results.innerHTML = ""; q.value = ""; };
        results.appendChild(b);
      });
  });
  q.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") { results.innerHTML = ""; q.value = ""; q.blur(); }
  });

  // ---- what is shown: status line in the top bar, and a note when only some events are drawn
  function updateStatus() {
    const parts = [$("timebar").querySelector(".range")?.textContent || ""];
    if (hidden.size) parts.push(`${hidden.size} thread${hidden.size === 1 ? "" : "s"} hidden`);
    if (mode !== "threads") parts.push(`lanes by ${mode === "regions" ? "region" : "domain"}`);
    const k = knowable();
    if (k) parts.push(`knowable on ${k.label}`);
    $("status").textContent = parts.filter(Boolean).join(" · ");
  }
  function inWindowItems() {
    const { t0, t1 } = timeline.window;
    const k = knowable();
    return data.nodes.filter((n) => {
      const [a, b] = span(n);
      return a <= t1 && (Number.isFinite(b) ? b : a) >= t0 && isKnown(n, k) && !n.threads.every((t) => hidden.has(t));
    });
  }
  function updateSubset() {
    const shown = [...timeline.nodes.values()].filter((n) => n.show).length;
    const all = inWindowItems().length;
    $("subset").textContent = view === "list" ? `${all} events in this period`
      : shown < all ? `Showing the ${shown} most important of ${all} events in this period; zoom in to see more`
        : `${all} events in this period`;
    updateStatus();
  }

  // ---- list view: the same events as a readable list (the fallback on small screens)
  function renderList() {
    if (view !== "list") return;
    const items = inWindowItems().sort((a, b) => a.occurred.range[0] - b.occurred.range[0]);
    const MAX = 400;
    $("list").innerHTML = `<p class="note">${items.length} events in this period, oldest first${items.length > MAX ? `; the first ${MAX} are listed, so narrow the period to see the rest` : ""}.</p>` +
      items.slice(0, MAX).map((n) => `<button class="li${n.id === selected ? " on" : ""}" data-go="${esc(n.id)}">
        <span class="y">${esc(yearLabel(n))}</span><span><b>${esc(n.title)}</b><br><span class="note">${esc(n.summary)}</span></span></button>`).join("");
    $("list").querySelectorAll("[data-go]").forEach((b) => { b.onclick = () => select(b.dataset.go, { fly: false }); });
  }

  // ---- guided paths and the start screen
  const startEl = $("start");
  const nodeIds = new Set(data.nodes.map((n) => n.id));
  const playable = data.paths.map((p) => ({ ...p, steps: p.steps.filter((id) => nodeIds.has(id)) })).filter((p) => p.steps.length >= 2);
  for (const path of playable) {
    const b = document.createElement("button");
    b.textContent = `Play: ${path.title}`;
    b.title = path.summary ?? "";
    b.onclick = () => { closeStart(); startTour(path.steps); };
    $("tours").appendChild(b);
  }
  const featured = FEATURED.map((id) => playable.find((p) => p.id === id)).filter(Boolean);
  for (const p of playable) if (featured.length < 3 && !featured.includes(p)) featured.push(p);
  $("featured").innerHTML = featured.map((p) => `<button class="path" data-path="${esc(p.id)}">
    <b>${esc(p.title)}</b><span class="note">${p.summary ? `${esc(p.summary)} · ` : ""}${p.steps.length} steps</span></button>`).join("");
  $("featured").querySelectorAll("[data-path]").forEach((b) => {
    b.onclick = () => { closeStart(); startTour(playable.find((p) => p.id === b.dataset.path).steps); };
  });
  function openStart() { startEl.hidden = false; $("exploreBtn").focus(); }
  function closeStart() {
    startEl.hidden = true;
    try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode: the start screen just shows again */ }
  }
  $("exploreBtn").onclick = closeStart;
  $("pathsBtn").onclick = openStart;  // opening the list does not reset anything
  startEl.addEventListener("click", (ev) => { if (ev.target === startEl) closeStart(); });

  const tourEl = $("tour");
  function startTour(steps) {
    // Remember the exploration, so ending the path puts it back.
    if (!tour) {
      beforeTour = { hidden: new Set(hidden), know: knowOn.checked ? Number(knowRange.value) : null,
                     window: [timeline.window.t0, timeline.window.t1], selected };
    }
    // Guided paths tell the whole story, so they switch "knowable on" off and show every thread.
    if (knowOn.checked) { knowOn.checked = false; applyKnowable(); }
    hidden.clear();
    applyHidden();
    if (view === "list") setView(narrow() ? "list" : "2d");
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
  function endTour({ restore = true } = {}) {
    if (!tour) return;
    tour = null;
    tourEl.hidden = true;
    timeline.setPinned([]);
    if (restore && beforeTour) {
      const b = beforeTour;
      for (const t of b.hidden) hidden.add(t);
      applyHidden();
      if (b.know !== null) { knowOn.checked = true; knowRange.value = String(b.know); applyKnowable(); }
      timeline.setWindow(...b.window);
      timeline.settle();
      select(b.selected, { fly: false });
    }
    beforeTour = null;
  }
  $("tNext").onclick = () => { tourI = Math.min(tour.length - 1, tourI + 1); showTour(); };
  $("tPrev").onclick = () => { tourI = Math.max(0, tourI - 1); showTour(); };
  $("tEnd").onclick = () => endTour();
  addEventListener("keydown", (ev) => {
    if (ev.target === q || ev.defaultPrevented || ev.target.closest?.("input, select, textarea")) return;
    if (ev.key === "Escape") {
      if (!startEl.hidden) closeStart();
      else if (selected) select(null);
      return;
    }
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

  // ---- sharing: the URL holds the selection, time window, view, lanes, hidden threads and "knowable on"
  let restoring = true, saveTimer = 0;
  const DEFAULTS = { view: narrow() ? "list" : "2d", lanes: "threads", scale: "compressed" };
  function currentState() {
    const w = timeline.window;
    const full = w.t0 <= w.limits[0] + 1e-6 && w.t1 >= w.limits[1] - 1e-6;
    return {
      item: selected, window: full ? null : [w.t0, w.t1], view, lanes: mode, hidden: [...hidden],
      scale: timeline.window.compressed ? "compressed" : "even", knowable: knowOn.checked ? knowable() : null,
    };
  }
  function saveState() {
    if (restoring) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        history.replaceState(null, "", location.pathname + location.search + formatState(currentState(), DEFAULTS));
      } catch {
        // Some embedded frames refuse URL changes; the viewer works without them.
      }
    }, 150);
  }
  $("shareBtn").onclick = async () => {
    const url = location.origin + location.pathname + location.search + formatState(currentState(), DEFAULTS);
    let copied = false;
    try { await navigator.clipboard.writeText(url); copied = true; } catch { /* no clipboard: show the link instead */ }
    toast(copied ? "Link copied: it opens this view, including the selected event, period and filters."
      : `Copy this link: ${url}`);
  };
  function toast(text) {
    const t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(t.timer);
    t.timer = setTimeout(() => { t.hidden = true; }, 5000);
  }

  // ---- go
  const state = parseState(location.hash, { items: nodeIds, threads: threadIds, parties, limits: timeline.window.limits });
  if (state.lanes) mode = state.lanes;
  modeButtons.forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.mode === mode)));
  for (const t of state.hidden ?? []) hidden.add(t);
  for (const [id, row] of threadRows) row.classList.toggle("off", hidden.has(id));
  if (state.scale) { timeline.setCompressed(state.scale === "compressed"); syncTime(); }
  rebuild();
  if (hidden.size) timeline.setHidden(hidden);
  bar = new TimeBar($("timebar"), data, timeline);
  setView(state.view ?? view);
  if (state.knowable) {
    knowOn.checked = true;
    knowParty.value = state.knowable.party ?? "";
    knowRange.value = String(state.knowable.t);
    applyKnowable();
  }
  if (state.window) { timeline.setWindow(...state.window); timeline.settle(); }
  bar.draw();
  timeline.start();
  if (state.item) select(state.item, { fly: !state.window });
  updateSubset();
  restoring = false;
  let seen = false;
  try { seen = !!localStorage.getItem(SEEN_KEY); } catch { /* treat as not seen */ }
  if (!location.hash && !seen && !location.search.includes("graph=")) openStart();
  if (location.hash && !Object.keys(state).length) toast("That link's view could not be restored, so the full map is shown.");
  addEventListener("resize", () => renderList());
  window.__viewer = { data, timeline, select };  // handy in the browser console and in tests
}

start();
