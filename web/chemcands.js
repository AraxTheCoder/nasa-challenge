// T128: candidates from a chemistry picture. Once a picture (one map or several, T93/T96) is on the map, the Live
// API lists the spots where its features show (pipeline/chemistry.py candidates(): compact peaks first, sharpness
// pairs at bright stars and the rims of saturated holes left out, named after the field's catalogue labels). This
// module shows them as a numbered list under the chemistry note and as the same numbers in white rings on the map.
// A click on a row centres the map on the spot (zoom kept) and opens its spectrum; a click on a ring selects its
// row and opens its spectrum (T141: the ring takes the click, else the map's own click would make the spot a new
// analysis region, T138, and clear the picture). Visualization only (Decision 2026-11-14): spots to look at, the
// spectrum is how the user judges; nothing here says what a spot is.
//
// Catalogues (ticked above the list, remembered): the spots are looked up there (pipeline/catcheck.py, positions
// moved by proper motion to SPHEREx's date), then listed uncatalogued first, other types next, the preset's expected
// types last (dimmed). The list shows at once; the lookup (a few seconds) reorders it.
//
// Drawn through explore.js's public draw hook and pointer events on #sky only (like outliers.js).

import { $, el, fmtNum } from "./util.js";
import * as explore from "./explore.js";
import { openSpectrum } from "./photometry.js";

const C_RING = "#ffffff";
const C_SEL = "#ffd400";
const st = { items: [], sel: null, placed: [], hooked: false, token: 0, featName: (k) => k, cats: [], on: null, args: null };
const CATS_KEY = "spherex.chemCats";
const TAG = { new: "uncatalogued", untyped: "no type" };          // other: its SIMBAD kind; known: "known <kind>"

/** The catalogues the Live API can check (from /api/chemistry/features); the ticked ones are remembered. */
export function setCatalogues(list) {
  st.cats = list ?? [];
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(CATS_KEY) ?? "null"); } catch { saved = null; }
  st.on = new Set(Array.isArray(saved) ? saved.filter((c) => st.cats.some((x) => x.id === c)) : st.cats.filter((c) => c.default).map((c) => c.id));
}

function catRow() {
  if (!st.cats.length) return null;
  return el("p", { class: "chem-cats" }, "Check: ", ...st.cats.map((c) => {
    const cb = el("input", { type: "checkbox", value: c.id });
    cb.checked = st.on.has(c.id);
    cb.addEventListener("change", () => {
      if (cb.checked) st.on.add(c.id); else st.on.delete(c.id);
      try { localStorage.setItem(CATS_KEY, JSON.stringify([...st.on])); } catch { /* private mode */ }
      if (st.args) showCandidates(...st.args);
    });
    return el("label", { title: c.what }, cb, ` ${c.name} `);
  }));
}

const catName = (id) => st.cats.find((c) => c.id === id)?.name ?? id;

function box() {
  let b = $("#chem-cands");
  if (!b) {
    b = el("div", { id: "chem-cands", class: "hud-panel small chem-cands", role: "region", "aria-label": "Spots to check" });
    b.hidden = true;
    $("#chem-note")?.after(b);
  }
  return b;
}

const title = (it, k) => it.catalogues?.simbad?.name ?? it.name
  ?? Object.values(it.catalogues ?? {}).find(Boolean)?.name ?? (it.near ? `near ${it.near.name}` : `Spot ${k + 1}`);

function tagText(it) {
  if (!it.tag) return null;
  const kind = it.catalogues?.simbad?.kind;
  return it.tag === "known" ? `known ${kind}` : it.tag === "other" ? kind : TAG[it.tag];
}

function select(k, open) {
  st.sel = k;
  const it = st.items[k];
  if (!it) return;
  if (open) {
    explore.goTo(it.ra_deg, it.dec_deg);
    openSpectrum(it.ra_deg, it.dec_deg, title(it, k));
  }
  for (const [i, b] of box().querySelectorAll("button.chem-cand").entries()) b.setAttribute("aria-pressed", String(i === k));
  box().querySelectorAll("button.chem-cand")[k]?.scrollIntoView({ block: "nearest" });
  explore.redraw();
}

function render(body, checking) {
  const b = box();
  const items = st.items;
  const head = el("p", { class: "chem-cand-head" }, el("strong", {}, items.length ? `Spots (${items.length})` : "No spot stands out"),
    items.length ? " · strongest first · click: spectrum" : ` (none reaches ${body.show_sigma}σ)`);
  const status = checking ? `Checking ${checking.map(catName).join(", ")}…`
    : body.failed?.length ? `No answer: ${body.failed.map(catName).join(", ")}` : null;
  const list = el("ol", { class: "chem-cand-list" }, ...items.map((it, k) => {
    const sig = Object.entries(it.sigma).map(([key, v]) => el("span", { class: v >= body.show_sigma ? "chem-sig on" : "chem-sig" },
      `${st.featName(key)} ${fmtNum(v, 1)}σ`));
    const tag = tagText(it);
    const btn = el("button", { type: "button", class: `chem-cand${it.tag === "known" ? " known" : ""}`, "aria-pressed": String(k === st.sel),
      title: `RA ${fmtNum(it.ra_deg, 4)}°, Dec ${fmtNum(it.dec_deg, 4)}°` },
    el("span", { class: "chem-cand-n" }, String(k + 1)), " ", el("strong", {}, title(it, k)), " ",
    tag ? el("span", { class: `chem-tag ${it.tag}` }, tag) : null, " ",
    el("span", { class: "muted" }, it.compact ? "point" : "extended"), el("span", { class: "chem-sigs" }, ...sig));
    btn.addEventListener("click", () => select(k, true));
    return el("li", {}, btn);
  }));
  const foot = el("p", { class: "muted" }, (body.checked?.length ? "Uncatalogued first, other types next, known last. " : "")
    + "σ: noise levels, + = feature shows (max ≈ 5).");
  b.replaceChildren(head, ...[catRow(), status && el("p", { class: "muted" }, status)].filter(Boolean),
    ...(items.length ? [list, foot] : []));
  b.hidden = false;
}

function paint(ctx, proj) {
  st.placed = [];
  if (!st.items.length) return;
  const v = proj.view();
  ctx.save();
  ctx.font = "bold 12px sans-serif";
  st.items.forEach((it, k) => {
    const s = proj.toScreen(it.ra_deg, it.dec_deg);
    if (!s.front || s.x < -30 || s.y < -30 || s.x > v.width + 30 || s.y > v.height + 30) return;
    const r = it.compact ? 9 : 13;
    ctx.lineWidth = 4.5; ctx.strokeStyle = "rgba(0,0,0,0.75)";
    ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 2; ctx.strokeStyle = k === st.sel ? C_SEL : C_RING;
    if (!it.compact) ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, 2 * Math.PI); ctx.stroke();
    ctx.setLineDash([]);
    const label = String(k + 1);
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,0.85)"; ctx.fillStyle = k === st.sel ? C_SEL : C_RING;
    ctx.strokeText(label, s.x + r * 0.75 + 2, s.y - r * 0.75 - 1);
    ctx.fillText(label, s.x + r * 0.75 + 2, s.y - r * 0.75 - 1);
    st.placed.push({ x: s.x, y: s.y, r, k });
  });
  ctx.restore();
}

function hook() {
  if (st.hooked || !explore.getSky()) return;
  st.hooked = true;
  explore.addDrawHook(paint);
  const sky = $("#sky");
  let down = null;
  sky?.addEventListener("pointerdown", (e) => { down = e.isPrimary ? { x: e.clientX, y: e.clientY } : null; });
  sky?.addEventListener("pointerup", (e) => {
    const d0 = down;
    down = null;
    // e.defaultPrevented: a 📍 pick (cursorpin.js) or another ring took the click
    if (e.defaultPrevented || !d0 || Math.hypot(e.clientX - d0.x, e.clientY - d0.y) > 4 || !st.placed.length) return;
    const rect = sky.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    let best = null, bd = Infinity;
    for (const p of st.placed) {
      const dd = Math.hypot(p.x - x, p.y - y);
      if (dd <= p.r + 6 && dd < bd) { bd = dd; best = p; }
    }
    if (!best) return;
    e.preventDefault();                         // T141: the ring takes the click (see the top)
    select(best.k, false);
    const it = st.items[best.k];
    openSpectrum(it.ra_deg, it.dec_deg, title(it, best.k));
  });
}

/** List the spots of the picture made of these map keys (`base` = .../api/targets/<id>/chemistry), then look them up
 *  in the ticked catalogues. featName(key) -> the feature's short name; preset: the preset's id (its expected types). */
export async function showCandidates(base, keys, featName, preset = null) {
  const token = ++st.token;
  st.args = [base, keys, featName, preset];
  st.items = [];
  st.sel = null;
  st.featName = featName ?? ((k) => k);
  const b = box();
  b.replaceChildren(el("p", { class: "muted" }, "Looking for spots…"));
  b.hidden = false;
  explore.redraw();
  const url = `${base}/candidates?maps=${encodeURIComponent(keys.join("-"))}`;
  const cats = [...(st.on ?? [])];
  const ask = async (u) => {
    try { return await (await fetch(u)).json(); } catch (err) { return { status: "error", message: err.message ?? String(err) }; }
  };
  let body = await ask(url);
  if (token !== st.token) return;
  if (body.status !== "ready") { b.replaceChildren(el("p", { class: "muted" }, `Spots unavailable: ${body.message ?? body.status}`)); return; }
  st.items = body.items ?? [];
  hook();
  render(body, st.items.length && cats.length ? cats : null);
  explore.redraw();
  if (!st.items.length || !cats.length) return;
  const checked = await ask(`${url}&cats=${cats.join(",")}${preset ? `&preset=${encodeURIComponent(preset)}` : ""}`);
  if (token !== st.token) return;
  if (checked.status !== "ready") { render({ ...body, failed: cats }, null); return; }
  st.items = checked.items ?? [];
  st.sel = null;
  render(checked, null);
  explore.redraw();
}

/** The picture is gone (cleared, another view took the map, another field): no list, no rings. */
export function clearCandidates() {
  st.token++;
  st.items = [];
  st.sel = null;
  const b = $("#chem-cands");
  if (b) b.hidden = true;
  explore.redraw();
}
