// T81: with the map as the only view (T80, body.map-only), the frame viewer's tools act on the map:
// whatever frame the viewer shows (A, B, blink, play, wavelength filter, timeline clicks) is drawn as
// that frame's layer, and with A − B on, the difference layer of the current pair. The map's own
// epoch buttons still work; using them takes over until the next frame change.

import { currentPair } from "./viewer.js";
import * as explore from "./explore.js";

const st = { diff: false, frame: null, epochMode: false };
const mapOnly = () => document.body.classList.contains("map-only");

async function sync() {
  if (!mapOnly() || st.epochMode) return;
  if (st.diff) {
    const p = currentPair?.();
    if (p?.a?.id && p?.b?.id) { await explore.showLayer(`d-${p.a.id}-${p.b.id}`); return; }   // a, b: frame objects
  }
  if (st.frame) await explore.showLayer(st.frame);
}

document.addEventListener("viewer:frame", (e) => { st.frame = e.detail?.frameId ?? null; st.epochMode = false; sync(); });
document.addEventListener("viewer:diff", (e) => { st.diff = Boolean(e.detail?.on); st.epochMode = false; sync(); });
document.addEventListener("viewer:target", () => { st.frame = null; st.epochMode = false; });
document.addEventListener("explore:epoch-picked", () => { st.epochMode = true; });
