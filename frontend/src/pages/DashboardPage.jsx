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

function StatCard({ icon: Icon, title, value, meta, to, tone = "blue" }) {
  return (
    <Link to={to} className={`r52-dashboard-stat r52-dashboard-stat-${tone}`}>
      <div className="r52-dashboard-stat-top">
        <div className="r52-dashboard-stat-icon"><Icon size={20} weight="duotone" /></div>
        <span className="r52-dashboard-stat-value">{value}</span>
      </div>
      <div className="r52-dashboard-stat-title">{title}</div>
      <div className="r52-dashboard-stat-meta">{meta || "Apri dettaglio"}</div>
    </Link>
  );
}

function TaskRow({ icon: Icon, title, subtitle, detail, to, urgent }) {
  return (
    <Link to={to} className={`r52-dashboard-task ${urgent ? "is-urgent" : ""}`}>
      <div className="r52-dashboard-task-icon"><Icon size={18} weight="duotone" /></div>
      <div className="min-w-0 flex-1">
        <div className="r52-dashboard-task-title">{title}</div>
        <div className="r52-dashboard-task-subtitle">{subtitle}</div>
        {detail && <div className="r52-dashboard-task-detail">{detail}</div>}
      </div>
    </Link>
  );
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

  return (
    <div className="r52-dashboard" data-testid="dashboard-page">
      <div className="r52-commandbar">
        <div>
          <div className="r52-commandbar-title">Quadro operativo</div>
          <div className="r52-commandbar-subtitle">Priorità e carichi di lavoro aggiornati dal database gestionale.</div>
        </div>
        <div className="r52-commandbar-actions">
          <span className="r52-last-update">{refreshedAt ? `Aggiornato ${refreshedAt.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}` : ""}</span>
          <Button variant="outline" onClick={() => load()} disabled={loading} className="r52-outline-button">
            <ArrowClockwise size={16} className={loading ? "animate-spin" : ""} /> Aggiorna
          </Button>
        </div>
      </div>

      {error && <div className="r52-alert r52-alert-danger">{error}</div>}

      <section>
        <div className="r52-section-heading">
          <div><div className="r52-section-kicker">Situazione</div><h2>Indicatori principali</h2></div>
        </div>
        <div className="r52-dashboard-stat-grid">
          <StatCard icon={CalendarBlank} title="Programmate" value={programmate.length} meta={`${programmateOggi} oggi`} to="/installazioni" tone="blue" />
          <StatCard icon={Wrench} title="Da installare" value={daInstallare.length} meta="da programmare / confermate" to="/installazioni" tone="navy" />
          <StatCard icon={Headset} title="Assistenze" value={assistenzeAperte.length} meta="aperte o in lavorazione" to="/assistenza" tone="teal" />
          <StatCard icon={ClipboardText} title="Sopralluoghi" value={sopralluoghiAperti.length} meta="da gestire" to="/sopralluoghi" tone="violet" />
          <StatCard icon={ShoppingCart} title="Ordini aperti" value={ordiniAperti.length} meta={`${preventiviAperti.length} preventivi aperti`} to="/clienti-ordini" tone="amber" />
          <StatCard icon={Package} title="Magazzino critico" value={magazzinoCritico} meta={`${data.esauriti.length} esauriti`} to="/inventario" tone="red" />
        </div>
      </section>

      <div className="r52-dashboard-main-grid">
        <section className="r52-panel r52-panel-flush">
          <div className="r52-panel-heading">
            <div><div className="r52-section-kicker">Priorità</div><h2>Da fare</h2><p>Attività che richiedono attenzione o programmazione.</p></div>
            <span className="r52-count-pill">{tasks.length}</span>
          </div>
          <div className="r52-task-list">
            {loading && !refreshedAt ? (
              <div className="r52-empty-state">Caricamento attività…</div>
            ) : tasks.length ? tasks.map((task) => <TaskRow key={task.key} {...task} />) : (
              <div className="r52-empty-state"><CheckCircle size={30} className="text-emerald-500" weight="fill" /><strong>Nessuna priorità aperta</strong><span>Il quadro operativo è libero da attività urgenti.</span></div>
            )}
          </div>
        </section>

        <section className="r52-panel">
          <div className="r52-panel-heading compact">
            <div><div className="r52-section-kicker">Navigazione</div><h2>Flusso gestionale</h2><p>Accesso rapido alle fasi operative.</p></div>
          </div>
          <div className="r52-flow-list">
            {quickFlow.map(([Icon, label, to], i) => (
              <Link key={to} to={to} className="r52-flow-link">
                <div className="r52-flow-icon"><Icon size={17} weight="duotone" /></div>
                <div className="r52-flow-label">{label}</div>
                <span className="r52-flow-step">{String(i + 1).padStart(2, "0")}</span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function includesAny(value, values) {
  return values.includes(value);
}