# Viewer

A timeline view of `dist/graph.json`, in 2D (the default), 3D or as a plain list, built with [Vite](https://vite.dev) and [three.js](https://threejs.org). It is one lens on the data; other views can read the same file.

## Layout

- **Top bar:** the name and counts, search, **Guided paths**, **Filters** and **Share**, and a line saying what is shown (period, hidden threads, lane arrangement, "knowable on").
- **Filters** (collapsible, closed at first; settings are kept while closed): 2D / 3D / List, compressed or even time, lanes by thread, region or domain, the thread list (click to hide), and what each relationship type means.
- **The timeline** fills the middle. Clicking a node selects it and opens the inspector at once. The 2D view fits between the panels and shrinks its row spacing so every lane fits. A note under it says when only the most important events in the period are drawn.
- **Inspector** (right; a bottom sheet on phones): status, title, dates, summary, connections, the traced contributing factors and later developments, contested interpretations, actors, sources and open questions. Close it with × or Escape.
- **Time navigator** (bottom): the histogram strip picks the historical period (this is separate from zooming the camera with the mouse or trackpad over the map), and the **Knowable on** controls, with a plain note on what that filter does and does not do.
- **Start screen** on a first visit: three guided paths and "Explore freely". **Guided paths** in the top bar brings it back without changing anything; ending a path puts back the period, hidden threads, "knowable on" date and selection it started from.
- **Phones:** the list view is the default, the inspector is a bottom sheet, and the top bar wraps.

## Shareable links

The URL hash holds the view, so a copied link (or the **Share** button) reopens it:

```
#e=cuban-missile-crisis-1962&t=1950.00,1980.00&v=2d&l=regions&h=cuba&s=even&k=1962.8100&p=US%20government
```

`e` selected item · `t` period (decimal years) · `v` view (`2d`, `3d`, `list`) · `l` lanes · `h` hidden threads · `s` time scale · `k` "knowable on" date · `p` the party it is known to. Defaults are left out. Old links of the form `#cuban-missile-crisis-1962` still work. Unknown or invalid parts are ignored; if nothing in a link can be used, the full map opens with a short notice. The rules are in `src/urlstate.js`, with unit tests.

## Run it

```sh
cd viewer
npm install          # once
npm run data         # rebuild ../dist/graph.json from ../data (runs tools/build.py)
npm run dev          # open the printed URL, usually http://localhost:5173
```

Rerun `npm run data` after editing anything in `data/`, then reload the page.

`npm run build` writes a static site to `viewer/build/`, with `graph.json` copied in. Any static host can serve it. It must be served over HTTP (it fetches `graph.json`), so opening `index.html` from disk does not work; locally, `npm run preview` or `python -m http.server` in `viewer/build/` will do.

## What it does

- Time runs along a central spine. Lanes around it are threads, regions or domains (the toggle top left). Items on several lanes sit between them.
- In thread mode, each domain gets its own slice of the circle, and threads that share many items and links sit next to each other. An item that sits near the spine crosses domains.
- When there are more than 26 threads, each domain collapses into one lane. Click a domain, in the legend or on its lane label, to open its threads; opening one closes the others. This keeps the circle readable however many threads the data grows to.
- Lane labels sit on the outer side of their lane, so they spread outwards instead of overlapping.
- **Zooming time.** The strip along the bottom shows how many items fall in each period. Drag across it to pick a period, drag the highlighted window to move it, scroll over it to zoom, and double-click to show everything. With the strip focused, or with no guided path running, ← → move the window, + and − zoom, and 0 shows everything. The window goes from the whole timeline down to six hours, and the tick marks adapt from 20-year steps to hours.
- **Importance decides what is drawn.** In any window, the 120 most important items are drawn (importance first, then number of links) and about 30 get labels; labels that would overlap are hidden. The selected item, its connections and the current step of a guided path are always drawn.
- **Sub-events.** An item that is `part_of` another appears only once its parent fills at least a quarter of the window, so zooming in opens events into their parts. A sub-event at least as important as its parent is never folded away; the 2022 invasion stays visible even though it is part of the 2021–22 buildup.
- **Lanes follow the window.** When a zoom settles, lanes for threads with nothing in view drop away, and domains open automatically if the remaining threads fit.
- **Long items** show a bar along their lane for as long as they lasted, once that is visible at the current zoom.
- **Knowable on.** Tick "Knowable on" in the time navigator and pick a date with the slider or the date box. Only items that were public by the end of that day are shown, using each item's `known.public` date (which defaults to when it happened). Pick a party under "to the public" (e.g. "to US government") to show what that party knew, even before the public did. Links need both ends known, the side panel leaves out connections that were not knowable yet and says how many, and search skips unknown items. A disc in the scene and a line on the time strip mark the date. Turning it on starts from the date the selected item became known, so "what was knowable then?" is one click. Guided paths switch it off. **Its limit:** it hides items and connections by date, but every summary was written later, with hindsight, so it is not a reconstruction of what people knew at the time; a "known then / learned later" content model is future work. The page says so next to the control.
- **2D, 3D or list.** 2D (the default) stacks the lanes as rows, viewed from straight above, like a subway map. Drag to pan and scroll to zoom the camera. 3D puts the lanes around a spine. The list shows the same events in the period, oldest first. Zooming time, selection and paths work the same in all three.
- Link types have their own colours. Contested links are dashed. Moving dots show direction, which matters because `revealed` links point back in time.
- Events are spheres, signals are octahedra, and decisions are boxes.
- Clicking an item, a search result or a connection dims everything unrelated, flies to it, and opens the side panel. The panel shows the dates (including when it became known), threads, regions, actors, connections, and sources with archive links and quotes. It also shows the item's **review status and open questions**, so the viewer doubles as a tool for checking the data.
- The selected item and the rest of the view go in the URL (see "Shareable links").
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
| `src/urlstate.js` | Reads and writes the view state in the URL hash. No three.js or DOM. |
| `src/main.js` | Wires the page together: top bar, filters, search, lanes, paths and start screen, selection, list view, "knowable on", sharing. |

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

- Series as bands, and branching scenarios at "today".
- A "known then / learned later" content model, so "knowable on" can show what was believed at the time, not just hide later items.
- The list view is plain: no grouping by thread, and long spans that started before the period are listed by their start year.
- Keyboard focus is not trapped inside the start screen, and the 3D view is not usable on phones (the list is the fallback).
