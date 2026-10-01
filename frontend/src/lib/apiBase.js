function resolveBackendUrl() {
  const configured = (process.env.REACT_APP_BACKEND_URL || "").trim();

  if (typeof window === "undefined") {
    return configured || "http://127.0.0.1:8001";
  }

  // In test locale (CRA su :3000) usiamo SEMPRE la stessa origine del browser.
  // Il dev-server inoltra /api al backend locale tramite "proxy" in package.json.
  // Questo rende identico il comportamento da PC e da smartphone in LAN.
  if (window.location.port === "3000") {
    return window.location.origin;
  }

  if (!configured) return window.location.origin;

  try {
    const u = new URL(configured);
    const browserHost = window.location.hostname;
    if ((u.hostname === "127.0.0.1" || u.hostname === "localhost") &&
        browserHost !== "127.0.0.1" && browserHost !== "localhost") {
      u.hostname = browserHost;
      return u.toString().replace(/\/$/, "");
    }
  } catch (_) {}

  return configured.replace(/\/$/, "");
}

export const BACKEND_URL = resolveBackendUrl();
export const API = `${BACKEND_URL}/api`;
