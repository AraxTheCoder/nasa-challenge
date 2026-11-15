// T55: the floating panels over the map ([data-hud] containers in index.html) can be dragged
// anywhere: by their grip (⠿) or by any empty part of a panel; inputs, buttons and sliders keep
// working as usual. Positions are remembered per browser (localStorage, a convenience only: the
// page works without it); double-clicking a grip docks that panel again. Undragged panels sit in
// the dock on the left (index.html); a dragged one leaves it.
// T124: on wide screens the panels are fixed to the window (they stay while the page scrolls to the
// analysis); on narrow ones they belong to the map's first screen and scroll away with it.

import { el } from "./util.js";

// T137: a panel folds to one line (the – next to its grip): folded it shows only ⠿ and its name, a click on the name
// opens it again; remembered per browser. Build progress and messages in the group stay visible.

// v6 (T124): positions relative to the window (wide screens) or to the map's first screen (.mapstage)
const KEY = "spherex.app.hud.v6";
const FOLD_KEY = "spherex.app.hudFold.v1";          // T137: {<data-hud>: true} for the folded ones
const NAMES = { field: "Field", view: "Map" };      // T137: a folded panel's name
const PINNED = matchMedia("(min-width: 1280px)");   // the same breakpoint as style.css
const INTERACTIVE = "input, select, button:not(.hud-grip), textarea, a, label, output, summary, [contenteditable]";
const KEEP = 48;          // px: the narrowest a panel gets
const THRESHOLD = 3;      // px before a press becomes a drag (so a click stays a click)

function loadAll(key = KEY) {
  try { return JSON.parse(localStorage.getItem(key)) ?? {}; } catch { return {}; }
}

function saveAll(all, key = KEY) {
  try { localStorage.setItem(key, JSON.stringify(all)); } catch { /* blocked: not remembered */ }
}

/** What the panels are placed in, as a box in viewport px: the window (wide screens: fixed panels), else the
 *  map's first screen (.mapstage, which scrolls with the page). */
function stageBox(hud) {
  const s = PINNED.matches ? null : hud.closest(".mapstage");
  return s ? s.getBoundingClientRect() : { left: 0, top: 0, width: innerWidth, height: innerHeight };
}

/** Show a panel at (left, top): px from the map screen's corner to where the panel shows (as relPos measures it).
 *  T137: all of it inside the screen, up to its edges, and not under the page header; larger than the screen: its
 *  top-left corner (with the grip) stays. Returns null when the panel isn't shown (nothing to measure). */
function place(hud, left, top) {
  if (!hud.getClientRects().length) return null;
  const box = stageBox(hud);
  hud.style.maxWidth = `${Math.max(KEEP, box.width)}px`;                  // T137: never wider than the screen
  const r = hud.getBoundingClientRect();
  // keep its width: near the right edge the box would otherwise shrink and re-wrap its contents (folded: only the
  // one-line tab shows, its width is taken when it opens)
  if (!hud.style.width && !hud.classList.contains("hud-folded")) hud.style.width = `${Math.ceil(r.width)}px`;
  const minTop = document.querySelector(".app-header")?.offsetHeight ?? 0;   // fixed over the map's top, both layouts
  const x = Math.min(Math.max(left, 0), Math.max(0, box.width - r.width));
  const y = Math.min(Math.max(top, minTop), Math.max(minTop, box.height - r.height));
  Object.assign(hud.style, { left: `${x}px`, top: `${y}px`, right: "auto", bottom: "auto", transform: "none" });
  hud.classList.add("hud-moved");
  // T137: left/top don't count from the screen's corner everywhere (style.css moves a moved panel 54 px down, under
  // the page header; on narrow screens the dock is what it is placed in): shift by what is off, so it shows at (x, y).
  // Without this every drag started 54 px lower (the panel jumped) and the header was counted twice.
  const now = hud.getBoundingClientRect();
  const offX = now.left - box.left - x, offY = now.top - box.top - y;
  if (Math.abs(offX) > 0.5 || Math.abs(offY) > 0.5) Object.assign(hud.style, { left: `${x - offX}px`, top: `${y - offY}px` });
  return { left: x, top: y };
}

/** A panel's position relative to the map's screen. */
function relPos(hud) {
  const r = hud.getBoundingClientRect(), box = stageBox(hud);
  return { left: r.left - box.left, top: r.top - box.top };
}

function reset(hud) {
  for (const p of ["left", "top", "right", "bottom", "transform", "width", "max-width"]) hud.style.removeProperty(p);
  hud.classList.remove("hud-moved");
}

function makeGrip(hud, name) {
  const grip = el("button", { type: "button", class: "hud-grip", "aria-label": "Move this panel",
    title: "Drag to move this panel · double-click to dock it again" }, "⠿");
  grip.addEventListener("dblclick", () => {
    const all = loadAll();
    delete all[name];
    saveAll(all);
    reset(hud);
  });
  return grip;
}

/** T137: the – after the grip folds the group to a one-line tab (⠿ + name); the name opens it again. */
function makeFoldable(hud, name, grip) {
  const label = NAMES[name] ?? name;
  const fold = el("button", { type: "button", class: "hud-fold", "aria-expanded": "true",
    "aria-label": `Fold the ${label} panel`, title: "Fold this panel to one line" }, "–");
  const open = el("button", { type: "button", class: "hud-unfold", "aria-expanded": "false",
    title: `Open the ${label} panel` }, `${label} +`);
  grip.after(fold);
  hud.prepend(el("div", { class: "hud-panel hud-tab" }, makeGrip(hud, name), open));
  const set = (on, focus) => {
    hud.classList.toggle("hud-folded", on);
    fold.setAttribute("aria-expanded", String(!on));
    open.setAttribute("aria-expanded", String(!on));
    if (!on && hud.classList.contains("hud-moved")) {            // moved while folded: keep it reachable, open
      const p = relPos(hud);
      if (!hud.style.width) {                                    // its open width, measured where nothing squeezes it
        hud.style.left = "0px";
        hud.style.width = `${Math.ceil(hud.getBoundingClientRect().width)}px`;
      }
      place(hud, p.left, p.top);
    }
    if (focus) (on ? open : fold).focus();
  };
  const remember = (on) => {
    const all = loadAll(FOLD_KEY);
    if (on) all[name] = true; else delete all[name];
    saveAll(all, FOLD_KEY);
  };
  fold.addEventListener("click", () => { set(true, true); remember(true); });
  open.addEventListener("click", () => { set(false, true); remember(false); });
  if (loadAll(FOLD_KEY)[name]) set(true, false);
}

function makeDraggable(hud) {
  const name = hud.dataset.hud;
  // the grip starts the group's first line: its first .hud-row, else its first panel
  const first = hud.querySelector(".hud-row") ?? hud.querySelector(".hud-panel");
  if (!first) return;
  const grip = makeGrip(hud, name);
  first.prepend(grip);
  makeFoldable(hud, name, grip);

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
  // a smaller window must not strand a moved panel off screen, nor a panel that grows (T137: the chemistry note,
  // the Spots list, a longer line) push its bottom out of the window
  const keepIn = (hud) => {
    if (hud.classList.contains("hud-dragging") || !hud.getClientRects().length) return;   // dragged now / not shown
    if (hud.classList.contains("hud-moved")) {
      const p = relPos(hud);
      place(hud, p.left, p.top);
      return;
    }
    const saved = loadAll()[hud.dataset.hud];      // moved earlier, but not shown when the page loaded: place it now
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) place(hud, saved.left, saved.top);
  };
  addEventListener("resize", () => huds.forEach(keepIn));
  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver((entries) => entries.forEach((e) => keepIn(e.target)));
    huds.forEach((hud) => ro.observe(hud));
  }
}
