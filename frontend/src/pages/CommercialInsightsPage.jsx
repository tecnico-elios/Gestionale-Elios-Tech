import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { ChartBar, Lightning, FileText, CalendarBlank } from "@phosphor-icons/react";

const MONTHS=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
const euro=v=>`€ ${Number(v||0).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const getYear=d=>{const m=String(d||"").match(/^(\d{4})/);return m?Number(m[1]):null};
const getMonth=d=>{const m=String(d||"").match(/^\d{4}-(\d{2})/);return m?Number(m[1])-1:null};

function Stat({label,value,sub,Icon}){return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex justify-between gap-3"><div><div className="text-[11px] uppercase tracking-wider font-bold text-slate-500">{label}</div><div className="mt-1 text-2xl sm:text-3xl font-black text-slate-950">{value}</div><div className="mt-2 text-xs text-slate-400">{sub}</div></div><div className="h-10 w-10 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-[#1A456B]"><Icon size={20} weight="bold"/></div></div></div>}

export default function CommercialInsightsPage({mode="fatturato"}){
  const [rows,setRows]=useState([]),[loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;(async()=>{setLoading(true);try{const {data}=await axios.get(`${API}/crm/clienti-summary`);if(active)setRows(data.items||[])}catch(e){toast.error("Impossibile caricare i dati",{description:e?.response?.data?.detail||e.message})}finally{if(active)setLoading(false)}})();return()=>{active=false}},[]);
  const years=useMemo(()=>[...new Set(rows.map(r=>getYear(r.data_firma)).filter(Boolean))].sort((a,b)=>b-a),[rows]);
  const [year,setYear]=useState(new Date().getFullYear());
  useEffect(()=>{if(years.length&&!years.includes(year))setYear(years[0])},[years,year]);
  const monthData=useMemo(()=>MONTHS.map((name,i)=>({name,fatturato:0,wallbox:0,contratti:0,report:0})),[]);
  const filtered=useMemo(()=>rows.filter(r=>getYear(r.data_firma)===Number(year)),[rows,year]);
  const chart=useMemo(()=>{const out=monthData.map(x=>({...x}));for(const r of filtered){const m=getMonth(r.data_firma);if(m==null||m<0||m>11)continue;out[m].fatturato+=Number(r.fatturato??r.capitale??0);out[m].wallbox+=Number(r.wb_totali??r.qty_wb??0);out[m].contratti+=1;out[m].report+=Number(r.reports_count||0)}return out},[filtered,monthData]);
  const annualRevenue=filtered.reduce((s,r)=>s+Number(r.fatturato??r.capitale??0),0);
  const annualWb=filtered.reduce((s,r)=>s+Number(r.wb_totali??r.qty_wb??0),0);
  const annualReports=filtered.reduce((s,r)=>s+Number(r.reports_count||0),0);
  const title=mode==="wallbox"?"Wallbox":mode==="report"?"Report":"Fatturato";
  const Icon=mode==="wallbox"?Lightning:mode==="report"?FileText:ChartBar;
  const dataKey=mode==="wallbox"?"wallbox":mode==="report"?"contratti":"fatturato";
  const tooltipFormatter=(v)=>mode==="fatturato"?euro(v):Number(v||0).toLocaleString("it-IT");
  return <div className="max-w-[1600px] mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-4">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3"><div><div className="text-xs font-semibold tracking-[.16em] uppercase text-[#1A456B]">Commesse</div><h1 className="et-page-heading text-3xl sm:text-4xl">{title}</h1><p className="text-sm text-slate-500 mt-1">Riepilogo ricostruito dai dati ordini migrati da Notion e poi gestiti localmente.</p></div><div className="flex items-center gap-2"><CalendarBlank size={18} className="text-slate-400"/><select value={year} onChange={e=>setYear(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold">{years.length?years.map(y=><option key={y} value={y}>{y}</option>):<option value={year}>{year}</option>}</select></div></div>
    {loading?<div className="py-12 text-center text-slate-500">Caricamento…</div>:<>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <Stat label="Fatturato annuale" value={euro(annualRevenue)} sub={`${year}`} Icon={ChartBar}/>
        <Stat label="Wallbox annuali" value={annualWb.toLocaleString("it-IT")} sub="Somma QTY WB" Icon={Lightning}/>
        <Stat label="Contratti" value={filtered.length.toLocaleString("it-IT")} sub="N. contratti / ordini" Icon={FileText}/>
        <Stat label="Report" value={annualReports.toLocaleString("it-IT")} sub="Report archiviati" Icon={FileText}/>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3 mb-4"><div><div className="font-black text-slate-900">{mode==="report"?"N. Contratti mensili":`${title} mensile`}</div><div className="text-xs text-slate-500 mt-1">Stessa logica dei grafici Notion: raggruppamento per mese della Data firma.</div></div><Icon size={24} className="text-[#1A456B]"/></div>
        <div className="h-[360px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{top:12,right:12,left:8,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis tickFormatter={mode==="fatturato"?v=>`${Math.round(Number(v)/1000)}k`:undefined}/><Tooltip formatter={tooltipFormatter}/><Bar dataKey={dataKey} radius={[7,7,0,0]} /></BarChart></ResponsiveContainer></div>
      </div>
      {mode==="report"&&<>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm"><div className="font-black text-slate-900 mb-4">Contratti per modalità di pagamento</div><div className="h-[320px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={Object.entries(filtered.reduce((a,r)=>{const k=r.pagamento||"Non indicato";a[k]=(a[k]||0)+1;return a},{})).map(([name,value])=>({name,value}))} margin={{top:12,right:12,left:8,bottom:40}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={75}/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" radius={[7,7,0,0]}/></BarChart></ResponsiveContainer></div></div>
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm"><div className="px-4 py-3 border-b font-bold">Clienti con report importati</div><div className="overflow-x-auto max-h-[520px]"><table className="w-full text-sm"><thead className="bg-slate-50 sticky top-0"><tr><th className="text-left p-3">Cliente / Struttura</th><th className="text-left p-3">Data firma</th><th className="text-left p-3">Stato</th><th className="text-center p-3">Report</th></tr></thead><tbody>{filtered.filter(r=>Number(r.reports_count||0)>0).map(r=><tr key={r.id} className="border-t border-slate-100"><td className="p-3 font-semibold">{r.nome_struttura||r.ragione_sociale||r.nome||"Cliente"}</td><td className="p-3">{r.data_firma||"—"}</td><td className="p-3">{r.ultimo_stato||"—"}</td><td className="p-3 text-center font-bold">{r.reports_count||0}</td></tr>)}</tbody></table></div></div>
      </>}
    </>}
  </div>
}
