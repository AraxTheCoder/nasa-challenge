// Live API client (docs/CONTRACTS.md v0.3 "Live API"). No DOM code in here.
//
// requestField() asks for a field, polls while the server builds it, and resolves with the URL of
// the finished target.json. Frame image paths in target.json are relative to that URL.

export const DEFAULT_API = "http://localhost:8000";
export const POLL_MS = 2000;

/** kind: "bad_request" (400), "no_data" (404), "error" (500 / unexpected), "unreachable" (network). */
export class ApiError extends Error {
  constructor(message, { kind = "error", http = null, id = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.http = http;
    this.id = id;
  }
}

/** Resolve a path from the API ("/api/...") against the configured base URL. */
export function apiUrl(apiBase, path) {
  return new URL(path, new URL(apiBase, location.href)).href;
}

async function getJson(url, signal) {
  let res;
  try {
    res = await fetch(url, { signal, cache: "no-cache" });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(`Can't reach the Live API at ${new URL(url).origin}.`, { kind: "unreachable" });
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    // not JSON; handled below via the HTTP status
  }
  return { http: res.status, body };
}

function toError(http, body) {
  const message = body?.message ?? body?.detail ?? `Live API answered HTTP ${http}.`;
  const id = body?.id ?? null;
  if (body?.status === "no_data") return new ApiError(message, { kind: "no_data", http, id });
  if (http === 400) return new ApiError(message, { kind: "bad_request", http, id });
  return new ApiError(message, { kind: "error", http, id });
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException("Aborted", "AbortError"));
    if (signal?.aborted) return abort();
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => { clearTimeout(timer); abort(); }, { once: true });
  });
}

/**
 * Request a field and wait until it is built.
 * @param {string} apiBase  e.g. "http://localhost:8000"
 * @param {{ra: string, dec: string, size: number, refresh?: boolean}} req  ra/dec as typed (decimal or sexagesimal)
 * @param {{onProgress?: (progress: object, id: string) => void, signal?: AbortSignal}} opts
 * @returns {Promise<{id: string, targetUrl: string}>}
 */
export async function requestField(apiBase, req, { onProgress, signal } = {}) {
  const q = new URLSearchParams({ ra: req.ra, dec: req.dec, size: String(req.size) });
  if (req.refresh) q.set("refresh", "1");
  let url = apiUrl(apiBase, `/api/target?${q}`);
  for (;;) {
    const { http, body } = await getJson(url, signal);
    if (http === 200 && body?.status === "ready" && body.target_url) {
      return { id: body.id, targetUrl: apiUrl(apiBase, body.target_url) };
    }
    if (http === 202 && body?.status === "building" && body.poll_url) {
      onProgress?.(body.progress ?? {}, body.id);
      url = apiUrl(apiBase, body.poll_url);
      await sleep(POLL_MS, signal);
      continue;
    }
    throw toError(http, body);
  }
}

/** GET /api/health → {ok, mode} or null if the API can't be reached. */
export async function health(apiBase, signal) {
  try {
    const { http, body } = await getJson(apiUrl(apiBase, "/api/health"), signal);
    return http === 200 ? body : null;
  } catch {
    return null;
  }
}
