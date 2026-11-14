// RA/Dec as typed into the form -> degrees, in the browser (T55 "Go" jumps without asking the API).
// Same rules as server/coords.py: decimal degrees, or sexagesimal (RA in hours unless it says d/°).

const SEP = /[hdms:°'"′″\s]+/i;

function sexagesimal(text) {
  let t = String(text ?? "").trim();
  const neg = t.startsWith("-");
  if (t[0] === "+" || t[0] === "-") t = t.slice(1);
  const parts = t.split(SEP).filter(Boolean);
  if (!parts.length || parts.length > 3) throw new Error(`cannot parse "${text}"`);
  const nums = parts.map(Number);
  if (nums.some((n) => !Number.isFinite(n) || n < 0) || nums.slice(1).some((n) => n >= 60)) {
    throw new Error(`cannot parse "${text}"`);
  }
  const value = nums[0] + nums.slice(1).reduce((s, n, i) => s + n / 60 ** (i + 1), 0);
  return { value, neg, sexa: parts.length > 1 || /[hdms:°'"′″]/i.test(t) };
}

/** Degrees in [0, 360); sexagesimal RA is hours unless it is written with d or °. */
export function parseRa(text) {
  const { value, neg, sexa } = sexagesimal(text);
  if (neg) throw new Error("RA must not be negative");
  const deg = sexa && !/d|°/i.test(text) ? value * 15 : value;
  if (!(deg >= 0 && deg < 360)) throw new Error("RA must be in [0, 360) deg / [0, 24) h");
  return deg;
}

/** Degrees in [-90, 90]. */
export function parseDec(text) {
  const { value, neg } = sexagesimal(text);
  const deg = neg ? -value : value;
  if (!(deg >= -90 && deg <= 90)) throw new Error("Dec must be in [-90, 90] deg");
  return deg;
}
