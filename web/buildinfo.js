// T145: which commit this page and its Live API run ("build 1b889a6", linked to GitHub), so anyone can see whether a
// deployment is up to date. From GET /api/health (CONTRACTS); stays hidden when the API doesn't say.
import { DEFAULT_API, apiUrl } from "./api.js";

const REPO = "https://github.com/AraxTheCoder/nasa-challenge";
const SHA = /^[0-9a-f]{40}$/;

async function show() {
  const a = document.getElementById("build-info");
  if (!a) return;
  const base = new URLSearchParams(location.search).get("api") ?? DEFAULT_API;
  try {
    const res = await fetch(apiUrl(base, "/api/health"), { cache: "no-cache", signal: AbortSignal.timeout(10000) });
    const h = await res.json();
    if (!SHA.test(h.commit ?? "")) return;
    a.textContent = `build ${h.commit.slice(0, 7)}`;
    a.href = `${REPO}/commit/${h.commit}`;
    a.title = `Code version: git commit ${h.commit}. Compare with the newest commit on GitHub.`;
    if (SHA.test(h.api_commit ?? "") && h.api_commit !== h.commit) {   // pulled, but the API not restarted yet
      a.textContent += ` · API ${h.api_commit.slice(0, 7)}`;
      a.title += ` The Live API still runs ${h.api_commit.slice(0, 7)} until it restarts.`;
    }
    a.hidden = false;
  } catch {
    // no Live API (offline ?data= mode): nothing to show
  }
}

show();
