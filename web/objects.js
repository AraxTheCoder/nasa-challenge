// Objects panel (T13): the detections and known objects of the shown target, with status (known /
// unknown / artifact), match, motion, score and a synthetic badge. Artifacts are hidden unless asked
// for (CONTRACTS "Detection"); unknown movers come first, since they are what the tool is for.
// The paths on the image are paths.js (T22). This module adds the list, a headline count and a focus
// ring for the object picked in the list (own SVG layer, so it never touches the paths layer).

import { $, el, fmtNum } from "./util.js";
import { showFrame } from "./viewer.js";

const NS = "http://www.w3.org/2000/svg";
const st = { target: null, frameId: null, focus: null, showArtifacts: false };

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const direction = (pa) => (Number.isFinite(pa) ? COMPASS[Math.round((((pa % 360) + 360) % 360) / 45) % 8] : null);
const ORDER = { unknown: 0, known: 1, missed: 2, artifact: 3 };

/** Detections first; a known object a detection matched is not listed twice. */
function objectsOf(t) {
  const dets = (t.detections ?? []).map((d) => ({
    key: `d:${d.id}`, status: d.status, name: d.matched_object ?? (d.status === "unknown" ? "Unknown mover" : `Artifact ${d.id}`),
    detail: d.matched_object ? `detection ${d.id}` : d.id, score: d.score, rate: d.motion?.rate_arcsec_per_hr,
    pa: d.motion?.pa_deg, positions: d.track ?? [], synthetic: d.synthetic !== false,
    reason: typeof d.reason === "string" ? d.reason : null, // v0.9, from detect.classify (T08)
  }));
  const matched = new Set((t.detections ?? []).filter((d) => d.status !== "artifact" && d.matched_object).map((d) => d.matched_object));
  const missed = (t.known_objects ?? []).filter((k) => !matched.has(k.name)).map((k) => ({
    key: `k:${k.name}`, status: "missed", name: k.name, detail: k.source ?? "catalogue", score: null, rate: null, pa: null,
    positions: k.positions ?? [], synthetic: k.synthetic !== false,
  }));
  return [...dets, ...missed].sort((a, b) => ORDER[a.status] - ORDER[b.status] || (b.score ?? 0) - (a.score ?? 0));
}

/**
 * Did a detection step run on this target? detect appends to provenance (CONTRACTS "detect").
 * Match the service name only, as whole words: the IRSA entry's query says "per epoch+detector".
 */
const detectionRan = (t) =>
  (t.detections?.length ?? 0) > 0 || (t.provenance ?? []).some((p) => /\bdetect(ion|\.run)?\b/i.test(p.service ?? ""));
// (The JPL known-object lookup, T07, is not mover detection: known objects can exist without it.)

function chip(status, ran = true) {
  const missed = ran ? "known · not detected" : "catalogued";
  const text = { unknown: "unknown", known: "known", missed, artifact: "artifact" }[status] ?? status;
  return el("span", { class: `obj-chip obj-${status}` }, text);
}

function motionText(o) {
  if (!Number.isFinite(o.rate)) return null;
  const dir = direction(o.pa);
  return `${fmtNum(o.rate, o.rate < 10 ? 1 : 0)}″/h${dir ? ` → ${dir}` : ""}`;
}

function render() {
  const t = st.target;
  const list = $("#objects-list");
  const summary = $("#objects-summary");
  if (!t) {
    list.replaceChildren();
    summary.textContent = "";
    return;
  }
  const all = objectsOf(t);
  const artifacts = all.filter((o) => o.status === "artifact").length;
  const shown = all.filter((o) => st.showArtifacts || o.status !== "artifact");
  const unknown = all.filter((o) => o.status === "unknown").length;
  const movers = all.filter((o) => o.status === "unknown" || o.status === "known").length;

  $("#objects-count").textContent = `(${shown.length})`;
  $("#objects-artifacts").hidden = artifacts === 0;
  $("#objects-artifacts-n").textContent = String(artifacts);

  // Headline next to the target name: unknown movers are the point of the tool.
  summary.replaceChildren();
  const ran = detectionRan(t);
  const catalogued = all.filter((o) => o.status === "missed").length;
  if (!ran) {
    summary.append("Mover detection has not run on this field yet");
    if (catalogued) summary.append(` · ${catalogued} known solar-system object${catalogued === 1 ? "" : "s"} in the field`);
  } else if (movers === 0) {
    summary.append("No moving objects found");
  } else {
    summary.append(`${movers} moving object${movers === 1 ? "" : "s"}: `,
      unknown ? el("strong", { class: "obj-unknown-text" }, `${unknown} unknown`) : "all known");
  }
  if (all.some((o) => o.synthetic)) summary.append(" ", el("span", { class: "badge badge-synthetic badge-small" }, "synthetic"));

  if (shown.length === 0) {
    list.replaceChildren(el("li", { class: "muted small" },
      detectionRan(t) ? "Nothing to list." : "Detections and known solar-system objects appear here once detection has run (T06–T08)."));
    return;
  }
  list.replaceChildren(...shown.map((o) => {
    const frames = o.positions.length;
    const sub = [o.detail, motionText(o), o.score != null ? `score ${fmtNum(o.score, 2)}` : null,
      `${frames} frame${frames === 1 ? "" : "s"}`].filter(Boolean).join(" · ");
    const row = el("li", {},
      el("button", { type: "button", class: `obj-row${st.focus === o.key ? " is-focus" : ""}`, "data-key": o.key,
        "aria-pressed": String(st.focus === o.key), onclick: () => focusObject(o) },
        el("span", { class: "obj-line" }, chip(o.status, ran), el("span", { class: "obj-name" }, o.name),
          o.synthetic ? el("span", { class: "badge badge-synthetic badge-small" }, "synthetic") : null),
        el("span", { class: "obj-sub muted small" }, sub),
        o.reason ? el("span", { class: "obj-reason small" }, o.reason) : null));
    return row;
  }));
}

function focusObject(o) {
  st.focus = st.focus === o.key ? null : o.key; // click again to clear
  if (st.focus && !o.positions.some((p) => p.frame_id === st.frameId) && o.positions.length) {
    showFrame(o.positions[0].frame_id); // fires viewer:frame, which draws the ring
  } else {
    drawFocus();
  }
  render();
}

/** Ring around the focused object at its position in the shown frame. */
function drawFocus() {
  let g = document.getElementById("focus-layer");
  if (!g) {
    g = document.createElementNS(NS, "g");
    g.id = "focus-layer";
    $("#overlay").append(g);
  }
  g.replaceChildren();
  const o = st.focus && st.target ? objectsOf(st.target).find((x) => x.key === st.focus) : null;
  const p = o?.positions.find((q) => q.frame_id === st.frameId);
  if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) return;
  const ring = document.createElementNS(NS, "circle");
  for (const [k, v] of Object.entries({ cx: p.x, cy: p.y, r: 5, class: "focus-ring", "vector-effect": "non-scaling-stroke" })) {
    ring.setAttribute(k, String(v));
  }
  g.append(ring);
}

document.addEventListener("viewer:target", (e) => {
  st.target = e.detail?.target ?? null;
  st.focus = null;
  st.frameId = null;
  document.getElementById("focus-layer")?.remove(); // the overlay is rebuilt per target
  render();
});

document.addEventListener("viewer:frame", (e) => {
  st.frameId = e.detail?.frameId ?? null;
  drawFocus();
});

export function initObjects() {
  $("#objects-show-artifacts").addEventListener("change", (e) => {
    st.showArtifacts = e.target.checked;
    render();
  });
}
