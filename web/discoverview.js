// T76 "Candidates" under the sky map: the discovery index from the Live API (GET /api/discoveries) as a list
// (filter by class, sort by score / class / name), markers on the map, and "Show me something interesting".
// Clicking a candidate fires "discoveries:open" ({detail: {candidate, synthetic}}); app.js opens its field
// (blink layers on the map, spectrum at the centre via photometry.js, the reason under the form).
// Until the survey (T75) delivers, the API serves a hand-made sample: the panel says so.

import { $, el } from "./util.js";
import * as explore from "./explore.js";
import { CLASSES, classLabel, displayName, filterCandidates, pickInteresting, sortCandidates } from "./discoveries.js";

const SHOW_MAX = 50;                 // rows in the list; the rest: "showing 50 of N"
const MARK = "#c9a7ff";              // one colour for all: the class is in the text, not the colour
const st = { list: [], synthetic: false, shownId: null, onMap: true, hooked: false };

function render() {
  const rows = sortCandidates(filterCandidates(st.list, $("#disc-class").value), $("#disc-sort").value);
  const tbody = $("#disc-table tbody");
  tbody.replaceChildren(...rows.slice(0, SHOW_MAX).map((c) => {
    const tr = el("tr", { "data-id": c.id, tabindex: "0", title: `Open ${displayName(c)}` },
      el("td", {}, classLabel(c.class)),
      el("td", { class: "disc-name" }, displayName(c),
        c.known ? el("span", { class: "disc-known muted small", title: `Known: ${c.known}` }, "known object") : ""),
      el("td", { class: "num" }, (c.score ?? 0).toFixed(2)),
      el("td", { class: "disc-reason" }, c.reason ?? ""));
    if (c.id === st.shownId) tr.setAttribute("aria-current", "true");
    return tr;
  }));
  const n = rows.length;
  $("#disc-count").textContent = n > SHOW_MAX ? `showing ${SHOW_MAX} of ${n}` : `${n}`;
  $("#disc-empty").hidden = n > 0;
  explore.redraw();
}

function open(c) {
  if (!c) return;
  st.shownId = c.id;
  render();
  document.dispatchEvent(new CustomEvent("discoveries:open", { detail: { candidate: c, synthetic: st.synthetic } }));
}

/** Markers: a ring per candidate in the list's current filter, its name next to it when zoomed in. */
function paint(ctx, proj) {
  if (!st.onMap || !st.list.length) return;
  const fov = explore.view()?.fovArcmin ?? 1e9;
  ctx.save();
  ctx.lineWidth = 2;
  ctx.font = "12px system-ui, sans-serif";
  for (const c of filterCandidates(st.list, $("#disc-class").value)) {
    const s = proj.toScreen(c.ra_deg, c.dec_deg);
    if (!s.front) continue;
    const r = c.id === st.shownId ? 11 : 8;
    ctx.strokeStyle = "rgba(0,0,0,0.6)";
    ctx.beginPath(); ctx.arc(s.x, s.y, r + 1.5, 0, 2 * Math.PI); ctx.stroke();
    ctx.strokeStyle = MARK;
    ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, 2 * Math.PI); ctx.stroke();
    if (fov < 20 * 60) {
      const text = `${displayName(c)} · ${classLabel(c.class).toLowerCase()}`;
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,0.7)"; ctx.strokeText(text, s.x + r + 4, s.y + 4);
      ctx.fillStyle = MARK; ctx.fillText(text, s.x + r + 4, s.y + 4);
      ctx.lineWidth = 2;
    }
  }
  ctx.restore();
}

function hookMap() {
  if (st.hooked || !explore.getSky()) return;
  st.hooked = true;
  explore.addDrawHook(paint);
}

/** Load the index from the Live API; the panel stays hidden without one (offline mode, API down). */
export async function initDiscoveries(api) {
  const box = $("#discoveries");
  if (!box || !api) return;
  $("#disc-class").replaceChildren(el("option", { value: "all" }, "all classes"),
    ...Object.entries(CLASSES).map(([k, v]) => el("option", { value: k, title: v.hint }, v.label)));
  $("#disc-class").addEventListener("change", render);
  $("#disc-sort").addEventListener("change", render);
  $("#disc-onmap").addEventListener("change", (e) => { st.onMap = e.target.checked; explore.redraw(); });
  $("#disc-table tbody").addEventListener("click", (e) => {
    const id = e.target.closest("tr")?.dataset.id;
    open(st.list.find((c) => c.id === id));
  });
  $("#disc-table tbody").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    const id = e.target.closest("tr")?.dataset.id;
    open(st.list.find((c) => c.id === id));
  });
  $("#disc-interesting").addEventListener("click", () => {
    open(pickInteresting(filterCandidates(st.list, $("#disc-class").value), { exclude: st.shownId }));
  });
  document.addEventListener("explore:ready", hookMap);
  hookMap();
  let body;
  try {
    const res = await fetch(`${api.replace(/\/$/, "")}/api/discoveries`, { cache: "no-cache" });
    if (!res.ok) return;
    body = await res.json();
  } catch { return; }
  st.list = Array.isArray(body.candidates) ? body.candidates : [];
  st.synthetic = Boolean(body.synthetic);
  $("#disc-sample").hidden = !st.synthetic;
  $("#disc-source").textContent = body.survey ? `${body.survey}${body.generated_utc ? ` · ${body.generated_utc.slice(0, 10)}` : ""}` : "";
  box.hidden = st.list.length === 0;
  render();
  document.dispatchEvent(new CustomEvent("discoveries:loaded", { detail: { candidates: st.list, synthetic: st.synthetic } }));
}

/** app.js tells which candidate's field is shown (also when it was opened from the URL), or null. */
export function markShown(id) {
  if (st.shownId === id) return;
  st.shownId = id;
  if (st.list.length) render();
}
