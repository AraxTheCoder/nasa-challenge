// T55: a fixed grid of field cells over the whole sky, so "Blink" covers the screen with fields that
// are the same every time (built once, then served from the Live API cache when you come back).
// Rows of CELL_ARCMIN in Dec; each row is cut into equal RA steps of at least CELL_ARCMIN on the sky.
// A cell's field is a square a little larger than its cell, so neighbours overlap and leave no gaps.
// Measured 2026-11-14: a 103' x 55' view as 8 parallel 30' fields: 103 s; as one 103' field: 198 s.

export const CELL_ARCMIN = 30;
const ROW_DEG = CELL_ARCMIN / 60;
const NROWS = Math.round(180 / ROW_DEG);
const D = Math.PI / 180;

function rowOf(dec) {
  return Math.min(NROWS - 1, Math.max(0, Math.floor((dec + 90) / ROW_DEG)));
}

/** RA layout of a row: number of cells, their RA step, and the field side that covers a cell (arcmin). */
export function rowLayout(row) {
  const decLo = -90 + row * ROW_DEG, decHi = decLo + ROW_DEG, decC = decLo + ROW_DEG / 2;
  const ncol = Math.max(1, Math.floor((360 * Math.cos(decC * D)) / ROW_DEG));
  const step = 360 / ncol;
  // widest true RA extent of a cell: at the row's edge nearest the equator
  const decWide = decLo <= 0 && decHi >= 0 ? 0 : Math.min(Math.abs(decLo), Math.abs(decHi));
  const width = step * 60 * Math.cos(decWide * D);
  const size = Math.ceil(Math.max(width, CELL_ARCMIN)) + 1;        // +1': overlap with the neighbours
  return { decC, ncol, step, size: Math.min(210, size) };
}

/** The cell that contains (ra, dec): {key, ra, dec (field centre, deg), size (field side, arcmin)}. */
export function cellOf(ra, dec) {
  const row = rowOf(dec);
  const { decC, ncol, step, size } = rowLayout(row);
  const col = Math.min(ncol - 1, Math.floor((((ra % 360) + 360) % 360) / step));
  return { key: `${row}/${col}`, ra: (col + 0.5) * step, dec: decC, size };
}

/** Unique cells containing any of the [ra, dec] points, nearest to `centre` ([ra, dec]) first. */
export function cellsCovering(points, centre) {
  const seen = new Map();
  for (const [ra, dec] of points) {
    const c = cellOf(ra, dec);
    if (!seen.has(c.key)) seen.set(c.key, c);
  }
  const dist = (c) => {
    if (!centre) return 0;
    const x = Math.sin(c.dec * D) * Math.sin(centre[1] * D)
      + Math.cos(c.dec * D) * Math.cos(centre[1] * D) * Math.cos((c.ra - centre[0]) * D);
    return Math.acos(Math.min(1, x));
  };
  return [...seen.values()].sort((a, b) => dist(a) - dist(b));
}
