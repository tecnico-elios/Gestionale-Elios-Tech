import axios from "axios";

// Emergency front-pressure for the PWA.
// - identical GETs from the same route share one network request;
// - stale GETs from the previous route are aborted when the next route starts I/O;
// - every GET is tagged so Render logs show which page generated it.
const originalGet = axios.get.bind(axios);
const inflight = new Map();
const MAX_INFLIGHT_AGE_MS = 15000;

function stableParams(params) {
  if (!params) return "";
  try {
    return JSON.stringify(
      Object.keys(params)
        .sort()
        .reduce((acc, key) => {
          acc[key] = params[key];
          return acc;
        }, {})
    );
  } catch (_) {
    return String(params);
  }
}

function currentSource() {
  if (typeof window === "undefined") return "ssr";
  return window.location.pathname || "/";
}

function abortStaleRoutes(source) {
  for (const [key, entry] of inflight.entries()) {
    if (entry.source !== source) {
      entry.controller.abort("route-changed");
      inflight.delete(key);
    }
  }
}

axios.get = function guardedGet(url, config = {}) {
  // Explicit caller-provided AbortController keeps full ownership.
  if (config?.signal || config?.skipRequestGuard) {
    return originalGet(url, config);
  }

  const source = currentSource();
  abortStaleRoutes(source);

  const key = `${source}|GET|${url}|${stableParams(config?.params)}`;
  const now = Date.now();
  const existing = inflight.get(key);

  if (existing && now - existing.startedAt < MAX_INFLIGHT_AGE_MS) {
    return existing.promise;
  }

  if (existing) {
    existing.controller.abort("superseded");
    inflight.delete(key);
  }

  const controller = new AbortController();
  const headers = {
    ...(config?.headers || {}),
    "X-Client-Source": source,
  };

  const promise = originalGet(url, {
    ...config,
    headers,
    signal: controller.signal,
  }).finally(() => {
    const current = inflight.get(key);
    if (current?.controller === controller) inflight.delete(key);
  });

  inflight.set(key, {
    source,
    controller,
    promise,
    startedAt: now,
  });

  return promise;
};

if (typeof window !== "undefined") {
  window.addEventListener("pagehide", () => {
    for (const entry of inflight.values()) entry.controller.abort("page-hidden");
    inflight.clear();
  });
}

export function abortAllPendingGets(reason = "manual") {
  for (const entry of inflight.values()) entry.controller.abort(reason);
  inflight.clear();
}
