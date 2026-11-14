// Stacks in the viewer (T59, challenge: "add together all the data taken by each of the six detector arrays",
// "add together ... images taken at different times"). "Stack: per epoch" shows, for the frame on screen, all
// frames of its epoch added together (all detectors); "per detector" all frames of its detector (all epochs).
// Blink and play keep working: each A/B switch shows the stack of that frame's group, so blinking two epochs
// compares two deep images. Exclusive with the difference and trail views. The maths is in stack.js.

import { $, el, fmtNum } from "./util.js";
import { currentPair, currentTarget } from "./viewer.js";
import { pixels } from "./diff.js";
import { stackGroup, stackPixels } from "./stack.js";

const st = { mode: "off", frameId: null, cache: new Map(), token: 0 };

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

function hide() {
  canvas().hidden = true;
  $("#stage-stack-label").hidden = true;
  $("#stack-note").hidden = true;
  if ($("#btn-diff").getAttribute("aria-pressed") !== "true") $("#stage-label").hidden = false;
}

async function draw() {
  const t = currentTarget();
  if (st.mode === "off" || !t) { hide(); return; }
  const frame = t.frames.find((f) => f.id === st.frameId) ?? t.frames[0];
  const group = stackGroup(t.frames, frame, st.mode);
  const { width = 1, height = 1 } = t.image ?? {};
  const key = `${t.id}|${st.mode}|${group.map((f) => f.id).join()}|${imageUrl(frame.id)}`;
  const token = ++st.token;
  let img = st.cache.get(key);
  try {
    if (!img) {
      const urls = group.map((f) => imageUrl(f.id)).filter(Boolean);
      const datas = await Promise.all(urls.map((u) => pixels(u, width, height)));
      if (token !== st.token || st.mode === "off") return;
      img = stackPixels(datas, width, height);
      st.cache.set(key, img);
    }
  } catch (err) {
    if (token !== st.token) return;
    $("#stack-note").textContent = `Stack unavailable: ${err.message ?? err}`;
    $("#stack-note").hidden = false;
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
  const epochs = [...new Set(group.map((f) => f.epoch))].sort((a, b) => a - b);
  $("#stage-stack-label").textContent = st.mode === "epoch"
    ? `${slot}Stack · epoch ${frame.epoch} · ${img.frames} frames · all detectors (${lamRange(group)})`
    : `${slot}Stack · detector ${frame.detector} (${lamRange(group)}) · ${img.frames} frames · epoch${epochs.length > 1 ? "s" : ""} ${epochs.join(", ")}`;
  $("#stage-stack-label").hidden = false;
  const gain = fmtNum(Math.sqrt(Math.max(img.frames, 1)), 1);
  $("#stack-note").textContent = `${img.frames} aligned frames added together: faint sources stand out about ${gain}× better ` +
    "than in one frame. " + (st.mode === "epoch"
      ? "Blink A and B from different epochs to compare the stacks: steady stars stay, movers jump."
      : "One detector (band) over all epochs: steady sources get deeper; anything that moved shows blurred or several times.") +
    " For looking, not for measuring brightness (built from the display images).";
  $("#stack-note").hidden = false;
}

function setMode(mode) {
  st.mode = mode;
  $("#stack-mode").value = mode;
  if (mode !== "off") {
    if ($("#btn-diff").getAttribute("aria-pressed") === "true") $("#btn-diff").click(); // one overlay at a time
    const trail = $("#trail-on");
    if (trail?.checked) { trail.checked = false; trail.dispatchEvent(new Event("change")); }
  }
  draw();
}

export function initStack() {
  $("#stack-mode").addEventListener("change", (e) => setMode(e.target.value));
  // The difference view (button or D key) and the trail view end the stack.
  new MutationObserver(() => {
    if ($("#btn-diff").getAttribute("aria-pressed") === "true" && st.mode !== "off") setMode("off");
  }).observe($("#btn-diff"), { attributes: true, attributeFilter: ["aria-pressed"] });
  document.addEventListener("change", (e) => { if (e.target?.id === "trail-on" && e.target.checked && st.mode !== "off") setMode("off"); });
  document.addEventListener("viewer:frame", (e) => { st.frameId = e.detail?.frameId ?? null; if (st.mode !== "off") draw(); });
  document.addEventListener("viewer:target", () => { st.cache.clear(); st.frameId = null; if (st.mode !== "off") draw(); else hide(); });
}
