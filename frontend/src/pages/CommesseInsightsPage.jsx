import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { ChartBar, Lightning, CalendarBlank, TrendUp } from "@phosphor-icons/react";

const MONTHS = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];
const euro = (v) => `€ ${Number(v || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const getYear = (d) => { const m = String(d || "").match(/^(\d{4})/); return m ? Number(m[1]) : null; };
const getMonth = (d) => { const m = String(d || "").match(/^\d{4}-(\d{2})/); return m ? Number(m[1]) - 1 : null; };

function Metric({ label, value, sub, Icon }) {
  return <div className="r52-insight-metric">
    <div className="r52-insight-metric-icon"><Icon size={21} weight="duotone" /></div>
    <div className="min-w-0"><div className="r52-insight-metric-label">{label}</div><div className="r52-insight-metric-value">{value}</div><div className="r52-insight-metric-sub">{sub}</div></div>
  </div>;
}

export default function CommesseInsightsPage({ mode = "fatturato" }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const { data } = await axios.get(`${API}/crm/clienti-summary`);
        if (active) setRows(data.items || []);
      } catch (e) {
        toast.error("Impossibile caricare i dati", { description: e?.response?.data?.detail || e.message });
      } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, []);

  const years = useMemo(() => [...new Set(rows.map((r) => getYear(r.data_firma)).filter(Boolean))].sort((a, b) => b - a), [rows]);
  const [year, setYear] = useState(new Date().getFullYear());
  useEffect(() => { if (years.length && !years.includes(year)) setYear(years[0]); }, [years, year]);
  const filtered = useMemo(() => rows.filter((r) => getYear(r.data_firma) === Number(year)), [rows, year]);
  const monthly = useMemo(() => {
    const out = MONTHS.map((name, i) => ({ name, month: i + 1, fatturato: 0, wallbox: 0 }));
    for (const r of filtered) {
      const m = getMonth(r.data_firma);
      if (m == null || m < 0 || m > 11) continue;
      out[m].fatturato += Number(r.fatturato ?? r.capitale ?? 0);
      out[m].wallbox += Number(r.wb_totali ?? r.qty_wb ?? 0);
    }
    return out;
  }, [filtered]);
  const yearly = useMemo(() => years.slice().sort((a, b) => a - b).map((y) => {
    const yr = rows.filter((r) => getYear(r.data_firma) === y);
    return {
      year: String(y),
      fatturato: yr.reduce((s, r) => s + Number(r.fatturato ?? r.capitale ?? 0), 0),
      wallbox: yr.reduce((s, r) => s + Number(r.wb_totali ?? r.qty_wb ?? 0), 0),
    };
  }), [rows, years]);
  const annualRevenue = filtered.reduce((s, r) => s + Number(r.fatturato ?? r.capitale ?? 0), 0);
  const annualWb = filtered.reduce((s, r) => s + Number(r.wb_totali ?? r.qty_wb ?? 0), 0);
  const isRevenue = mode === "fatturato";
  const Icon = isRevenue ? ChartBar : Lightning;
  const dataKey = isRevenue ? "fatturato" : "wallbox";
  const tooltipFormatter = (v) => isRevenue ? euro(v) : `${Number(v || 0).toLocaleString("it-IT")} WB`;
  const yTick = isRevenue ? ((v) => `${Math.round(Number(v) / 1000)}k`) : undefined;
  const activeMonths = monthly.filter((m) => Number(m[dataKey] || 0) > 0).length;

  return <div className="r52-insights-workspace">
    <div className="r52-commandbar">
      <div>
        <div className="r52-commandbar-title">Analisi {isRevenue ? "economica" : "Wallbox"}</div>
        <div className="r52-commandbar-subtitle">Valore degli ordini raggruppato per cliente e ultima data firma. Include gli ordini ancora da fatturare; non rappresenta le fatture emesse.</div>
      </div>
      <div className="r52-commandbar-actions">
        <CalendarBlank size={17} className="text-slate-400" />
        <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold">
          {years.length ? years.map((y) => <option key={y} value={y}>{y}</option>) : <option value={year}>{year}</option>}
        </select>
      </div>
    </div>

    {loading ? <div className="r52-empty-state">Caricamento dati…</div> : <>
      <div className="r52-insight-metrics-grid">
        <Metric label={isRevenue ? "Totale anno" : "Wallbox anno"} value={isRevenue ? euro(annualRevenue) : annualWb.toLocaleString("it-IT")} sub={String(year)} Icon={Icon} />
        <Metric label="Mesi con attività" value={String(activeMonths)} sub="su 12 mesi" Icon={CalendarBlank} />
        <Metric label={isRevenue ? "Clienti con ordini" : "Clienti con wallbox"} value={String(filtered.filter((r) => Number(isRevenue ? (r.fatturato ?? r.capitale ?? 0) : (r.wb_totali ?? r.qty_wb ?? 0)) > 0).length)} sub="nel periodo selezionato" Icon={TrendUp} />
      </div>

      <section className="r52-panel r52-chart-panel">
        <div className="r52-panel-heading"><div><div className="r52-section-kicker">Mensile</div><h2>{isRevenue ? "Valore ordini per mese" : "Wallbox per mese"}</h2><p>Distribuzione basata sulla data firma registrata nel gestionale.</p></div><Icon size={23} className="text-[#1A456B]" /></div>
        <div className="r52-chart-body"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthly} margin={{ top: 12, right: 12, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7edf3" /><XAxis dataKey="name" /><YAxis allowDecimals={!isRevenue ? false : undefined} tickFormatter={yTick} /><Tooltip formatter={tooltipFormatter} /><Bar dataKey={dataKey} fill="#2d6ea3" radius={[7, 7, 0, 0]} /></BarChart></ResponsiveContainer></div>
      </section>

      <section className="r52-panel r52-chart-panel">
        <div className="r52-panel-heading"><div><div className="r52-section-kicker">Storico</div><h2>{isRevenue ? "Andamento valore ordini annuale" : "Andamento wallbox annuale"}</h2><p>Confronto tra gli anni presenti nel database.</p></div></div>
        <div className="r52-chart-body smaller"><ResponsiveContainer width="100%" height="100%"><LineChart data={yearly} margin={{ top: 12, right: 18, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7edf3" /><XAxis dataKey="year" /><YAxis allowDecimals={!isRevenue ? false : undefined} tickFormatter={yTick} /><Tooltip formatter={tooltipFormatter} /><Line type="monotone" dataKey={dataKey} stroke="#2d6ea3" strokeWidth={3} dot={{ r: 4, fill: "#f6c344", stroke: "#1a456b", strokeWidth: 2 }} /></LineChart></ResponsiveContainer></div>
      </section>
    </>}
  </div>;
}