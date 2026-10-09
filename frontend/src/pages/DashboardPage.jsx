import { API } from "../lib/apiBase";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  CalendarBlank, ClipboardText, FileText, Headset, Package, ShoppingCart,
  Warning, Wrench, CheckCircle, ArrowClockwise,
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { formatDateIT } from "../lib/dateFmt";

function localDateString(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function StatCard({ icon: Icon, title, value, meta, to }) {
  return <Link to={to} className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm hover:border-slate-300 transition block min-w-0">
    <div className="flex items-start justify-between gap-3"><div className="h-9 w-9 rounded-lg bg-slate-100 flex items-center justify-center text-[#1A456B]"><Icon size={19} weight="bold" /></div><span className="text-2xl font-black text-slate-900">{value}</span></div>
    <div className="mt-3 text-sm font-bold text-slate-800">{title}</div>
    <div className="mt-0.5 text-xs text-slate-500 truncate">{meta || "Apri dettaglio"}</div>
  </Link>;
}

function TaskRow({ icon: Icon, title, subtitle, detail, to, urgent }) {
  return <Link to={to} className="flex items-start gap-3 px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition">
    <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${urgent ? "bg-red-50 text-red-600" : "bg-slate-100 text-[#1A456B]"}`}><Icon size={18} weight="bold" /></div>
    <div className="min-w-0 flex-1"><div className="text-sm font-bold text-slate-900 truncate">{title}</div><div className="text-xs text-slate-600 truncate mt-0.5">{subtitle}</div>{detail && <div className="text-xs text-slate-400 truncate mt-0.5">{detail}</div>}</div>
  </Link>;
}

export default function DashboardPage() {
  const [data, setData] = useState({ clienti: [], sedi: [], sopralluoghi: [], preventivi: [], ordini: [], installazioni: [], assistenza: [], anomalie: [], sottoScorta: [], esauriti: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshedAt, setRefreshedAt] = useState(null);
  const [refreshSeconds, setRefreshSeconds] = useState(0);

  const safeGet = useCallback(async (url, fallback) => {
    try { return (await axios.get(url)).data; } catch { return fallback; }
  }, []);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [clienti, sedi, sopralluoghi, preventivi, ordini, installazioni, assistenza, anomalie, kpi] = await Promise.all([
        safeGet(`${API}/crm/clienti`, { items: [] }),
        safeGet(`${API}/crm/sedi`, { items: [] }),
        safeGet(`${API}/crm/sopralluoghi`, { items: [] }),
        safeGet(`${API}/crm/preventivi`, { items: [] }),
        safeGet(`${API}/crm/ordini-clienti`, { items: [] }),
        safeGet(`${API}/crm/installazioni`, { items: [] }),
        safeGet(`${API}/crm/assistenza`, { items: [] }),
        safeGet(`${API}/anomalie?limit=200`, { items: [] }),
        safeGet(`${API}/dashboard/kpi`, {}),
      ]);
      setData({
        clienti: clienti.items || [], sedi: sedi.items || [], sopralluoghi: sopralluoghi.items || [],
        preventivi: preventivi.items || [], ordini: ordini.items || [], installazioni: installazioni.items || [],
        assistenza: assistenza.items || [], anomalie: anomalie.items || [],
        sottoScorta: kpi.sotto_scorta || [], esauriti: kpi.esauriti || [],
      });
      setRefreshedAt(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Errore caricamento Dashboard");
    } finally { if (!silent) setLoading(false); }
  }, [safeGet]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const { data: settings } = await axios.get(`${API}/settings`);
        const enabled = !!settings?.general?.auto_refresh_enabled;
        const seconds = Number(settings?.dashboard?.autorefresh_seconds || 0);
        setRefreshSeconds(enabled && seconds >= 15 ? seconds : 0);
      } catch { setRefreshSeconds(0); }
    };
    loadSettings();
    window.addEventListener("elios:settings-changed", loadSettings);
    return () => window.removeEventListener("elios:settings-changed", loadSettings);
  }, []);

  useEffect(() => {
    if (!refreshSeconds) return undefined;
    const id = window.setInterval(() => load(true), refreshSeconds * 1000);
    return () => window.clearInterval(id);
  }, [load, refreshSeconds]);

  useEffect(() => {
    const onRefresh = () => load(true);
    window.addEventListener("elios:refresh-dashboard", onRefresh);
    return () => window.removeEventListener("elios:refresh-dashboard", onRefresh);
  }, [load]);

  const clientiById = useMemo(() => Object.fromEntries(data.clienti.map((x) => [String(x.id), x])), [data.clienti]);
  const sediById = useMemo(() => Object.fromEntries(data.sedi.map((x) => [String(x.id), x])), [data.sedi]);
  const clientName = useCallback((id) => { const c = clientiById[String(id)] || {}; return c.ragione_sociale || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente"; }, [clientiById]);
  const siteName = useCallback((id) => { const s = sediById[String(id)] || {}; return s.nome || [s.indirizzo, s.comune].filter(Boolean).join(" · ") || "Sede"; }, [sediById]);

  const today = localDateString();
  const programmate = data.installazioni.filter((x) => normalize(x.stato) === "programmata");
  const programmateOggi = programmate.filter((x) => String(x.data || "").slice(0, 10) === today).length;
  const daInstallare = data.installazioni.filter((x) => ["da programmare", "confermata / da installare", "confermata", "da installare"].includes(normalize(x.stato)));
  const assistenzeAperte = data.assistenza.filter((x) => !["risolta", "completata", "chiusa"].includes(normalize(x.stato)));
  const sopralluoghiAperti = data.sopralluoghi.filter((x) => !["eseguito", "annullato"].includes(normalize(x.stato)));
  const preventiviAperti = data.preventivi.filter((x) => !["accettato", "rifiutato"].includes(normalize(x.stato)));
  const ordiniAperti = data.ordini.filter((x) => !["completato", "annullato"].includes(normalize(x.stato)));
  const magazzinoCritico = useMemo(() => {
    const ids = new Set();
    [...data.esauriti, ...data.sottoScorta].forEach((x) => ids.add(x.id || x.code || x.name));
    return ids.size;
  }, [data.esauriti, data.sottoScorta]);

  const tasks = useMemo(() => {
    const out = [];
    data.assistenza.forEach((x) => {
      const stato = normalize(x.stato);
      if (["risolta", "completata", "chiusa"].includes(stato)) return;
      out.push({ key: `a-${x.id}`, priority: ["urgente", "aperta"].includes(normalize(x.priorita)) ? 1 : 2, icon: Headset, title: x.numero ? `Assistenza ${x.numero}` : "Assistenza aperta", subtitle: `${clientName(x.cliente_id)}${x.sede_id ? ` · ${siteName(x.sede_id)}` : ""}`, detail: x.descrizione || x.note_tecniche || x.stato, to: "/assistenza", urgent: normalize(x.priorita) === "urgente" });
    });
    data.installazioni.forEach((x) => {
      const stato = normalize(x.stato);
      if (["in sospeso", "sospesa"].includes(stato)) out.push({ key: `i-s-${x.id}`, priority: 1, icon: Wrench, title: "Installazione sospesa", subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`, detail: x.note || "Richiede verifica", to: "/installazioni", urgent: true });
      else if (["da programmare", "confermata / da installare", "confermata", "da installare"].includes(stato)) out.push({ key: `i-${x.id}`, priority: 2, icon: Wrench, title: "Installazione da gestire", subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`, detail: x.data ? `Data: ${formatDateIT(x.data)}` : "Da programmare", to: "/installazioni" });
    });
    data.sopralluoghi.forEach((x) => {
      if (normalize(x.stato) !== "da programmare") return;
      out.push({ key: `s-${x.id}`, priority: 3, icon: ClipboardText, title: "Sopralluogo da programmare", subtitle: `${clientName(x.cliente_id)}${x.sede_id ? ` · ${siteName(x.sede_id)}` : ""}`, detail: x.data ? formatDateIT(x.data) : "Definisci data e tecnico", to: "/sopralluoghi" });
    });
    data.preventivi.forEach((x) => {
      if (!includesAny(normalize(x.stato), ["bozza", "inviato", "scaduto"])) return;
      out.push({ key: `p-${x.id}`, priority: normalize(x.stato) === "scaduto" ? 2 : 4, icon: FileText, title: normalize(x.stato) === "scaduto" ? "Preventivo scaduto" : "Preventivo da seguire", subtitle: `${x.numero ? `${x.numero} · ` : ""}${clientName(x.cliente_id)}`, detail: x.stato, to: "/preventivi", urgent: normalize(x.stato) === "scaduto" });
    });
    data.anomalie.filter((x) => normalize(x.status || x.stato) !== "risolta").slice(0, 5).forEach((x) => out.push({ key: `e-${x.id || x._id}`, priority: 1, icon: Warning, title: "Anomalia da verificare", subtitle: x.title || x.message || x.tipo || "Sistema", detail: x.detail || x.descrizione || "", to: "/anomalie", urgent: true }));
    return out.sort((a, b) => a.priority - b.priority).slice(0, 12);
  }, [data.assistenza, data.installazioni, data.sopralluoghi, data.preventivi, data.anomalie, clientName, siteName]);

  const quickFlow = [
    [ShoppingCart, "Clienti / Ordini", "/clienti-ordini"],
    [Wrench, "Commesse", "/commesse"],
    [ClipboardText, "Sopralluoghi", "/sopralluoghi"],
    [FileText, "Preventivi", "/preventivi"],
    [CalendarBlank, "Calendario", "/calendario"],
    [Wrench, "Installazioni", "/installazioni"],
    [Headset, "Assistenza", "/assistenza"],
  ];

  return <div className="max-w-[1500px] mx-auto px-4 sm:px-6 py-5 space-y-5" data-testid="dashboard-page">
    <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-3"><div><div className="text-xs uppercase tracking-[.16em] text-[#1A456B] font-semibold">Elios Tech</div><h1 className="text-3xl font-black text-slate-900">Dashboard operativa</h1><p className="text-sm text-slate-500 mt-1">Priorità tecniche, installazioni, assistenze, ordini e magazzino in un'unica vista.</p></div><div className="flex items-center gap-3"><div className="text-xs text-slate-400">{refreshedAt ? `Aggiornato ${refreshedAt.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}` : ""}</div><Button variant="outline" onClick={() => load()} disabled={loading}><ArrowClockwise size={16} className={loading ? "animate-spin" : ""} /> Aggiorna</Button></div></div>

    {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
      <StatCard icon={CalendarBlank} title="Programmate" value={programmate.length} meta={`${programmateOggi} oggi`} to="/installazioni" />
      <StatCard icon={Wrench} title="Da installare" value={daInstallare.length} meta="da programmare / confermate" to="/installazioni" />
      <StatCard icon={Headset} title="Assistenze" value={assistenzeAperte.length} meta="aperte o in lavorazione" to="/assistenza" />
      <StatCard icon={ClipboardText} title="Sopralluoghi" value={sopralluoghiAperti.length} meta="da gestire" to="/sopralluoghi" />
      <StatCard icon={ShoppingCart} title="Ordini aperti" value={ordiniAperti.length} meta={`${preventiviAperti.length} preventivi aperti`} to="/clienti-ordini" />
      <StatCard icon={Package} title="Magazzino critico" value={magazzinoCritico} meta={`${data.esauriti.length} esauriti`} to="/inventario" />
    </div>

    <div className="grid xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,.65fr)] gap-5">
      <section className="bg-white border border-slate-200 rounded-xl overflow-hidden"><div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between"><div><h2 className="font-black text-slate-900">Da fare</h2><p className="text-xs text-slate-500">Attività che richiedono attenzione</p></div><span className="text-xs font-bold text-slate-500">{tasks.length}</span></div>{loading && !refreshedAt ? <div className="p-8 text-center text-sm text-slate-400">Caricamento…</div> : tasks.length ? tasks.map((task) => <TaskRow key={task.key} {...task} />) : <div className="p-8 text-center"><CheckCircle size={28} className="mx-auto text-emerald-500" weight="fill" /><div className="text-sm font-semibold text-slate-700 mt-2">Nessuna priorità aperta</div></div>}</section>

      <section className="bg-white border border-slate-200 rounded-xl p-4 h-fit"><h2 className="font-black text-slate-900">Flusso gestionale</h2><p className="text-xs text-slate-500 mt-1 mb-3">Accesso rapido alle fasi operative.</p><div className="grid sm:grid-cols-2 xl:grid-cols-1 gap-2">{quickFlow.map(([Icon, label, to], i) => <Link key={to} to={to} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50"><div className="h-8 w-8 rounded-lg bg-slate-100 text-[#1A456B] flex items-center justify-center"><Icon size={16} /></div><div className="flex-1 text-sm font-semibold text-slate-800">{label}</div><span className="text-xs text-slate-400">{i + 1}</span></Link>)}</div></section>
    </div>
  </div>;
}

function includesAny(value, values) {
  return values.includes(value);
}
