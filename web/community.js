// T120: citizen collaboration per map tile. A "💬" button on the map shows, for the tile under the view centre
// (HEALPix order 6, the tiles the map builds fields for, ~55′), how often it has been viewed and how many comments
// it has; it opens a panel with the tile's discussion thread (comments, one level of replies, "look here" positions)
// and a "Recent" tab with the latest comments anywhere on the sky. A view counts once the map rests on a tile for a
// few seconds (the server counts one per browser per tile per hour). Everything is shown as plain text.
// API: GET/POST /api/community/... (server/community.py).

import { $, el } from "./util.js";
import * as explore from "./explore.js";
import { ang2pix } from "./healpix.js";

const ORDER = 6;
const REST_MS = 4000;              // resting this long on a tile counts as a view
const NAME_KEY = "spherex.community.name", ID_KEY = "spherex.community.browser";
const st = { pix: null, counts: null, open: false, tab: "tile", thread: null, viewed: new Set(), restTimer: null,
  moveTimer: null, hooked: false, replyTo: null };

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode: not remembered */ } },
};
function browserId() {
  let id = store.get(ID_KEY);
  if (!id) { id = Math.random().toString(36).slice(2) + Date.now().toString(36); store.set(ID_KEY, id); }
  return id;
}
const api = (path) => `${(explore.getApiBase() ?? "").replace(/\/$/, "")}/api/community${path}`;

function ago(iso) {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (!Number.isFinite(s)) return "";
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(iso).toISOString().slice(0, 10);
}

// ---------- the button on the map ----------

function button() {
  let b = $("#community-btn");
  if (!b) {
    const stage = $("#explore");
    if (!stage) return null;
    b = el("button", { id: "community-btn", type: "button", class: "community-btn",
      title: "Discuss this part of the sky with others: the tile under the centre of the view" }, "💬 Discuss");
    b.addEventListener("click", () => (st.open ? close() : openPanel("tile")));
    stage.append(b);
  }
  return b;
}

function showCounts() {
  const b = button();
  if (!b) return;
  const c = st.counts;
  b.textContent = c ? `💬 ${c.comments} · 👁 ${c.views}` : "💬 Discuss";
  b.title = st.pix == null ? "Discuss this part of the sky" :
    `Tile ${st.pix} (the ~1° square under the view centre): ${c?.views ?? 0} views, ${c?.comments ?? 0} comments. Open the discussion.`;
}

async function refreshCounts() {
  if (st.pix == null || !explore.getApiBase()) return;
  const pix = st.pix;
  try {
    const r = await (await fetch(api(`/counts?pix=${pix}`), { cache: "no-cache" })).json();
    if (pix === st.pix) { st.counts = r.tiles?.[String(pix)] ?? null; showCounts(); }
  } catch { /* no API: the button stays plain */ }
}

function onMove() {
  const v = explore.view();
  if (!v) return;
  const pix = ang2pix(ORDER, v.ra, v.dec);
  if (pix === st.pix) return;
  st.pix = pix;
  st.counts = null;
  showCounts();
  clearTimeout(st.moveTimer);
  st.moveTimer = setTimeout(refreshCounts, 400);
  clearTimeout(st.restTimer);
  st.restTimer = setTimeout(() => countView(pix), REST_MS);
  if (st.open && st.tab === "tile") loadThread();
}

async function countView(pix) {
  const v = explore.view();
  if (pix !== st.pix || st.viewed.has(pix) || !v || v.fovArcmin > 360) return;   // looking at it, not flying over
  st.viewed.add(pix);
  try {
    const r = await (await fetch(api(`/tiles/${pix}/view`), { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ browser: browserId() }) })).json();
    if (pix === st.pix && st.counts) { st.counts.views = r.views; showCounts(); }
    if (pix === st.pix && st.open && st.thread) { st.thread.views = r.views; render(); }
  } catch { /* not counted */ }
}

// ---------- the panel ----------

function panel() {
  let p = $("#community");
  if (!p) {
    p = el("aside", { id: "community", class: "community", role: "dialog", "aria-label": "Discussion" });
    p.hidden = true;
    document.body.append(p);
  }
  return p;
}

function close() { st.open = false; panel().hidden = true; }

async function openPanel(tab) {
  st.open = true;
  st.tab = tab;
  panel().hidden = false;
  if (tab === "tile") await loadThread(); else await loadRecent();
}

async function loadThread() {
  if (st.pix == null) return;
  const pix = st.pix;
  render(el("p", { class: "muted small" }, "Loading…"));
  try {
    const r = await (await fetch(api(`/tiles/${pix}`), { cache: "no-cache" })).json();
    if (pix !== st.pix || st.tab !== "tile") return;
    st.thread = r;
    st.counts = { views: r.views, comments: r.n_comments };
    showCounts();
    render();
  } catch (err) { render(el("p", { class: "msg msg-warn" }, `Can't reach the Live API: ${err.message}`)); }
}

async function loadRecent() {
  render(el("p", { class: "muted small" }, "Loading…"));
  try {
    const r = await (await fetch(api("/recent?limit=25"), { cache: "no-cache" })).json();
    if (st.tab !== "recent") return;
    st.recent = r;
    render();
  } catch (err) { render(el("p", { class: "msg msg-warn" }, `Can't reach the Live API: ${err.message}`)); }
}

function lookHere(c) {
  if (c.ra_deg == null || c.dec_deg == null) return null;
  const b = el("button", { type: "button", class: "link small", title: "Show the map where this was written about" }, "📍 look here");
  b.addEventListener("click", () => explore.goTo(c.ra_deg, c.dec_deg, c.fov_arcmin ? c.fov_arcmin / 60 : undefined));
  return b;
}

function commentEl(c, isReply = false) {
  const reply = isReply ? null : el("button", { type: "button", class: "link small" }, "reply");
  reply?.addEventListener("click", () => { st.replyTo = c; render(); $("#community-text")?.focus(); });
  return el("li", { class: isReply ? "cm-reply" : "cm-item" },
    el("div", { class: "cm-head small" }, el("strong", {}, c.author), el("span", { class: "muted" }, ` · ${ago(c.created_utc)}`)),
    el("p", { class: "cm-text" }, c.text),
    el("div", { class: "cm-actions" }, lookHere(c), reply),
    !isReply && c.replies?.length ? el("ul", { class: "cm-replies" }, ...c.replies.map((r) => commentEl(r, true))) : null);
}

function form() {
  const name = el("input", { id: "community-name", type: "text", maxlength: "40", placeholder: "your name (optional)",
    value: store.get(NAME_KEY) ?? "" });
  const text = el("textarea", { id: "community-text", rows: "3", maxlength: "2000",
    placeholder: st.replyTo ? `Reply to ${st.replyTo.author}…` : "What do you see here? A question, an idea, a find…" });
  const attach = el("input", { type: "checkbox", id: "community-attach" });
  attach.checked = true;
  const send = el("button", { type: "button", class: "primary" }, st.replyTo ? "Reply" : "Post");
  const msg = el("p", { class: "small", id: "community-msg" });
  send.addEventListener("click", async () => {
    const body = { author: name.value.trim(), text: text.value };
    if (st.replyTo) body.parent_id = st.replyTo.id;
    const v = explore.view();
    if (attach.checked && v) Object.assign(body, { ra_deg: ((v.ra % 360) + 360) % 360, dec_deg: v.dec, fov_arcmin: Math.min(v.fovArcmin, 600) });
    store.set(NAME_KEY, body.author);
    send.disabled = true;
    try {
      const res = await fetch(api(`/tiles/${st.pix}/comments`), { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) });
      const r = await res.json().catch(() => ({}));
      if (!res.ok) { msg.textContent = r.message ?? `the Live API answered ${res.status}`; send.disabled = false; return; }
      st.replyTo = null;
      await loadThread();
    } catch (err) { msg.textContent = `Can't reach the Live API: ${err.message}`; send.disabled = false; }
  });
  const cancel = st.replyTo ? el("button", { type: "button", class: "link small" }, "cancel reply") : null;
  cancel?.addEventListener("click", () => { st.replyTo = null; render(); });
  return el("div", { class: "cm-form" }, name, text,
    el("label", { class: "small muted" }, attach, " attach the current view (position + zoom), so others can look"),
    el("div", { class: "cm-actions" }, send, cancel), msg);
}

function render(extra) {
  const p = panel();
  const tabs = el("div", { class: "cm-tabs" }, ...[["tile", "This tile"], ["recent", "Recent everywhere"]].map(([k, label]) => {
    const b = el("button", { type: "button", class: `link${st.tab === k ? " active" : ""}`, "aria-pressed": String(st.tab === k) }, label);
    b.addEventListener("click", () => openPanel(k));
    return b;
  }));
  const x = el("button", { type: "button", class: "link cm-x", "aria-label": "Close" }, "×");
  x.addEventListener("click", close);
  const parts = [el("div", { class: "cm-top" }, tabs, x)];
  if (extra) parts.push(extra);
  else if (st.tab === "tile" && st.thread) {
    const t = st.thread, c = t.center;
    const go = el("button", { type: "button", class: "link small" }, "centre the map on it");
    go.addEventListener("click", () => explore.goTo(c.ra_deg, c.dec_deg, 1.5));
    parts.push(el("h3", {}, `Tile ${t.tile.pix}`),
      el("p", { class: "small muted" }, `RA ${c.ra_deg.toFixed(2)}°, Dec ${c.dec_deg.toFixed(2)}° (about 1° across) · `
        + `👁 ${t.views} view${t.views === 1 ? "" : "s"} · 💬 ${t.n_comments} comment${t.n_comments === 1 ? "" : "s"} · `, go),
      t.comments.length ? el("ul", { class: "cm-list" }, ...t.comments.map((c2) => commentEl(c2)))
        : el("p", { class: "muted" }, "No discussion here yet. Be the first: what do you see?"),
      form());
  } else if (st.tab === "recent" && st.recent) {
    const items = st.recent.latest ?? [];
    parts.push(el("h3", {}, "Recent discussions"),
      items.length ? el("ul", { class: "cm-list" }, ...items.map((c) => {
        const go = el("button", { type: "button", class: "link small" }, `tile ${c.pix} →`);
        go.addEventListener("click", () => {
          const pos = c.ra_deg != null ? [c.ra_deg, c.dec_deg, c.fov_arcmin ? c.fov_arcmin / 60 : 1.5] : [c.center.ra_deg, c.center.dec_deg, 1.5];
          explore.goTo(...pos);
          st.tab = "tile";
          setTimeout(() => { onMove(); loadThread(); }, 300);
        });
        return el("li", { class: "cm-item" },
          el("div", { class: "cm-head small" }, el("strong", {}, c.author), el("span", { class: "muted" }, ` · ${ago(c.created_utc)} · `), go),
          el("p", { class: "cm-text" }, c.text.length > 240 ? `${c.text.slice(0, 240)}…` : c.text));
      })) : el("p", { class: "muted" }, "No comments anywhere yet."),
      (st.recent.most_viewed ?? []).length ? el("p", { class: "small muted" }, "Most viewed: " +
        st.recent.most_viewed.slice(0, 5).map((t) => `tile ${t.pix} (${t.views})`).join(", ")) : null);
  }
  p.replaceChildren(...parts.filter(Boolean));
}

// ---------- wiring ----------

function hook() {
  const sky = explore.getSky();
  if (!sky || st.hooked) return;
  st.hooked = true;
  button();
  sky.on("change", onMove);
  onMove();
}

document.addEventListener("explore:ready", hook);
hook();
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.open && !e.target.closest?.("textarea, input")) close(); });
// for web/tests and the console
globalThis.spherexCommunity = { tile: () => st.pix, counts: () => st.counts };
