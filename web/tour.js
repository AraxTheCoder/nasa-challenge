// T92: a guided tour of the five official targets. "▶ Tour" on the map (or ?tour=1 in a link) opens a small card;
// each stop opens its field the way a shared link does (?ra=&dec=&size= + the page's own back/forward handling,
// so the field builds or opens from cache and blinks by itself) and says in one or two sentences what to watch.
// Some stops have a button that opens the star's spectrum below the map, with its motion measured by SPHEREx
// (T91). The card stays on screen while the page scrolls. Nothing else of the page is changed.

import { $, el } from "./util.js";
import { measureNext } from "./motion.js";

const STOPS = [
  { title: "SPHEREx, for anyone",
    text: "SPHEREx photographs the whole sky every six months in 102 infrared colours. Five stops show what changes " +
      "between its visits. Each field blinks by itself; you can pan, zoom and click anything." },
  { title: "Barnard's Star: the fastest star in the sky", ra: 269.4463, dec: 4.7682,
    text: "Watch the bright dot in the middle step north from visit to visit: 10 arcseconds a year, the largest motion " +
      "of any star.", action: "Measure its speed with SPHEREx", measure: true },
  { title: "Epsilon Indi B: two brown dwarfs", ra: 331.0966, dec: -56.8007,
    text: "Too cold to be stars, too heavy to be planets. SPHEREx measures how they move and, from the wobble Earth's " +
      "orbit gives them, how far away they are.", action: "Show its motion and distance", measure: true },
  { title: "WISE 0855: the coldest brown dwarf known", ra: 133.7598, dec: -7.2422,
    text: "Colder than the North Pole and invisible to our eyes: it only glows at the red end of SPHEREx's colours. " +
      "Slide the band towards 4.5 µm: that's where such cold objects shine." },
  { title: "RW Aurigae: a star still being born", ra: 76.9566, dec: 30.4013,
    text: "Gas and dust still fall onto it, so its brightness changes from visit to visit. Its spectrum shows each " +
      "visit separately.", action: "Show its spectrum over time" },
  { title: "R Draconis: a giant that pulses", ra: 248.1672, dec: 66.755,
    text: "It swells and dims every eight months. At its brightest it overwhelms SPHEREx's detectors, and the tool " +
      "says so instead of showing made-up numbers." },
  { title: "Your turn",
    text: "Type any coordinates, blink any spot, click any dot for its spectrum, or switch on “Unusual spectra” " +
      "to see which stars don't look like their neighbours." },
];

const st = { i: -1 };

function card() {
  let c = $("#tour-card");
  if (!c) {
    c = el("aside", { id: "tour-card", class: "tour-card", role: "dialog", "aria-label": "Guided tour", "aria-live": "polite" });
    c.hidden = true;
    document.body.append(c);
  }
  return c;
}

/** Open a field the way a shared link does: the page's popstate handler builds it (or opens it from cache). */
function openField(ra, dec) {
  const url = new URL(location.href);
  url.searchParams.set("ra", String(ra));
  url.searchParams.set("dec", String(dec));
  url.searchParams.set("size", "15");
  url.searchParams.delete("blink");
  history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function show(i) {
  st.i = Math.max(0, Math.min(STOPS.length - 1, i));
  const s = STOPS[st.i];
  const c = card();
  const back = el("button", { type: "button", class: "link" }, "‹ Back");
  back.disabled = st.i === 0;
  back.addEventListener("click", () => show(st.i - 1));
  const last = st.i === STOPS.length - 1;
  const next = el("button", { type: "button", class: "primary" }, st.i === 0 ? "Start ›" : last ? "Done" : "Next ›");
  next.addEventListener("click", () => (last ? close() : show(st.i + 1)));
  const x = el("button", { type: "button", class: "link tour-x", "aria-label": "Close the tour" }, "×");
  x.addEventListener("click", close);
  let act = null;
  if (s.action) {
    act = el("button", { type: "button" }, s.action);
    act.addEventListener("click", () => {
      if (s.measure) measureNext();               // the motion box measures right away (cached: shows at once)
      globalThis.spherexSpectrumAt?.(s.ra, s.dec, s.title.split(":")[0]);
    });
  }
  const n = STOPS.length - 2;        // the five targets
  c.replaceChildren(...[
    el("div", { class: "tour-head" },
      el("span", { class: "muted small" }, st.i === 0 ? "Guided tour" : last ? "Tour" : `Stop ${st.i} of ${n}`), x),
    el("h3", {}, s.title),
    el("p", {}, s.text),
    act,
    el("div", { class: "tour-nav" }, back, next),
  ].filter(Boolean));
  c.hidden = false;
  if (s.ra != null) openField(s.ra, s.dec);
  next.focus({ preventScroll: true });
}

function close() {
  card().hidden = true;
  st.i = -1;
  const url = new URL(location.href);
  if (url.searchParams.has("tour")) { url.searchParams.delete("tour"); history.replaceState(null, "", url); }
}

function addButton() {
  const stage = $("#explore");
  if (!stage || $("#tour-start")) return;
  const b = el("button", { id: "tour-start", type: "button", class: "tour-start",
    title: "A one-minute tour of the five official targets" }, "▶ Tour");
  b.addEventListener("click", () => (st.i >= 0 ? close() : show(0)));
  stage.append(b);
}

addButton();
document.addEventListener("keydown", (e) => {
  if (st.i < 0 || e.target.closest?.("input, select, textarea")) return;
  if (e.key === "Escape") close();
});
if (new URLSearchParams(location.search).get("tour") === "1") queueMicrotask(() => show(0));
