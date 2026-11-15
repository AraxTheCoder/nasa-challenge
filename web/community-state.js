// Community drafts survive DOM replacement and reloads; storage failures fall back to this tab's memory.
export function draftStore(storage) {
  const memory = new Map();
  const key = (pix, parent) => `spherex.community.draft.${pix}.${parent ?? "root"}`;
  return {
    get(pix, parent) {
      const k = key(pix, parent);
      if (memory.has(k)) return memory.get(k);
      let saved;
      try { saved = JSON.parse(storage?.getItem(k) ?? "null"); } catch { /* invalid/unavailable storage */ }
      const draft = { text: "", title: "", kind: "discussion", attach: true, ...saved };
      memory.set(k, draft);
      return draft;
    },
    save(pix, parent, draft) {
      memory.set(key(pix, parent), draft);
      try { storage?.setItem(key(pix, parent), JSON.stringify(draft)); } catch { /* keep in memory */ }
    },
    clear(pix, parent) {
      memory.delete(key(pix, parent));
      try { storage?.removeItem(key(pix, parent)); } catch { /* unavailable storage */ }
    },
  };
}

export function discussionLink(href, pix, id) {
  const source = new URL(href), url = new URL(source.pathname, source.origin);
  // Keep a custom API endpoint; drop unrelated navigation, debug and analysis state.
  if (source.searchParams.has("api")) url.searchParams.set("api", source.searchParams.get("api"));
  url.searchParams.set("community", String(pix));
  url.searchParams.set("comment", String(id));
  return url.href;
}
