import { LINK_TYPES, esc, loadGraph, yearLabel } from "./data.js";
import { renderDetail } from "./panel.js";
import { Timeline } from "./scene.js";

const $ = (id) => document.getElementById(id);

async function start() {
  let data;
  try {
    data = await loadGraph("graph.json");
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

  const timeline = new Timeline($("stage"), $("labels"), data, {
    onPick: (id) => select(id),
  });

  // ---- header counts and draft banner
  $("count").textContent = `${data.nodes.length} events · ${data.links.length} links`;
  const total = Object.values(data.reviewCounts).reduce((a, b) => a + b, 0);
  const unverified = data.reviewCounts.unverified ?? 0;
  if (unverified) {
    $("draft").textContent = `Draft data: ${unverified} of ${total} items and links are unverified. ` +
      "Open any item to see its review status and open questions.";
    $("draft").hidden = false;
  }

  // ---- thread toggles
  for (const t of data.graph.threads) {
    if (!data.nodes.some((n) => n.threads.includes(t.id))) continue;
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
      timeline.build(b.dataset.mode);
      timeline.highlight(selected);
      if (selected) timeline.focus(selected);
    };
  }

  // ---- selection and detail panel
  const detail = $("detail");
  function select(id, { fly = true } = {}) {
    selected = id && data.byId.has(id) && timeline.nodes.has(id) ? id : null;
    timeline.highlight(selected);
    history.replaceState(null, "", selected ? `#${selected}` : location.pathname + location.search);
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
    $("tTxt").textContent = `${tourI + 1} / ${tour.length} · ${yearLabel(item)} ${item.title}`;
    select(item.id);
  }
  function endTour() { tour = null; tourEl.hidden = true; }
  $("tNext").onclick = () => { tourI = Math.min(tour.length - 1, tourI + 1); showTour(); };
  $("tPrev").onclick = () => { tourI = Math.max(0, tourI - 1); showTour(); };
  $("tEnd").onclick = () => { endTour(); select(null); };
  addEventListener("keydown", (ev) => {
    if (!tour || ev.target === q) return;
    if (ev.key === "ArrowRight") $("tNext").click();
    if (ev.key === "ArrowLeft") $("tPrev").click();
  });

  // ---- go
  timeline.build("threads");
  timeline.start();
  const fromHash = decodeURIComponent(location.hash.slice(1));
  if (fromHash) select(fromHash);
  window.__viewer = { data, timeline, select };  // handy in the browser console and in tests
}

start();
