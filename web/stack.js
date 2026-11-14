// Stacks (T59): add aligned frames together so faint sources stand out. Pure functions, no DOM (checked by
// web/tests/stack_check.mjs); stackview.js draws the result over the stage.
//
// Each frame is first put on a common scale: minus its large-scale background (medians in BLOCK-pixel blocks,
// smoothly interpolated, so frame edges with a different sky level and gradients don't add up into patches),
// divided by its robust noise, because the display PNGs are stretched one by one. The stack is sum / sqrt(n): empty sky stays at the same noise level
// whatever the number of frames, and a steady source grows with sqrt(n), so a 12-frame stack shows sources
// ~3.5x fainter than one frame. Display only: the PNGs are stretched, so this is for looking, not photometry.

export const NO_DATA = [64, 84, 140];   // same colour as the difference view
const LO = -3, HI = 40;                  // display range in noise units (asinh stretch)
export const BLOCK = 16;                 // background blocks, px (~100" at 6.15"/px: bigger than a star)

const median = (a) => { a.sort((x, y) => x - y); return a.length ? a[a.length >> 1] : NaN; };

/** Large-scale background of one RGBA frame: block medians of the valid pixels, bilinear between block
 *  centres; blocks without data take the frame's overall median. */
export function background(rgba, width, height, block = BLOCK) {
  const bx = Math.ceil(width / block), by = Math.ceil(height / block);
  const grid = new Float32Array(bx * by);
  const all = [];
  for (let j = 0; j < by; j++) for (let i = 0; i < bx; i++) {
    const vals = [];
    for (let y = j * block; y < Math.min(height, (j + 1) * block); y++) {
      for (let x = i * block; x < Math.min(width, (i + 1) * block); x++) {
        const p = (y * width + x) * 4;
        if (rgba[p + 3] > 0) vals.push(rgba[p]);
      }
    }
    grid[j * bx + i] = vals.length >= block ? median(vals) : NaN;
    if (Number.isFinite(grid[j * bx + i])) all.push(grid[j * bx + i]);
  }
  const fill = all.length ? median(all) : 0;
  for (let k = 0; k < grid.length; k++) if (!Number.isFinite(grid[k])) grid[k] = fill;
  const bg = new Float32Array(width * height);
  for (let y = 0; y < height; y++) {
    const gy = Math.min(Math.max((y + 0.5) / block - 0.5, 0), by - 1), j0 = Math.floor(gy), j1 = Math.min(j0 + 1, by - 1), ty = gy - j0;
    for (let x = 0; x < width; x++) {
      const gx = Math.min(Math.max((x + 0.5) / block - 0.5, 0), bx - 1), i0 = Math.floor(gx), i1 = Math.min(i0 + 1, bx - 1), tx = gx - i0;
      bg[y * width + x] = (grid[j0 * bx + i0] * (1 - tx) + grid[j0 * bx + i1] * tx) * (1 - ty)
        + (grid[j1 * bx + i0] * (1 - tx) + grid[j1 * bx + i1] * tx) * ty;
    }
  }
  return bg;
}

/** Median and robust sigma (1.4826 * MAD) of the valid grey values of one RGBA frame, from a pixel sample. */
export function frameScale(rgba) {
  const vals = [];
  const step = Math.max(1, Math.floor(rgba.length / 4 / 20000)) * 4;
  for (let i = 0; i < rgba.length; i += step) if (rgba[i + 3] > 0) vals.push(rgba[i]);
  if (vals.length < 10) return null;
  vals.sort((a, b) => a - b);
  const med = vals[vals.length >> 1];
  const dev = vals.map((v) => Math.abs(v - med)).sort((a, b) => a - b);
  return { med, sigma: Math.max(1.4826 * dev[dev.length >> 1], 0.5) };
}

/**
 * Stack RGBA frames of equal size. Returns {data (RGBA for a canvas), n (frames per pixel), frames (used)}.
 * Pixels with alpha 0 (no data) don't count; where no frame has data the stack shows NO_DATA.
 * shifts (T69, optional, one {dx, dy} per frame, pixels): output pixel (x, y) takes frame k at
 * (x + dx, y + dy), bilinear, so whatever moves by exactly those shifts stays put and adds up (shift-and-stack).
 */
export function stackPixels(frames, width, height, shifts = null) {
  const N = width * height;
  const sum = new Float32Array(N), n = new Uint16Array(N);
  let used = 0;
  frames.forEach((rgba, k) => {
    const s = frameScale(rgba);
    if (!s) return;
    used++;
    const bg = background(rgba, width, height);
    const sh = shifts?.[k];
    if (!sh || (sh.dx === 0 && sh.dy === 0)) {
      for (let i = 0, p = 0; i < N; i++, p += 4) {
        if (rgba[p + 3] === 0) continue;
        sum[i] += (rgba[p] - bg[i]) / s.sigma;
        n[i]++;
      }
      return;
    }
    const z = (i) => (rgba[i * 4 + 3] === 0 ? NaN : (rgba[i * 4] - bg[i]) / s.sigma);
    for (let y = 0; y < height; y++) {
      const sy = y + sh.dy, y0 = Math.floor(sy), ty = sy - y0;
      if (y0 < 0 || y0 + 1 >= height) continue;
      for (let x = 0; x < width; x++) {
        const sx = x + sh.dx, x0 = Math.floor(sx), tx = sx - x0;
        if (x0 < 0 || x0 + 1 >= width) continue;
        const i0 = y0 * width + x0;
        const v = (z(i0) * (1 - tx) + z(i0 + 1) * tx) * (1 - ty) + (z(i0 + width) * (1 - tx) + z(i0 + width + 1) * tx) * ty;
        if (Number.isNaN(v)) continue;            // touches a no-data pixel
        sum[y * width + x] += v;
        n[y * width + x]++;
      }
    }
  });
  const out = new Uint8ClampedArray(N * 4);
  const a0 = Math.asinh(LO / 3), a1 = Math.asinh(HI / 3);
  for (let i = 0, p = 0; i < N; i++, p += 4) {
    if (!n[i]) { out.set(NO_DATA, p); out[p + 3] = 255; continue; }
    const z = sum[i] / Math.sqrt(n[i]);
    const g = Math.round(255 * Math.min(1, Math.max(0, (Math.asinh(z / 3) - a0) / (a1 - a0))));
    out[p] = out[p + 1] = out[p + 2] = g;
    out[p + 3] = 255;
  }
  return { data: out, n, frames: used };
}

/**
 * Shifts for stacking along an object (T69): positions [{frame_id, x, y}] -> {frames, shifts} relative to the
 * first position, for the frames that have a position.
 */
export function shiftsAlong(frames, positions) {
  const byId = new Map(positions.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).map((p) => [p.frame_id, p]));
  const use = frames.filter((f) => byId.has(f.id));
  if (!use.length) return { frames: [], shifts: [] };
  const ref = byId.get(use[0].id);
  return { frames: use, shifts: use.map((f) => ({ dx: byId.get(f.id).x - ref.x, dy: byId.get(f.id).y - ref.y })) };
}

/**
 * Shifts for a guessed motion (T69, synthetic tracking): rate in arcsec/hour toward position angle pa
 * (degrees east of north), relative to frame `ref`. x grows to the west, y to the south (CONTRACTS).
 */
export function shiftsForMotion(frames, ref, rateArcsecPerHour, paDeg, pixelScaleArcsec) {
  const east = rateArcsecPerHour * Math.sin(paDeg * Math.PI / 180), north = rateArcsecPerHour * Math.cos(paDeg * Math.PI / 180);
  return frames.map((f) => {
    const hours = (f.mjd - ref.mjd) * 24;
    return { dx: -east * hours / pixelScaleArcsec, dy: -north * hours / pixelScaleArcsec };
  });
}

/** Which frames go into the stack for `frame`: same epoch (all detectors) or same detector (all epochs). */
export function stackGroup(frames, frame, mode) {
  if (!frame) return [];
  return mode === "epoch" ? frames.filter((f) => f.epoch === frame.epoch)
    : mode === "detector" ? frames.filter((f) => f.detector === frame.detector) : [];
}
