import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Keep the app usable instead of leaving the user on a blank page.
    console.error("Elios Tech UI error", error, info);
  }

  goDashboard = () => {
    window.location.assign("/dashboard");
  };

  reload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <section className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">Elios Tech</div>
          <h1 className="mt-2 text-2xl font-bold text-slate-950">La pagina non si è caricata correttamente</h1>
          <p className="mt-2 text-sm text-slate-600">Il gestionale non resta su una pagina bianca: puoi ricaricare oppure tornare direttamente alla Dashboard.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button type="button" onClick={this.goDashboard} className="h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white">Vai alla Dashboard</button>
            <button type="button" onClick={this.reload} className="h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800">Ricarica</button>
          </div>
        </section>
      </main>
    );
  }
}
