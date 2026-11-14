// Object inspector (T23): click an object on the image (label, known object or detection) and a
// side panel shows what it is, how it moves and its history frame by frame. paths.js sends the
// object with a "paths:select" event; clicking a history row jumps to that frame.
//
// "Brightness here" is read from the display PNG (already stretched, 0-255), so it is a relative
// value for comparing frames, not a calibrated flux.

import { $, el, fmtNum, sourceName } from "./util.js";
import { showFrame } from "./viewer.js";

const st = { target: null, obj: null, frameId: null, samples: new Map() };

function panel() {
  let p = $("#inspector");
  if (!p) {
    p = el("section", { id: "inspector", class: "panel inspector", hidden: true, "aria-labelledby": "inspector-title" },
      el("div", { class: "insp-head" },
        el("h3", { id: "inspector-title" }, "Inspector"),
        el("button", { type: "button", class: "link", onclick: close }, "Close")),
      el("div", { id: "inspector-body" }));
    $("#side").prepend(p);
  }
  return p;
}

function close() {
  st.obj = null;
  panel().hidden = true;
}

const sexa = (deg, hours) => {
  const v = hours ? deg / 15 : Math.abs(deg);
  const h = Math.floor(v), m = Math.floor((v - h) * 60), s = ((v - h) * 60 - m) * 60;
  return hours ? `${h}h${String(m).padStart(2, "0")}m${s.toFixed(1).padStart(4, "0")}s`
    : `${deg < 0 ? "−" : "+"}${h}°${String(m).padStart(2, "0")}′${s.toFixed(0).padStart(2, "0")}″`;
};

function lookupLinks(ra, dec) {
  const sign = dec >= 0 ? "%2B" : "";
  return el("p", { class: "small insp-links" },
    el("a", { href: `https://simbad.cfa.harvard.edu/simbad/sim-coo?Coord=${ra.toFixed(5)}%20${sign}${dec.toFixed(5)}&Radius=10&Radius.unit=arcsec`, target: "_blank", rel: "noopener" }, "SIMBAD ↗"),
    " · ",
    el("a", { href: `https://irsa.ipac.caltech.edu/applications/finderchart/?locstr=${ra.toFixed(5)}+${dec.toFixed(5)}`, target: "_blank", rel: "noopener" }, "IRSA finder chart ↗"));
}

function motionRows(o) {
  const m = o.motion;
  if (!m) return o.pm != null ? [["Proper motion", `${(o.pm / 1000).toFixed(3)}″/yr`]] : [];
  const rate = m.class === "fast mover" ? `${fmtNum(m.max_rate_within_epoch_arcsec_per_hr, 1)}″/h within an epoch`
    : m.rate_arcsec_per_yr != null ? `${fmtNum(m.rate_arcsec_per_yr, 2)}″/yr` : "–";
  return [
    ["Motion class", m.class],
    ["", m.note],
    ["Rate", rate],
    ["Direction", m.direction ? `${m.direction} (${fmtNum(m.pa_deg, 0)}° E of N)` : "–"],
    ["Over the series", `${fmtNum(m.shift_arcsec, 1)}″ = ${fmtNum(m.shift_px, 2)} px in ${fmtNum(m.days, 0)} days`],
  ];
}

function render() {
  const o = st.obj;
  if (!o || !st.target) return;
  const p = panel();
  p.hidden = false;
  const frames = [...st.target.frames].sort((a, b) => a.mjd - b.mjd);
  const pos = new Map(o.positions.map((q) => [q.frame_id, q]));
  const cur = pos.get(st.frameId) ?? o.positions[0];
  const info = [
    ["Type", o.info + (o.otype && o.otype !== "*" ? ` (${o.otype})` : "")],
    ["Catalogue", sourceName(o.source)],
    ...(o.note ? [["About", o.note]] : []),
    ...(o.mag != null ? [["Brightness", `${o.magBand ?? "G"} = ${fmtNum(o.mag, 2)} mag`]] : []),
    ...motionRows(o),
    ...(cur ? [["Position now", `${sexa(cur.ra_deg, true)} ${sexa(cur.dec_deg, false)}`], ["", `${fmtNum(cur.ra_deg, 5)}°, ${fmtNum(cur.dec_deg, 5)}°`]] : []),
    ...(o.synthetic ? [["Note", "synthetic, not a real object"]] : []),
  ];
  const rows = frames.filter((f) => pos.has(f.id)).map((f) => {
    const q = pos.get(f.id), b = st.samples.get(f.id);
    return el("tr", { class: f.id === st.frameId ? "shown" : null, onclick: () => showFrame(f.id), title: "show this frame" },
      el("td", {}, f.time_utc?.slice(0, 16).replace("T", " ") ?? "–"),
      el("td", {}, String(f.epoch ?? "–")),
      el("td", {}, fmtNum(f.wavelength_um, 2)),
      el("td", {}, `${fmtNum(q.x, 1)}, ${fmtNum(q.y, 1)}`),
      el("td", { class: "insp-bright" }, b == null ? "…" : b < 0 ? "no data" : el("span", { class: "bar", style: `--v:${b / 255}` }, String(b))));
  });
  $("#inspector-body").replaceChildren(
    el("p", { class: "insp-name" }, o.name),
    el("dl", { class: "info" }, ...info.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
    cur && !o.synthetic ? lookupLinks(cur.ra_deg, cur.dec_deg) : null,
    el("h3", { class: "insp-sub" }, `History · ${rows.length} frames`),
    el("p", { class: "muted small" }, "Brightness here = brightest display pixel within 1 px (0–255, stretched, not calibrated). Click a row to show that frame."),
    el("div", { class: "table-wrap" }, el("table", { class: "frames insp-table" },
      el("thead", {}, el("tr", {}, ...["Time (UTC)", "Ep.", "λ µm", "x, y px", "Bright."].map((h) => el("th", {}, h)))),
      el("tbody", {}, ...rows))));
}

// Read brightness at the object's position in each frame (cross-origin images need CORS: the Live
// API sends it; offline ?data= folders are same-origin anyway).
async function sample(o) {
  st.samples = new Map();
  const imgs = [...document.querySelectorAll("#frame-stack img")];
  const c = document.createElement("canvas"), ctx = c.getContext("2d", { willReadFrequently: true });
  for (const q of o.positions) {
    const src = imgs.find((i) => i.alt === `Frame ${q.frame_id}`)?.src;
    if (!src) continue;
    try {
      const im = new Image(); im.crossOrigin = "anonymous"; im.src = src; await im.decode();
      c.width = im.naturalWidth; c.height = im.naturalHeight; ctx.drawImage(im, 0, 0);
      const x0 = Math.round(q.x), y0 = Math.round(q.y);
      let best = -1;
      for (let y = y0 - 1; y <= y0 + 1; y++) for (let x = x0 - 1; x <= x0 + 1; x++) {
        if (x < 0 || y < 0 || x >= c.width || y >= c.height) continue;
        const d = ctx.getImageData(x, y, 1, 1).data;
        if (d[3] > 0) best = Math.max(best, d[0]);
      }
      st.samples.set(q.frame_id, best);
    } catch { /* tainted or failed: leave "…" */ }
    if (st.obj === o) render();
  }
}

document.addEventListener("paths:select", (e) => {
  st.obj = e.detail?.obj ?? null;
  if (!st.obj) return close();
  render();
  sample(st.obj);
});
document.addEventListener("viewer:target", (e) => { st.target = e.detail?.target ?? null; close(); });
document.addEventListener("viewer:frame", (e) => { st.frameId = e.detail?.frameId ?? null; if (st.obj) render(); });
