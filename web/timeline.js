// Epoch timeline (T12): one small panel per survey epoch, x = time within that epoch, y = wavelength
// at the target centre (one shared y scale). Frames at the same height in different panels were
// taken at the same wavelength, which is what makes a fair blink (stars look the same; CONTRACTS
// "Pair"). Pure view: viewer.js owns the state and calls renderTimeline() / markTimeline().

import { fmtNum, fmtTime } from "./util.js";

const NS = "http://www.w3.org/2000/svg";
const HEIGHT = 136;
const PAD_TOP = 24;    // panel titles
const PAD_BOTTOM = 18; // date labels
const PAD_LEFT = 40;   // wavelength axis labels
const GAP = 10;        // between epoch panels
const DOT_R = 4.5;     // >= 8px marks
const HIT_R = 10;      // hit target larger than the mark
const scales = new WeakMap(); // <svg> -> {yOf, range}, for markTimeline

function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, String(v));
  node.append(...children);
  return node;
}

function niceRange(lo, hi) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0.7, 5.1];
  const pad = Math.max(0.05, (hi - lo) * 0.08);
  return [Math.max(0, lo - pad), hi + pad];
}

function yTicks(lo, hi) {
  const span = hi - lo;
  const step = span > 3 ? 1 : span > 1.2 ? 0.5 : span > 0.5 ? 0.2 : span > 0.2 ? 0.1 : 0.05;
  const digits = step >= 1 ? 0 : step >= 0.1 ? 1 : 2; // same decimals on every label
  const ticks = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) ticks.push(Number(t.toFixed(3)));
  return { ticks, digits };
}

const day = (iso) => (iso ?? "").slice(0, 10);

/**
 * Draw the timeline into `host` (a block element). `frames` sorted by time.
 * onPick(frameId) is called when a frame dot is clicked.
 */
export function renderTimeline(host, frames, { onPick }) {
  host.replaceChildren();
  const usable = frames.filter((f) => Number.isFinite(f.mjd) && Number.isFinite(f.wavelength_um));
  if (usable.length === 0) return;

  const width = Math.max(280, Math.round(host.clientWidth || 640));
  const epochs = [...new Set(usable.map((f) => f.epoch))].sort((a, b) => a - b)
    .map((epoch) => ({ epoch, frames: usable.filter((f) => f.epoch === epoch) }));
  const lams = usable.map((f) => f.wavelength_um);
  const [y0, y1] = niceRange(Math.min(...lams), Math.max(...lams));
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const yOf = (w) => PAD_TOP + plotH * (1 - (w - y0) / (y1 - y0));
  const panelW = (width - PAD_LEFT - GAP * (epochs.length - 1)) / epochs.length;

  const root = svg("svg", {
    class: "tl-svg", width, height: HEIGHT, viewBox: `0 0 ${width} ${HEIGHT}`, role: "img",
    "aria-label": `${usable.length} frames in ${epochs.length} epoch(s), by time and wavelength`,
  });

  // Wavelength filter band (positioned by markTimeline), under everything else.
  root.append(svg("rect", { class: "tl-band", x: PAD_LEFT, width: width - PAD_LEFT, y: 0, height: 0, visibility: "hidden" }));
  scales.set(root, { yOf, range: [y0, y1] });

  // Recessive y grid + labels.
  const { ticks, digits } = yTicks(y0, y1);
  for (const t of ticks) {
    const y = yOf(t);
    root.append(
      svg("line", { class: "tl-grid", x1: PAD_LEFT, x2: width, y1: y, y2: y }),
      svg("text", { class: "tl-axis", x: PAD_LEFT - 6, y: y + 3.5, "text-anchor": "end" }, fmtNum(t, digits)),
    );
  }
  root.append(svg("text", { class: "tl-axis", x: 2, y: PAD_TOP - 10 }, "λ µm"));

  epochs.forEach(({ epoch, frames: fs }, i) => {
    const x0 = PAD_LEFT + i * (panelW + GAP);
    const t0 = Math.min(...fs.map((f) => f.mjd));
    const t1 = Math.max(...fs.map((f) => f.mjd));
    const inner = Math.max(1, panelW - 2 * HIT_R);
    const xOf = (m) => x0 + HIT_R + (t1 > t0 ? inner * ((m - t0) / (t1 - t0)) : inner / 2);
    const first = fs[0].time_utc;
    const last = fs[fs.length - 1].time_utc;
    const range = day(first) === day(last) ? day(first) : `${day(first)} → ${day(last).slice(5)}`;
    const title = panelW >= 190 ? `Epoch ${epoch} · ${range} · ${fs.length} frames`
      : panelW >= 110 ? `Epoch ${epoch} · ${fs.length}` : `E${epoch} · ${fs.length}`;

    root.append(
      svg("rect", { class: "tl-panel", x: x0, y: PAD_TOP - 4, width: panelW, height: plotH + 8, rx: 4 }),
      svg("text", { class: "tl-title", x: x0 + 2, y: PAD_TOP - 10 }, title),
      svg("text", { class: "tl-axis", x: x0 + 2, y: HEIGHT - 4 }, panelW >= 110 ? day(first).slice(5) : ""),
      svg("text", { class: "tl-axis", x: x0 + panelW - 2, y: HEIGHT - 4, "text-anchor": "end" },
        panelW >= 110 && day(last) !== day(first) ? day(last).slice(5) : ""),
    );

    for (const f of fs) {
      const cx = xOf(f.mjd);
      const cy = yOf(f.wavelength_um);
      const tip = `${f.id} · ${fmtTime(f.time_utc)} · ${fmtNum(f.wavelength_um, 3)} µm` +
        `${f.detector == null ? "" : ` · D${f.detector}`} · epoch ${epoch}`;
      const g = svg("g", { class: "tl-frame", "data-frame": f.id },
        svg("title", {}, tip),
        svg("circle", { class: "tl-hit", cx, cy, r: HIT_R }),
        svg("circle", { class: "tl-dot", cx, cy, r: DOT_R }),
      );
      g.addEventListener("click", () => onPick(f.id));
      root.append(g);
    }
  });

  host.append(root);
}

/** Update highlights without redrawing: shown frame, A, B, frames outside the filter, filter band. */
export function markTimeline(host, { shownId, aId, bId, isVisible, filter }) {
  const root = host.querySelector(".tl-svg");
  if (!root) return;
  for (const g of root.querySelectorAll(".tl-frame")) {
    const id = g.dataset.frame;
    g.classList.toggle("is-shown", id === shownId);
    g.classList.toggle("is-a", id === aId);
    g.classList.toggle("is-b", id === bId);
    g.classList.toggle("is-out", !isVisible(id));
  }
  // Keep the shown frame on top of neighbours.
  const shown = root.querySelector(".tl-frame.is-shown");
  if (shown) root.append(shown);

  const band = root.querySelector(".tl-band");
  const { yOf, range: [y0, y1] } = scales.get(root);
  const lo = filter.min ?? null;
  const hi = filter.max ?? null;
  if (lo == null && hi == null) {
    band.setAttribute("visibility", "hidden");
    return;
  }
  const top = yOf(Math.min(hi ?? y1, y1));
  const bottom = yOf(Math.max(lo ?? y0, y0));
  band.setAttribute("y", String(Math.min(top, bottom)));
  band.setAttribute("height", String(Math.abs(bottom - top)));
  band.setAttribute("visibility", "visible");
}
