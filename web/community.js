// Per-tile discussion, saved second-look evidence and drafts. All community content is plain text.
import { DEFAULT_API } from "./api.js";
import { $, el, releasesOf } from "./util.js";
import * as explore from "./explore.js";
import { currentTarget, currentPair, selectPair } from "./viewer.js";
import { ang2pix } from "./healpix.js";
import { draftStore, discussionLink } from "./community-state.js";

const ORDER = 6, REST_MS = 4000;
const NAME_KEY = "spherex.community.name", ID_KEY = "spherex.community.browser";
let storage;
try { storage = localStorage; } catch { /* private mode */ }
const drafts = draftStore(storage);
const st = { pix: null, counts: null, open: false, tab: "tile", thread: null, viewed: new Set(),
  workspace: false, mapPix: null, coverageSort: "least", linked: false, hooked: false, replyTo: null, request: 0, posting: new Set(), focusId: null, notice: "", restoring: null };
const store = {
  get(k) { try { return storage?.getItem(k); } catch { return null; } },
  set(k, v) { try { storage?.setItem(k, v); } catch { /* not remembered */ } },
};
function browserId() {
  let id = store.get(ID_KEY);
  if (!id) { id = Math.random().toString(36).slice(2) + Date.now().toString(36); store.set(ID_KEY, id); }
  return id;
}
const api = (path) => `${(explore.getApiBase() ?? new URLSearchParams(location.search).get("api") ?? DEFAULT_API).replace(/\/$/, "")}/api/community${path}`;
async function read(path, opts = {}) {
  const res = await fetch(api(path), { cache: "no-cache", signal: AbortSignal.timeout(15000), ...opts });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.message ?? `The Live API answered ${res.status}.`);
  return body;
}
function ago(iso) {
  const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  if (!Number.isFinite(s)) return "";
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toISOString().slice(0, 10);
}
function button() {
  let b = $("#community-btn");
  if (!b && $("#explore")) {
    b = el("button", { id: "community-btn", type: "button", class: "community-btn", "aria-controls": "community" }, "💬 Discuss");
    b.addEventListener("click", () => st.open ? close() : openPanel("tile"));
    $("#explore").append(b);
  }
  return b;
}
function showCounts() {
  const b = button();
  if (!b) return;
  b.textContent = st.counts ? `💬 ${st.counts.comments} · 👁 ${st.counts.views}` : "💬 Discuss";
  const coverage = st.coverage ? `${st.coverage.label} (${st.coverage.browsers} visiting browsers). ` : "";
  b.title = `Discuss tile ${st.pix ?? "under the view centre"}. ${coverage}Views count visits, not scientific reviews.`;
  b.setAttribute("aria-expanded", String(st.open));
}
async function refreshCounts() {
  const pix = st.pix;
  if (pix == null || !explore.getApiBase()) return;
  try {
    const r = await read(`/counts?pix=${pix}`);
    if (pix === st.pix) { st.counts = r.tiles?.[String(pix)] ?? null; st.coverage = r.coverage?.[String(pix)]; showCounts(); }
  } catch { /* discussion remains accessible */ }
}
function setTile(pix) {
  if (pix === st.pix) return;
  st.pix = pix; st.replyTo = null; st.thread = null; st.counts = null; st.coverage = null; st.focusId = null; st.notice = "";
  showCounts();
}
function onMove() {
  const v = explore.view();
  if (!v) return;
  const pix = ang2pix(ORDER, v.ra, v.dec);
  st.mapPix = pix;
  if (st.restoring != null) return;
  if (st.workspace) {
    if (st.pix == null) { setTile(pix); if (st.open && st.tab === "tile") loadThread(); }
    return;
  }
  if (pix === st.pix) return;
  setTile(pix);
  clearTimeout(st.moveTimer);
  st.moveTimer = setTimeout(refreshCounts, 400);
  clearTimeout(st.restTimer);
  st.restTimer = setTimeout(() => countView(pix), REST_MS);
  if (st.open && st.tab === "tile") loadThread();
}
async function countView(pix) {
  const v = explore.view();
  if (document.hidden || st.workspace || pix !== st.pix || st.viewed.has(pix) || !v || v.fovArcmin > 360) return;
  try {
    const r = await read(`/tiles/${pix}/view`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ browser: browserId() }) });
    st.viewed.add(pix);
    if (pix === st.pix) { if (st.counts) st.counts.views = r.views; st.coverage = r.coverage; showCounts(); }
    document.dispatchEvent(new CustomEvent("community:coverage-changed"));
    // Update only the count. Replacing the composer here used to erase drafts and move focus.
    if (pix === st.pix && st.thread?.tile.pix === pix) {
      st.thread.views = r.views;
      st.thread.coverage = r.coverage;
      const badge = $("#community-tile-coverage");
      if (badge && r.coverage) badge.replaceWith(coverageBadge(r.coverage, "community-tile-coverage"));
      const count = $("#community-views");
      if (count) count.textContent = `👁 ${r.views} visits`;
    }
  } catch { /* retry on the next visit */ }
}
function panel() {
  let p = $("#community");
  if (!p) {
    p = el("aside", { id: "community", class: "community", role: "dialog", "aria-label": "Sky discussions" });
    p.hidden = true; document.body.append(p);
  }
  return p;
}
function setWorkspace(active, { push = true } = {}) {
  if (active && !st.workspace) st.exploreScroll = scrollY;
  st.workspace = active;
  document.body.classList.toggle("community-workspace", active);
  const world = $("#explore-workspace");
  if (world) { world.inert = active; world.setAttribute("aria-hidden", String(active)); }
  for (const name of ["explore", "community"]) {
    const tab = $(`#workspace-${name}`), selected = (name === "community") === active;
    tab?.setAttribute("aria-selected", String(selected));
    if (tab) tab.tabIndex = selected ? 0 : -1;
  }
  panel().setAttribute("role", active ? "tabpanel" : "dialog");
  if (active) panel().setAttribute("aria-labelledby", "workspace-community");
  else panel().removeAttribute("aria-labelledby");
  if (push) {
    const url = new URL(location.href);
    if (active) url.searchParams.set("view", "community"); else url.searchParams.delete("view");
    if (url.href !== location.href) history.pushState(null, "", url);
    document.dispatchEvent(new CustomEvent("workspace:navigate"));
  }
  if (active) { scrollTo(0, 0); openPanel("recent"); }
  else {
    st.open = false; ++st.request; panel().hidden = true;
    if (st.mapPix != null) { setTile(st.mapPix); clearTimeout(st.restTimer); st.restTimer = setTimeout(() => countView(st.mapPix), REST_MS); }
    showCounts(); scrollTo(0, st.exploreScroll ?? 0);
  }
}
function close() {
  if (st.workspace) { setWorkspace(false); $("#workspace-explore")?.focus(); }
  else { st.open = false; ++st.request; panel().hidden = true; showCounts(); button()?.focus(); }
}
function initWorkspace() {
  const tabs = [$("#workspace-explore"), $("#workspace-community")].filter(Boolean);
  for (const tab of tabs) {
    tab.addEventListener("click", () => setWorkspace(tab.id === "workspace-community"));
    tab.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault(); e.stopPropagation();
      const target = e.key === "Home" ? tabs[0] : e.key === "End" ? tabs.at(-1) : tabs.find((t) => t !== tab);
      target.click(); target.focus();
    });
  }
  const applyUrl = () => {
    const p = new URLSearchParams(location.search);
    const active = p.get("view") === "community";
    if (active !== st.workspace) setWorkspace(active, { push: false });
  };
  addEventListener("popstate", applyUrl);
  applyUrl();
  if (new URLSearchParams(location.search).get("explore") === "0" || new URLSearchParams(location.search).has("data")) openLinked();
}
async function openPanel(tab) {
  st.open = true; st.tab = tab; panel().hidden = false; showCounts();
  await (tab === "tile" ? loadThread() : tab === "coverage" ? loadCoverage() : loadRecent());
}
async function loadThread() {
  if (st.pix == null) { render(); return; }
  const pix = st.pix, request = ++st.request;
  render(el("p", { class: "muted small", role: "status" }, "Loading discussion…"));
  try {
    const r = await read(`/tiles/${pix}`);
    if (request !== st.request || pix !== st.pix || st.tab !== "tile" || !st.open) return;
    st.thread = r; st.coverage = r.coverage; st.counts = { views: r.views, comments: r.n_comments }; showCounts(); render();
    if (st.focusId) {
      const item = $(`#cm-comment-${st.focusId}`);
      if (item) { item.scrollIntoView({ block: "nearest" }); item.focus({ preventScroll: true }); }
      else { st.notice = "That comment is unavailable. You can still read this tile’s discussion."; render(); }
    }
  } catch (err) { if (request === st.request) render(el("p", { class: "msg msg-warn", role: "alert" }, err.message)); }
}
async function loadRecent() {
  const tab = st.tab, request = ++st.request;
  render(el("p", { class: "muted small", role: "status" }, "Loading discussions…"));
  try {
    const r = await read(`/recent?limit=25${tab === "unanswered" ? "&unanswered=true" : ""}`);
    if (request !== st.request || st.tab !== tab || !st.open) return;
    st.recent = r; render();
  } catch (err) { if (request === st.request) render(el("p", { class: "msg msg-warn", role: "alert" }, err.message)); }
}
function coverageBadge(c, id) {
  if (!c) return null;
  return el("span", { id, class: `cm-coverage cm-coverage-${c.level}`, title: "Based on distinct visiting browser IDs, not confirmed scientific reviews" },
    `${c.label} · ${c.browsers} browser${c.browsers === 1 ? "" : "s"}`);
}
async function loadCoverage() {
  const request = ++st.request;
  render(el("p", { class: "muted small", role: "status" }, "Loading community coverage…"));
  try {
    const r = await read(`/coverage?limit=24&sort=${st.coverageSort}`);
    if (request !== st.request || st.tab !== "coverage" || !st.open) return;
    st.coverageOverview = r; render();
  } catch (err) { if (request === st.request) render(el("p", { class: "msg msg-warn", role: "alert" }, err.message)); }
}
function viewOnMap(c) {
  const pix = c.pix ?? st.pix, pos = position(c);
  if (!explore.getSky() && pos) {
    const url = new URL(location.href);
    for (const key of ["view", "explore", "data", "target", "size", "blink"]) url.searchParams.delete(key);
    url.searchParams.set("ra", String(pos[0])); url.searchParams.set("dec", String(pos[1]));
    url.searchParams.set("community", String(pix));
    if (c.id != null) url.searchParams.set("comment", String(c.id)); else url.searchParams.delete("comment");
    location.assign(url); return;
  }
  if (st.workspace) setWorkspace(false);
  if (pos) explore.goTo(...pos);
  setTile(pix); st.focusId = c.id ?? null;
  openPanel("tile");
}
function position(c) {
  const center = c.center ?? st.thread?.center;
  return c.ra_deg != null && c.dec_deg != null ? [c.ra_deg, c.dec_deg, (c.fov_arcmin ?? 90) / 60]
    : center ? [center.ra_deg, center.dec_deg, 1.5] : null;
}
async function openDiscussion(c) {
  const pix = c.pix ?? st.pix;
  // Move before choosing the thread: old comments may pin a position outside their parent tile.
  const pos = position(c);
  if (pos && !st.workspace) explore.goTo(...pos);
  setTile(pix); st.focusId = c.id; st.notice = "";
  await openPanel("tile");
}
async function restoreEvidence(c) {
  st.notice = "";
  st.restoring = c.id;
  const pos = position(c);
  if (pos) explore.goTo(...pos);
  const e = c.evidence;
  if (e?.wavelength_um) {
    const bands = explore.bandWavelengths();
    if (bands.length) explore.setBand(bands.reduce((best, v, i) => Math.abs(v - e.wavelength_um) < Math.abs(bands[best] - e.wavelength_um) ? i : best, 0));
  }
  if (!e?.target_id) { st.restoring = null; return; }
  const done = async (ok) => {
    if (st.restoring !== c.id) return;
    if (!ok || currentTarget()?.id !== e.target_id) {
      st.notice = "The saved field is no longer available. The position and evidence remain here; build a field to inspect current data.";
    } else {
      const ids = new Set(currentTarget().frames.map((f) => f.id));
      const sameFrame = (slot) => {
        const f = currentTarget().frames.find((f) => f.id === e[`frame_${slot}`]);
        return f && (!e[`frame_${slot}_time`] || f.time_utc === e[`frame_${slot}_time`])
          && (!e[`frame_${slot}_obs`] || f.obs_id === e[`frame_${slot}_obs`]);
      };
      const pairAvailable = ids.has(e.frame_a) && ids.has(e.frame_b) && sameFrame("a") && sameFrame("b");
      if (pairAvailable) selectPair(e.frame_a, e.frame_b);
      else if (e.frame_a || e.frame_b) st.notice = "The saved frames are unavailable in this field. The evidence below records the original comparison.";
      const flags = $("#flags-toggle");
      if (flags && typeof e.flags === "boolean" && flags.checked !== e.flags) { flags.checked = e.flags; flags.dispatchEvent(new Event("change")); }
      if (e.layer && (!e.frame_a || pairAvailable) && /^[a-zA-Z0-9_-]{1,180}$/.test(e.layer)) {
        document.dispatchEvent(new CustomEvent("map:take"));
        if (!await explore.showLayer(e.layer)) st.notice = "The saved map layer is unavailable. The position and frame comparison remain accessible.";
      }
      if (pos) explore.goTo(...pos);
    }
    st.restoring = null;
    if (st.open) render();
  };
  document.dispatchEvent(new CustomEvent("community:restore", { detail: { targetId: e.target_id, done } }));
}
function snapshot() {
  const v = st.workspace && st.thread && st.mapPix !== st.pix
    ? { ra: st.thread.center.ra_deg, dec: st.thread.center.dec_deg, fovArcmin: 90 } : explore.view();
  if (!v) return null;
  const saved = { ra_deg: ((v.ra % 360) + 360) % 360, dec_deg: v.dec, fov_arcmin: Math.min(v.fovArcmin, 600), evidence: {} };
  const e = saved.evidence, t = currentTarget(), pair = currentPair();
  const wave = explore.bandWavelengths()[explore.getSky()?.base?.slice];
  if (Number.isFinite(wave)) e.wavelength_um = wave;
  if ((!st.workspace || st.mapPix === st.pix) && t?.center && ang2pix(ORDER, t.center.ra_deg, t.center.dec_deg) === st.pix) {
    Object.assign(e, { target_id: t.id, field_ra_deg: t.center.ra_deg, field_dec_deg: t.center.dec_deg,
      field_size_arcmin: t.size_arcmin, synthetic: t.synthetic !== false, flags: Boolean($("#flags-toggle")?.checked) });
    if (pair) {
      Object.assign(e, { frame_a: pair.a.id, frame_b: pair.b.id });
      for (const slot of ["a", "b"]) {
        if (pair[slot].time_utc) e[`frame_${slot}_time`] = pair[slot].time_utc;
        if (pair[slot].obs_id) e[`frame_${slot}_obs`] = pair[slot].obs_id;
      }
    }
    const release = releasesOf(t.frames ?? []);
    if (release) e.release = release;
    const layer = explore.currentLayer();
    if (layer) e.layer = layer;
  }
  return saved;
}
function evidenceEl(c) {
  if (c.ra_deg == null) return null;
  const e = c.evidence ?? {};
  const parts = [`RA ${c.ra_deg.toFixed(4)}°, Dec ${c.dec_deg.toFixed(4)}°`, c.fov_arcmin ? `${c.fov_arcmin.toFixed(1)}′ view` : null,
    e.wavelength_um ? `${e.wavelength_um.toFixed(3)} µm` : null, e.frame_a ? `A ${e.frame_a} / B ${e.frame_b ?? "—"}` : null,
    e.frame_a_time ? `Epoch A ${e.frame_a_time}` : null, e.frame_b_time ? `Epoch B ${e.frame_b_time}` : null,
    e.release, e.layer ? `Layer ${e.layer}` : null, e.flags ? "Quality flags on" : null, e.synthetic ? "SYNTHETIC — not SPHEREx data" : null];
  return el("p", { class: "cm-evidence small muted" }, parts.filter(Boolean).join(" · "));
}
function shareButton(c) {
  const b = el("button", { type: "button", class: "link small" }, "Share");
  b.addEventListener("click", async () => {
    const link = discussionLink(location.href, c.pix ?? st.pix, c.id);
    try { await navigator.clipboard.writeText(link); b.textContent = "Link copied"; }
    catch {
      const input = el("input", { type: "text", readonly: true, "aria-label": "Discussion share link", value: link });
      b.after(input); input.focus(); input.select();
    }
  });
  return b;
}
function commentEl(c, isReply = false) {
  const reply = isReply ? null : el("button", { type: "button", class: "link small" }, "Reply");
  reply?.addEventListener("click", () => { st.replyTo = c; render(); $("#community-text")?.focus(); });
  const look = c.ra_deg == null ? null : el("button", { type: "button", class: "link small" }, c.evidence?.target_id ? "Open saved evidence" : "📍 Look here");
  look?.addEventListener("click", async () => {
    const pix = st.pix;
    if (st.workspace) { setWorkspace(false); setTile(pix); await openPanel("tile"); }
    restoreEvidence(c);
  });
  return el("li", { id: `cm-comment-${c.id}`, tabindex: "-1", class: `${isReply ? "cm-reply" : "cm-item"}${st.focusId === c.id ? " cm-highlight" : ""}` },
    el("div", { class: "cm-head small" }, el("strong", {}, c.author), el("span", { class: "muted" }, ` · ${ago(c.created_utc)}`),
      c.kind === "second_look" ? el("span", { class: "cm-badge" }, "Second look") : null),
    c.title ? el("h4", {}, c.title) : null, el("p", { class: "cm-text" }, c.text), evidenceEl(c),
    el("div", { class: "cm-actions" }, look, reply, shareButton(c)),
    !isReply && c.replies?.length ? el("ul", { class: "cm-replies" }, ...c.replies.map((r) => commentEl(r, true))) : null);
}
function form() {
  const pix = st.pix, parent = st.replyTo?.id ?? null, draft = drafts.get(pix, parent), postingKey = `${pix}:${parent}`;
  const name = el("input", { id: "community-name", type: "text", maxlength: "40", autocomplete: "nickname", value: store.get(NAME_KEY) ?? "" });
  const kind = el("select", { id: "community-kind" }, el("option", { value: "discussion" }, "Discussion"), el("option", { value: "second_look" }, "Request a second look"));
  kind.value = draft.kind;
  const title = el("input", { id: "community-title", type: "text", maxlength: "120", "aria-label": "Observation title", value: draft.title, placeholder: "What should others check? (optional)" });
  const text = el("textarea", { id: "community-text", rows: "4", maxlength: "2000", placeholder: parent ? `Reply to ${st.replyTo.author}…` : "What changed? Which epochs did you compare? What have you checked?" }, draft.text);
  const attach = el("input", { type: "checkbox", id: "community-attach" });
  attach.checked = draft.attach;
  const send = el("button", { type: "button", class: "primary" }, parent ? "Reply" : "Post");
  const msg = el("p", { class: "small", id: "community-msg", role: "status", "aria-live": "polite" });
  const save = () => {
    Object.assign(draft, { text: text.value, title: title.value, kind: kind.value, attach: attach.checked });
    drafts.save(pix, parent, draft); store.set(NAME_KEY, name.value);
  };
  for (const input of [name, kind, title, text, attach]) input.addEventListener("input", save);
  const syncKind = () => {
    if (!parent && kind.value === "second_look") { attach.checked = true; attach.disabled = true; }
    else attach.disabled = st.posting.has(postingKey);
    title.hidden = Boolean(parent) || kind.value !== "second_look";
    save();
  };
  kind.addEventListener("change", syncKind);
  const busy = st.posting.has(postingKey);
  for (const input of [name, kind, title, text, attach, send]) input.disabled = busy;
  syncKind();
  send.addEventListener("click", async () => {
    save();
    if (!text.value.trim()) { msg.textContent = "Write a comment before posting."; text.focus(); return; }
    if (st.posting.has(postingKey)) return;
    const body = { author: name.value.trim(), text: draft.text, kind: parent ? "discussion" : draft.kind, title: parent ? "" : draft.title };
    if (parent) body.parent_id = parent;
    const saved = draft.attach ? snapshot() : null;
    if (draft.attach && (!saved || pix !== st.pix)) { msg.textContent = "Return to this tile to attach the view."; return; }
    if (saved) Object.assign(body, saved);
    st.posting.add(postingKey);
    for (const input of [name, kind, title, text, attach, send]) input.disabled = true;
    try {
      const r = await read(`/tiles/${pix}/comments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      drafts.clear(pix, parent);
      st.posting.delete(postingKey);
      if (st.pix === pix && st.open && st.tab === "tile") {
        if ((st.replyTo?.id ?? null) === parent) st.replyTo = null;
        st.focusId = r.comment.id; st.notice = "Posted. Your observation is ready for others to review.";
        await loadThread();
      }
    } catch (err) {
      st.posting.delete(postingKey);
      if (st.pix === pix && st.tab === "tile" && st.open && (st.replyTo?.id ?? null) === parent) {
        render();
        $("#community-msg").textContent = `${err.message} Your draft is saved.`;
      }
      msg.textContent = `${err.message} Your draft is saved.`;
      for (const input of [name, kind, title, text, attach, send]) input.disabled = false;
      if (!parent && kind.value === "second_look") attach.disabled = true;
    } finally { st.posting.delete(postingKey); }
  });
  const cancel = parent ? el("button", { type: "button", class: "link small" }, "Cancel reply") : null;
  cancel?.addEventListener("click", () => { st.replyTo = null; render(); });
  return el("div", { class: "cm-form" },
    el("h4", {}, parent ? `Reply to ${st.replyTo.author}` : "Join the discussion"),
    parent ? null : el("label", { for: "community-kind", class: "small" }, "Post type", kind),
    el("label", { for: "community-name", class: "small" }, "Display name (optional)", name), title,
    el("label", { for: "community-text", class: "small" }, parent ? "Your reply" : "Your observation or question", text),
    el("label", { class: "small muted" }, attach, " Save position, zoom and available comparison evidence"),
    el("p", { class: "small muted" }, "Drafts are saved in this browser. A second look asks for another opinion; it does not confirm a discovery."),
    el("div", { class: "cm-actions" }, send, cancel), msg);
}
function render(extra) {
  const tabs = el("div", { class: "cm-tabs" }, ...[["recent", "Recent"], ["unanswered", "Unanswered"], ["coverage", "Coverage"], ["tile", "This tile"]].map(([key, label]) => {
    const b = el("button", { type: "button", class: `link${st.tab === key ? " active" : ""}`, "aria-pressed": String(st.tab === key) }, label);
    b.addEventListener("click", () => openPanel(key)); return b;
  }));
  const x = el("button", { type: "button", class: "link cm-x", "aria-label": "Close discussion" }, "×");
  x.addEventListener("click", close);
  const parts = [];
  if (st.workspace) parts.push(el("header", { class: "cm-workspace-head" }, el("h2", {}, "Community"),
    el("p", { class: "muted" }, "Compare observations, ask for a second look, and find sky that needs more attention.")));
  parts.push(el("div", { class: "cm-top" }, tabs, st.workspace ? null : x));
  if (st.notice) parts.push(el("p", { class: "small", role: "status" }, st.notice));
  if (extra) parts.push(extra);
  else if (st.tab === "tile" && st.thread?.tile.pix === st.pix) {
    const t = st.thread;
    const map = el("button", { type: "button", class: "link small" }, "View tile on map →");
    map.addEventListener("click", () => viewOnMap(t.tile));
    parts.push(el("div", { class: "cm-thread-head" }, el("h3", {}, `Tile ${t.tile.pix}`), map),
      coverageBadge(t.coverage, "community-tile-coverage"),
      el("p", { class: "small muted" }, el("span", { id: "community-views" }, `👁 ${t.views} visits`), ` · 💬 ${t.n_comments} comments`),
      t.comments.length ? el("ul", { class: "cm-list" }, ...t.comments.map((c) => commentEl(c)))
        : el("p", { class: "muted" }, "No discussion yet. Ask a question or invite someone to take a second look."), form());
  } else if (st.tab === "tile") {
    parts.push(el("h3", {}, "Discuss a sky tile"), el("p", { class: "muted" }, "Choose a tile from Coverage or explore the sky to start a discussion."));
  } else if (st.tab === "coverage" && st.coverageOverview) {
    const overview = st.coverageOverview;
    const sort = el("select", { id: "community-coverage-sort", "aria-label": "Sort tiles by community attention" },
      el("option", { value: "least" }, "Less visited first"), el("option", { value: "most" }, "Most visited first"));
    sort.value = st.coverageSort;
    sort.addEventListener("change", () => { st.coverageSort = sort.value; loadCoverage(); });
    parts.push(el("h3", {}, "Community coverage"), el("p", { class: "muted" },
      "More independent visits mean more attention. These levels count browser IDs, not verified people, and do not measure the chance that a tile is fully explored."),
      el("div", { class: "cm-coverage-summary" }, ...overview.tiers.map((tier) => el("div", { class: `cm-coverage-card cm-coverage-${tier.level}` },
        el("strong", {}, overview.summary[tier.level].toLocaleString()), el("span", {}, tier.label),
        el("small", { class: "muted" }, tier.max_browsers == null ? `${tier.min_browsers}+ browsers` : tier.min_browsers === 0 ? "No recorded visits" : `${tier.min_browsers}–${tier.max_browsers} browsers`)))),
      el("label", { class: "cm-sort small" }, "Find sky to explore ", sort),
      overview.tiles.length ? el("ul", { class: "cm-list cm-coverage-list" }, ...overview.tiles.map((t) => {
        const go = el("button", { type: "button", class: "link small" }, "View on map →");
        go.addEventListener("click", () => viewOnMap(t));
        const discuss = el("button", { type: "button", class: "link small" }, "Discuss tile");
        discuss.addEventListener("click", () => openDiscussion(t));
        return el("li", { class: "cm-item" }, el("strong", {}, `Tile ${t.pix}`), coverageBadge(t.coverage),
          el("p", { class: "small muted" }, `${t.views} visits · ${t.n_comments} comments · RA ${t.center.ra_deg.toFixed(2)}°, Dec ${t.center.dec_deg.toFixed(2)}°`),
          el("div", { class: "cm-actions" }, go, discuss));
      })) : el("p", { class: "muted" }, "No recorded visits yet. Choose Less visited first to find a starting point."));
  } else if (st.recent && st.tab !== "tile") {
    const items = st.recent.latest ?? [];
    parts.push(el("h3", {}, st.tab === "unanswered" ? "Needs a second look" : "Recent discussions"),
      el("p", { class: "small muted" }, st.tab === "unanswered" ? "Requests with no replies yet. Open one and help check the evidence." : "Questions and observations from across the sky."),
      items.length ? el("ul", { class: "cm-list" }, ...items.map((c) => {
        const go = el("button", { type: "button", class: "link small" }, "Open discussion →");
        go.addEventListener("click", () => openDiscussion(c));
        return el("li", { class: "cm-item" }, el("strong", {}, c.title || (c.kind === "second_look" ? "Request a second look" : `Tile ${c.pix}`)),
          el("p", { class: "small muted" }, `${c.author} · ${ago(c.created_utc)}`),
          el("p", { class: "cm-text" }, c.text.length > 240 ? `${c.text.slice(0, 240)}…` : c.text), go);
      })) : el("p", { class: "muted" }, st.tab === "unanswered" ? "No unanswered requests right now. Start one from This tile." : "No discussions yet."));
    if (st.tab === "recent" && st.recent.most_discussed?.length) parts.push(el("h4", {}, "Most discussed"),
      el("div", { class: "cm-actions" }, ...st.recent.most_discussed.slice(0, 5).map((t) => {
        const b = el("button", { type: "button", class: "link small" }, `Tile ${t.pix} (${t.n_comments})`);
        b.addEventListener("click", () => openDiscussion(t)); return b;
      })));
  }
  panel().replaceChildren(...parts);
}
async function openLinked() {
  const params = new URLSearchParams(location.search), pix = Number(params.get("community")), id = Number(params.get("comment"));
  if (st.linked || !params.has("community") || !Number.isInteger(pix) || pix < 0 || pix >= 49152) return;
  st.linked = true;
  setTile(pix); st.focusId = Number.isInteger(id) && id > 0 ? id : null;
  await openPanel("tile");
  const comments = st.thread?.comments.flatMap((c) => [c, ...(c.replies ?? [])]) ?? [];
  const c = comments.find((c) => c.id === id);
  if (c && !st.workspace) await restoreEvidence(c);
  else if (st.thread && !st.workspace) explore.goTo(st.thread.center.ra_deg, st.thread.center.dec_deg, 1.5);
}
function hook() {
  const sky = explore.getSky();
  if (!sky || st.hooked) return;
  st.hooked = true; button(); sky.on("change", onMove); onMove(); openLinked();
}
document.addEventListener("explore:ready", hook);
setTimeout(() => { initWorkspace(); hook(); }, 0);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && st.open) { e.stopImmediatePropagation(); close(); } });
globalThis.spherexCommunity = { tile: () => st.pix, counts: () => st.counts };
