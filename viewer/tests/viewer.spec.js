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
  // Wait for the camera to settle, then click where the node is drawn.
  const point = await page.evaluate(async () => {
    const { timeline } = window.__viewer;
    const node = timeline.nodes.get("russian-invasion-of-ukraine-2022");
    const v = node.pos.clone().project(timeline.camera);
    return { x: (v.x * 0.5 + 0.5) * innerWidth, y: (-v.y * 0.5 + 0.5) * innerHeight };
  });
  await page.mouse.click(point.x, point.y);
  await expect(page.locator("#detail h2")).toHaveText("Russia invades Ukraine");
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
    await expect(page.locator("#count")).toHaveText("400 events · 500 links");
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
      timeline.camera.position.set(timeline.x(timeline.y0) - 120, 0, 0);
      timeline.controls.target.set(0, 0, 0);
    });
    const label = page.locator('.lane[data-lane="domain:science"]');
    await expect(label).toBeVisible();
    await label.click();
    await expect(page.locator(".lane")).toHaveCount(5 + 5);
  });
});
