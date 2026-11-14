// Stacks in the viewer. The maths is in stack.js. Exclusive with the difference and trail views.
//  - T59 (challenge: "add together all the data taken by each of the six detector arrays", "add together ...
//    images taken at different times"): "per epoch" = all frames of the shown frame's epoch (all detectors),
//    "per detector" = all frames of its detector (all epochs). Blink and play keep working: each A/B switch
//    shows the stack of that frame's group, so blinking two epochs compares two deep images.
//  - T69 shift-and-stack: "along the selected object" shifts every frame so the clicked object stays put (it
//    adds up sharp, stars smear); "along a guessed motion" does the same for a rate + direction typed in, over
//    the shown frame's epoch: the standard way to find movers too faint for one frame (Planet X mode, T10).

import { $, el, fmtNum } from "./util.js";
import { currentPair, currentTarget } from "./viewer.js";
import { pixels } from "./diff.js";
import { shiftsAlong, shiftsForMotion, stackGroup, stackPixels } from "./stack.js";

const st = { mode: "off", frameId: null, obj: null, cache: new Map(), token: 0 };
const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

function canvas() {
  let c = $("#stack-canvas");
  if (!c) {
    c = el("canvas", { id: "stack-canvas", class: "diff-canvas", "aria-hidden": "true", hidden: true });
    $("#frame-stack").after(c); // above the frames, below the SVG overlay (names and paths stay on top)
  }
  return c;
}

const imageUrl = (id) => [...document.querySelectorAll("#frame-stack img")].find((i) => i.alt === `Frame ${id}`)?.src;
const lamRange = (fs) => {
  const w = fs.map((f) => f.wavelength_um).filter(Number.isFinite);
  return w.length ? `${fmtNum(Math.min(...w), 2)}–${fmtNum(Math.max(...w), 2)} µm` : "";
};

function hide(message = "") {
  canvas().hidden = true;
  $("#stage-stack-label").hidden = true;
  $("#stack-note").textContent = message;
  $("#stack-note").hidden = !message;
  if ($("#btn-diff").getAttribute("aria-pressed") !== "true") $("#stage-label").hidden = false;
}

/** What to stack for the frame on screen: {frames, shifts, label, note} or {message} when nothing can be stacked. */
function plan(t, frame) {
  const sorted = [...t.frames].sort((a, b) => a.mjd - b.mjd);
  if (st.mode === "epoch" || st.mode === "detector") {
    const group = stackGroup(sorted, frame, st.mode);
    const epochs = [...new Set(group.map((f) => f.epoch))];
    return {
      frames: group, shifts: null,
      label: st.mode === "epoch"
        ? `Stack · epoch ${frame.epoch} · ${group.length} frames · all detectors (${lamRange(group)})`
        : `Stack · detector ${frame.detector} (${lamRange(group)}) · ${group.length} frames · epoch${epochs.length > 1 ? "s" : ""} ${epochs.join(", ")}`,
      note: st.mode === "epoch"
        ? "Blink A and B from different epochs to compare the stacks: steady stars stay, movers jump."
        : "One detector (band) over all epochs: steady sources get deeper; anything that moved shows blurred or several times.",
    };
  }
  if (st.mode === "object") {
    if (!st.obj) return { message: "Click an object on the image (a name, an asteroid, a detection), and the stack follows it." };
    const { frames, shifts } = shiftsAlong(sorted, st.obj.positions ?? []);
    if (frames.length < 2) return { message: `${st.obj.name} has a position in ${frames.length} frame only: nothing to stack along.` };
    return {
      frames, shifts, label: `Stack along ${st.obj.name} · ${frames.length} frames`,
      note: `Every frame is shifted so that ${st.obj.name} stays in place: it adds up sharp, while everything that ` +
        "doesn't move with it smears into a row of dots or a streak. That is how movers too faint for one frame are found.",
    };
  }
  // st.mode === "motion": a guessed motion over the shown frame's epoch
  const rate = Number($("#stack-rate").value), pa = Number($("#stack-pa").value);
  if (!(rate > 0) || !Number.isFinite(pa)) return { message: "Type a rate (″ per hour) and a direction (degrees from north through east)." };
  const group = sorted.filter((f) => f.epoch === frame.epoch);
  const shifts = shiftsForMotion(group, group[0], rate, pa, t.image?.pixel_scale_arcsec ?? 6.15);
  const far = Math.max(...shifts.map((s) => Math.hypot(s.dx, s.dy)));
  const dir = COMPASS[Math.round((((pa % 360) + 360) % 360) / 45) % 8];
  return {
    frames: group, shifts,
    label: `Stack along a guessed motion · ${+rate.toFixed(2)}″/h toward ${+pa.toFixed(0)}° (${dir}) · epoch ${frame.epoch} · ${group.length} frames`,
    note: "Every frame of this epoch is shifted by the motion you typed: anything that really moves that way piles up " +
      `into one sharp dot, steady stars smear. This epoch's frames span ${fmtNum((group[group.length - 1].mjd - group[0].mjd), 1)} days, ` +
      "so only slow motions stay on the image (below ~0.5″/h: bodies far beyond Neptune move ~0.1–0.3″/h); " +
      "asteroids (~30″/h) cross the field between frames." +
      (far > (t.image?.width ?? 100) / 2 ? ` At this rate the shift reaches ${fmtNum(far, 0)} px over the epoch, so most frames only overlap part of the field.` : ""),
  };
}

async function draw() {
  const t = currentTarget();
  if (st.mode === "off" || !t) { hide(); return; }
  const frame = t.frames.find((f) => f.id === st.frameId) ?? t.frames[0];
  const pl = plan(t, frame);
  if (pl.message) { hide(pl.message); return; }
  const { width = 1, height = 1 } = t.image ?? {};
  const shiftKey = pl.shifts ? pl.shifts.map((s) => `${s.dx.toFixed(2)},${s.dy.toFixed(2)}`).join(";") : "";
  const key = `${t.id}|${pl.frames.map((f) => f.id).join()}|${shiftKey}|${imageUrl(frame.id)}`;
  const token = ++st.token;
  let img = st.cache.get(key);
  try {
    if (!img) {
      const datas = await Promise.all(pl.frames.map((f) => pixels(imageUrl(f.id), width, height)));
      if (token !== st.token || st.mode === "off") return;
      img = stackPixels(datas, width, height, pl.shifts);
      st.cache.set(key, img);
    }
  } catch (err) {
    if (token === st.token) hide(`Stack unavailable: ${err.message ?? err}`);
    return;
  }
  if (token !== st.token) return;
  const c = canvas();
  c.width = width;
  c.height = height;
  c.getContext("2d").putImageData(new ImageData(img.data, width, height), 0, 0);
  c.hidden = false;
  $("#stage-label").hidden = true;
  const p = currentPair();
  const slot = p?.a.id === frame.id ? "A · " : p?.b.id === frame.id ? "B · " : "";
  $("#stage-stack-label").textContent = (st.mode === "epoch" || st.mode === "detector" ? slot : "") + pl.label;
  $("#stage-stack-label").hidden = false;
  const gain = fmtNum(Math.sqrt(Math.max(img.frames, 1)), 1);
  $("#stack-note").textContent = `${img.frames} aligned frames added together: faint sources stand out about ${gain}× better ` +
    `than in one frame. ${pl.note} For looking, not for measuring brightness (built from the display images).`;
  $("#stack-note").hidden = false;
}

function setMode(mode) {
  st.mode = mode;
  $("#stack-mode").value = mode;
  $("#stack-motion").hidden = mode !== "motion";
  if (mode !== "off") {
    if ($("#btn-diff").getAttribute("aria-pressed") === "true") $("#btn-diff").click(); // one overlay at a time
    const trail = $("#trail-on");
    if (trail?.checked) { trail.checked = false; trail.dispatchEvent(new Event("change")); }
  }
  draw();
}

export function initStack() {
  $("#stack-mode").addEventListener("change", (e) => setMode(e.target.value));
  for (const id of ["#stack-rate", "#stack-pa"]) $(id).addEventListener("change", () => { if (st.mode === "motion") draw(); });
  // The difference view (button or D key) and the trail view end the stack.
  new MutationObserver(() => {
    if ($("#btn-diff").getAttribute("aria-pressed") === "true" && st.mode !== "off") setMode("off");
  }).observe($("#btn-diff"), { attributes: true, attributeFilter: ["aria-pressed"] });
  document.addEventListener("change", (e) => { if (e.target?.id === "trail-on" && e.target.checked && st.mode !== "off") setMode("off"); });
  document.addEventListener("paths:select", (e) => { st.obj = e.detail?.obj ?? null; if (st.mode === "object") draw(); });
  document.addEventListener("viewer:frame", (e) => { st.frameId = e.detail?.frameId ?? null; if (st.mode !== "off") draw(); });
  document.addEventListener("viewer:target", () => {
    st.cache.clear(); st.frameId = null; st.obj = null;
    if (st.mode !== "off") draw(); else hide();
  });
}
