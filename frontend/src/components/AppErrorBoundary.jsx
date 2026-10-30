import React from "react";
import { API } from "../lib/apiBase";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Elios Tech UI error", error, info);

    // Best-effort crash telemetry: never blocks the recovery UI.
    try {
      fetch(`${API}/_diag/ui-error`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        keepalive: true,
        body: JSON.stringify({
          path: `${window.location.pathname}${window.location.search || ""}`,
          message: error?.message || String(error || "Errore UI"),
          stack: error?.stack || "",
          componentStack: info?.componentStack || "",
          userAgent: navigator.userAgent || "",
        }),
      }).catch(() => {});
    } catch (_) {}
  }

  clearBrowserAppCache = async () => {
    try {
      if ("caches" in window) {
        const keys = await window.caches.keys();
        await Promise.all(keys.map((key) => window.caches.delete(key)));
      }
    } catch (_) {}

    try {
      if ("serviceWorker" in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.unregister()));
      }
    } catch (_) {}
  };

  goDashboard = async () => {
    await this.clearBrowserAppCache();
    window.location.replace(`/dashboard?fresh=${Date.now()}`);
  };

  reload = async () => {
    await this.clearBrowserAppCache();
    const url = new URL(window.location.href);
    url.searchParams.set("fresh", String(Date.now()));
    window.location.replace(url.toString());
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <section className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">Elios Tech</div>
          <h1 className="mt-2 text-2xl font-bold text-slate-950">La pagina non si è caricata correttamente</h1>
          <p className="mt-2 text-sm text-slate-600">L'errore è stato registrato automaticamente. Ricarica per prendere la versione più recente del gestionale oppure torna alla Dashboard.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button type="button" onClick={this.goDashboard} className="h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white">Vai alla Dashboard</button>
            <button type="button" onClick={this.reload} className="h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800">Ricarica pulita</button>
          </div>
        </section>
      </main>
    );
  }
}
