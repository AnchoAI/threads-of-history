// The 3D timeline: time along a central spine, lanes arranged in a ring around it.
// Ported from prototype/index.html; the data now comes from graph.json.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { LINK_TYPES, esc, yearLabel } from "./data.js";
import { computeLanes } from "./layout.js";

const XS = 4;       // world units per year (fixed for now; a stretchable axis comes later)
const R = 26;       // lane radius for up to 10 lanes; grows gently beyond that
const BG = 0x0B0F14;
const NEUTRAL_LANE = "#6B7686";

export class Timeline {
  constructor(stage, labelsEl, data, { onPick, onLaneClick } = {}) {
    this.data = data;
    this.labelsEl = labelsEl;
    this.onPick = onPick ?? (() => {});
    this.onLaneClick = onLaneClick ?? (() => {});
    this.mode = "threads";
    this.expanded = new Set();  // domains opened into their threads (when lanes are collapsed)
    this.layout = null;
    this.hidden = new Set();
    this.selected = null;
    this.fly = null;
    this.world = null;
    this.nodes = new Map();   // id -> { item, mesh, tethers, el, pos, dim }
    this.linkObjs = [];
    this.laneLabels = [];
    this.laneLines = {};
    this.reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

    const years = data.nodes.map((n) => n.occurred.range[0]);
    this.y0 = Math.floor(Math.min(...years) / 10) * 10 - 2;
    this.y1 = Math.max(Math.ceil(Math.max(...years)), new Date().getFullYear()) + 1;
    this.xMid = (this.y0 + this.y1) / 2;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(BG);
    stage.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(BG, 260, 640);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 3000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    const span = (this.y1 - this.y0) * XS;
    this.home = {
      pos: new THREE.Vector3(-span * 0.15, span * 0.25, span * 0.72),
      tgt: new THREE.Vector3(span * 0.07, 0, 0),
    };
    this.camera.position.copy(this.home.pos);
    this.controls.target.copy(this.home.tgt);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const light = new THREE.DirectionalLight(0xffffff, 1.2);
    light.position.set(50, 100, 80);
    this.scene.add(light);

    this.#buildSpine();
    this.#bindPointer();
    addEventListener("resize", () => this.resize());
    this.resize();
  }

  x(year) {
    return (year - this.xMid) * XS;
  }

  #buildSpine() {
    const xa = this.x(this.y0), xb = this.x(this.y1);
    const spine = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, xb - xa, 12),
      new THREE.MeshBasicMaterial({ color: 0xC9C2B2 }));
    spine.rotation.z = Math.PI / 2;
    spine.position.x = (xa + xb) / 2;
    this.scene.add(spine);
    this.staticLabels = [];
    for (let y = Math.ceil(this.y0 / 5) * 5; y <= this.y1; y += 5) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(y % 10 === 0 ? 1.4 : 0.9, 0.08, 6, 32),
        new THREE.MeshBasicMaterial({ color: 0x55606e }));
      ring.rotation.y = Math.PI / 2;
      ring.position.x = this.x(y);
      this.scene.add(ring);
      if (y % 10 === 0) {
        const el = document.createElement("div");
        el.className = "yr";
        el.textContent = y;
        this.labelsEl.appendChild(el);
        this.staticLabels.push({ el, p: new THREE.Vector3(this.x(y), 0, 0) });
      }
    }
  }

  laneColor(lane) {
    return lane?.color ?? NEUTRAL_LANE;
  }

  // (Re)build lanes, nodes and links for the current lane arrangement.
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

    const xa = this.x(this.y0), xb = this.x(this.y1);
    this.layout = computeLanes(this.data, this.mode, this.expanded);
    const { lanes } = this.layout;
    const radius = R * Math.max(1, Math.sqrt(lanes.length / 10));
    const dir = {};
    const laneById = {};
    for (const lane of lanes) {
      laneById[lane.id] = lane;
      dir[lane.id] = new THREE.Vector3(0, Math.sin(lane.angle), Math.cos(lane.angle));
      const p = dir[lane.id].clone().multiplyScalar(radius);
      const color = this.laneColor(lane);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(xa, p.y, p.z), new THREE.Vector3(xb, p.y, p.z)]),
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
      this.laneLabels.push({ el, p: new THREE.Vector3(xa, p.y, p.z), lane });
    }

    for (const item of this.data.nodes) {
      const x = this.x(item.occurred.range[0]);
      const ls = this.layout.lanesOf(item).filter((k) => dir[k]);
      const v = new THREE.Vector3();
      ls.forEach((k) => v.add(dir[k]));
      if (ls.length) v.divideScalar(ls.length);
      const pos = new THREE.Vector3(x, v.y * radius, v.z * radius);
      const color = new THREE.Color(this.data.threadColor[item.threads[0]] ?? NEUTRAL_LANE);
      const degree = this.data.linksOf.get(item.id).length;
      const size = (1.2 + 0.25 * degree ** 0.8) * (0.8 + 0.08 * (item.importance ?? 3));
      const mesh = new THREE.Mesh(nodeGeometry(item.kind, size),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, roughness: 0.5, transparent: true }));
      mesh.position.copy(pos);
      mesh.userData.id = item.id;
      this.world.add(mesh);
      const tethers = ls.map((k) => {
        const lp = dir[k].clone().multiplyScalar(radius);
        lp.x = x;
        const t = new THREE.Line(new THREE.BufferGeometry().setFromPoints([pos, lp]),
          new THREE.LineBasicMaterial({ color: this.laneColor(laneById[k]), transparent: true, opacity: 0.4 }));
        this.world.add(t);
        return t;
      });
      const el = document.createElement("div");
      el.className = "lbl";
      el.innerHTML = `<span class="y">${esc(yearLabel(item))}</span>${esc(item.title)}`;
      this.labelsEl.appendChild(el);
      this.nodes.set(item.id, { item, mesh, tethers, el, pos, dim: false });
    }

    for (const link of this.data.links) {
      const A = this.nodes.get(link.from).pos, B = this.nodes.get(link.to).pos;
      const mid = A.clone().add(B).multiplyScalar(0.5);
      const out = new THREE.Vector3(0, mid.y, mid.z);
      if (out.length() < 1) out.set(0, 1, 0);
      out.normalize();
      const dx = Math.abs(A.x - B.x);
      const bend = { led_to: 5 + dx * 0.1, revealed: 9 + dx * 0.16, part_of: 3 + dx * 0.05 }[link.type] ?? 14 + dx * 0.2;
      if (link.type === "revealed") out.y += 0.6;
      if (link.type === "echo") out.y -= 0.6;
      out.normalize();
      const curve = new THREE.QuadraticBezierCurve3(A, mid.clone().add(out.multiplyScalar(bend)), B);
      const color = LINK_TYPES[link.type]?.color ?? "#E6E1D6";
      const contested = link.confidence === "contested";
      const mat = contested
        ? new THREE.LineDashedMaterial({ color, dashSize: 1.4, gapSize: 1.1, transparent: true, opacity: 0.7 })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.6 });
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(60)), mat);
      if (contested) line.computeLineDistances();
      this.world.add(line);
      const dot = new THREE.Mesh(new THREE.SphereGeometry(0.45, 8, 6), new THREE.MeshBasicMaterial({ color }));
      this.world.add(dot);
      this.linkObjs.push({ link, curve, mat, line, dot, t: Math.random(), vis: true });
    }
    this.applyVisibility();
    this.highlight();
  }

  setHidden(hidden) {
    this.hidden = hidden;
    this.applyVisibility();
    this.highlight();
  }

  isVisible(item) {
    return item.threads.some((t) => !this.hidden.has(t));
  }

  // A thread lane is hidden with its thread; a collapsed domain lane when all its threads are.
  laneHidden(lane) {
    if (lane.kind === "thread") return this.hidden.has(lane.id);
    if (lane.threads) return lane.threads.every((t) => this.hidden.has(t));
    return false;
  }

  applyVisibility() {
    for (const l of this.laneLabels) {
      l.hide = this.laneHidden(l.lane);
      this.laneLines[l.lane.id].visible = !l.hide;
    }
    for (const n of this.nodes.values()) {
      const v = this.isVisible(n.item);
      n.mesh.visible = v;
      n.tethers.forEach((t) => { t.visible = v; });
    }
    for (const L of this.linkObjs) {
      L.vis = this.isVisible(L.link.a) && this.isVisible(L.link.b);
      L.line.visible = L.vis;
    }
  }

  // Dim everything not connected to the selected item.
  highlight(id = this.selected) {
    this.selected = id;
    for (const n of this.nodes.values()) {
      const on = !id || n.item.id === id || this.data.linksOf.get(n.item.id).some((l) => l.from === id || l.to === id);
      n.mesh.material.opacity = on ? 1 : 0.15;
      n.dim = !on;
    }
    for (const L of this.linkObjs) {
      const on = !id || L.link.from === id || L.link.to === id;
      L.mat.opacity = on ? (id ? 1 : 0.6) : 0.05;
      L.dot.visible = on && L.vis;
    }
  }

  focus(id) {
    const n = this.nodes.get(id);
    if (n) this.flyTo(n.pos);
  }

  flyTo(p, dist = 95) {
    const dir = this.camera.position.clone().sub(this.controls.target).normalize();
    this.fly = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(),
                 p1: p.clone().add(dir.multiplyScalar(dist)), t1: p.clone() };
  }

  reset() {
    this.fly = { t: 0, p0: this.camera.position.clone(), t0: this.controls.target.clone(),
                 p1: this.home.pos.clone(), t1: this.home.tgt.clone() };
  }

  #bindPointer() {
    const el = this.renderer.domElement;
    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let down = null;
    const pick = (ev) => {
      const r = el.getBoundingClientRect();
      mouse.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mouse, this.camera);
      const meshes = [...this.nodes.values()].map((n) => n.mesh).filter((m) => m.visible);
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
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  #project(p, el, opacity) {
    const v = this.tmp.copy(p).project(this.camera);
    if (v.z > 1 || Math.abs(v.x) > 1.2 || Math.abs(v.y) > 1.2) {
      el.style.display = "none";
      return;
    }
    el.style.display = "";
    el.style.left = `${(v.x * 0.5 + 0.5) * innerWidth}px`;
    el.style.top = `${(-v.y * 0.5 + 0.5) * innerHeight}px`;
    if (opacity !== undefined) el.style.opacity = opacity;
  }

  start() {
    this.tmp = new THREE.Vector3();
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
      for (const n of this.nodes.values()) {
        if (!n.mesh.visible) { n.el.style.display = "none"; continue; }
        const d = this.camera.position.distanceTo(n.pos);
        let o = Math.max(0, Math.min(1, (230 - d) / 110));
        if (n.dim) o *= 0.08;
        if (n.item.id === this.selected) o = 1;
        this.#project(n.pos, n.el, o);
        n.el.style.fontWeight = n.item.id === this.selected ? 600 : 500;
      }
      for (const l of this.laneLabels) {
        if (l.hide) { l.el.style.display = "none"; continue; }
        this.#project(l.p, l.el, 0.9);
        // Put the text on the lane's outer side, so labels spread outwards instead of
        // running back across the circle.
        const lane = this.tmp.copy(l.p).project(this.camera).x;
        const spine = this.tmp.set(l.p.x, 0, 0).project(this.camera).x;
        l.el.classList.toggle("right", lane > spine);
      }
      for (const y of this.staticLabels) this.#project(y.p, y.el);
      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }
}

// Events are spheres, signals octahedra, decisions boxes, so kinds read at a glance.
function nodeGeometry(kind, size) {
  if (kind === "signal") return new THREE.OctahedronGeometry(size * 1.2);
  if (kind === "decision") return new THREE.BoxGeometry(size * 1.5, size * 1.5, size * 1.5);
  return new THREE.SphereGeometry(size, 20, 14);
}
