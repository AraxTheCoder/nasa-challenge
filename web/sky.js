// T36 Sky map: our own HiPS renderer (WebGL, no dependencies). Pan, zoom and pinch over the whole
// sky like Google Earth; a base map (SPHEREx all-sky HiPS or a comparison survey) plus overlay
// layers (our per-epoch SPHEREx HiPS, T32), of which one is shown at a time, so blinking is just a
// switch between already loaded textures.
//
// Geometry: HEALPix NESTED tiles (healpix.js), stereographic projection around the view centre
// (conformal, like Aladin's default), north up, east left. Dragging turns the sphere under the
// cursor. Zoomed out, the whole sky comes from each HiPS's Norder3/Allsky mosaic (one image).
// Tile texel (row, col) <-> sub-pixel ix (even bits) = row, iy = col.
//
//   const sky = createSky(container)
//   await sky.setBase(url) ; sky.setOverlays([{url, label, epoch}]) ; sky.showOverlay(i)
//   sky.goTo(ra, dec, fovDeg) ; sky.view() ; sky.on("change", fn) ; sky.addDrawHook(fn(ctx, proj))

import { ang2pix, nest2xyf, tileGrid } from "./healpix.js";

const DEG = Math.PI / 180;
const TEXEL_ARCSEC_ORDER0 = 412.2;        // HiPS texel size at order 0 (512 px tiles)
const MAX_FOV = 240;                      // stereographic shows more than a hemisphere
const BACK_COSC = -0.6;                   // don't draw beyond ~127 deg from the centre
const MIN_FOV = 1 / 60;                   // 1 arcmin
const MAX_TEXTURES = 200;           // 1 MB of GPU memory each
const MAX_PARALLEL_LOADS = 12;            // our tile cache is local; browsers cap per host anyway

// ---------- HiPS layer ------------------------------------------------------------------------

async function readProperties(url) {
  const res = await fetch(`${url.replace(/\/$/, "")}/properties`);
  if (!res.ok) throw new Error(`${url}/properties: HTTP ${res.status}`);
  const props = {};
  for (const line of (await res.text()).split(/\r?\n/)) {
    const m = line.match(/^\s*([\w.]+)\s*=\s*(.*?)\s*$/);
    if (m) props[m[1]] = m[2];
  }
  return props;
}

class Layer {
  constructor(url, props, opts = {}) {
    this.url = url.replace(/\/$/, "");
    this.maxOrder = Number(props.hips_order ?? 3);
    this.minOrder = Math.max(0, Number(props.hips_order_min ?? 0));
    const formats = (props.hips_tile_format ?? "png").split(/\s+/);
    this.ext = formats.includes("png") ? "png" : formats.includes("jpeg") ? "jpg" : formats[0];
    this.depth = Number(props.hips_cube_depth ?? 1);
    // Cubes: start on the band the HiPS recommends (IRSA's SPHEREx cube: frames 50/51 are blank).
    this.slice = Math.min(this.depth - 1, opts.slice ?? Number(props.hips_cube_firstframe ?? 0));
    this.label = opts.label ?? props.obs_title ?? url;
    this.props = props;
    this.tiles = new Map();     // key -> {state: "loading"|"ok"|"missing", tex, used}
  }
  tileUrl(order, pix) {
    const s = this.depth > 1 && this.slice > 0 ? `_${this.slice}` : "";
    return `${this.url}/Norder${order}/Dir${Math.floor(pix / 10000) * 10000}/Npix${pix}${s}.${this.ext}`;
  }
  key(order, pix) { return `${this.slice}/${order}/${pix}`; }
  allskyUrl() {
    const s = this.depth > 1 && this.slice > 0 ? `_${this.slice}` : "";
    return `${this.url}/Norder3/Allsky${s}.${this.ext}`;
  }
}

// ---------- WebGL ----------------------------------------------------------------------------

const VS = `attribute vec2 a_pos; attribute vec2 a_uv; varying vec2 v_uv;
void main() { v_uv = a_uv; gl_Position = vec4(a_pos, 0.0, 1.0); }`;
const FS = `precision mediump float; varying vec2 v_uv; uniform sampler2D u_tex; uniform float u_alpha;
void main() { vec4 c = texture2D(u_tex, v_uv); gl_FragColor = vec4(c.rgb, c.a * u_alpha); }`;

function makeGl(canvas) {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, alpha: false, antialias: false });
  if (!gl) throw new Error("WebGL is not available in this browser");
  const sh = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  gl.useProgram(prog);
  const loc = { pos: gl.getAttribLocation(prog, "a_pos"), uv: gl.getAttribLocation(prog, "a_uv"),
    alpha: gl.getUniformLocation(prog, "u_alpha") };
  const posBuf = gl.createBuffer();
  const uvBuf = gl.createBuffer();
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  return { gl, loc, posBuf, uvBuf };
}

// ---------- the map ---------------------------------------------------------------------------

export function createSky(container, { ra = 0, dec = 0, fov = 60 } = {}) {
  container.classList.add("sky");
  const canvas = document.createElement("canvas");
  canvas.className = "sky-gl";
  const over = document.createElement("canvas");
  over.className = "sky-overlay";
  container.append(canvas, over);
  const ctx2d = over.getContext("2d");
  const G = makeGl(canvas);
  const { gl } = G;

  const st = { ra, dec, fov, w: 1, h: 1, dpr: 1, base: null, overlays: [], shown: -1,
    dirty: true, loads: 0, queue: [], hooks: [], frame: 0, listeners: { change: [], tiles: [] } };

  // ----- projection (stereographic, north up, east left) -----
  // Screen px per unit of the projection plane: the view's half width covers fov/2.
  const R = () => (st.w / 2) / (2 * Math.tan((Math.min(st.fov, MAX_FOV) * DEG) / 4));
  function toScreen(raDeg, decDeg) {
    const d0 = st.dec * DEG, a = decDeg * DEG, dl = (raDeg - st.ra) * DEG;
    const cosc = Math.sin(d0) * Math.sin(a) + Math.cos(d0) * Math.cos(a) * Math.cos(dl);
    const k = 2 / Math.max(1e-6, 1 + cosc);
    const x = k * Math.cos(a) * Math.sin(dl);
    const y = k * (Math.cos(d0) * Math.sin(a) - Math.sin(d0) * Math.cos(a) * Math.cos(dl));
    const r = R();
    return { x: st.w / 2 - x * r, y: st.h / 2 - y * r, front: cosc > BACK_COSC, cosc };
  }
  function fromScreen(px, py) {
    const r = R();
    const x = -(px - st.w / 2) / r, y = -(py - st.h / 2) / r;
    const rho = Math.hypot(x, y);
    if (rho < 1e-12) return [st.ra, st.dec];
    const c = 2 * Math.atan(rho / 2), d0 = st.dec * DEG;
    if (Math.cos(c) <= BACK_COSC) return null;
    const dec = Math.asin(Math.cos(c) * Math.sin(d0) + (y * Math.sin(c) * Math.cos(d0)) / rho) / DEG;
    const ra = st.ra + Math.atan2(x * Math.sin(c), rho * Math.cos(d0) * Math.cos(c) - y * Math.sin(d0) * Math.sin(c)) / DEG;
    return [((ra % 360) + 360) % 360, dec];
  }
  const proj = { toScreen, fromScreen, view: () => api.view() };

  // ----- tiles -----
  function pickOrder(layer) {
    const arcsecPerPx = (st.fov * 3600) / (st.w * st.dpr);
    const k = Math.ceil(Math.log2(TEXEL_ARCSEC_ORDER0 / arcsecPerPx));
    return Math.max(layer.minOrder, Math.min(layer.maxOrder, k));
  }

  function visibleTiles(order) {
    const out = new Set();
    if (order <= 3) {
      const n = 12 * 4 ** order;
      for (let p = 0; p < n; p++) {
        const g = tileGrid(order, p, 2);
        for (let i = 0; i < g.length; i += 2) {
          const s = toScreen(g[i], g[i + 1]);
          if (s.front && s.x > -st.w * 0.2 && s.x < st.w * 1.2 && s.y > -st.h * 0.2 && s.y < st.h * 1.2) { out.add(p); break; }
        }
      }
      return [...out];
    }
    const step = 40;
    for (let y = -step; y <= st.h + step; y += step) {
      for (let x = -step; x <= st.w + step; x += step) {
        const s = fromScreen(Math.min(Math.max(x, 0), st.w), Math.min(Math.max(y, 0), st.h));
        if (s) out.add(ang2pix(order, s[0], s[1]));
      }
    }
    return [...out];
  }

  // T41: every render says which tiles it wants (t.want = frame) and how close to the centre they
  // are (prio, px); the queue loads the most central wanted tiles first and drops the stale ones,
  // so after a pan the browser's few connections go to what is on screen now.
  function request(layer, order, pix, prio = 1e9) {
    const k = layer.key(order, pix);
    let t = layer.tiles.get(k);
    if (t) {
      t.used = performance.now();
      t.want = st.frame;
      if (t.state === "queued") t.prio = Math.min(t.prio, prio);
      return t;
    }
    t = { state: "queued", tex: null, used: performance.now(), want: st.frame, prio, key: k };
    layer.tiles.set(k, t);
    st.queue.push({ layer, order, pix, t });
    pump();
    return t;
  }

  function requestAllsky(layer) {
    const k = `${layer.slice}/allsky`;
    let t = layer.tiles.get(k);
    if (t) { t.used = performance.now() + 1e9; return t; }    // never evicted first
    t = { state: "queued", tex: null, used: performance.now() + 1e9, want: Infinity, prio: -1, key: k };
    layer.tiles.set(k, t);
    st.queue.push({ layer, url: layer.allskyUrl(), t });
    pump();
    return t;
  }

  /** Zoomed out: all visible order-3 tiles from the Allsky mosaic, one texture, one draw call. */
  function drawAllsky(layer, t) {
    const cols = 27, rows = Math.ceil(768 / cols), n = 4;
    const pos = [], uv = [];
    for (const pix of visibleTiles(3)) {
      const g = tileGrid(3, pix, n);
      const sp = [];
      for (let i = 0; i < g.length; i += 2) sp.push(toScreen(g[i], g[i + 1]));
      const c0 = pix % cols, r0 = Math.floor(pix / cols);
      const vtx = (a, b) => {
        const s = sp[a * (n + 1) + b];
        pos.push((s.x / st.w) * 2 - 1, 1 - (s.y / st.h) * 2);
        uv.push((c0 + b / n) / cols, (r0 + a / n) / rows);
      };
      for (let a = 0; a < n; a++) {
        for (let b = 0; b < n; b++) {
          const q = [sp[a * (n + 1) + b], sp[(a + 1) * (n + 1) + b], sp[a * (n + 1) + b + 1], sp[(a + 1) * (n + 1) + b + 1]];
          if (q.some((p) => !p.front)) continue;
          vtx(a, b); vtx(a + 1, b); vtx(a, b + 1);
          vtx(a + 1, b); vtx(a + 1, b + 1); vtx(a, b + 1);
        }
      }
    }
    drawTriangles(t.tex, pos, uv);
  }

  function drawTriangles(tex, pos, uv) {
    if (!pos.length) return;
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.bindBuffer(gl.ARRAY_BUFFER, G.posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pos), gl.STREAM_DRAW);
    gl.enableVertexAttribArray(G.loc.pos);
    gl.vertexAttribPointer(G.loc.pos, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, G.uvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uv), gl.STREAM_DRAW);
    gl.enableVertexAttribArray(G.loc.uv);
    gl.vertexAttribPointer(G.loc.uv, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.TRIANGLES, 0, pos.length / 2);
  }

  function pump() {
    if (st.queue.length > 1) {
      st.queue = st.queue.filter((j) => {
        const stale = j.t.state === "queued" && j.t.want < st.frame - 1 && j.t.prio < 1e12;
        if (stale) j.layer.tiles.delete(j.t.key);          // asked again if it comes back on screen
        return !stale && j.t.state === "queued";
      });
      st.queue.sort((a, b) => b.t.prio - a.t.prio);         // pop() takes the smallest prio
    }
    while (st.loads < MAX_PARALLEL_LOADS && st.queue.length) {
      const job = st.queue.pop();
      if (job.t.state !== "queued") continue;
      job.t.state = "loading";
      st.loads++;
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        st.loads--;
        const tex = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        job.t.tex = tex;
        job.t.state = "ok";
        evict();
        markDirty();
        pump();
      };
      img.onerror = () => { st.loads--; job.t.state = "missing"; pump(); };
      img.src = job.url ?? job.layer.tileUrl(job.order, job.pix);
    }
  }

  function evict() {
    const all = [];
    for (const layer of [st.base, ...st.overlays]) {
      if (!layer) continue;
      for (const [k, t] of layer.tiles) if (t.tex) all.push([t.used, layer, k, t]);
    }
    if (all.length <= MAX_TEXTURES) return;
    all.sort((a, b) => a[0] - b[0]);
    for (const [, layer, k, t] of all.slice(0, all.length - MAX_TEXTURES)) {
      gl.deleteTexture(t.tex);
      layer.tiles.delete(k);
    }
  }

  /** Texture to draw for a tile: its own, or the nearest loaded ancestor with a sub-rectangle. */
  function textureFor(layer, order, pix, prio) {
    const own = request(layer, order, pix, prio);
    if (own.state === "ok") return { tex: own.tex, d: 0, aOff: 0, bOff: 0 };
    const { ix, iy } = nest2xyf(order, pix);
    for (let d = 1; order - d >= layer.minOrder; d++) {
      const anc = layer.tiles.get(layer.key(order - d, Math.floor(pix / 4 ** d)));
      if (anc?.state === "ok") {
        const m = 2 ** d;
        return { tex: anc.tex, d, aOff: ix % m, bOff: iy % m };
      }
      if (d === 1 && order - 1 >= layer.minOrder) request(layer, order - 1, Math.floor(pix / 4), prio - 1);
    }
    return null;
  }

  function drawLayer(layer, alpha) {
    if (!layer) return;
    const order = pickOrder(layer);
    gl.uniform1f(G.loc.alpha, alpha);
    if (order <= 3) {                        // zoomed out: whole sky at once, sharper tiles on top
      const all = requestAllsky(layer);
      if (all.state === "ok") drawAllsky(layer, all);
    }
    const n = order <= 4 ? 8 : 4;
    for (const pix of visibleTiles(order)) {
      const g = tileGrid(order, pix, n);
      const sp = [];
      for (let i = 0; i < g.length; i += 2) sp.push(toScreen(g[i], g[i + 1]));
      const mid = sp[Math.floor(sp.length / 2)];
      const tx = textureFor(layer, order, pix, Math.hypot(mid.x - st.w / 2, mid.y - st.h / 2));
      if (!tx) continue;
      const pos = [], uv = [];
      const m = 2 ** tx.d;
      const vtx = (a, b) => {
        const s = sp[a * (n + 1) + b];
        pos.push((s.x / st.w) * 2 - 1, 1 - (s.y / st.h) * 2);
        uv.push((tx.bOff + b / n) / m, (tx.aOff + a / n) / m);   // s <- iy (col), t <- ix (row)
      };
      for (let a = 0; a < n; a++) {
        for (let b = 0; b < n; b++) {
          const q = [sp[a * (n + 1) + b], sp[(a + 1) * (n + 1) + b], sp[a * (n + 1) + b + 1], sp[(a + 1) * (n + 1) + b + 1]];
          if (q.some((s) => !s.front)) continue;
          vtx(a, b); vtx(a + 1, b); vtx(a, b + 1);
          vtx(a + 1, b); vtx(a + 1, b + 1); vtx(a, b + 1);
        }
      }
      drawTriangles(tx.tex, pos, uv);
    }
  }

  function render() {
    st.dirty = false;
    st.frame++;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.02, 0.03, 0.06, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    drawLayer(st.base, 1);
    st.overlays.forEach((l, i) => {
      if (i === st.shown) drawLayer(l, 1);
      else prefetch(l);                 // keep the other epochs loaded, so a switch is instant
    });
    ctx2d.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
    ctx2d.clearRect(0, 0, st.w, st.h);
    for (const hook of st.hooks) {
      try { hook(ctx2d, proj); } catch (e) { console.error(e); }
    }
  }

  function prefetch(layer) {
    const order = pickOrder(layer);
    for (const pix of visibleTiles(order)) request(layer, order, pix, 5e5);   // after visible tiles
  }

  function markDirty() {
    if (st.dirty) return;
    st.dirty = true;
    requestAnimationFrame(render);
  }

  function changed() {
    markDirty();
    st.listeners.change.forEach((fn) => fn(api.view()));
  }

  // ----- size -----
  function resize() {
    const r = container.getBoundingClientRect();
    st.dpr = window.devicePixelRatio || 1;
    st.w = Math.max(1, r.width);
    st.h = Math.max(1, r.height);
    for (const c of [canvas, over]) {
      c.width = Math.round(st.w * st.dpr);
      c.height = Math.round(st.h * st.dpr);
    }
    st.dirty = false;
    markDirty();
  }
  new ResizeObserver(resize).observe(container);

  // ----- interaction: drag, wheel, pinch, double click, keys -----
  const pointers = new Map();
  let pinch = null;
  const rel = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };

  function panBy(dx, dy) {
    const k = 1 / R() / DEG;                         // deg per px at the centre
    st.dec = Math.max(-90, Math.min(90, st.dec + dy * k));
    st.ra = (((st.ra + (dx * k) / Math.max(0.05, Math.cos(st.dec * DEG))) % 360) + 360) % 360;
    changed();
  }

  function zoomAt(factor, px, py) {
    const before = fromScreen(px, py);
    st.fov = Math.max(MIN_FOV, Math.min(MAX_FOV, st.fov * factor));
    if (before) {
      const s = toScreen(before[0], before[1]);
      if (s.front) panBy(px - s.x, py - s.y);        // keep the point under the cursor in place
    }
    changed();
  }

  over.style.pointerEvents = "none";
  canvas.style.touchAction = "none";
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, rel(e));
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) };
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) {
      const p = fromScreen(...rel(e));
      st.listeners.change.forEach((fn) => fn(api.view(), p));
      return;
    }
    const prev = pointers.get(e.pointerId), now = rel(e);
    pointers.set(e.pointerId, now);
    if (pointers.size === 1) panBy(now[0] - prev[0], now[1] - prev[1]);
    else if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (d > 0) zoomAt(pinch.d / d, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      pinch.d = d;
    }
  });
  const up = (e) => { pointers.delete(e.pointerId); if (pointers.size < 2) pinch = null; };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [x, y] = rel(e);
    zoomAt(Math.exp(e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)), x, y);
  }, { passive: false });
  canvas.addEventListener("dblclick", (e) => zoomAt(0.5, ...rel(e)));
  canvas.tabIndex = 0;
  canvas.addEventListener("keydown", (e) => {
    const step = 60;
    const keys = { ArrowLeft: () => panBy(step, 0), ArrowRight: () => panBy(-step, 0), ArrowUp: () => panBy(0, step),
      ArrowDown: () => panBy(0, -step), "+": () => zoomAt(0.7, st.w / 2, st.h / 2), "=": () => zoomAt(0.7, st.w / 2, st.h / 2),
      "-": () => zoomAt(1 / 0.7, st.w / 2, st.h / 2) };
    if (keys[e.key]) { e.preventDefault(); e.stopPropagation(); keys[e.key](); }
  });

  // ----- public API -----
  const api = {
    async setBase(url, opts) {
      const layer = new Layer(url, await readProperties(url), opts);
      if (st.base) for (const t of st.base.tiles.values()) if (t.tex) gl.deleteTexture(t.tex);
      st.base = layer;
      markDirty();
      return layer;
    },
    setSlice(i) {
      if (!st.base || st.base.depth <= 1) return;
      st.base.slice = Math.max(0, Math.min(st.base.depth - 1, i));
      markDirty();
    },
    /** layers: [{url, label, epoch}] — all are prefetched, one is drawn (showOverlay). */
    async setOverlays(layers) {
      for (const l of st.overlays) for (const t of l.tiles.values()) if (t.tex) gl.deleteTexture(t.tex);
      st.overlays = [];
      st.shown = -1;
      const made = await Promise.all(layers.map(async (l) => {
        try { return Object.assign(new Layer(l.url, await readProperties(l.url), l), { meta: l }); }
        catch (e) { console.warn(e); return null; }
      }));
      st.overlays = made.filter(Boolean);
      markDirty();
      return st.overlays.map((l) => l.meta);
    },
    showOverlay(i) { st.shown = i; markDirty(); },
    goTo(ra, dec, fov) {
      st.ra = ((Number(ra) % 360) + 360) % 360;
      st.dec = Math.max(-90, Math.min(90, Number(dec)));
      if (fov) st.fov = Math.max(MIN_FOV, Math.min(MAX_FOV, fov));
      changed();
    },
    view: () => ({ ra: st.ra, dec: st.dec, fov: st.fov, width: st.w, height: st.h }),
    on(ev, fn) { st.listeners[ev]?.push(fn); },
    addDrawHook(fn) { st.hooks.push(fn); markDirty(); },
    redraw: markDirty,
    get base() { return st.base; },
    proj,
  };
  resize();
  return api;
}
