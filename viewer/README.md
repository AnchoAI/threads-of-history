# Viewer

A 3D view of `dist/graph.json`, built with [Vite](https://vite.dev) and [three.js](https://threejs.org). It is one lens on the data; other views can read the same file.

## Run it

```sh
cd viewer
npm install          # once
npm run data         # rebuild ../dist/graph.json from ../data (runs tools/build.py)
npm run dev          # open the printed URL, usually http://localhost:5173
```

Rerun `npm run data` after editing anything in `data/`, then reload the page.

`npm run build` writes a static site to `viewer/build/`, with `graph.json` copied in. Any static host can serve it.

## What it does

- Time runs along a central spine. Lanes around it are threads, regions or domains (the toggle top left). Items on several lanes sit between them.
- In thread mode, each domain gets its own slice of the circle, and threads that share many items and links sit next to each other. An item that sits near the spine crosses domains.
- When there are more than 16 threads, each domain collapses into one lane. Click a domain, in the legend or on its lane label, to open its threads; opening one closes the others. This keeps the circle readable however many threads the data grows to.
- Lane labels sit on the outer side of their lane, so they spread outwards instead of overlapping.
- **Zooming time.** The strip along the bottom shows how many items fall in each period. Drag across it to pick a period, drag the highlighted window to move it, scroll over it to zoom, and double-click to show everything. With the strip focused, or with no guided path running, ← → move the window, + and − zoom, and 0 shows everything. The window goes from the whole timeline down to six hours, and the tick marks adapt from 20-year steps to hours.
- **Importance decides what is drawn.** In any window, the 120 most important items are drawn (importance first, then number of links) and about 30 get labels; labels that would overlap are hidden. The selected item, its connections and the current step of a guided path are always drawn.
- **Sub-events.** An item that is `part_of` another appears only once its parent fills at least a quarter of the window, so zooming in opens events into their parts. A sub-event at least as important as its parent is never folded away; the 2022 invasion stays visible even though it is part of the 2021–22 buildup.
- **Lanes follow the window.** When a zoom settles, lanes for threads with nothing in view drop away, and domains open automatically if the remaining threads fit.
- **Long items** show a bar along their lane for as long as they lasted, once that is visible at the current zoom.
- **Knowable on.** Tick "Show only what was known by a date" and pick a date with the slider or the date box. Only items that were public by the end of that day are shown, using each item's `known.public` date (which defaults to when it happened). Pick a party under "to the public" (e.g. "to US government") to show what that party knew, even before the public did. Nothing leaks from hindsight: links need both ends known, the side panel leaves out connections that were not knowable yet and says how many, and search skips unknown items. A disc in the scene and a line on the time strip mark the date. Turning it on starts from the selected item's date, so "what was knowable when this happened?" is one click. Guided paths switch it off.
- **3D or 2D.** 2D stacks the lanes as rows, viewed from straight above, like a subway map. Drag to pan and scroll to zoom the camera. Everything else (zooming time, selection, paths) works the same in both.
- Link types have their own colours. Contested links are dashed. Moving dots show direction, which matters because `revealed` links point back in time.
- Events are spheres, signals are octahedra, and decisions are boxes.
- Clicking an item, a search result or a connection dims everything unrelated, flies to it, and opens the side panel. The panel shows the dates (including when it became known), threads, regions, actors, connections, and sources with archive links and quotes. It also shows the item's **review status and open questions**, so the viewer doubles as a tool for checking the data.
- The selected item goes in the URL (`#cuban-missile-crisis-1962`), so you can link to it.
- Guided paths step through a chain of items with the arrow keys.

## Code

| File | What it does |
|---|---|
| `src/data.js` | Loads and indexes `graph.json`; date formatting; escaping. No three.js. |
| `src/timescale.js` | The time window (which slice of time fills the spine), zooming and panning it, and the tick marks. No three.js. |
| `src/visibility.js` | Which items to draw and label for a window: importance, sub-events, the selection, and what was knowable by a date. No three.js. |
| `src/timebar.js` | The zoom strip along the bottom. |
| `src/layout.js` | Which lanes exist, their order and their angles: domain slices, collapsing, ordering by shared items. No three.js. |
| `src/scene.js` | The three.js timeline: spine, lanes, nodes, links, camera, picking. |
| `src/panel.js` | The side panel's HTML. |
| `src/main.js` | Wires the page together: legend, search, lanes, paths, selection. |

Text from the data is always escaped before it reaches the page, and only `http(s)` URLs become links, because the data comes from contributors.

In the browser console, `window.__viewer` gives you `{ data, timeline, select }`, which is handy for poking around.

## Tests

```sh
npm run data
npx playwright install chromium   # once
npm test                          # layout unit tests, then the browser tests
npm run test:unit                 # just the layout, zoom, visibility and knowable-on rules (plain Node, no browser)
```

The browser tests run against the real `dist/graph.json`, so they check the viewer and the data together. To use a Chromium that is already installed, set `PLAYWRIGHT_CHROMIUM_PATH` to its executable.

### Stress-test data

`tests/fixtures/stress-graph.json` is a **fake** graph (40 threads in 6 domains, about 400 events and 500 links, plus one parent event with six day-level parts) for checking the layout at scale. Nothing in it is history, and it never goes near `data/`. With the dev server running, open it at `http://localhost:5173/?graph=tests/fixtures/stress-graph.json`. Regenerate it with `npm run fixtures`.

## Not done yet

These are the next viewer milestones in `CLAUDE.md`: series as bands, era zones, "why did this happen?", and branching scenarios. "Knowable on" will show much more once the deep dives add items whose `known` dates differ from when they happened; today only three do (Sykes–Picot, the first Soviet atomic test, the Cuban Missile Crisis).
