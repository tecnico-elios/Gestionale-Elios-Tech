import axios from "axios";

// Global front-pressure for the PWA.
// - identical GETs from the same route share one network request;
// - stale GETs from the previous route are aborted;
// - hot startup pages explicitly request small CRM pages;
// - every GET is tagged so Render logs identify the React route that generated it.
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

function isGenericCrmList(url) {
  const value = String(url || "");
  return /\/api\/crm\/(clienti|contatti|sedi|sopralluoghi|preventivi|ordini-clienti|installazioni|interventi-tecnici|assistenza)(?:\?|$)/.test(value);
}

function applyRouteBudget(url, config, source) {
  const next = { ...config, params: { ...(config?.params || {}) } };
  if (!isGenericCrmList(url)) return next;
  if (next.params.page != null || next.params.limit != null) return next;

  // Dashboard needs representative operational rows, not every historical row.
  if (source === "/dashboard") {
    next.params.page = 1;
    next.params.limit = 100;
    return next;
  }

  // Calendar only needs lookup options for its editor. Keep this bounded while
  // legacy administration screens retain their complete compatibility dataset.
  if (source === "/calendario") {
    next.params.page = 1;
    next.params.limit = 200;
  }

  return next;
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
  const source = currentSource();
  const budgeted = applyRouteBudget(url, config, source);
  const headers = {
    ...(budgeted?.headers || {}),
    "X-Client-Source": source,
  };

  // Explicit caller-provided AbortController keeps cancellation ownership, but
  // still receives source tagging and route budgets.
  if (budgeted?.signal || budgeted?.skipRequestGuard) {
    return originalGet(url, { ...budgeted, headers });
  }

  abortStaleRoutes(source);

  const key = `${source}|GET|${url}|${stableParams(budgeted?.params)}`;
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
  const promise = originalGet(url, {
    ...budgeted,
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
