import { API } from "../lib/apiBase";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  ClipboardText,
  FileText,
  Headset,
  UserPlus,
  Package,
  ShoppingCart,
  Warning,
  WarningCircle,
  CheckCircle,
  Wrench,
} from "@phosphor-icons/react";
import { formatDateIT } from "../lib/dateFmt";



function localDateString(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function addDays(dateString, days) {
  const [y, m, d] = String(dateString).split("-").map(Number);
  const dt = new Date(y, (m || 1) - 1, d || 1);
  dt.setDate(dt.getDate() + days);
  return localDateString(dt);
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

export default function DashboardPage() {
  const [data, setData] = useState({
    lead: [],
    clienti: [],
    sedi: [],
    sopralluoghi: [],
    preventivi: [],
    ordini: [],
    installazioni: [],
    assistenza: [],
    anomalie: [],
    sottoScorta: [],
    esauriti: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshedAt, setRefreshedAt] = useState(null);
  const [refreshSeconds, setRefreshSeconds] = useState(0);

  const safeGet = useCallback(async (url, fallback) => {
    try {
      const { data: response } = await axios.get(url);
      return response;
    } catch {
      return fallback;
    }
  }, []);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);

    try {
      const [
        leadRes,
        clientiRes,
        sediRes,
        sopralluoghiRes,
        preventiviRes,
        ordiniRes,
        installazioniRes,
        assistenzaRes,
        anomalieRes,
        kpiRes,
      ] = await Promise.all([
        safeGet(`${API}/crm/lead`, { items: [] }),
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
        lead: leadRes?.items || [],
        clienti: clientiRes?.items || [],
        sedi: sediRes?.items || [],
        sopralluoghi: sopralluoghiRes?.items || [],
        preventivi: preventiviRes?.items || [],
        ordini: ordiniRes?.items || [],
        installazioni: installazioniRes?.items || [],
        assistenza: assistenzaRes?.items || [],
        anomalie: anomalieRes?.items || [],
        sottoScorta: kpiRes?.sotto_scorta || [],
        esauriti: kpiRes?.esauriti || [],
      });
      setRefreshedAt(new Date());
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Errore caricamento Dashboard");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [safeGet]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const { data: settings } = await axios.get(`${API}/settings`);
        const enabled = !!settings?.general?.auto_refresh_enabled;
        const seconds = Number(settings?.dashboard?.autorefresh_seconds || 0);
        setRefreshSeconds(enabled && seconds >= 15 ? seconds : 0);
      } catch {
        setRefreshSeconds(0);
      }
    };
    loadSettings();
    window.addEventListener("elios:settings-changed", loadSettings);
    return () => window.removeEventListener("elios:settings-changed", loadSettings);
  }, []);

  useEffect(() => {
    if (!refreshSeconds) return undefined;
    const id = setInterval(() => load(true), refreshSeconds * 1000);
    return () => clearInterval(id);
  }, [load, refreshSeconds]);

  useEffect(() => {
    const onRefresh = () => load(true);
    window.addEventListener("elios:refresh-dashboard", onRefresh);
    return () => window.removeEventListener("elios:refresh-dashboard", onRefresh);
  }, [load]);

  const clientiById = useMemo(
    () => Object.fromEntries(data.clienti.map((x) => [String(x.id), x])),
    [data.clienti]
  );
  const sediById = useMemo(
    () => Object.fromEntries(data.sedi.map((x) => [String(x.id), x])),
    [data.sedi]
  );

  const clientName = useCallback((id) => {
    const c = clientiById[String(id)] || {};
    return c.ragione_sociale || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente";
  }, [clientiById]);

  const siteName = useCallback((id) => {
    const s = sediById[String(id)] || {};
    return s.nome || [s.indirizzo, s.comune].filter(Boolean).join(" · ") || "Sede";
  }, [sediById]);

  const today = localDateString();
  const weekEnd = addDays(today, 7);

  const installazioniDaProgrammare = data.installazioni.filter(
    (x) => normalizeText(x.stato) === "da programmare"
  );
  const installazioniProgrammate = data.installazioni.filter((x) => normalizeText(x.stato) === "programmata");
  const installazioniConfermate = data.installazioni.filter((x) => normalizeText(x.stato) === "confermata / da installare");
  const installazioniCompletate = data.installazioni.filter((x) => normalizeText(x.stato) === "completata");
  const installazioniSospese = data.installazioni.filter((x) => ["in sospeso","sospesa"].includes(normalizeText(x.stato)));
  const programmateOggi = installazioniProgrammate.filter((x) => String(x.data || "").slice(0,10) === today).length;
  const programmateSettimana = installazioniProgrammate.filter((x) => x.data && String(x.data).slice(0,10) >= today && String(x.data).slice(0,10) <= weekEnd).length;
  const assistenzeAperte = data.assistenza.filter((x) =>
    ["aperta", "da programmare", "programmata", "in lavorazione", "in attesa cliente / fornitore", "tecnico in intervento"].includes(normalizeText(x.stato))
  );
  const preventiviDaSeguire = data.preventivi.filter((x) =>
    ["bozza", "inviato", "scaduto"].includes(normalizeText(x.stato))
  );
  const sopralluoghiDaProgrammare = data.sopralluoghi.filter(
    (x) => normalizeText(x.stato) === "da programmare"
  );
  const ordiniDaAvviare = data.ordini.filter((x) =>
    ["contratto firmato", "ordine confermato"].includes(normalizeText(x.stato_commerciale || x.stato)) &&
    !["completata", "consegnato"].includes(normalizeText(x.stato_installazione || x.stato_logistico))
  );
  const leadDaContattare = data.lead.filter((x) =>
    ["da contattare", "appuntamento da fissare"].includes(normalizeText(x.stato))
  );
  const finanziarieDaGestire = data.ordini.filter((x) =>
    ["in istruttoria", "integrazione richiesta", "respinta", "approvata"].includes(normalizeText(x.stato_finanziaria))
  );

  const magazzinoCritico = useMemo(() => {
    const ids = new Set();
    [...data.esauriti, ...data.sottoScorta].forEach((x) => ids.add(x.id || x.code || x.name));
    return ids.size;
  }, [data.esauriti, data.sottoScorta]);

  const tasks = useMemo(() => {
    const list = [];

    data.assistenza.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (!["aperta", "in lavorazione"].includes(stato)) return;
      list.push({
        key: `assist-${x.id}`,
        priority: 1,
        tone: "red",
        icon: Headset,
        title: stato === "aperta" ? "Assistenza aperta" : "Assistenza in lavorazione",
        subtitle: `${x.numero ? `Ticket ${x.numero} · ` : ""}${clientName(x.cliente_id)}${x.sede_id ? ` · ${siteName(x.sede_id)}` : ""}`,
        detail: x.descrizione || "Richiede gestione",
        to: "/assistenza",
        action: "Apri assistenza",
      });
    });

    data.preventivi.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (!["bozza", "inviato", "scaduto"].includes(stato)) return;
      const scaduto = stato === "scaduto";
      list.push({
        key: `prev-${x.id}`,
        priority: scaduto ? 1 : stato === "bozza" ? 2 : 3,
        tone: scaduto ? "red" : "amber",
        icon: FileText,
        title: scaduto ? "Preventivo scaduto" : stato === "bozza" ? "Preventivo da completare" : "Preventivo da seguire",
        subtitle: `${x.numero ? `Preventivo ${x.numero} · ` : ""}${clientName(x.cliente_id)}`,
        detail: x.importo ? `€ ${Number(x.importo).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "",
        to: "/preventivi",
        action: "Apri preventivi",
      });
    });

    data.installazioni.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (["in sospeso","sospesa"].includes(stato)) {
        list.push({ key:`inst-sosp-${x.id}`, priority:1, tone:"red", icon:Wrench, title:"Installazione in sospeso", subtitle:`${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`, detail:x.note||"Richiede attenzione", to:"/installazioni", action:"Apri" });
        return;
      }
      if (stato === "installata") {
        list.push({ key:`inst-done-${x.id}`, priority:2, tone:"amber", icon:Wrench, title:"Installazione eseguita da chiudere", subtitle:`${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`, detail:"Verifica report e chiudi come completata", to:"/installazioni", action:"Verifica" });
        return;
      }
      if (stato !== "da programmare") return;
      list.push({
        key: `inst-${x.id}`,
        priority: 1,
        tone: "red",
        icon: Wrench,
        title: "Installazione da programmare",
        subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`,
        detail: x.tecnico ? `Tecnico: ${x.tecnico}` : "Assegna data e tecnico",
        to: "/installazioni",
        action: "Programma",
      });
    });

    data.sopralluoghi.forEach((x) => {
      if (normalizeText(x.stato) !== "da programmare") return;
      list.push({
        key: `sopr-${x.id}`,
        priority: 2,
        tone: "amber",
        icon: ClipboardText,
        title: "Sopralluogo da programmare",
        subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`,
        detail: x.data ? `Data indicata: ${formatDateIT(x.data)}` : "Definisci data e tecnico",
        to: "/sopralluoghi",
        action: "Programma",
      });
    });

    data.ordini.forEach((x) => {
      const commerciale = normalizeText(x.stato_commerciale || x.stato);
      if (!["contratto firmato", "ordine confermato"].includes(commerciale)) return;
      const installazione = normalizeText(x.stato_installazione);
      const logistica = normalizeText(x.stato_logistico);
      if (installazione === "completata" || logistica === "consegnato") return;
      list.push({
        key: `ord-${x.id}`,
        priority: 2,
        tone: "blue",
        icon: ShoppingCart,
        title: "Ordine confermato da avviare",
        subtitle: `${x.numero ? `Ordine ${x.numero} · ` : ""}${clientName(x.cliente_id)}${x.sede_id ? ` · ${siteName(x.sede_id)}` : ""}`,
        detail: x.data ? formatDateIT(x.data) : "",
        to: "/clienti-ordini",
        action: "Apri Clienti / Ordini",
      });
    });

    data.ordini.forEach((x) => {
      const stato = normalizeText(x.stato_finanziaria);
      if (!["in istruttoria", "integrazione richiesta", "respinta", "approvata"].includes(stato)) return;
      const labels = {
        "in istruttoria": ["Finanziaria in istruttoria", 3, "amber"],
        "integrazione richiesta": ["Integrazione finanziaria richiesta", 1, "red"],
        respinta: ["Pratica finanziaria respinta", 1, "red"],
        approvata: ["Finanziaria approvata da avviare", 2, "blue"],
      };
      const [title, priority, tone] = labels[stato];
      list.push({
        key: `fin-${x.id}`,
        priority,
        tone,
        icon: FileText,
        title,
        subtitle: `${x.numero ? `Ordine ${x.numero} · ` : ""}${clientName(x.cliente_id)}`,
        detail: [x.finanziaria || x.modalita_pagamento, x.numero_pratica_finanziaria ? `Pratica ${x.numero_pratica_finanziaria}` : ""].filter(Boolean).join(" · "),
        to: "/clienti-ordini",
        action: "Apri pratica",
      });
    });

    data.lead.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (!["da contattare", "appuntamento da fissare"].includes(stato)) return;
      list.push({
        key: `lead-${x.id}`,
        priority: stato === "da contattare" ? 2 : 3,
        tone: "blue",
        icon: UserPlus,
        title: stato === "da contattare" ? "Lead da contattare" : "Appuntamento da fissare",
        subtitle: [x.nome, x.referente].filter(Boolean).join(" · ") || "Lead commerciale",
        detail: x.telefono || x.email || "",
        to: "/lead",
        action: "Apri lead",
      });
    });

    if (data.anomalie.length > 0) {
      list.push({
        key: "anomalie",
        priority: 1,
        tone: "red",
        icon: Warning,
        title: `${data.anomalie.length} ${data.anomalie.length === 1 ? "anomalia da verificare" : "anomalie da verificare"}`,
        subtitle: "Controlla errori di seriali, giacenze e configurazione prodotti",
        detail: "",
        to: "/anomalie",
        action: "Controlla",
      });
    }

    if (data.esauriti.length > 0) {
      list.push({
        key: "esauriti",
        priority: 1,
        tone: "red",
        icon: Package,
        title: `${data.esauriti.length} ${data.esauriti.length === 1 ? "prodotto esaurito" : "prodotti esauriti"}`,
        subtitle: data.esauriti.slice(0, 3).map((x) => x.name).filter(Boolean).join(" · "),
        detail: "Verifica approvvigionamento",
        to: "/inventario",
        action: "Apri magazzino",
      });
    } else if (data.sottoScorta.length > 0) {
      list.push({
        key: "sottoscorta",
        priority: 2,
        tone: "amber",
        icon: WarningCircle,
        title: `${data.sottoScorta.length} ${data.sottoScorta.length === 1 ? "prodotto sotto scorta" : "prodotti sotto scorta"}`,
        subtitle: data.sottoScorta.slice(0, 3).map((x) => x.name).filter(Boolean).join(" · "),
        detail: "Valuta riordino materiale",
        to: "/inventario",
        action: "Apri magazzino",
      });
    }

    return list.sort((a, b) => a.priority - b.priority).slice(0, 12);
  }, [data, clientName, siteName]);

  const upcoming = useMemo(() => {
    const list = [];

    data.installazioni.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (!x.data || !["programmata", "confermata / da installare", "installata"].includes(stato)) return;
      if (x.data < today || x.data > weekEnd) return;
      list.push({
        key: `up-inst-${x.id}`,
        date: x.data,
        type: "Installazione",
        icon: Wrench,
        title: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`,
        detail: x.tecnico ? `Tecnico: ${x.tecnico}` : "Tecnico da assegnare",
        to: "/installazioni",
      });
    });

    data.sopralluoghi.forEach((x) => {
      const stato = normalizeText(x.stato);
      if (!x.data || stato !== "programmato") return;
      if (x.data < today || x.data > weekEnd) return;
      list.push({
        key: `up-sopr-${x.id}`,
        date: x.data,
        type: "Sopralluogo",
        icon: ClipboardText,
        title: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`,
        detail: [x.ora, x.tecnico].filter(Boolean).join(" · ") || "",
        to: "/sopralluoghi",
      });
    });

    return list.sort((a, b) => String(a.date).localeCompare(String(b.date))).slice(0, 10);
  }, [data.installazioni, data.sopralluoghi, clientName, siteName, today, weekEnd]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6" data-testid="dashboard-page">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div><h1 className="et-page-heading text-3xl sm:text-4xl">Dashboard</h1></div>
      </div>

      {error && (
        <div className="border border-red-200 bg-red-50 text-red-700 p-4 rounded-md text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <ActionKpi to="/installazioni" icon={Wrench} label="Programmate" value={installazioniProgrammate.length} sub={`${programmateOggi} oggi · ${programmateSettimana} nei prossimi 7 giorni`} tone="amber" />
        <ActionKpi to="/installazioni" icon={CheckCircle} label="Da installare" value={installazioniConfermate.length} sub={`${installazioniDaProgrammare.length} ancora da programmare`} tone={installazioniConfermate.length?"green":"slate"} />
        <ActionKpi to="/assistenza" icon={Headset} label="Assistenze aperte" value={assistenzeAperte.length} sub={assistenzeAperte.length?"Richiedono gestione":"Nessuna aperta"} tone={assistenzeAperte.length?"red":"green"} />
        <ActionKpi to="/inventario" icon={Package} label="Magazzino critico" value={magazzinoCritico} sub={`${data.sottoScorta.length} sotto scorta · ${data.esauriti.length} esauriti`} tone={data.esauriti.length?"red":magazzinoCritico?"amber":"green"} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
        <section className="xl:col-span-2 bg-white border border-slate-200 rounded-md overflow-hidden" data-testid="dashboard-tasks">
          <div className="px-4 sm:px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
            <div>
              <div className="font-bold text-slate-900">Attività</div>
            </div>
            <span className="font-mono-tight text-xs text-slate-500 bg-slate-100 rounded px-2 py-1">{tasks.length}</span>
          </div>

          {loading && tasks.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-400">Caricamento attività…</div>
          ) : tasks.length === 0 ? (
            <div className="py-12 px-4 text-center">
              <div className="text-lg font-bold text-emerald-700">Nessuna attività urgente</div>
              <div className="text-sm text-slate-500 mt-1">Al momento non risultano attività aperte o criticità.</div>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {tasks.map((task) => <TaskRow key={task.key} task={task} />)}
            </div>
          )}
        </section>

        <section className="bg-white border border-slate-200 rounded-md overflow-hidden" data-testid="dashboard-summary">
          <div className="px-4 py-4 border-b border-slate-200">
            <div className="font-bold text-slate-900">In attesa</div>
          </div>
          <div className="divide-y divide-slate-100">
            <MiniCount to="/lead" icon={UserPlus} label="Lead da contattare" value={leadDaContattare.length} />
            <MiniCount to="/sopralluoghi" icon={ClipboardText} label="Sopralluoghi da programmare" value={sopralluoghiDaProgrammare.length} />
            <MiniCount to="/clienti-ordini" icon={ShoppingCart} label="Ordini da avviare" value={ordiniDaAvviare.length} />
            <MiniCount to="/clienti-ordini" icon={FileText} label="Finanziarie da gestire" value={finanziarieDaGestire.length} danger={data.ordini.some((x) => ["respinta", "integrazione richiesta"].includes(normalizeText(x.stato_finanziaria)))} />
            <MiniCount to="/anomalie" icon={Warning} label="Anomalie registrate" value={data.anomalie.length} danger={data.anomalie.length > 0} />
            <MiniCount to="/inventario" icon={WarningCircle} label="Prodotti sotto scorta" value={data.sottoScorta.length} danger={data.esauriti.length > 0} />
          </div>
        </section>
      </div>

      <section className="bg-white border border-slate-200 rounded-md overflow-hidden" data-testid="dashboard-upcoming">
        <div className="px-4 sm:px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
          <div>
            <div className="font-bold text-slate-900">Prossimi 7 giorni</div>
          </div>
          <span className="font-mono-tight text-xs text-slate-500 bg-slate-100 rounded px-2 py-1">{upcoming.length}</span>
        </div>
        {upcoming.length === 0 ? (
          <div className="py-9 text-center text-sm text-slate-400">Nessuna attività programmata nei prossimi 7 giorni.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {upcoming.map((item) => (
              <Link key={item.key} to={item.to} className="px-4 sm:px-5 py-3 flex items-center gap-3 hover:bg-slate-50 transition-colors">
                <div className="w-14 shrink-0 text-center border border-slate-200 rounded-md py-1.5 bg-slate-50">
                  <div className="text-[10px] uppercase tracking-wide text-slate-400">Data</div>
                  <div className="text-xs font-bold text-slate-800 font-mono-tight">{formatDateIT(item.date)}</div>
                </div>
                <div className="w-9 h-9 rounded-md bg-slate-100 flex items-center justify-center text-slate-700 shrink-0">
                  <item.icon size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs uppercase font-bold tracking-wide text-slate-400">{item.type}</div>
                  <div className="text-sm font-semibold text-slate-900 truncate">{item.title}</div>
                  {item.detail && <div className="text-xs text-slate-500 truncate mt-0.5">{item.detail}</div>}
                </div>
                <span className="text-xs text-slate-400 shrink-0">Apri →</span>
              </Link>
            ))}
          </div>
        )}
      </section>

      {refreshedAt && (
        <div className="text-[10px] text-slate-400 text-center">
          Ultimo aggiornamento: {refreshedAt.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}{refreshSeconds > 0 ? ` · aggiornamento automatico ogni ${refreshSeconds} secondi` : ""}
        </div>
      )}
    </div>
  );
}

function ActionKpi({ to, icon: Icon, label, value, sub, tone = "slate" }) {
  const accents = {
    red: "text-red-600 bg-red-50 border-red-100",
    amber: "text-amber-600 bg-amber-50 border-amber-100",
    green: "text-emerald-600 bg-emerald-50 border-emerald-100",
    darkgreen: "text-emerald-700 bg-emerald-50 border-emerald-100",
    slate: "text-slate-600 bg-slate-50 border-slate-100",
  };
  return (
    <Link to={to} className="group rounded-2xl border border-slate-200 bg-white px-4 py-3.5 sm:px-5 shadow-[0_1px_2px_rgba(15,23,42,.04)] hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md transition-all min-h-[116px]">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] sm:text-xs font-bold uppercase tracking-[.08em] leading-tight text-slate-500">{label}</div>
        <div className={`h-9 w-9 rounded-xl border flex items-center justify-center shrink-0 ${accents[tone] || accents.slate}`}><Icon size={18} weight="bold" /></div>
      </div>
      <div className="flex items-end justify-between gap-3 mt-2">
        <div className={`text-3xl sm:text-4xl font-black font-mono-tight ${String(accents[tone] || accents.slate).split(" ")[0]}`}>{value}</div>
        <div className="text-[11px] font-semibold text-slate-400 group-hover:text-slate-700 transition-colors">Apri →</div>
      </div>
      {sub&&<div className="text-[11px] text-slate-400 mt-1 truncate">{sub}</div>}
    </Link>
  );
}

function TaskRow({ task }) {
  const tones = {
    red: "bg-red-50 text-red-700 border-red-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const Icon = task.icon;
  return (
    <Link to={task.to} className="px-4 sm:px-5 py-3.5 flex items-center gap-3 hover:bg-slate-50 transition-colors group">
      <div className={`w-10 h-10 border rounded-md flex items-center justify-center shrink-0 ${tones[task.tone] || tones.blue}`}>
        <Icon size={20} weight="bold" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-bold text-slate-900 truncate">{task.title}</div>
        <div className="text-xs text-slate-600 truncate mt-0.5">{task.subtitle}</div>
        {task.detail && <div className="text-[11px] text-slate-400 truncate mt-0.5">{task.detail}</div>}
      </div>
      <div className="text-xs font-semibold text-slate-500 group-hover:text-slate-900 shrink-0 hidden sm:block">{task.action} →</div>
    </Link>
  );
}

function MiniCount({ to, icon: Icon, label, value, danger = false }) {
  return (
    <Link to={to} className="px-4 py-3 flex items-center gap-3 hover:bg-slate-50 transition-colors">
      <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${danger ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"}`}>
        <Icon size={16} />
      </div>
      <div className="text-sm text-slate-700 flex-1 min-w-0">{label}</div>
      <div className={`font-black font-mono-tight ${danger ? "text-red-700" : "text-slate-900"}`}>{value}</div>
    </Link>
  );
}
