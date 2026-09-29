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
- Link types have their own colours. Contested links are dashed. Moving dots show direction, which matters because `revealed` links point back in time.
- Events are spheres, signals are octahedra, and decisions are boxes.
- Clicking an item, a search result or a connection dims everything unrelated, flies to it, and opens the side panel. The panel shows the dates (including when it became known), threads, regions, actors, connections, and sources with archive links and quotes. It also shows the item's **review status and open questions**, so the viewer doubles as a tool for checking the data.
- The selected item goes in the URL (`#cuban-missile-crisis-1962`), so you can link to it.
- Guided paths step through a chain of items with the arrow keys.

## Code

| File | What it does |
|---|---|
| `src/data.js` | Loads and indexes `graph.json`; date formatting; escaping. No three.js. |
| `src/scene.js` | The three.js timeline: spine, lanes, nodes, links, camera, picking. |
| `src/panel.js` | The side panel's HTML. |
| `src/main.js` | Wires the page together: legend, search, lanes, paths, selection. |

Text from the data is always escaped before it reaches the page, and only `http(s)` URLs become links, because the data comes from contributors.

In the browser console, `window.__viewer` gives you `{ data, timeline, select }`, which is handy for poking around.

## Tests

```sh
npm run data
npx playwright install chromium   # once
npm test
```

The tests run against the real `dist/graph.json`, so they check the viewer and the data together. To use a Chromium that is already installed, set `PLAYWRIGHT_CHROMIUM_PATH` to its executable.

## Not done yet

These are the next viewer milestones in `CLAUDE.md`: a stretchable time axis with `part_of` zooming, visibility by importance and zoom, series as bands, the "knowable on" slider, era zones, "why did this happen?", and branching scenarios.
