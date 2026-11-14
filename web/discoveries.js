// T76 discovery index: pure helpers, no DOM (checked by web/tests/discoveries_check.mjs). discoverview.js draws
// the list and the map markers; app.js opens a candidate's field. Format: docs/CONTRACTS.md "Discoveries".

/** Candidate classes (T73), most interesting first. */
export const CLASSES = {
  brown_dwarf: { label: "Brown dwarf", hint: "moves between epochs, dim at 1–2 µm, bright at 4–5 µm" },
  variable: { label: "Variable", hint: "brighter or fainter between epochs at the same wavelength" },
  spectral: { label: "Odd spectrum", hint: "doesn't follow a star's shape: dust, ices, emission lines" },
  mover: { label: "Mover", hint: "changes position between frames or epochs" },
  other: { label: "Other", hint: "" },
};
const ORDER = Object.keys(CLASSES);

export const classLabel = (cls) => CLASSES[cls]?.label ?? String(cls ?? "?");

export function displayName(c) {
  if (c.name) return c.name;
  const dec = c.dec_deg >= 0 ? `+${c.dec_deg.toFixed(3)}` : `−${Math.abs(c.dec_deg).toFixed(3)}`;
  return `RA ${c.ra_deg.toFixed(3)}° Dec ${dec}°`;
}

/** "" or "all" = every class. */
export const filterCandidates = (list, cls) => (!cls || cls === "all" ? [...list] : list.filter((c) => c.class === cls));

/** by: "score" (best first), "class" (T73 order, then score), "name". Stable: ties keep the id order. */
export function sortCandidates(list, by = "score") {
  const byScore = (a, b) => (b.score ?? 0) - (a.score ?? 0) || String(a.id).localeCompare(String(b.id));
  const rank = (c) => { const i = ORDER.indexOf(c.class); return i < 0 ? ORDER.length : i; };
  const cmp = by === "class" ? (a, b) => rank(a) - rank(b) || byScore(a, b)
    : by === "name" ? (a, b) => displayName(a).localeCompare(displayName(b), "en", { numeric: true }) || byScore(a, b)
      : byScore;
  return [...list].sort(cmp);
}

/**
 * "Show me something interesting": a random candidate from the better half by score (at least 3 to choose
 * from), never the one already shown. rng() in [0, 1) for tests. null if there is nothing else.
 */
export function pickInteresting(list, { exclude = null, rng = Math.random } = {}) {
  const pool = sortCandidates(list).filter((c) => c.id !== exclude);
  if (!pool.length) return null;
  const top = pool.slice(0, Math.max(3, Math.ceil(pool.length / 2)));
  return top[Math.min(top.length - 1, Math.floor(rng() * top.length))];
}

/** The candidate a field request (ra, dec as typed or as numbers) points at, within tolDeg; else null. */
export function candidateAt(list, ra, dec, tolDeg = 2e-4) {
  const r = Number(ra), d = Number(dec);
  if (!Number.isFinite(r) || !Number.isFinite(d)) return null;
  return list.find((c) => Math.abs(c.dec_deg - d) <= tolDeg &&
    Math.abs(((c.ra_deg - r + 540) % 360) - 180) * Math.cos((d * Math.PI) / 180) <= tolDeg) ?? null;
}

/** One line under the form: what it is, why it was picked, and whether it is already known. */
export function whyLine(c, synthetic = false) {
  const head = `${classLabel(c.class)} · score ${(c.score ?? 0).toFixed(2)}${synthetic ? " (hand-made sample)" : ""}`;
  const known = c.known ? ` Known object (${c.known}): a check that the search finds what is already known, not a new find.` : "";
  return { head, text: `${c.reason ?? ""}${known}` };
}
