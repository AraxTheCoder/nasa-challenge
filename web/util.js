// Small DOM and formatting helpers shared by the web modules.

export const $ = (sel) => document.querySelector(sel);

/** el("tr", {class: "x", onclick: fn, "data-id": 1}, child, "text", [more]) */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children.flat().filter((c) => c != null && c !== false));
  return node;
}

export function fmtTime(iso) {
  if (!iso) return "–";
  return iso.replace("T", " ").replace(/\.\d+/, "").replace(/Z$/, " UTC");
}

export function fmtNum(v, digits) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "–";
}

export function fmtDuration(days) {
  const d = Math.abs(days);
  const h = d * 24;
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${d.toFixed(1)} d`;
}

export function fmtElapsed(ms) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Only http(s) links may become hrefs (target.json is data, not trusted markup). */
/** T64: SPHEREx release of a collection: "spherex_qr3_deep" -> "QR3 deep", "spherex_dr1" -> "DR1". */
export function releaseName(collection) {
  if (!collection) return null;
  const [rel, ...rest] = String(collection).replace(/^spherex_/, "").split("_");
  return [rel.toUpperCase(), ...rest].join(" ");
}

/** Release of a frame: its collection, or (fields built before T64) the release folder in its source_url. */
export function frameRelease(f) {
  if (f?.collection) return releaseName(f.collection);
  const m = /\/(dr\d+|qr\d*)\/level2\//.exec(f?.source_url ?? "");
  return m ? m[1].toUpperCase() : null;
}

/** "DR1 + QR3" for a list of frames (deep or not merged), "" if no frame tells. */
export const releasesOf = (frames) => [...new Set(frames.map((f) => frameRelease(f)?.split(" ")[0]).filter(Boolean))].sort().join(" + ");

export const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);

/** True when keyboard focus is somewhere the user types text. */
export function isTyping(target) {
  if (!target?.closest) return false;
  if (target.closest("textarea, select, [contenteditable]")) return true;
  const input = target.closest("input");
  return !!input && !["radio", "checkbox", "range", "button", "submit"].includes(input.type);
}

/** T52: catalogue names for label `source` values (CONTRACTS v0.11). */
const SOURCE_NAMES = { simbad: "SIMBAD", gaia_dr3: "Gaia DR3", vsx: "VSX (AAVSO variable stars)",
  catwise2020: "CatWISE2020", horizons: "JPL Horizons", mpcorb: "MPC orbits (computed here)",
  "jpl-sbident": "JPL SB Identification", skybot: "IMCCE SkyBoT" };
export const sourceName = (s) => SOURCE_NAMES[s] ?? s ?? "–";
