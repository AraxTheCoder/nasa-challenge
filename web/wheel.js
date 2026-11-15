// T124: the thumbwheel on the right edge. The mouse wheel over the map zooms the map, so the page has its
// own scroll control: roll the mouse wheel over the thumbwheel, drag it, or use the arrow keys on it; the two
// arrows jump to the map and to the analysis. Its ridges roll with the page and a mark beside it shows how
// far down the page is. A third button (wide screens) makes the analysis column wider.

import { $ } from "./util.js";

const DRAG_GAIN = 3;        // page px per px the wheel is dragged
const ROLL = 0.3;           // px the ridges move per page px
const KEY_STEP = 80;
const WIDE_KEY = "spherex.deck.wide";

const smooth = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

/** Scroll the page to the map (true) or to where the analysis starts. */
export function scrollToMap(toMap = true) {
  const deck = $("#analysis");
  const top = toMap || !deck ? 0 : deck.getBoundingClientRect().top + scrollY;
  scrollTo({ top, behavior: smooth() });
}

export function initWheel() {
  const rail = $("#wheel"), knob = $("#wheel-knob");
  if (!rail || !knob) return;
  const up = $("#wheel-up"), down = $("#wheel-down"), wide = $("#wheel-wide");
  const max = () => Math.max(0, document.documentElement.scrollHeight - innerHeight);

  const sync = () => {
    const m = max(), y = Math.min(scrollY, m);
    knob.style.setProperty("--roll", `${Math.round(y * ROLL)}px`);
    knob.style.setProperty("--p", m ? (y / m).toFixed(4) : "0");
    knob.setAttribute("aria-valuenow", String(m ? Math.round((100 * y) / m) : 0));
    rail.classList.toggle("at-top", y < 8);
    up.disabled = y < 2;
    down.disabled = y > m - 2;
  };
  addEventListener("scroll", sync, { passive: true });
  addEventListener("resize", sync);
  new ResizeObserver(sync).observe(document.body);   // the analysis grows and shrinks with what is shown

  up.addEventListener("click", () => scrollToMap(true));
  down.addEventListener("click", () => scrollToMap(false));

  // the mouse wheel anywhere on the rail scrolls the page
  rail.addEventListener("wheel", (e) => {
    e.preventDefault();
    const unit = e.deltaMode === 1 ? 32 : e.deltaMode === 2 ? innerHeight : 1;
    scrollBy(0, e.deltaY * unit);
  }, { passive: false });

  // drag: the wheel's face moves with the finger, the page follows like under a mouse wheel
  let last = null;
  knob.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    last = e.clientY;
    knob.setPointerCapture(e.pointerId);
    knob.classList.add("rolling");
    e.preventDefault();
  });
  knob.addEventListener("pointermove", (e) => {
    if (last === null) return;
    scrollBy(0, (e.clientY - last) * DRAG_GAIN);
    last = e.clientY;
  });
  const release = () => { last = null; knob.classList.remove("rolling"); };
  knob.addEventListener("pointerup", release);
  knob.addEventListener("pointercancel", release);

  knob.addEventListener("keydown", (e) => {
    const page = innerHeight * 0.8;
    const by = { ArrowDown: KEY_STEP, ArrowUp: -KEY_STEP, PageDown: page, PageUp: -page }[e.key];
    if (by) scrollBy({ top: by, behavior: smooth() });
    else if (e.key === "Home") scrollToMap(true);
    else if (e.key === "End") scrollTo({ top: max(), behavior: smooth() });
    else return;
    e.preventDefault();
  });

  // wider analysis column (wide screens; remembered)
  const setWide = (on) => {
    document.body.classList.toggle("deck-wide", on);
    wide.setAttribute("aria-pressed", String(on));
    const text = on ? "Narrower analysis panels" : "Wider analysis panels";
    wide.title = text;
    wide.setAttribute("aria-label", text);
  };
  let on = false;
  try { on = localStorage.getItem(WIDE_KEY) === "1"; } catch { /* not remembered */ }
  setWide(on);
  wide.addEventListener("click", () => {
    on = !on;
    setWide(on);
    try { localStorage.setItem(WIDE_KEY, on ? "1" : "0"); } catch { /* not remembered */ }
  });

  sync();
}
