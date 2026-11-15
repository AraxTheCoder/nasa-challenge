// T123: one progress bar for everything that runs, so the user always knows what is happening.
// It watches the page's own requests to the Live API (a wrapper around window.fetch; nothing else changes) and reads
// the progress the answers already carry: a field build's `progress` {step, done, total, message}, the `done` /
// `total` of the jobs (all-exposure spectrum, unusual spectra, motion, chemistry), or just "working…" for a request
// that takes a while (quality flags, labels, known objects, SIMBAD redshifts). Map tiles are counted. A thin bar at
// the top of the page fills for a job with a total and moves for one without; a line below says what runs.
// Jobs that are polled stay listed between polls; one that stops being asked for drops out after a few seconds.

const ROUTES = [
  [/\/api\/target\?|\/api\/jobs\//, "Building the field"],
  [/\/spectral-outliers/, "Unusual spectra: measuring every source"],
  [/\/photometry/, "Spectrum from all exposures"],
  [/\/motion/, "Measuring the motion"],
  [/\/chemistry/, "Chemistry map"],
  [/\/flags/, "Quality flags"],
  [/\/labels/, "Catalogue labels"],
  [/\/objects/, "Known asteroids and moving sources"],
  [/\/redshift/, "Galaxy redshifts (SIMBAD)"],
  [/\/sky-labels/, "Names on the map"],
];
const TILE = /\/api\/(hips|sky)\//;
const SHOW_AFTER_MS = 350;        // quick answers never flash the bar
const STALE_MS = 5000;            // a polled job not asked for this long is over
const st = { jobs: new Map(), tiles: 0, tilesSince: 0, timer: null };

const now = () => performance.now();

function describe(url) {
  let u;
  try { u = new URL(url, location.href); } catch { return null; }
  if (!u.pathname.startsWith("/api/") || u.pathname === "/api/health") return null;
  if (TILE.test(u.pathname)) return { tile: true };
  const hit = ROUTES.find(([re]) => re.test(u.pathname + u.search));
  if (!hit) return null;
  const q = new URLSearchParams(u.search);
  q.delete("start");
  // one entry per job: a field build is one job whether asked as /api/target or polled as /api/jobs/<id>
  const key = hit[1] === ROUTES[0][1] ? "field" : `${u.pathname}?${q}`;
  return { key, label: hit[1] };
}

function touch(d) {
  let j = st.jobs.get(d.key);
  if (!j) { j = { label: d.label, since: now(), inflight: 0, done: null, total: null, note: "", finished: 0 }; st.jobs.set(d.key, j); }
  j.last = now();
  j.finished = 0;
  return j;
}

function fromAnswer(j, body, status) {
  if (!body || typeof body !== "object") return;
  const p = body.progress && typeof body.progress === "object" ? body.progress : body;
  if (Number.isFinite(p.done)) j.done = p.done;
  if (Number.isFinite(p.total)) j.total = p.total;
  if (typeof p.message === "string") j.note = p.message;
  const running = status === 202 || body.status === "building";
  if (!running) j.finished = now();          // ready, error, no data, not started: this job is over
}

const realFetch = window.fetch.bind(window);
window.fetch = function fetchWithActivity(input, init) {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input?.url;
  const d = url ? describe(url) : null;
  if (!d) return realFetch(input, init);
  if (d.tile) {
    if (!st.tiles) st.tilesSince = now();
    st.tiles++;
    schedule();
    const done = () => { st.tiles = Math.max(0, st.tiles - 1); schedule(); };
    return realFetch(input, init).then((r) => { done(); return r; }, (e) => { done(); throw e; });
  }
  const j = touch(d);
  j.inflight++;
  schedule();
  return realFetch(input, init).then((res) => {
    j.inflight--;
    j.last = now();
    const type = res.headers.get("content-type") ?? "";
    if (type.includes("json")) {
      res.clone().json().then((body) => { fromAnswer(j, body, res.status); schedule(); }, () => { j.finished = now(); schedule(); });
    } else {
      j.finished = now();
    }
    schedule();
    return res;
  }, (err) => {
    j.inflight--;
    j.finished = now();
    schedule();
    throw err;
  });
};

// ---------- the bar ----------

function bar() {
  let b = document.getElementById("activity");
  if (!b) {
    b = document.createElement("div");
    b.id = "activity";
    b.className = "activity";
    b.setAttribute("role", "status");
    b.setAttribute("aria-live", "polite");
    b.innerHTML = '<div class="activity-track"><div class="activity-fill"></div></div><div class="activity-text"></div>';
    b.hidden = true;
    document.body.append(b);
  }
  return b;
}

function schedule() {
  if (!st.timer) st.timer = setTimeout(() => { st.timer = null; render(); }, 120);
}

function render() {
  const t = now();
  for (const [k, j] of st.jobs) {
    const over = (j.finished && t - j.finished > 700) || (!j.inflight && t - j.last > STALE_MS);
    if (over) st.jobs.delete(k);
  }
  const shown = [...st.jobs.values()].filter((j) => !j.finished && t - j.since > SHOW_AFTER_MS);
  const tiles = st.tiles && t - st.tilesSince > SHOW_AFTER_MS ? st.tiles : 0;
  const b = bar();
  if (!shown.length && !tiles) {
    b.hidden = true;
    if (st.jobs.size || st.tiles) setTimeout(schedule, 400);   // something may still pass SHOW_AFTER_MS
    return;
  }
  const parts = shown.map((j) => {
    const known = Number.isFinite(j.done) && Number.isFinite(j.total) && j.total > 0;
    const note = j.note && !/^\d+\/\d+$/.test(j.note) ? `: ${j.note}` : "";
    const n = !known ? "" : note ? ` (${Math.round((100 * j.done) / j.total)}%)` : ` ${j.done} of ${j.total}`;
    return `${j.label}${note}${n}`;
  });
  if (tiles) parts.push(`Map images: ${tiles} loading`);
  const lead = shown.find((j) => Number.isFinite(j.done) && Number.isFinite(j.total) && j.total > 0);
  const fill = b.querySelector(".activity-fill");
  if (lead) {
    fill.classList.remove("activity-busy");
    fill.style.width = `${Math.max(3, Math.min(100, (100 * lead.done) / lead.total))}%`;
  } else {
    fill.classList.add("activity-busy");
    fill.style.width = "";
  }
  b.querySelector(".activity-text").textContent = parts.join(" · ");
  b.hidden = false;
  setTimeout(schedule, 1000);          // keep ages and stale jobs current while something runs
}

// for web/tests and the console
globalThis.spherexActivity = { jobs: () => [...st.jobs.values()].map((j) => ({ ...j })), tiles: () => st.tiles,
  text: () => (bar().hidden ? "" : bar().querySelector(".activity-text").textContent) };
