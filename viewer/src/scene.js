// The timeline scene: time along a central spine, lanes around it (3D) or stacked (2D).
// Ported from prototype/index.html; the data now comes from graph.json.
//
// How it fits together:
// - A TimeWindow (timescale.js) decides which slice of time fills the spine. Zooming changes
//   the window, not the camera, so the view can go from a century down to hours.
// - computeLanes (layout.js) decides the lanes, from the items in the window: lanes for
//   threads with nothing in view drop away when a zoom settles.
// - chooseVisible (visibility.js) decides which items to draw and label, by importance.
// - build() creates meshes for one lane layout; relayout() moves them for a new window and
//   switches them on or off. relayout() runs on every zoom step, build() only when lanes change.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { LINK_TYPES, esc, yearLabel } from "./data.js";
import { computeLanes } from "./layout.js";
import { TimeWindow, WORLD_LENGTH, ticks } from "./timescale.js";
import { chooseVisible, inWindow, parents, span } from "./visibility.js";

const R = 26;          // 3D lane radius for up to 10 lanes; grows gently beyond that
const ROW = 16;        // 2D gap between lanes
const BG = 0x0B0F14;
const NEUTRAL_LANE = "#6B7686";
const L2 = WORLD_LENGTH / 2;

export class Timeline {
  constructor(stage, labelsEl, data, { onPick, onLaneClick, onWindow, onBuild, leftInset } = {}) {
    this.data = data;
    this.labelsEl = labelsEl;
    this.onPick = onPick ?? (() => {});
    this.onLaneClick = onLaneClick ?? (() => {});
    this.onWindow = onWindow ?? (() => {});
    this.onBuild = onBuild ?? (() => {});
    this.leftInset = leftInset ?? (() => 8);   // 2D lane names start right of this (px)
    this.mode = "threads";
    this.view = "3d";
    this.expanded = new Set();
    this.hidden = new Set();
    this.selected = null;
    this.pinned = [];
    this.knowable = null;       // { t, party } when the "knowable on" slider is on
    this.layout = null;
    this.laneKey = "";
    this.world = null;
    this.nodes = new Map();     // id -> { item, mesh, bar, tethers, el, pos, lanes, dim }
    this.linkObjs = [];
    this.laneLabels = [];
    this.laneLines = {};
    this.tickObjs = [];
    this.fly = null;
    this.parentOf = parents(data);
    this.reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.tmp = new THREE.Vector3();

    const starts = data.nodes.map((n) => n.occurred.range[0]);
    const lo = Math.floor(Math.min(...starts) / 10) * 10 - 2;
    const hi = Math.max(Math.ceil(Math.max(...starts)), new Date().getFullYear()) + 1;
    this.window = new TimeWindow(lo, hi);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(BG);
    stage.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(50, 100, 80);
    this.scene.add(light);
    const spine = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, WORLD_LENGTH, 12),
      new THREE.MeshBasicMaterial({ color: 0xC9C2B2 }));
    spine.rotation.z = Math.PI / 2;
    this.spine = spine;
    this.scene.add(spine);

    this.persp = new THREE.PerspectiveCamera(50, 1, 0.1, 3000);
    this.ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 2000);
    this.#useView("3d");
    this.#bindPointer();
    addEventListener("resize", () => this.resize());
    this.resize();
  }

  get camera() {
    return this.view === "2d" ? this.ortho : this.persp;
  }

  x(t) {
    return this.window.x(t);
  }

  // ---------------------------------------------------------------- views

  setView(view) {
    if (view === this.view) return;
    this.#useView(view);
    this.build();
  }

  #useView(view) {
    this.view = view;
    this.controls?.dispose();
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    if (view === "2d") {
      this.controls.enableRotate = false;
      this.controls.screenSpacePanning = true;
      this.controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
      this.controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_PAN };
      this.scene.fog = null;
    } else {
      this.scene.fog = new THREE.Fog(BG, 260, 640);
    }
    this.spine.visible = view === "3d";
    this.home = view === "2d"
      ? { pos: new THREE.Vector3(0, 0, 500), tgt: new THREE.Vector3(0, 0, 0) }
      : { pos: new THREE.Vector3(-WORLD_LENGTH * 0.15, WORLD_LENGTH * 0.25, WORLD_LENGTH * 0.72),
          tgt: new THREE.Vector3(WORLD_LENGTH * 0.07, 0, 0) };
    this.camera.position.copy(this.home.pos);
    this.controls.target.copy(this.home.tgt);
    if (view === "2d") this.ortho.zoom = 1;
    this.resize();
    if (view === "2d") {
      this.camera.position.copy(this.home.pos);
      this.controls.target.copy(this.home.tgt);
    }
    // Settle the new camera now, so picking and label positions are right before the next frame.
    this.controls.update();
    this.camera.updateMatrixWorld();
  }

  // Where a lane sits: around the spine in 3D, as a row in 2D.
  #lanePositions(lanes) {
    const out = {};
    if (this.view === "2d") {
      lanes.forEach((lane, i) => { out[lane.id] = new THREE.Vector3(0, ((lanes.length - 1) / 2 - i) * ROW, 0); });
    } else {
      const radius = R * Math.max(1, Math.sqrt(lanes.length / 10));
      for (const lane of lanes) out[lane.id] = new THREE.Vector3(0, Math.sin(lane.angle) * radius, Math.cos(lane.angle) * radius);
    }
    return out;
  }

  laneColor(lane) {
    return lane?.color ?? NEUTRAL_LANE;
  }

  // ---------------------------------------------------------------- building

  // Items that could appear in the current window (ignoring importance), for lane layout.
  #windowItems() {
    const items = this.data.nodes.filter((n) => inWindow(n, this.window));
    return items.length ? items : this.data.nodes;
  }

  // (Re)build lanes, nodes and links. Called when the lane set changes, not on every zoom step.
  build(mode = this.mode, expanded = this.expanded) {
    this.mode = mode;
    this.expanded = expanded;
    if (this.world) {
      this.world.traverse((o) => { o.geometry?.dispose(); o.material?.dispose(); });
      this.scene.remove(this.world);
    }
    this.laneLabels.forEach((l) => l.el.remove());
    this.nodes.forEach((n) => n.el.remove());
    this.laneLabels = [];
    this.laneLines = {};
    this.nodes = new Map();
    this.linkObjs = [];
    this.world = new THREE.Group();
    this.scene.add(this.world);

    this.layout = computeLanes({ ...this.data, nodes: this.#windowItems() }, this.mode, this.expanded);
    const { lanes } = this.layout;
    this.laneKey = lanes.map((l) => l.id).join("|");
    const lanePos = this.#lanePositions(lanes);
    const laneById = Object.fromEntries(lanes.map((l) => [l.id, l]));

    for (const lane of lanes) {
      const p = lanePos[lane.id];
      const color = this.laneColor(lane);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-L2, p.y, p.z), new THREE.Vector3(L2, p.y, p.z)]),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: lane.kind === "thread" ? 0.28 : 0.4 }));
      this.world.add(line);
      this.laneLines[lane.id] = line;
      const el = document.createElement("div");
      el.className = "lane";
      el.style.color = color;
      el.textContent = lane.name;
      el.dataset.lane = lane.id;
      // Domains open into their threads, and an open domain's threads close it again.
      if (this.layout.collapsed && lane.domain) {
        el.classList.add("clickable");
        el.title = lane.kind === "domain" ? "Show this domain's threads" : "Collapse this domain";
        el.addEventListener("click", () => this.onLaneClick(lane.domain));
      }
      this.labelsEl.appendChild(el);
      this.laneLabels.push({ el, p: new THREE.Vector3(-L2, p.y, p.z), lane });
    }

    for (const item of this.data.nodes) {
      // Items outside the window may have no lane of their own in this layout; they are
      // hidden until the window moves and the lanes are rebuilt.
      const ls = this.layout.lanesOf(item).filter((k) => lanePos[k]);
      const offset = new THREE.Vector3();
      ls.forEach((k) => offset.add(lanePos[k]));
      if (ls.length) offset.divideScalar(ls.length);
      offset.x = 0;
      const color = new THREE.Color(this.data.threadColor[item.threads[0]] ?? NEUTRAL_LANE);
      const degree = this.data.linksOf.get(item.id).length;
      const size = (1.2 + 0.25 * degree ** 0.8) * (0.8 + 0.08 * (item.importance ?? 3));
      const mesh = new THREE.Mesh(nodeGeometry(item.kind, size),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, roughness: 0.5, transparent: true }));
      mesh.userData.id = item.id;
      this.world.add(mesh);
      // A bar along the lane shows how long the item lasted, once that is visible at this zoom.
      const bar = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }));
      this.world.add(bar);
      const tethers = ls.map((k) => {
        const t = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
          new THREE.LineBasicMaterial({ color: this.laneColor(laneById[k]), transparent: true, opacity: 0.4 }));
        this.world.add(t);
        return { line: t, lane: lanePos[k] };
      });
      const el = document.createElement("div");
      el.className = "lbl";
      el.innerHTML = `<span class="y">${esc(yearLabel(item))}</span>${esc(item.title)}`;
      this.labelsEl.appendChild(el);
      this.nodes.set(item.id, { item, mesh, bar, tethers, el, offset, placed: ls.length > 0,
                                pos: new THREE.Vector3(), dim: false, show: false, label: false });
    }

    for (const link of this.data.links) {
      const color = LINK_TYPES[link.type]?.color ?? "#E6E1D6";
      const contested = link.confidence === "contested";
      const mat = contested
        ? new THREE.LineDashedMaterial({ color, dashSize: 1.4, gapSize: 1.1, transparent: true, opacity: 0.7 })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.6 });
      const line = new THREE.Line(new THREE.BufferGeometry(), mat);
      this.world.add(line);
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.45, 8, 6), new THREE.MeshBasicMaterial({ color }));
      this.world.add(dot);
      this.linkObjs.push({ link, curve: null, mat, line, dot, t: Math.random(), vis: false, contested });
    }
    for (const l of this.laneLabels) {
      l.hide = this.#laneHidden(l.lane);
      this.laneLines[l.lane.id].visible = !l.hide;
    }
    this.relayout();
    this.onBuild(this.layout);
  }

  // Rebuild only if the lanes for the current window differ from the ones drawn.
  settle() {
    const layout = computeLanes({ ...this.data, nodes: this.#windowItems() }, this.mode, this.expanded);
    if (layout.lanes.map((l) => l.id).join("|") !== this.laneKey) this.build();
  }

  // ---------------------------------------------------------------- per-window layout

  relayout() {
    const win = this.window;
    const { visible, labelled } = chooseVisible(this.data, win, {
      hiddenThreads: this.hidden, selected: this.selected, pinned: this.pinned, parentOf: this.parentOf,
      knowable: this.knowable,
    });
    this.visibleIds = visible;
    for (const n of this.nodes.values()) {
      n.show = n.placed && visible.has(n.item.id);
      n.label = n.show && labelled.has(n.item.id);
      n.mesh.visible = n.show;
      n.tethers.forEach((t) => { t.line.visible = n.show; });
      if (!n.show) { n.bar.visible = false; continue; }
      const [a, b] = span(n.item);
      const x = this.x(Math.max(a, win.t0));
      n.pos.set(x, n.offset.y, n.offset.z);
      n.mesh.position.copy(n.pos);
      for (const t of n.tethers) setLine(t.line, n.pos, new THREE.Vector3(x, t.lane.y, t.lane.z));
      const xEnd = this.x(Math.min(Number.isFinite(b) ? b : win.t1, win.t1));
      n.bar.visible = xEnd - x > 3;
      if (n.bar.visible) setLine(n.bar, n.pos, new THREE.Vector3(xEnd, n.pos.y, n.pos.z));
    }
    for (const L of this.linkObjs) {
      const na = this.nodes.get(L.link.from), nb = this.nodes.get(L.link.to);
      L.vis = na.show && nb.show;
      L.line.visible = L.vis;
      if (!L.vis) { L.dot.visible = false; continue; }
      L.curve = this.#curve(L.link.type, na.pos, nb.pos);
      L.line.geometry.setFromPoints(L.curve.getPoints(48));
      L.line.geometry.computeBoundingSphere();
      if (L.contested) L.line.computeLineDistances();
    }
    // Labels are placed in this order each frame; a label that would overlap one already
    // placed is hidden. The selected item goes first, then by importance.
    this.labelOrder = [...this.nodes.values()].filter((n) => n.label)
      .sort((a, b) => (b.item.id === this.selected) - (a.item.id === this.selected)
        || (b.item.importance ?? 3) - (a.item.importance ?? 3));
    this.#buildTicks();
    this.highlight();
    this.onWindow(win);
  }

  #curve(type, A, B) {
    const mid = A.clone().add(B).multiplyScalar(0.5);
    const out = this.view === "2d" ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, mid.y, mid.z);
    if (out.length() < 1) out.set(0, 1, 0);
    out.normalize();
    const dx = Math.abs(A.x - B.x);
    const bend = { led_to: 5 + dx * 0.1, revealed: 9 + dx * 0.16, part_of: 3 + dx * 0.05 }[type] ?? 14 + dx * 0.2;
    if (type === "revealed") out.y += 0.6;
    if (type === "echo") out.y -= this.view === "2d" ? 2.5 : 0.6;
    out.normalize();
    return new THREE.QuadraticBezierCurve3(A.clone(), mid.add(out.multiplyScalar(bend)), B.clone());
  }

  // Ticks, plus the "knowable on" marker when the slider is on.
  #buildTicks() {
    for (const t of this.tickObjs) {
      t.mesh.geometry.dispose();
      t.mesh.material.dispose();
      this.scene.remove(t.mesh);
      t.el?.remove();
    }
    this.tickObjs = [];
    for (const tk of ticks(this.window)) {
      const x = this.x(tk.t);
      let mesh;
      if (this.view === "2d") {
        const h = (this.layout?.lanes.length ?? 1) * ROW / 2 + ROW;
        mesh = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, -h, -1), new THREE.Vector3(x, h, -1)]),
          new THREE.LineBasicMaterial({ color: 0x55606e, transparent: true, opacity: tk.major ? 0.5 : 0.25 }));
      } else {
        mesh = new THREE.Mesh(new THREE.TorusGeometry(tk.major ? 1.4 : 0.9, 0.08, 6, 32),
          new THREE.MeshBasicMaterial({ color: 0x55606e }));
        mesh.rotation.y = Math.PI / 2;
        mesh.position.x = x;
      }
      this.scene.add(mesh);
      const el = document.createElement("div");
      el.className = "yr";
      el.textContent = tk.label;
      this.labelsEl.appendChild(el);
      const h = this.view === "2d" ? -((this.layout?.lanes.length ?? 1) * ROW / 2 + ROW) : 0;
      this.tickObjs.push({ mesh, el, p: new THREE.Vector3(x, h, 0) });
    }
    const k = this.knowable;
    if (k && k.t >= this.window.t0 && k.t <= this.window.t1) {
      const x = this.x(k.t);
      const accent = 0x8FD3FF;
      let mesh, p;
      if (this.view === "2d") {
        const h = (this.layout?.lanes.length ?? 1) * ROW / 2 + ROW;
        mesh = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, -h, -0.5), new THREE.Vector3(x, h, -0.5)]),
          new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.9 }));
        p = new THREE.Vector3(x, h, 0);
      } else {
        const radius = R * Math.max(1, Math.sqrt((this.layout?.lanes.length ?? 1) / 10)) * 1.25;
        mesh = new THREE.Mesh(new THREE.CircleGeometry(radius, 48),
          new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false }));
        mesh.rotation.y = Math.PI / 2;
        mesh.position.x = x;
        p = new THREE.Vector3(x, radius, 0);
      }
      this.scene.add(mesh);
      const el = document.createElement("div");
      el.className = "yr knowable-mark";
      el.textContent = `Knowable on ${k.label}${k.party ? ` · ${k.party}` : ""}`;
      this.labelsEl.appendChild(el);
      this.tickObjs.push({ mesh, el, p });
    }
  }

  // ---------------------------------------------------------------- state changes

  setHidden(hidden) {
    this.hidden = hidden;
    for (const l of this.laneLabels) {
      l.hide = this.#laneHidden(l.lane);
      this.laneLines[l.lane.id].visible = !l.hide;
    }
    this.relayout();
  }

  // A thread lane is hidden with its thread; a collapsed domain lane when all its threads are.
  #laneHidden(lane) {
    if (lane.kind === "thread") return this.hidden.has(lane.id);
    if (lane.threads) return lane.threads.every((t) => this.hidden.has(t));
    return false;
  }

  setWindow(t0, t1) {
    this.window.set(t0, t1);
    this.relayout();
  }

  setPinned(ids) {
    this.pinned = ids;
  }

  // knowable: null to show everything, or { t: decimal year, party: string | null, label }
  setKnowable(knowable) {
    this.knowable = knowable;
    this.relayout();
  }

  // Dim everything not connected to the selected item.
  highlight(id = this.selected) {
    const changed = id !== this.selected;
    this.selected = id;
    if (changed) { this.relayout(); return; }  // the selection is always drawn, so visibility may change
    for (const n of this.nodes.values()) {
      const on = !id || n.item.id === id || this.data.linksOf.get(n.item.id).some((l) => l.from === id || l.to === id);
      n.mesh.material.opacity = on ? 1 : 0.15;
      n.bar.material.opacity = on ? 0.55 : 0.08;
      n.dim = !on;
    }
    for (const L of this.linkObjs) {
      const on = !id || L.link.from === id || L.link.to === id;
      L.mat.opacity = on ? (id ? 1 : 0.6) : 0.05;
      L.dot.visible = on && L.vis;
    }
  }

  // Bring an item into the window if needed, then move the camera to it.
  focus(id) {
    const n = this.nodes.get(id);
    if (!n) return;
    const [a, b] = span(n.item);
    if (!inWindow(n.item, this.window)) {
      const len = Number.isFinite(b) ? b - a : 0;
      if (len > this.window.span) this.window.set(a - len * 0.25, b + len * 0.25);
      else this.window.centre(a);
      this.relayout();
      this.settle();
    }
    const node = this.nodes.get(id);
    if (node?.show) this.flyTo(node.pos);
  }

  flyTo(p, dist = 95) {
    if (this.view === "2d") {
      const d = p.clone().sub(this.controls.target);
      d.z = 0;
      this.fly = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(),
                   p1: this.camera.position.clone().add(d), t1: this.controls.target.clone().add(d) };
      return;
    }
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    this.fly = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(),
                 p1: p.clone().add(dir.multiplyScalar(dist)), t1: p.clone() };
  }

  reset() {
    this.window.reset();
    if (this.view === "2d") {
      this.ortho.zoom = 1;
      this.ortho.updateProjectionMatrix();
    }
    this.fly = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(),
                 p1: this.home.pos.clone(), t1: this.home.tgt.clone() };
    this.relayout();
    this.settle();
  }

  // ---------------------------------------------------------------- input and rendering

  #bindPointer() {
    const el = this.renderer.domElement;
    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let down = null;
    const pick = (ev) => {
      const r = el.getBoundingClientRect();
      mouse.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
      // Positions may have changed since the last frame (a zoom or a view switch).
      this.scene.updateMatrixWorld();
      this.camera.updateMatrixWorld();
      ray.setFromCamera(mouse, this.camera);
      const meshes = [...this.nodes.values()].filter((n) => n.show).map((n) => n.mesh);
      return ray.intersectObjects(meshes)[0]?.object ?? null;
    };
    el.addEventListener("pointerdown", (ev) => { down = [ev.clientX, ev.clientY]; });
    el.addEventListener("pointerup", (ev) => {
      if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 5) return;
      this.onPick(pick(ev)?.userData.id ?? null);
    });
    el.addEventListener("pointermove", (ev) => { el.style.cursor = pick(ev) ? "pointer" : "grab"; });
  }

  resize() {
    const w = innerWidth, h = innerHeight;
    this.renderer.setSize(w, h);
    this.persp.aspect = w / h;
    this.persp.updateProjectionMatrix();
    // In 2D, fit the whole window into the free area right of the legend.
    const inset = Math.min(this.leftInset(), w * 0.5);
    const usable = w - inset - 16;
    const half = (WORLD_LENGTH * 1.04 / 2) * (w / usable);
    Object.assign(this.ortho, { left: -half, right: half, top: half * h / w, bottom: -half * h / w });
    this.ortho.updateProjectionMatrix();
    const perUnit = w / (2 * half);
    const cx = (w / 2 - (inset + usable / 2)) / perUnit;
    if (this.home && this.view === "2d") {
      this.home.pos.x = cx;
      this.home.tgt.x = cx;
    }
  }

  #project(p, el, opacity) {
    const v = this.tmp.copy(p).project(this.camera);
    if (v.z > 1 || Math.abs(v.x) > 1.2 || Math.abs(v.y) > 1.2) {
      el.style.display = "none";
      return false;
    }
    el.style.display = "";
    el.style.left = `${(v.x * 0.5 + 0.5) * innerWidth}px`;
    el.style.top = `${(-v.y * 0.5 + 0.5) * innerHeight}px`;
    if (opacity !== undefined) el.style.opacity = opacity;
    return true;
  }

  start() {
    const tick = () => {
      requestAnimationFrame(tick);
      if (this.fly) {
        const f = this.fly;
        f.t = Math.min(1, f.t + (this.reduceMotion ? 1 : 0.035));
        const s = f.t * f.t * (3 - 2 * f.t);
        this.camera.position.lerpVectors(f.p0, f.p1, s);
        this.controls.target.lerpVectors(f.t0, f.t1, s);
        if (f.t >= 1) this.fly = null;
      }
      this.controls.update();
      for (const L of this.linkObjs) {
        if (!L.dot.visible) continue;
        if (!this.reduceMotion) L.t = (L.t + 0.004) % 1;
        L.dot.position.copy(L.curve.getPoint(this.reduceMotion ? 0.5 : L.t));
      }
      const flat = this.view === "2d";
      const inset = flat ? this.leftInset() : 0;
      for (const n of this.nodes.values()) if (!n.label) n.el.style.display = "none";
      const placed = [];
      for (const n of this.labelOrder ?? []) {
        let o = flat ? 1 : Math.max(0, Math.min(1, (260 - this.camera.position.distanceTo(n.pos)) / 110));
        if (n.dim) o *= 0.08;
        if (n.item.id === this.selected) o = 1;
        if (o < 0.05 || !this.#project(n.pos, n.el, o)) { n.el.style.display = "none"; continue; }
        n.w ??= n.el.offsetWidth;  // label text never changes, so measure once
        const x = parseFloat(n.el.style.left) + 16, y = parseFloat(n.el.style.top);
        const box = [x, y - 8, x + n.w, y + 8];
        if (placed.some((p) => box[0] < p[2] && box[2] > p[0] && box[1] < p[3] && box[3] > p[1])) {
          n.el.style.display = "none";
          continue;
        }
        placed.push(box);
        n.el.style.fontWeight = n.item.id === this.selected ? 600 : 500;
      }
      for (const l of this.laneLabels) {
        if (l.hide) { l.el.style.display = "none"; continue; }
        if (flat) {
          // In 2D, lane names sit at the left edge of the screen, on their row.
          const v = this.tmp.copy(l.p).project(this.camera);
          const visible = Math.abs(v.y) <= 1.05;
          l.el.style.display = visible ? "" : "none";
          l.el.style.left = `${inset}px`;
          l.el.style.top = `${(-v.y * 0.5 + 0.5) * innerHeight}px`;
          l.el.classList.add("row-label");
          continue;
        }
        this.#project(l.p, l.el, 0.9);
        // Put the text on the lane's outer side, so labels spread outwards instead of
        // running back across the circle.
        const lane = this.tmp.copy(l.p).project(this.camera).x;
        const spine = this.tmp.set(l.p.x, 0, 0).project(this.camera).x;
        l.el.classList.toggle("right", lane > spine);
      }
      for (const t of this.tickObjs) this.#project(t.p, t.el);
      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }
}

function setLine(line, a, b) {
  line.geometry.setFromPoints([a, b]);
  line.geometry.computeBoundingSphere();
}

// Events are spheres, signals octahedra, decisions boxes, so kinds read at a glance.
function nodeGeometry(kind, size) {
  if (kind === "signal") return new THREE.OctahedronGeometry(size * 1.2);
  if (kind === "decision") return new THREE.BoxGeometry(size * 1.5, size * 1.5, size * 1.5);
  return new THREE.SphereGeometry(size, 20, 14);
}
