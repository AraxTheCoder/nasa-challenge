// T93 "Chemistry" on the sky map: for the shown field, where does a chemical feature absorb or emit? The Live API
// makes the map (pipeline/chemistry.py: the image at the feature's wavelength minus the continuum from just below
// and above, from the field's own SPHEREx exposures) and serves it as the map layer x-<feature>. Visualization
// only: the note says what dark / bright / a colour means and what can fool it; the user judges.
// T96: tick several features. One = the grey map (dark = absorption, bright = emission); two or more = one
// colour picture (layer x-<a>-<b>[-<c>...], features in wavelength order): each feature in its colour (shortest
// blue, longest red; two: cyan + red; T108: no limit, from four on hues by wavelength and mixes are ambiguous), as bright as it emits (lines, PAH) or absorbs (ices, water) beyond one
// noise level. The maps are made one after another (memory), each once per field. The picture stays when the
// field's layers are rebuilt (false colour on / off); another view of the map (A/B, A − B, a pass) ends it.
// T107: presets at the top of the list (from /api/chemistry/features `presets`): tested combinations for kinds of
// places (ionised gas, ices in cold clouds, lit cloud edges). One click ticks their features; the note then says
// how to read the colours, what fools it and a field where it was tried. Visualization only, nothing classified.
// T109: "Redshift z" in the list. A galaxy's features arrive at λ(1 + z); from cz ≈ 1 300 km/s (Br-α) they miss
// the rest-wavelength window. The maps are made at the z in the box (one z per picture); when the list is opened
// the Live API names the field's galaxies with a measured redshift (SIMBAD) and a big one at the centre fills it in.
// T127: presets for kinds of objects too (brown dwarfs, young stars, cool giants, protostars, star-forming galaxies,
// quasars), listed as "Objects" above the T107 "Places". A preset with needs_z (galaxies, quasars) is made only at
// the object's redshift; with z = 0 the note says so instead of measuring.
// T128: once a picture is on the map, chemcands.js lists the spots where its features show (rings + a list).

import { $, el, fmtNum } from "./util.js";
import * as explore from "./explore.js";
import { clearCandidates, setCatalogues, showCandidates } from "./chemcands.js";   // T128: spots where the picture's features show

const st = { api: null, target: null, z: 0, zTouched: false, zAsked: null, features: [], presets: [], presetBtns: new Map(), combine: { max: 3, colours: {} }, sel: [], boxes: new Map(),
  ready: new Map(), token: 0, shown: null, picked: null };

const byId = (id) => st.features.find((f) => f.id === id);
const inOrder = (ids) => [...ids].sort((a, b) => byId(a).um - byId(b).um);
const label = (f) => `${f.name} (${fmtNum(f.um, 2)} µm)`;
const base = () => `${st.api}/api/targets/${encodeURIComponent(st.target.id)}/chemistry`;

const sameSet = (p, ids) => p.features.length === ids.length && p.features.every((f) => ids.includes(f));
/** The preset whose features are exactly these (ticked by its button or by hand), or undefined. T127: the one
 *  clicked last wins when two presets share their features. */
const presetOf = (ids) => (st.picked && sameSet(st.picked, ids) ? st.picked : st.presets.find((p) => sameSet(p, ids)));

/** id -> colour in the picture of these features (empty for one: the grey map). */
function colours(ids) {
  const cs = st.combine.colours?.[String(ids.length)];
  return new Map(ids.length > 1 && cs ? inOrder(ids).map((id, i) => [id, cs[i]]) : []);
}

// T132: notes are two short lines (what is shown + keys, how to read it); the rest under "More" (open state
// remembered per browser).
const MORE_KEY = "spherex.chemMore";
let moreOpen = false;
try { moreOpen = localStorage.getItem(MORE_KEY) === "1"; } catch { /* private mode */ }
const line = (...parts) => el("span", { class: "chem-line" }, ...parts.filter((x) => x != null));

function more(...parts) {
  const d = el("details", { class: "chem-more" }, el("summary", {}, "More"), ...parts.filter(Boolean));
  d.open = moreOpen;
  d.addEventListener("toggle", () => {
    moreOpen = d.open;
    try { localStorage.setItem(MORE_KEY, d.open ? "1" : "0"); } catch { /* private mode */ }
  });
  return d;
}

/** "H₂O 1.4 µm", "CO₂ ice 4.27 µm", at a redshift "Pa-β → 1.485 µm" (names that carry µm keep theirs at z = 0). */
function fname(f) {
  if (st.z > 0) return `${f.name} → ${fmtNum(atZ(f.um), 3)} µm`;
  return f.name.includes("µm") ? f.name : `${f.name} ${fmtNum(f.um, 2)} µm`;
}

function note(parts) {
  const box = $("#chem-note");
  const shown = parts.filter(Boolean);
  box.replaceChildren(...shown);
  box.hidden = shown.length === 0;
}

/** Checkboxes, swatches and the summary follow st.sel. */
function syncControls() {
  const cs = colours(st.sel);
  const full = st.sel.length >= st.combine.max;
  for (const [id, box] of st.boxes) {
    box.checked = st.sel.includes(id);
    box.disabled = full && !box.checked;
    const row = box.closest("label");
    row.title = box.disabled ? `At most ${st.combine.max} at once` : byId(id).what;
    const sw = row.querySelector(".chem-swatch");
    sw.hidden = !cs.has(id);
    sw.style.background = cs.get(id) ?? "";
  }
  const pre = presetOf(st.sel);
  for (const [id, b] of st.presetBtns) b.setAttribute("aria-pressed", String(pre?.id === id));
  $("#chem-summary").textContent = pre ? pre.name : st.sel.length ? inOrder(st.sel).map((id) => byId(id).name).join(" + ") : "off";
  $("#chem-clear").hidden = !st.sel.length;
}

/** Something else took the map, or the field changed: forget the picture (the layer is replaced by then). */
function off() {
  st.token++;
  st.shown = null;
  clearCandidates();
  st.sel = [];
  syncControls();
  note([]);
}

/** The user unticked everything: the picture goes and the automatic blink gets the map back. */
function clear() {
  const had = st.shown;
  off();
  if (had) {
    explore.hideOverlay();
    document.dispatchEvent(new CustomEvent("map:give"));
  }
}

function toggle(id, on) {
  st.sel = on ? [...st.sel.filter((x) => x !== id), id].slice(-st.combine.max) : st.sel.filter((x) => x !== id);
  syncControls();
  if (!st.sel.length) { clear(); return; }
  apply();
}

function choosePreset(p) {
  if (presetOf(st.sel)?.id === p.id) return;
  st.picked = p;
  st.sel = [...p.features];
  syncControls();
  apply();
}

const atZ = (um) => um * (1 + st.z);
const RETRY_S = 90;          // T110: how long a measurement waits for a restarting Live API

/** Make (or reuse) one feature's map at the current z; resolves with the ready body or an error body. */
async function ensure(id, token, k, n) {
  const ck = `${id}@${st.z}`;
  if (st.ready.has(ck)) return st.ready.get(ck);
  const f = byId(id);
  const which = n > 1 ? ` (${k + 1} of ${n})` : "";
  const url = `${base()}?feature=${encodeURIComponent(id)}${st.z > 0 ? `&z=${st.z}` : ""}`;
  const head = el("strong", {}, `${label(f)}${which}: `);
  note([head, "measuring the field's SPHEREx exposures around this wavelength…"]);
  // T110: a Live API restart (or a dropped connection) mid-measurement must not end it: the job is gone after a
  // restart, so ask with start=1 again, for up to RETRY_S; give up only after that.
  let res, body, start = true, lost = null;
  for (;;) {
    try {
      res = await fetch(start ? `${url}&start=1` : url);
      body = await res.json();
      if (res.status >= 500 && body?.status !== "error") throw new Error(`HTTP ${res.status}`);
      lost = null;
    } catch (err) {
      if (token !== st.token) return { status: "cancelled" };
      lost ??= Date.now();
      if (Date.now() - lost > RETRY_S * 1000) throw err;
      note([head, "the Live API is not answering (restarting?), trying again…"]);
      start = true;
      await new Promise((r) => setTimeout(r, 3000));
      continue;
    }
    if (body?.status === "not_started" && !start) { start = true; continue; }   // restarted between two polls
    start = false;
    if (res.status !== 202 || token !== st.token) break;
    note([head, `measuring… ${body.done ?? 0} of ${body.total || "?"} exposures`]);
    await new Promise((r) => setTimeout(r, 1500));
  }
  if (body.status === "ready") st.ready.set(ck, body);
  return body;
}

async function apply() {
  const token = ++st.token;
  clearCandidates();
  const ids = inOrder(st.sel);
  if (!st.target || !ids.length) return;
  const need = presetOf(ids);
  if (need?.needs_z && !(st.z > 0)) {                 // T127: galaxies / quasars only at their redshift
    note([line(el("strong", {}, need.name), ` needs the object's redshift: type z above (SIMBAD fills it in for a galaxy or quasar at the centre) · `,
      el("a", { href: `?ra=${need.try.ra}&dec=${need.try.dec}&size=${need.try.size}` }, `try ${need.try.name}`))]);
    return;
  }
  const stats = [];
  try {
    for (const [k, id] of ids.entries()) {          // one after another: each reads tens of exposures
      const body = await ensure(id, token, k, ids.length);
      if (token !== st.token) return;
      if (body.status !== "ready") { note([`${byId(id).name}: ${body.message ?? body.status}`]); return; }
      stats.push(body);
    }
  } catch (err) {
    if (token === st.token) note([`Chemistry map unavailable: ${err.message ?? err}`]);
    return;
  }
  const keys = stats.map((b, i) => b.key ?? ids[i]);           // T109: <feature>[_z<z·10⁴>]
  const layer = `x-${keys.join("-")}`;
  st.shown = layer;
  document.dispatchEvent(new CustomEvent("map:take"));          // the automatic blink leaves the map alone
  const ok = await explore.showLayer(layer);
  if (token !== st.token) return;
  const png = `${base()}/${keys.join("-")}.png`;
  if (ok) showCandidates(base(), keys, (k) => byId(k.replace(/_z\d+$/, ""))?.name ?? k, presetOf(ids)?.id);   // T128
  const link = el("a", { href: png, target: "_blank", rel: "noopener" }, ids.length > 1 ? "picture" : "map image");
  const notShown = ok ? null : line("(The map layer could not be shown here.)");
  const zt = st.z > 0 ? ` at z = ${st.z}` : "";
  if (ids.length === 1) {
    const b = stats[0];
    const f = byId(b.feature ?? ids[0]);
    note([
      line(el("strong", {}, `${fname(f)} minus continuum${zt}`), " · ", el("span", { class: "chem-key chem-dark" }), " absorbs · ",
        el("span", { class: "chem-key chem-bright" }), " emits"),
      line(f.what),
      notShown,
      more(line(`${b.exposures_used} exposures (per spot ${b.median_on} on, ${b.median_continuum} around) · ±5σ = black / white.`),
        line("Black/white pairs at stars: sharpness, not chemistry. ", link)),
    ]);
    return;
  }
  const cs = colours(ids);
  const pre = presetOf(ids);
  const here = pre && st.target && Math.abs(st.target.center?.ra_deg - pre.try.ra) < 0.2 && Math.abs(st.target.center?.dec_deg - pre.try.dec) < 0.2;
  const dirs = new Set(ids.map((id) => byId(id).shows));
  const scale = dirs.size > 1 ? "brighter = stronger" : dirs.has("emission") ? "brighter = stronger emission" : "brighter = deeper absorption";
  const fs = stats.map((b) => byId(b.feature ?? b.id));
  note([
    line(el("strong", {}, pre ? pre.name : "Picture"), zt, " · ",
      ...fs.flatMap((f) => [el("span", { class: "chem-key", style: `background:${cs.get(f.id)}` }),
        el("span", { title: f.what }, ` ${fname(f)} `)]), "· ", scale),
    line(pre ? pre.read : ids.length <= 3 ? "Mixed colours = several at one spot (red + green = yellow, all = white) · black = none"
      : `Mixed colours = several at one spot; with ${ids.length} colours a mix can look like another feature's own colour: check its single maps`),
    notShown,
    more(pre ? line(`Looks for: ${pre.looks_for}.`) : null,
      line(`Fooled by: ${pre ? `${pre.caveats}; ` : ""}coloured pairs at stars (sharpness).`),
      line(`Exposures: ${stats.map((b) => b.exposures_used).join(" · ")}. Colour from 1σ, full at 5σ; black = none; shown where all maps have data.`),
      line(pre && !here ? ["Tried on ", el("a", { href: `?ra=${pre.try.ra}&dec=${pre.try.dec}&size=${pre.try.size}` }, pre.try.name), " · "] : null, link)),
  ]);
}

/** T109: set z (rounded like the server: 4 decimals); maps follow if a picture is on. */
function setZ(z, touched = true) {
  const v = Math.min(1, Math.max(0, Math.round((Number(z) || 0) * 1e4) / 1e4));
  st.zTouched ||= touched;
  const box = $("#chem-z");
  if (box && Number(box.value) !== v) box.value = v ? String(v) : "0";
  if (v === st.z) return;
  st.z = v;
  syncZ();
  if (st.sel.length) apply();
}

function syncZ() {
  const hint = $("#chem-z-hint");
  if (!hint) return;
  const g = st.zInfo?.galaxies?.[0];
  const parts = [];
  if (g) {
    const use = el("button", { type: "button", class: "link small" }, "use");
    use.addEventListener("click", () => setZ(g.z));
    const inUse = Math.round(g.z * 1e4) / 1e4 === st.z;           // st.z is kept to 4 decimals (T127: 3C 273, 0.15757)
    parts.push(`SIMBAD: ${g.name}, z = ${g.z} (${g.cz_km_s.toLocaleString("en")} km/s) `, inUse ? "· in use" : use);
  } else if (st.zInfo) {
    parts.push("No galaxy with a measured redshift here: z = 0 (Milky Way objects need none).");
  }
  if (st.z > 0) parts.push(el("span", { class: "chem-line" }, `Features are looked for at λ × ${fmtNum(1 + st.z, 4)}.`));
  hint.replaceChildren(...parts);
}

/** Ask the Live API once per field which galaxies with a redshift it holds; fill z for a big one at the centre. */
async function askRedshift() {
  if (!st.target || st.target.synthetic || st.zAsked === st.target.id) return;
  const tid = st.target.id;
  st.zAsked = tid;
  try {
    const body = await (await fetch(`${st.api}/api/targets/${encodeURIComponent(tid)}/redshift`)).json();
    if (st.target?.id !== tid) return;
    st.zInfo = body;
    const g = body.galaxies?.[0];
    // fill in only for the galaxy the field is about (at the centre, or covering it) and if nobody typed a z
    if (g && !st.zTouched && !st.shown && (g.sep_arcmin <= 1 || g.sep_arcmin <= (g.major_arcmin ?? 0) / 2)) setZ(g.z, false);
    syncZ();
  } catch { st.zAsked = null; }
}

export async function initChemistry(api) {
  st.api = api?.replace(/\/$/, "") ?? null;
  const box = $("#chem-box");
  if (!box || !st.api) return;
  const visible = () => { box.hidden = !st.target || st.target.synthetic || !st.features.length || !explore.getSky(); };
  // Another view took over the map (A/B, blink, A − B, a pass or epoch picked by hand): the picture is gone.
  for (const ev of ["viewer:frame", "viewer:diff"]) document.addEventListener(ev, () => { if (st.shown) off(); });
  document.addEventListener("explore:epoch-picked", (e) => {
    if (!st.shown) return;
    // T96: app.js rebuilt the field's layers by itself (false colour on / off, T89): put the picture back on top
    if (e.detail?.auto) explore.showLayer(st.shown).then((ok) => { if (!ok) off(); });
    else off();
  });
  // T90: the automatic blink took the map back (the view moved to another tile)
  document.addEventListener("map:manual", (e) => { if (!e.detail?.on && st.shown) off(); });
  document.addEventListener("viewer:target", (e) => {
    // T104: the same field announced again (its labels or known objects arrived, the Labels switch): the picture
    // stays; only another field (or none) ends it
    const t = e.detail?.target ?? null;
    if (t && st.target && t.id === st.target.id) {
      st.target = t;
      if (st.shown) explore.showLayer(st.shown).then((ok) => { if (!ok) off(); });
      return;
    }
    off();
    st.ready.clear();
    st.target = e.detail?.target ?? null;
    st.zInfo = null;
    st.zTouched = false;
    setZ(0, false);
    syncZ();
    if ($("#chem-box")?.open) askRedshift();
    visible();
  });
  $("#chem-clear").addEventListener("click", clear);
  try {
    const body = await (await fetch(`${st.api}/api/chemistry/features`)).json();
    st.features = body.features ?? [];
    if (body.combine) st.combine = body.combine;
    setCatalogues(body.catalogues);                                          // T128
    st.presets = (body.presets ?? []).filter((p) => p.features.length <= st.combine.max && p.features.every(byId));
  } catch { st.features = []; st.presets = []; }
  const presetBtn = (p) => {
    const b = el("button", { type: "button", class: "chem-preset", "aria-pressed": "false",
      title: `${p.looks_for}. Tried on: ${p.tested}.` }, p.name,
    el("span", { class: "muted small" }, ` ${p.features.map((f) => byId(f).name).join(" + ")}${p.needs_z ? " · at its redshift" : ""}`));
    b.addEventListener("click", () => choosePreset(p));
    st.presetBtns.set(p.id, b);
    return b;
  };
  // T127: objects first (what the challenge looks for), then the T107 places; presets without a group are places
  const groups = [["object", "Presets for objects"], ["place", "Presets for places"]]
    .map(([g, title]) => [title, st.presets.filter((p) => (p.group ?? "place") === g), g]).filter(([, ps]) => ps.length);
  const presets = groups.length ? el("div", { class: "chem-presets", role: "group", "aria-label": "Presets" },
    ...groups.flatMap(([title, ps, g]) => [el("span", { class: "muted small chem-group" }, title), ...ps.map(presetBtn),
      g === "object" ? el("span", { class: "muted small" }, "Comets and asteroids move between exposures: each map "
        + "combines all of them, so they do not show here (blink the field instead).") : null].filter(Boolean))) : null;
  const zIn = el("input", { id: "chem-z", type: "number", min: "0", max: "1", step: "0.0001", value: "0", inputmode: "decimal",
    title: "Redshift of the object: its features arrive at λ × (1 + z). 0 for anything in the Milky Way." });
  zIn.addEventListener("change", () => setZ(zIn.value));
  const zRow = el("div", { class: "chem-zrow" }, el("label", { for: "chem-z" }, "Redshift z "), zIn,
    el("p", { id: "chem-z-hint", class: "muted small" }));
  // T137: the open list ends above the window's bottom and scrolls (the panels float over a fixed map since T124,
  // so the page can't scroll to its end); a list inside its panel (narrow screens) keeps style.css's cap
  const fit = () => {
    const list = $("#chem-list");
    if (!box.open || !list) return;
    list.style.maxHeight = getComputedStyle(list).position === "absolute"
      ? `${Math.max(160, Math.floor(innerHeight - list.getBoundingClientRect().top - 12))}px` : "";
  };
  box.addEventListener("toggle", () => { if (box.open) { askRedshift(); fit(); } });
  addEventListener("resize", fit);
  $("#chem-list").prepend(...[presets, zRow].filter(Boolean), ...st.features.map((f) => {
    const cb = el("input", { type: "checkbox", value: f.id });
    cb.addEventListener("change", () => toggle(f.id, cb.checked));
    st.boxes.set(f.id, cb);
    return el("label", { class: "chem-row", title: f.what }, cb, el("span", { class: "chem-key chem-swatch", hidden: true }),
      ` ${f.name} · ${fmtNum(f.um, 2)} µm `, el("span", { class: "muted small" }, f.shows === "emission" ? "emits" : "absorbs"));
  }));
  $("#chem-hint").textContent = "Pick a preset, or tick features: one = a grey map, more = one colour picture (clearest with up to three).";
  syncControls();
  visible();
}
