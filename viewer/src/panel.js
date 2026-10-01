// The detail panel for a selected item. Everything from the data is escaped.
import { LINK_TYPES, esc, formatSpan, safeUrl, yearLabel } from "./data.js";
import { isKnown } from "./visibility.js";

const STATUS_TEXT = {
  unverified: "Unverified",
  sourced: "Sourced, not yet reviewed",
  reviewed: "Reviewed",
};

// knowable: when the "knowable on" slider is on, connections to items not yet known are
// left out, so the panel does not leak hindsight.
export function renderDetail(item, data, { knowable = null } = {}) {
  const threads = Object.fromEntries(data.graph.threads.map((t) => [t.id, t]));
  const regions = Object.fromEntries(data.graph.regions.map((r) => [r.id, r]));
  const status = item.review?.status ?? "unverified";

  const known = item.known?.public;
  const knownDiffers = known && known.start !== item.occurred.start;
  const knownBy = (item.known?.by ?? [])
    .map((k) => `<div class="known">Known to ${esc(k.party)}: ${esc(formatSpan(k.when))}</div>`).join("");

  const chips = [
    ...item.threads.map((id) => {
      const c = threads[id]?.color ?? "#8A93A0";
      return `<span class="chip" style="color:${c};border-color:${c}">${esc(threads[id]?.name ?? id)}</span>`;
    }),
    ...item.regions.map((id) => `<span class="chip rg">${esc(regions[id]?.name ?? id)}</span>`),
  ].join("");

  const actors = (item.actors ?? [])
    .map((id) => data.byId.get(id))
    .filter(Boolean)
    .map((a) => `<span class="chip rg" title="${esc(a.summary)}">${esc(a.title)}</span>`).join("");

  const allLinks = data.linksOf.get(item.id);
  const links = allLinks.filter((l) => isKnown(other(l, item), knowable)).sort((p, q) =>
    other(p, item).occurred.range[0] - other(q, item).occurred.range[0]);
  const withheld = allLinks.length - links.length;
  const linkHtml = links.map((l) => {
    const o = other(l, item);
    const t = LINK_TYPES[l.type] ?? { color: "#E6E1D6", out: l.type, in: l.type };
    const dir = l.from === item.id ? t.out : t.in;
    const contested = l.confidence === "contested";
    return `<button class="lk" style="border-color:${t.color};${contested ? "border-left-style:dashed" : ""}" data-go="${esc(o.id)}">
      <span class="t">${esc(dir)} · ${esc(yearLabel(o))}${contested ? " · contested" : ""}${l.review?.status === "unverified" ? " · unverified" : ""}</span>
      <b>${esc(o.title)}</b><br>${esc(l.note)}</button>`;
  }).join("");

  const notes = item.review?.notes?.length
    ? `<div class="h">Open questions</div><ul>${item.review.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`
    : "";

  return `
    <div class="kind">${esc(item.kind)}<span class="badge ${esc(status)}">${esc(STATUS_TEXT[status] ?? status)}</span></div>
    <div class="date">${esc(formatSpan(item.occurred))}</div>
    ${knownDiffers ? `<div class="known">Became public: ${esc(formatSpan(known))}</div>` : ""}
    ${knownBy}
    <h2>${esc(item.title)}</h2>
    <div class="chips">${chips}</div>
    <p>${esc(item.summary)}</p>
    ${actors ? `<div class="h">Actors</div><div class="chips">${actors}</div>` : ""}
    <div class="h">Connections (${links.length})</div>
    ${linkHtml || (withheld ? "" : '<p class="note">None yet.</p>')}
    ${withheld ? `<p class="note withheld">${withheld} more connection${withheld === 1 ? "" : "s"} not yet knowable on ${esc(knowable.label)}.</p>` : ""}
    <div class="h">Sources</div>
    ${renderSources(item.sources)}
    ${notes}
    <div class="btns"><button class="ghost" id="closeD">Close</button></div>`;
}

function other(link, item) {
  return link.from === item.id ? link.b : link.a;
}

function renderSources(sources = []) {
  if (!sources.length) return '<p class="note">No sources yet.</p>';
  return `<ul>${sources.map((s) => {
    const url = safeUrl(s.url);
    const archive = safeUrl(s.archive_url);
    const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a>` : esc(s.title);
    const meta = [s.publisher, s.date, s.type].filter(Boolean).map(esc).join(" · ");
    const arch = archive ? ` · <a href="${esc(archive)}" target="_blank" rel="noopener noreferrer">archived</a>` : " · not archived";
    const quote = s.quote ? `<blockquote>“${esc(s.quote)}”</blockquote>` : "";
    return `<li>${title}<br><span class="note">${meta}${arch}</span>${quote}</li>`;
  }).join("")}</ul>`;
}
