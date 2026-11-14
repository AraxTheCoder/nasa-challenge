// T55: the floating panels over the map ([data-hud] containers in index.html) can be dragged
// anywhere: by their grip (⠿) or by any empty part of a panel; inputs, buttons and sliders keep
// working as usual. Positions are remembered per browser (localStorage, a convenience only: the
// page works without it); double-clicking a grip docks that panel again. Undragged panels sit in
// the two docks on the left (default layout, index.html); a dragged one leaves its dock.

import { el } from "./util.js";

// v5 (T90): positions relative to the map's screen (.mapstage), which scrolls with the page in web/
const KEY = "spherex.app.hud.v5";
const INTERACTIVE = "input, select, button:not(.hud-grip), textarea, a, label, output, summary, [contenteditable]";
const KEEP = 48;          // px of a panel that always stay on screen
const THRESHOLD = 3;      // px before a press becomes a drag (so a click stays a click)

function loadAll() {
  try { return JSON.parse(localStorage.getItem(KEY)) ?? {}; } catch { return {}; }
}

function saveAll(all) {
  try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* blocked: not remembered */ }
}

/** The map's screen the panels float over (T90: .mapstage scrolls with the page); its box in viewport px. */
function stageBox(hud) {
  const s = hud.closest(".mapstage");
  return s ? s.getBoundingClientRect() : { left: 0, top: 0, width: innerWidth, height: innerHeight };
}

/** Put a panel at (left, top) px relative to the map's screen, kept reachable: its top edge (with the
 *  grip) stays inside it. */
function place(hud, left, top) {
  const r = hud.getBoundingClientRect(), box = stageBox(hud);
  // keep its width: near the right edge the box would otherwise shrink and re-wrap its contents
  if (!hud.style.width) hud.style.width = `${Math.ceil(r.width)}px`;
  const x = Math.min(Math.max(left, KEEP - r.width), box.width - KEEP);
  const y = Math.min(Math.max(top, 0), box.height - KEEP);
  Object.assign(hud.style, { left: `${x}px`, top: `${y}px`, right: "auto", bottom: "auto", transform: "none" });
  hud.classList.add("hud-moved");
  return { left: x, top: y };
}

/** A panel's position relative to the map's screen. */
function relPos(hud) {
  const r = hud.getBoundingClientRect(), box = stageBox(hud);
  return { left: r.left - box.left, top: r.top - box.top };
}

function reset(hud) {
  for (const p of ["left", "top", "right", "bottom", "transform", "width"]) hud.style.removeProperty(p);
  hud.classList.remove("hud-moved");
}

function makeDraggable(hud) {
  const name = hud.dataset.hud;
  // the grip starts the group's first line: its first .hud-row, else its first panel
  const first = hud.querySelector(".hud-row") ?? hud.querySelector(".hud-panel");
  if (!first) return;
  const grip = el("button", { type: "button", class: "hud-grip", "aria-label": "Move this panel",
    title: "Drag to move this panel · double-click to dock it again" }, "⠿");
  first.prepend(grip);

  grip.addEventListener("dblclick", () => {
    const all = loadAll();
    delete all[name];
    saveAll(all);
    reset(hud);
  });

  hud.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || !e.target.closest(".hud-panel")) return;
    if (e.target.closest(INTERACTIVE)) return;       // typing, clicking, sliding as usual
    const p0 = relPos(hud);
    const start = { x: e.clientX, y: e.clientY, left: p0.left, top: p0.top };
    let dragging = false;
    e.preventDefault();                               // no text selection while dragging
    const move = (m) => {
      const dx = m.clientX - start.x, dy = m.clientY - start.y;
      if (!dragging && Math.hypot(dx, dy) < THRESHOLD) return;
      if (!dragging) { dragging = true; hud.classList.add("hud-dragging"); }
      place(hud, start.left + dx, start.top + dy);
    };
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      removeEventListener("pointercancel", up);
      hud.classList.remove("hud-dragging");
      if (!dragging) return;
      const p2 = relPos(hud);
      saveAll({ ...loadAll(), [name]: { left: Math.round(p2.left), top: Math.round(p2.top) } });
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
    addEventListener("pointercancel", up);
  });

  const saved = loadAll()[name];
  if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) place(hud, saved.left, saved.top);
}

export function initHud() {
  const huds = [...document.querySelectorAll("[data-hud]")];
  huds.forEach(makeDraggable);
  // a smaller window must not strand a moved panel off screen
  addEventListener("resize", () => {
    for (const hud of huds) {
      if (!hud.classList.contains("hud-moved")) continue;
      const p = relPos(hud);
      place(hud, p.left, p.top);
    }
  });
}
