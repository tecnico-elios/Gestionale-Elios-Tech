import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { FilePdf, Plus, PencilSimple, Trash } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import StandaloneInstallationReportDialog from "../components/StandaloneInstallationReportDialog";
import { appConfirm } from "../lib/appConfirm";

export default function FreeReportsPage(){
  const [items,setItems]=useState([]); const [loading,setLoading]=useState(true); const [search,setSearch]=useState(""); const [open,setOpen]=useState(false); const [selected,setSelected]=useState(null);
  const load=async()=>{setLoading(true);try{const {data}=await axios.get(`${API}/free-reports`);setItems(data.items||[])}catch(e){toast.error(e?.response?.data?.detail||"Impossibile caricare i report")}finally{setLoading(false)}};
  useEffect(()=>{load()},[]);
  const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return items;return items.filter(r=>[r.title,r.data?.cliente,r.data?.tecnico,r.data?.data,r.data?.indirizzo,...(r.data?.seriali||[])].some(v=>String(v||"").toLowerCase().includes(q)))},[items,search]);
  const create=()=>{setSelected(null);setOpen(true)}; const edit=(r)=>{setSelected(r);setOpen(true)};
  const remove=async(r)=>{if(!(await appConfirm({title:"Elimina report installazione",message:`Eliminare definitivamente il report “${r.title||"Report pre e post installazione"}”?`,confirmLabel:"Elimina",danger:true})))return;try{await axios.delete(`${API}/free-reports/${r.id}`);toast.success("Report eliminato");await load()}catch(e){toast.error(e?.response?.data?.detail||"Impossibile eliminare il report")}};
  const openPdf=async(r)=>{try{const {data}=await axios.get(`${API}/free-reports/${r.id}/pdf`,{responseType:"blob"});const u=URL.createObjectURL(data);window.open(u,"_blank","noopener,noreferrer");setTimeout(()=>URL.revokeObjectURL(u),60000)}catch(e){toast.error(e?.response?.data?.detail||"PDF non ancora disponibile")}};
  return <div className="space-y-5" data-testid="free-reports-page">
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3"><div><h2 className="text-xl font-black text-slate-900">Report pre e post installazione</h2><p className="text-sm text-slate-500 mt-1">Lo stesso report disponibile nelle Installazioni, ma compilabile liberamente senza collegamento obbligatorio a cliente o installazione.</p></div><button onClick={create} className="inline-flex items-center justify-center gap-2 h-11 px-4 rounded-xl bg-slate-900 text-white font-semibold hover:bg-slate-800"><Plus size={18}/> Nuovo report</button></div>
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden"><div className="p-4 border-b border-slate-200"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cerca per cliente, tecnico, data, indirizzo o seriale..." className="h-10 w-full md:max-w-md px-3 rounded-lg border border-slate-300 bg-white text-sm"/></div><div className="divide-y divide-slate-100">{loading&&<div className="p-6 text-sm text-slate-500">Caricamento...</div>}{!loading&&filtered.length===0&&<div className="p-6 text-sm text-slate-500">Nessun report presente.</div>}{filtered.map(r=><div key={r.id} className="p-5 hover:bg-slate-50/70"><div className="flex items-start justify-between gap-4"><div className="min-w-0"><div className="font-semibold text-slate-900">{r.title||"Report pre e post installazione"}</div><div className="text-sm text-slate-500 mt-1">{r.data?.tecnico||"Tecnico non indicato"}{r.data?.indirizzo?` · ${r.data.indirizzo}`:""}</div>{r.data?.seriali?.length>0&&<div className="text-xs text-slate-500 mt-2">Seriali: {r.data.seriali.join(", ")}</div>}</div><div className="flex gap-1 shrink-0"><button onClick={()=>edit(r)} className="p-2 rounded-lg hover:bg-slate-200" title="Modifica"><PencilSimple size={18}/></button>{r.generated_document_id&&<button onClick={()=>openPdf(r)} className="p-2 rounded-lg hover:bg-slate-200" title="Apri PDF"><FilePdf size={18}/></button>}<button onClick={()=>remove(r)} className="p-2 rounded-lg hover:bg-red-50 text-red-600" title="Elimina"><Trash size={18}/></button></div></div></div>)}</div></div>
    <StandaloneInstallationReportDialog open={open} onOpenChange={setOpen} report={selected} onSaved={load}/>
  </div>
}
