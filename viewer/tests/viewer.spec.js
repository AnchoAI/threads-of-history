import { test, expect } from "@playwright/test";

// These run against the real dist/graph.json, so they check the viewer and the data together.

async function open(page, hash = "") {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // Network noise (e.g. web fonts blocked in a sandbox) is not a viewer bug; script errors are.
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) errors.push(m.text());
  });
  await page.goto("/" + hash);
  await expect(page.locator("#count")).toContainText("events");
  return errors;
}

async function graphCounts(page) {
  return page.evaluate(() => ({
    nodes: window.__viewer.data.nodes.length,
    links: window.__viewer.data.links.length,
  }));
}

test("loads the graph, draws a canvas and shows the draft banner", async ({ page }) => {
  const errors = await open(page);
  const { nodes, links } = await graphCounts(page);
  expect(nodes).toBeGreaterThan(0);
  await expect(page.locator("#count")).toHaveText(`${nodes} events · ${links} links`);
  await expect(page.locator("#stage canvas")).toBeVisible();
  await expect(page.locator("#draft")).toContainText("unverified");
  const lanes = await page.evaluate(() => window.__viewer.timeline.layout.lanes.length);
  await expect(page.locator(".lane")).toHaveCount(lanes);
  await expect(page.locator("#tours button")).toHaveCount(3);
  expect(errors).toEqual([]);
});

test("search opens an item with its review status, sources and connections", async ({ page }) => {
  await open(page);
  await page.fill("#q", "missile crisis");
  await page.locator("#results button", { hasText: "Cuban Missile Crisis" }).click();
  const detail = page.locator("#detail");
  await expect(detail).toBeVisible();
  await expect(detail.locator("h2")).toHaveText("Cuban Missile Crisis");
  await expect(detail.locator(".badge")).toHaveText("Unverified");
  await expect(detail).toContainText("Open questions");
  await expect(detail).toContainText("Known to US government");
  await expect(detail.locator("a", { hasText: "Cuban Missile Crisis" })).toHaveAttribute("href", /wikipedia\.org/);
  await expect(page).toHaveURL(/#cuban-missile-crisis-1962$/);

  // Following a connection moves the panel to the other item.
  await detail.locator(".lk", { hasText: "Moscow–Washington hotline" }).click();
  await expect(detail.locator("h2")).toHaveText("Moscow–Washington hotline");

  await detail.locator("#closeD").click();
  await expect(detail).toBeHidden();
});

test("a link in the URL opens that item", async ({ page }) => {
  await open(page, "#first-soviet-atomic-test-1949");
  await expect(page.locator("#detail h2")).toHaveText("First Soviet atomic test");
  await expect(page.locator("#detail")).toContainText("Became public: September 1949");
});

test("clicking a node on the canvas selects it", async ({ page }) => {
  await open(page);
  const node = await isolatedNode(page);
  expect(node).not.toBeNull();
  await page.mouse.click(node.x, node.y);
  await expect(page.locator("#detail h2")).toHaveText(node.title);
});

test("lanes can be arranged by thread, region or domain", async ({ page }) => {
  await open(page);
  await expect(page.locator(".lane", { hasText: "Cuba" })).toHaveCount(1);
  await page.click('.seg button[data-mode="regions"]');
  await expect(page.locator(".lane", { hasText: "Americas" })).toHaveCount(1);
  await page.click('.seg button[data-mode="domains"]');
  await expect(page.locator(".lane", { hasText: "Politics & conflict" })).toHaveCount(1);
  await expect(page.locator('.seg button[data-mode="domains"]')).toHaveAttribute("aria-pressed", "true");
});

test("hiding a thread hides items that are only on that thread", async ({ page }) => {
  await open(page);
  const visible = () => page.evaluate(() =>
    window.__viewer.timeline.nodes.get("cuban-revolution-1959").mesh.visible);
  expect(await visible()).toBe(true);
  await page.locator('#threadList .row[data-thread="cuba"]').click();
  await expect(page.locator('#threadList .row[data-thread="cuba"]')).toHaveClass(/off/);
  expect(await visible()).toBe(false);
});

test("guided paths step with the arrow keys", async ({ page }) => {
  await open(page);
  await page.locator("#tours button", { hasText: "Cuba → Nord Stream" }).click();
  await expect(page.locator("#tour")).toBeVisible();
  await expect(page.locator("#tTxt")).toContainText("1 / 12");
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#tTxt")).toContainText("2 / 12");
  await expect(page.locator("#detail h2")).toHaveText("Bay of Pigs");
  await page.click("#tEnd");
  await expect(page.locator("#tour")).toBeHidden();
});

test("text from the data is escaped", async ({ page }) => {
  await open(page);
  const out = await page.evaluate(async () => {
    const { esc, safeUrl } = await import("/src/data.js");
    return [esc('<img src=x onerror="alert(1)">'), safeUrl("javascript:alert(1)"), safeUrl("https://example.org/a")];
  });
  expect(out).toEqual(["&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", null, "https://example.org/a"]);
});

test("a missing graph.json shows how to build it", async ({ page }) => {
  await page.route("**/graph.json", (route) => route.fulfill({ status: 404, body: "" }));
  await page.goto("/");
  await expect(page.locator("#error")).toContainText("npm run data");
});

// ---------------------------------------------------------------- many threads (fake fixture)

test.describe("with 40 threads (fake stress data)", () => {
  const STRESS = "?graph=tests/fixtures/stress-graph.json";

  test("domains collapse to one lane each and open on click", async ({ page }) => {
    const errors = await open(page, STRESS);
    await expect(page.locator("#count")).toHaveText("407 events · 506 links");
    await expect(page.locator(".lane")).toHaveCount(6);
    await expect(page.locator("#laneHint")).toBeVisible();

    // Open a domain from the legend: its threads get lanes, the rest stay collapsed.
    await page.locator('#threadList .dom[data-domain="economy"]').click();
    await expect(page.locator(".lane")).toHaveCount(8 + 5);
    await expect(page.locator('#threadList .dom[data-domain="economy"]')).toHaveAttribute("aria-expanded", "true");

    // Opening another domain closes the first.
    await page.locator('#threadList .dom[data-domain="sports"]').click();
    await expect(page.locator(".lane")).toHaveCount(3 + 5);
    await page.locator('#threadList .dom[data-domain="sports"]').click();
    await expect(page.locator(".lane")).toHaveCount(6);
    expect(errors).toEqual([]);
  });

  test("clicking a domain's lane label opens it", async ({ page }) => {
    await open(page, STRESS);
    await page.evaluate(() => {
      // Point the camera down the spine so every lane label is on screen.
      const { timeline } = window.__viewer;
      timeline.camera.position.set(timeline.x(timeline.window.t0) - 120, 0, 0);
      timeline.controls.target.set(0, 0, 0);
    });
    const label = page.locator('.lane[data-lane="domain:science"]');
    await expect(label).toBeVisible();
    await label.click();
    await expect(page.locator(".lane")).toHaveCount(5 + 5);
  });
});

// ---------------------------------------------------------------- zooming and 2D

// The drawn node furthest (on screen) from any other drawn node, so a click on it cannot land
// on a neighbour. Picking a fixed event would break whenever new data puts something next to it.
const isolatedNode = (page) => page.evaluate(() => {
  const { timeline } = window.__viewer;
  timeline.scene.updateMatrixWorld();
  timeline.camera.updateMatrixWorld();
  const pts = [...timeline.nodes.values()].filter((n) => n.show).map((n) => {
    const v = n.pos.clone().project(timeline.camera);
    return { id: n.item.id, title: n.item.title, x: (v.x * 0.5 + 0.5) * innerWidth, y: (-v.y * 0.5 + 0.5) * innerHeight };
  }).filter((p) => p.x > 300 && p.x < innerWidth - 400 && p.y > 40 && p.y < innerHeight - 140);
  let best = null, bestD = -1;
  for (const p of pts) {
    const d = Math.min(...pts.filter((q) => q !== p).map((q) => Math.hypot(p.x - q.x, p.y - q.y)));
    if (d > bestD) { best = p; bestD = d; }
  }
  return best;
});

const windowSpan = (page) => page.evaluate(() => window.__viewer.timeline.window.span);
const shown = (page) => page.evaluate(() => [...window.__viewer.timeline.nodes.values()].filter((n) => n.show).length);

test("the keyboard zooms and moves the time window", async ({ page }) => {
  await open(page);
  const full = await windowSpan(page);
  const range = page.locator("#timebar .range");
  const before = await range.textContent();
  await page.locator("body").press("+");
  await page.locator("body").press("+");
  expect(await windowSpan(page)).toBeCloseTo(full * 0.49, 1);
  await expect(range).not.toHaveText(before);
  await page.locator("body").press("ArrowLeft");
  await page.locator("body").press("0");
  expect(await windowSpan(page)).toBeCloseTo(full, 5);
});

test("dragging across the time strip picks a period; double-click shows everything", async ({ page }) => {
  await open(page);
  const box = await page.locator("#timebar canvas").boundingBox();
  const y = box.y + box.height / 2;
  await page.mouse.move(box.x + box.width * 0.4, y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5, y, { steps: 5 });
  await page.mouse.up();
  const span = await windowSpan(page);
  const full = await page.evaluate(() => { const [a, b] = window.__viewer.timeline.window.limits; return b - a; });
  expect(span).toBeGreaterThan(full * 0.08);
  expect(span).toBeLessThan(full * 0.12);
  await page.locator("#timebar canvas").dblclick();
  expect(await windowSpan(page)).toBeCloseTo(full, 5);
});

test("selecting an item outside the window brings it into view", async ({ page }) => {
  await open(page);
  await page.evaluate(() => { const t = window.__viewer.timeline; t.setWindow(2010, 2020); t.settle(); });
  await page.fill("#q", "Cuban Revolution");
  await page.locator("#results button", { hasText: "Cuban Revolution" }).click();
  const w = await page.evaluate(() => { const { t0, t1 } = window.__viewer.timeline.window; return [t0, t1]; });
  expect(w[0]).toBeLessThanOrEqual(1959.1);
  expect(w[1]).toBeGreaterThanOrEqual(1959.1);
  expect(await page.evaluate(() => window.__viewer.timeline.nodes.get("cuban-revolution-1959").show)).toBe(true);
});

test("the 2D view stacks lanes as rows and still picks nodes", async ({ page }) => {
  await open(page);
  await page.click('.seg button[data-view="2d"]');
  await expect(page.locator('.seg button[data-view="2d"]')).toHaveAttribute("aria-pressed", "true");
  const info = await page.evaluate(() => {
    const t = window.__viewer.timeline;
    const ys = [...new Set(Object.values(t.laneLines).map((l) => l.geometry.attributes.position.getY(0)))];
    const zs = Object.values(t.laneLines).map((l) => l.geometry.attributes.position.getZ(0));
    return { ortho: t.camera.isOrthographicCamera, rows: ys.length, lanes: t.layout.lanes.length, flat: zs.every((z) => z === 0) };
  });
  expect(info).toEqual({ ortho: true, rows: info.lanes, lanes: info.lanes, flat: true });
  const node = await isolatedNode(page);
  expect(node).not.toBeNull();
  await page.mouse.click(node.x, node.y);
  await expect(page.locator("#detail h2")).toHaveText(node.title);
});

test.describe("zooming with many items (fake stress data)", () => {
  const STRESS = "?graph=tests/fixtures/stress-graph.json";

  test("zoomed out, only the most important items and labels are drawn", async ({ page }) => {
    await open(page, STRESS);
    expect(await shown(page)).toBeLessThanOrEqual(120);
    const labels = await page.evaluate(() => [...window.__viewer.timeline.nodes.values()].filter((n) => n.label).length);
    expect(labels).toBeLessThanOrEqual(31);
  });

  test("zooming in on a parent event opens its parts", async ({ page }) => {
    await open(page, STRESS);
    const partsShown = () => page.evaluate(() =>
      [...window.__viewer.timeline.nodes.values()].filter((n) => n.item.id.startsWith("test-crisis-day-") && n.show).length);
    expect(await partsShown()).toBe(0);
    await page.evaluate(() => { const t = window.__viewer.timeline; t.setWindow(1962.7, 1963.0); t.settle(); });
    expect(await partsShown()).toBe(6);
    await expect(page.locator("#timebar .range")).toHaveText(/1962/);
  });
});

// ---------------------------------------------------------------- knowable on

const nodeShown = (page, id) => page.evaluate((i) => window.__viewer.timeline.nodes.get(i).show, id);

test("knowable on: starts at the selected item's date and hides hindsight", async ({ page }) => {
  await open(page, "#cuban-missile-crisis-1962");
  await expect(page.locator("#detail h2")).toHaveText("Cuban Missile Crisis");
  await page.check("#knowOn");
  await expect(page.locator("#knowControls")).toBeVisible();
  await expect(page.locator("#knowDate")).toHaveValue(/^1962-10-/);
  await expect(page.locator("#knowCount")).toContainText("known publicly by");
  await expect(page.locator(".knowable-mark")).toContainText("Knowable on");

  // The 2022 invasion it is compared with was not knowable in 1962, in the scene or the panel.
  expect(await nodeShown(page, "russian-invasion-of-ukraine-2022")).toBe(false);
  await expect(page.locator("#detail .lk", { hasText: "Russia invades Ukraine" })).toHaveCount(0);
  await expect(page.locator("#detail .withheld")).toContainText("not yet knowable");

  // Switching it off brings everything back.
  await page.uncheck("#knowOn");
  await expect(page.locator("#knowControls")).toBeHidden();
  await expect(page.locator("#detail .lk", { hasText: "Russia invades Ukraine" })).toHaveCount(1);
});

test("knowable on: a secret agreement appears only once it was published", async ({ page }) => {
  await open(page);
  await page.evaluate(() => { const t = window.__viewer.timeline; t.setWindow(1910, 1925); t.settle(); });
  await page.check("#knowOn");
  await page.fill("#knowDate", "1917-01-01");
  await page.locator("#knowDate").dispatchEvent("change");
  expect(await nodeShown(page, "sykes-picot-agreement-1916")).toBe(false);
  await page.fill("#knowDate", "1918-01-01");
  await page.locator("#knowDate").dispatchEvent("change");
  expect(await nodeShown(page, "sykes-picot-agreement-1916")).toBe(true);
});

test("knowable on: search and guided paths respect it", async ({ page }) => {
  await open(page);
  await page.check("#knowOn");
  await page.fill("#knowDate", "1950-01-01");
  await page.locator("#knowDate").dispatchEvent("change");
  await page.fill("#q", "Ukraine");
  await expect(page.locator("#results button", { hasText: "Russia invades Ukraine" })).toHaveCount(0);
  await page.fill("#q", "");
  await expect(page.locator("#knowParty option", { hasText: "to US government" })).toHaveCount(1);
  // Guided paths tell the whole story, so starting one switches the filter off.
  await page.locator("#tours button").first().click();
  await expect(page.locator("#knowOn")).not.toBeChecked();
});
