// T78: "Frames at λ" in the blink viewer. Type a wavelength (µm), A and B become the frames closest to it in
// the earliest and the latest epoch (lambda.js picks them), and a note says how far off each one is: SPHEREx's
// linear variable filters put every exposure at a slightly different wavelength, so no frame hits it exactly.
// The value goes into the page URL (?lam=2.17), so a link shows the same frames; app.js uses the same
// parameter for the sky map's band.

import { $, el, fmtNum } from "./util.js";
import { currentTarget, selectPair, showFrame } from "./viewer.js";
import { FEATURES } from "./spectrum.js";
import { framesAt, parseLam } from "./lambda.js";

export const lamFromUrl = () => parseLam(new URLSearchParams(location.search).get("lam"));

export function setLamUrl(lam) {
  const u = new URL(location.href);
  if (lam == null) u.searchParams.delete("lam");
  else u.searchParams.set("lam", String(+lam.toFixed(4)));
  if (u.href !== location.href) history.replaceState(history.state, "", u);
}

const signed = (v) => `${v >= 0 ? "+" : "−"}${fmtNum(Math.abs(v), 3)}`;

function apply(lam) {
  const t = currentTarget();
  const note = $("#lam-at-note");
  if (!t) return;
  const r = framesAt(t.frames ?? [], lam);
  if (!r) { note.textContent = "No frame has a wavelength."; return; }
  const part = (slot, f, off) => `${slot} ${f.id} (epoch ${f.epoch}) at ${fmtNum(f.wavelength_um, 3)} µm (${signed(off)})`;
  if (r.b) selectPair(r.a.id, r.b.id);
  else showFrame(r.a.id);
  const far = Math.max(Math.abs(r.offA), Math.abs(r.offB ?? 0)) > 0.1;
  note.textContent = [
    part("A", r.a, r.offA),
    r.b ? part("B", r.b, r.offB) : "only one epoch has a frame near it",
    r.b ? (r.matched ? "same wavelength: a fair comparison" : "not quite the same wavelength: stars may differ in brightness") : null,
    far ? "the closest frames in this field" : null,
  ].filter(Boolean).join(" · ");
  setLamUrl(lam);
}

export function initLamPick() {
  $("#lam-features").replaceChildren(...FEATURES.map((f) => el("option", { value: String(f.um) }, f.name)));
  const input = $("#lam-at");
  input.addEventListener("change", () => {
    const text = input.value.trim();
    if (!text) { $("#lam-at-note").textContent = ""; setLamUrl(null); return; }
    const lam = parseLam(text);
    if (lam == null) {
      $("#lam-at-note").textContent = "Type a wavelength between 0.75 and 5.0 µm, e.g. 2.17 (or 2170 nm).";
      return;
    }
    input.value = String(+lam.toFixed(4));
    apply(lam);
  });
  // Every (re)show of a field resets A/B (also when labels or known objects arrive later), so the wavelength
  // in the URL is applied again each time.
  document.addEventListener("viewer:target", (e) => {
    $("#lam-at-note").textContent = "";
    const lam = lamFromUrl();
    if (!e.detail?.target || lam == null) return;
    input.value = String(lam);
    apply(lam);
  });
}
