// Trail view (T23): stack frames with "brightest pixel wins", so steady stars stay single dots and
// anything that moved leaves a row of dots or a streak. Works on the frame images the viewer has
// already loaded; nothing is fetched. Listens to the viewer's events like paths.js:
//   viewer:target {target}   viewer:frame {frameId}

import { $, el } from "./util.js";

const st = { target: null, frames: [], frameId: null, on: false, scope: "epoch" };

function canvas() {
  let c = $("#trail-canvas");
  if (!c) {
    c = el("canvas", { id: "trail-canvas", class: "trail-canvas", "aria-hidden": "true", hidden: true });
    $("#frame-stack").after(c); // above the frames, below the SVG overlay (labels and paths stay on top)
  }
  return c;
}

function framesInScope() {
  const cur = st.frames.find((f) => f.id === st.frameId) ?? st.frames[0];
  return st.scope === "epoch" ? st.frames.filter((f) => f.epoch === cur?.epoch) : st.frames;
}

function imageFor(id) {
  return [...document.querySelectorAll("#frame-stack img")].find((i) => i.alt === `Frame ${id}`);
}

function draw() {
  const c = canvas();
  c.hidden = !st.on || !st.target;
  updateNote();
  if (c.hidden) return;
  const { width = 1, height = 1 } = st.target.image ?? {};
  c.width = width; c.height = height;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.globalCompositeOperation = "source-over";
  ctx.clearRect(0, 0, width, height);
  ctx.globalCompositeOperation = "lighten"; // per pixel: keep the brighter value = max stack
  let used = 0;
  for (const f of framesInScope()) {
    const img = imageFor(f.id);
    if (img?.complete && img.naturalWidth) { ctx.drawImage(img, 0, 0, width, height); used++; }
    else img?.addEventListener("load", draw, { once: true });
  }
  c.dataset.used = String(used);
  updateNote();
}

function updateNote() {
  const n = $("#trail-note");
  if (!n) return;
  if (!st.on) { n.textContent = ""; return; }
  const sel = framesInScope();
  const cur = st.frames.find((f) => f.id === st.frameId);
  n.textContent = `${canvas().dataset.used ?? sel.length} frames stacked (${st.scope === "epoch" ? `epoch ${cur?.epoch ?? "?"}` : "all epochs"}), brightest pixel wins · movers show as rows of dots`;
}

function controls() {
  if ($("#trail-controls")) return;
  const box = el("div", { id: "trail-controls", class: "paths-row trail-row" },
    el("label", { class: "paths-check" },
      el("input", { type: "checkbox", id: "trail-on", onchange: (e) => { st.on = e.target.checked; draw(); } }), " Trail view"),
    el("label", { class: "paths-check" }, "of ",
      el("select", { id: "trail-scope", onchange: (e) => { st.scope = e.target.value; draw(); } },
        el("option", { value: "epoch" }, "this epoch"), el("option", { value: "all" }, "all epochs"))),
    el("span", { id: "trail-note", class: "muted small" }));
  const anchor = $("#paths-controls") ?? $("#viewer-body .controls");
  anchor.after(box);
}

document.addEventListener("viewer:target", (e) => {
  st.target = e.detail?.target ?? null;
  st.frames = st.target ? [...st.target.frames].sort((a, b) => a.mjd - b.mjd) : [];
  st.frameId = null;
  if (!st.target) { canvas().hidden = true; return; }
  controls();
});

document.addEventListener("viewer:frame", (e) => {
  const prev = st.frames.find((f) => f.id === st.frameId)?.epoch;
  st.frameId = e.detail?.frameId ?? null;
  const now = st.frames.find((f) => f.id === st.frameId)?.epoch;
  if (st.on && (st.scope === "all" ? !canvas().dataset.used : prev !== now)) draw(); // only redraw when the set changes
  else updateNote();
});
