// T93 "Chemistry" on the sky map: for the shown field, where does a chemical feature absorb or emit? The Live API
// makes the map (pipeline/chemistry.py: the image at the feature's wavelength minus the continuum from just below
// and above, from the field's own SPHEREx exposures) and serves it as the map layer x-<feature>. Visualization
// only: the note says what dark / bright means and what can fool it; the user judges.

import { $, el, fmtNum } from "./util.js";
import * as explore from "./explore.js";

const st = { api: null, target: null, features: [], token: 0, shown: null };

function note(parts) {
  const box = $("#chem-note");
  box.replaceChildren(...parts.filter(Boolean));
  box.hidden = parts.filter(Boolean).length === 0;
}

function off() {
  st.token++;
  st.shown = null;
  $("#chem-feature").value = "";
  note([]);
}

async function pick(id) {
  const token = ++st.token;
  const t = st.target;
  const f = st.features.find((x) => x.id === id);
  if (!id || !t || !f) { off(); return; }
  const url = `${st.api}/api/targets/${encodeURIComponent(t.id)}/chemistry?feature=${encodeURIComponent(id)}`;
  note([el("strong", {}, `${f.name} (${fmtNum(f.um, 2)} µm): `), "measuring the field's SPHEREx exposures around this wavelength…"]);
  let body;
  try {
    let res = await fetch(`${url}&start=1`);
    body = await res.json();
    while (res.status === 202 && token === st.token) {
      note([el("strong", {}, `${f.name} (${fmtNum(f.um, 2)} µm): `),
        `measuring… ${body.done ?? 0} of ${body.total || "?"} exposures`]);
      await new Promise((r) => setTimeout(r, 1500));
      res = await fetch(url);
      body = await res.json();
    }
  } catch (err) {
    if (token === st.token) note([`Chemistry map unavailable: ${err.message ?? err}`]);
    return;
  }
  if (token !== st.token) return;
  if (body.status !== "ready") { note([`${f.name}: ${body.message ?? body.status}`]); return; }
  st.shown = body.layer;
  const ok = await explore.showLayer(body.layer);
  if (token !== st.token) return;
  const png = `${st.api}/api/targets/${encodeURIComponent(t.id)}/chemistry/${id}.png`;
  note([
    el("strong", {}, `${body.name} (${fmtNum(body.um, 2)} µm) minus its continuum. `),
    el("span", { class: "chem-key chem-dark" }), " darker = less light than at the neighbouring wavelengths (absorption) · ",
    el("span", { class: "chem-key chem-grey" }), " grey = like the neighbours · ",
    el("span", { class: "chem-key chem-bright" }), " brighter = more light (emission). ",
    `${body.what}. `,
    `From ${body.exposures_used} SPHEREx exposures (per spot: ${body.median_on} on the feature, ${body.median_continuum} around it; `,
    `±5 noise levels = black / white). Stars mostly cancel; leftover black-and-white pairs at stars are sharpness differences, not chemistry. `,
    ok ? null : "(The map layer could not be shown here.) ",
    el("a", { href: png, target: "_blank", rel: "noopener" }, "map image"),
  ]);
}

export async function initChemistry(api) {
  st.api = api?.replace(/\/$/, "") ?? null;
  const box = $("#chem-box");
  if (!box || !st.api) return;
  $("#chem-feature").addEventListener("change", (e) => pick(e.target.value));
  // Another view took over the map (A/B, blink, A − B, an epoch button): the chemistry map is gone.
  for (const ev of ["viewer:frame", "viewer:diff", "explore:epoch-picked"]) document.addEventListener(ev, () => { if (st.shown) off(); });
  document.addEventListener("viewer:target", (e) => {
    off();
    st.target = e.detail?.target ?? null;
    box.hidden = !st.target || st.target.synthetic || !st.features.length || !explore.getSky();
  });
  try {
    const res = await fetch(`${st.api}/api/chemistry/features`);
    st.features = (await res.json()).features ?? [];
  } catch { st.features = []; }
  $("#chem-feature").append(...st.features.map((f) =>
    el("option", { value: f.id, title: f.what }, `${f.name} · ${fmtNum(f.um, 2)} µm`)));
  box.hidden = !st.target || st.target.synthetic || !st.features.length || !explore.getSky();
}
