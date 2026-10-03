import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { ChartBar, Lightning, CalendarBlank } from "@phosphor-icons/react";

const MONTHS=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
const euro=v=>`€ ${Number(v||0).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const getYear=d=>{const m=String(d||"").match(/^(\d{4})/);return m?Number(m[1]):null};
const getMonth=d=>{const m=String(d||"").match(/^\d{4}-(\d{2})/);return m?Number(m[1])-1:null};

function Stat({label,value,sub,Icon}){return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex justify-between gap-3"><div><div className="text-[11px] uppercase tracking-wider font-bold text-slate-500">{label}</div><div className="mt-1 text-3xl font-black text-slate-950">{value}</div><div className="mt-2 text-xs text-slate-400">{sub}</div></div><div className="h-11 w-11 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-[#1A456B]"><Icon size={22} weight="bold"/></div></div></div>}

export default function CommercialInsightsPage({mode="fatturato"}){
  const [rows,setRows]=useState([]),[loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;(async()=>{setLoading(true);try{const {data}=await axios.get(`${API}/crm/clienti-summary`);if(active)setRows(data.items||[])}catch(e){toast.error("Impossibile caricare i dati",{description:e?.response?.data?.detail||e.message})}finally{if(active)setLoading(false)}})();return()=>{active=false}},[]);
  const years=useMemo(()=>[...new Set(rows.map(r=>getYear(r.data_firma)).filter(Boolean))].sort((a,b)=>b-a),[rows]);
  const [year,setYear]=useState(new Date().getFullYear());
  useEffect(()=>{if(years.length&&!years.includes(year))setYear(years[0])},[years,year]);
  const filtered=useMemo(()=>rows.filter(r=>getYear(r.data_firma)===Number(year)),[rows,year]);
  const monthly=useMemo(()=>{
    const out=MONTHS.map((name,i)=>({name,month:i+1,fatturato:0,wallbox:0}));
    for(const r of filtered){const m=getMonth(r.data_firma);if(m==null||m<0||m>11)continue;out[m].fatturato+=Number(r.fatturato??r.capitale??0);out[m].wallbox+=Number(r.wb_totali??r.qty_wb??0)}
    return out;
  },[filtered]);
  const yearly=useMemo(()=>years.slice().sort((a,b)=>a-b).map(y=>{const yr=rows.filter(r=>getYear(r.data_firma)===y);return {year:String(y),fatturato:yr.reduce((s,r)=>s+Number(r.fatturato??r.capitale??0),0),wallbox:yr.reduce((s,r)=>s+Number(r.wb_totali??r.qty_wb??0),0)}}),[rows,years]);
  const annualRevenue=filtered.reduce((s,r)=>s+Number(r.fatturato??r.capitale??0),0);
  const annualWb=filtered.reduce((s,r)=>s+Number(r.wb_totali??r.qty_wb??0),0);
  const isRevenue=mode==="fatturato";
  const title=isRevenue?"Fatturato":"Wallbox";
  const Icon=isRevenue?ChartBar:Lightning;
  const dataKey=isRevenue?"fatturato":"wallbox";
  const tooltipFormatter=v=>isRevenue?euro(v):`${Number(v||0).toLocaleString("it-IT")} WB`;
  const yTick=isRevenue?(v=>`${Math.round(Number(v)/1000)}k`):undefined;
  return <div className="max-w-[1600px] mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-4">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3"><div><div className="text-xs font-semibold tracking-[.16em] uppercase text-[#1A456B]">Amministrazione</div><h1 className="et-page-heading text-3xl sm:text-4xl">{title}</h1><p className="text-sm text-slate-500 mt-1">{isRevenue?"Analisi del fatturato per mese e per anno.":"Numero di wallbox ordinate per mese e per anno."}</p></div><div className="flex items-center gap-2"><CalendarBlank size={18} className="text-slate-400"/><select value={year} onChange={e=>setYear(Number(e.target.value))} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold">{years.length?years.map(y=><option key={y} value={y}>{y}</option>):<option value={year}>{year}</option>}</select></div></div>
    {loading?<div className="py-12 text-center text-slate-500">Caricamento…</div>:<>
      <div className="max-w-xl"><Stat label={isRevenue?"Fatturato annuale":"Wallbox annuali"} value={isRevenue?euro(annualRevenue):annualWb.toLocaleString("it-IT")} sub={isRevenue?String(year):`Totale QTY WB · ${year}`} Icon={Icon}/></div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3 mb-4"><div><div className="font-black text-slate-900">{isRevenue?"Fatturato mensile":"Wallbox mensili"}</div><div className="text-xs text-slate-500 mt-1">Raggruppamento per mese della Data firma, come nella vista Notion.</div></div><Icon size={24} className="text-[#1A456B]"/></div>
        <div className="h-[360px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthly} margin={{top:12,right:12,left:8,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name"/><YAxis allowDecimals={!isRevenue?false:undefined} tickFormatter={yTick}/><Tooltip formatter={tooltipFormatter}/><Bar dataKey={dataKey} radius={[7,7,0,0]} /></BarChart></ResponsiveContainer></div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
        <div className="font-black text-slate-900 mb-4">{isRevenue?"Andamento fatturato annuale":"Andamento wallbox annuale"}</div>
        <div className="h-[300px]"><ResponsiveContainer width="100%" height="100%"><LineChart data={yearly} margin={{top:12,right:18,left:8,bottom:8}}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="year"/><YAxis allowDecimals={!isRevenue?false:undefined} tickFormatter={yTick}/><Tooltip formatter={tooltipFormatter}/><Line type="monotone" dataKey={dataKey} strokeWidth={3} dot={{r:4}}/></LineChart></ResponsiveContainer></div>
      </div>
    </>}
  </div>
}
