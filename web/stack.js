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
 */
export function stackPixels(frames, width, height) {
  const N = width * height;
  const sum = new Float32Array(N), n = new Uint16Array(N);
  let used = 0;
  for (const rgba of frames) {
    const s = frameScale(rgba);
    if (!s) continue;
    used++;
    const bg = background(rgba, width, height);
    for (let i = 0, p = 0; i < N; i++, p += 4) {
      if (rgba[p + 3] === 0) continue;
      sum[i] += (rgba[p] - bg[i]) / s.sigma;
      n[i]++;
    }
  }
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

/** Which frames go into the stack for `frame`: same epoch (all detectors) or same detector (all epochs). */
export function stackGroup(frames, frame, mode) {
  if (!frame) return [];
  return mode === "epoch" ? frames.filter((f) => f.epoch === frame.epoch)
    : mode === "detector" ? frames.filter((f) => f.detector === frame.detector) : [];
}
