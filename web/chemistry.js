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

import { $, el, fmtNum } from "./util.js";
import * as explore from "./explore.js";

const st = { api: null, target: null, features: [], presets: [], presetBtns: new Map(), combine: { max: 3, colours: {} }, sel: [], boxes: new Map(),
  ready: new Map(), token: 0, shown: null };

const byId = (id) => st.features.find((f) => f.id === id);
const inOrder = (ids) => [...ids].sort((a, b) => byId(a).um - byId(b).um);
const label = (f) => `${f.name} (${fmtNum(f.um, 2)} µm)`;
const base = () => `${st.api}/api/targets/${encodeURIComponent(st.target.id)}/chemistry`;

/** The preset whose features are exactly these (ticked by its button or by hand), or undefined. */
const presetOf = (ids) => st.presets.find((p) => p.features.length === ids.length && p.features.every((f) => ids.includes(f)));

/** id -> colour in the picture of these features (empty for one: the grey map). */
function colours(ids) {
  const cs = st.combine.colours?.[String(ids.length)];
  return new Map(ids.length > 1 && cs ? inOrder(ids).map((id, i) => [id, cs[i]]) : []);
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
  st.sel = [...p.features];
  syncControls();
  apply();
}

/** Make (or reuse) one feature's map; resolves with the ready body or an error body. */
async function ensure(id, token, k, n) {
  if (st.ready.has(id)) return st.ready.get(id);
  const f = byId(id);
  const which = n > 1 ? ` (${k + 1} of ${n})` : "";
  const url = `${base()}?feature=${encodeURIComponent(id)}`;
  note([el("strong", {}, `${label(f)}${which}: `), "measuring the field's SPHEREx exposures around this wavelength…"]);
  let res = await fetch(`${url}&start=1`);
  let body = await res.json();
  while (res.status === 202 && token === st.token) {
    note([el("strong", {}, `${label(f)}${which}: `), `measuring… ${body.done ?? 0} of ${body.total || "?"} exposures`]);
    await new Promise((r) => setTimeout(r, 1500));
    res = await fetch(url);
    body = await res.json();
  }
  if (body.status === "ready") st.ready.set(id, body);
  return body;
}

async function apply() {
  const token = ++st.token;
  const ids = inOrder(st.sel);
  if (!st.target || !ids.length) return;
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
  const layer = `x-${ids.join("-")}`;
  st.shown = layer;
  document.dispatchEvent(new CustomEvent("map:take"));          // the automatic blink leaves the map alone
  const ok = await explore.showLayer(layer);
  if (token !== st.token) return;
  const png = `${base()}/${ids.join("-")}.png`;
  const tail = [ok ? null : "(The map layer could not be shown here.) ",
    el("a", { href: png, target: "_blank", rel: "noopener" }, ids.length > 1 ? "picture" : "map image")];
  if (ids.length === 1) {
    const b = stats[0];
    note([
      el("strong", {}, `${label(b)} minus its continuum. `),
      el("span", { class: "chem-key chem-dark" }), " darker = less light than at the neighbouring wavelengths (absorption) · ",
      el("span", { class: "chem-key chem-grey" }), " grey = like the neighbours · ",
      el("span", { class: "chem-key chem-bright" }), " brighter = more light (emission). ",
      `${b.what}. `,
      `From ${b.exposures_used} SPHEREx exposures (per spot: ${b.median_on} on the feature, ${b.median_continuum} around it; `,
      "±5 noise levels = black / white). Stars mostly cancel; leftover black-and-white pairs at stars are sharpness differences, not chemistry. ",
      ...tail,
    ]);
    return;
  }
  const cs = colours(ids);
  const pre = presetOf(ids);
  const here = pre && st.target && Math.abs(st.target.center?.ra_deg - pre.try.ra) < 0.2 && Math.abs(st.target.center?.dec_deg - pre.try.dec) < 0.2;
  note([
    pre ? el("strong", {}, `${pre.name}: `) : null,
    pre ? `${pre.looks_for}. ${pre.read} ` : null,
    pre ? el("span", { class: "chem-line" }, el("em", {}, "Can fool it: "), pre.caveats) : null,
    pre && !here ? el("span", { class: "chem-line" }, "Tried on: ",
      el("a", { href: `?ra=${pre.try.ra}&dec=${pre.try.dec}&size=${pre.try.size}` }, pre.try.name), ".") : null,
    el("strong", {}, `${stats.map((b) => b.name).join(" + ")}, one colour each. `),
    ...stats.map((b) => el("span", { class: "chem-line" },
      el("span", { class: "chem-key", style: `background:${cs.get(b.feature ?? b.id)}` }),
      ` ${label(b)}: ${byId(b.feature ?? b.id).shows === "emission" ? "where it emits" : "where it absorbs (depth)"} · `,
      `${b.what} · ${b.exposures_used} exposures`)),
    "Brighter = stronger (from one noise level; full colour at five). Where colours mix, several are strong at the same spot ",
    ids.length <= 3 ? "(e.g. red + green = yellow, all three = white); " :
      el("em", {}, `with ${ids.length} colours a mix can look like another feature's own colour (e.g. green + red = yellow): check a spot with its single maps; `),
    "black = none of them stands out. Shown where all the maps have data. ",
    "Coloured pairs at stars are sharpness differences, not chemistry. ",
    ...tail,
  ]);
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
    visible();
  });
  $("#chem-clear").addEventListener("click", clear);
  try {
    const body = await (await fetch(`${st.api}/api/chemistry/features`)).json();
    st.features = body.features ?? [];
    if (body.combine) st.combine = body.combine;
    st.presets = (body.presets ?? []).filter((p) => p.features.length <= st.combine.max && p.features.every(byId));
  } catch { st.features = []; st.presets = []; }
  const presets = st.presets.length ? el("div", { class: "chem-presets", role: "group", "aria-label": "Presets" },
    el("span", { class: "muted small" }, "Presets"),
    ...st.presets.map((p) => {
      const b = el("button", { type: "button", class: "chem-preset", "aria-pressed": "false",
        title: `${p.looks_for}. Tried on: ${p.tested}.` }, p.name,
      el("span", { class: "muted small" }, ` ${p.features.map((f) => byId(f).name).join(" + ")}`));
      b.addEventListener("click", () => choosePreset(p));
      st.presetBtns.set(p.id, b);
      return b;
    })) : null;
  $("#chem-list").prepend(...[presets].filter(Boolean), ...st.features.map((f) => {
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
