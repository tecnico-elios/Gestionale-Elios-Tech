import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Plus, PencilSimple, Trash, FileText, Clock, CalendarBlank, SlidersHorizontal, ChartBar } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { useAuth } from "../lib/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { appConfirm } from "../lib/appConfirm";

const STANDARD_FIELDS=[
  {key:"data",label:"Data",type:"date",showInList:true,searchable:true,required:true},
  {key:"account_owner",label:"Persona",type:"text",showInList:true,searchable:true},
  {key:"mansione",label:"Mansione",type:"select",showInList:true,searchable:true,options:["Social","Posizionamento mappe","Organizzazione installazioni","Chiamata cliente","Configurazione","Assistenza","Lavoro con Rossi/Bussatori","Aggiornamento gestionale","Installazione","Sopralluogo","Altro"]},
  {key:"ore",label:"Ore lavorate",type:"number",showInList:true,searchable:true},
  {key:"note",label:"Cosa è stato fatto / Note",type:"textarea",showInList:true,searchable:true,full:true},
];
const emptyFor=fields=>Object.fromEntries((fields||[]).map(f=>[f.key,f.type==="checkbox"?false:""]));
const labelValue=(v,f)=>{if(v==null||v==="")return "—";if(f?.type==="number")return String(v);if(Array.isArray(v))return v.map(x=>typeof x==="object"?(x?.name||x?.label||x?.email||x?.id||JSON.stringify(x)):String(x)).join(", ");if(typeof v==="object")return v?.name||v?.label||v?.email||v?.id||JSON.stringify(v);return String(v)};

export default function ReportsPage(){
  const {isAdmin}=useAuth(); const navigate=useNavigate();
  const [modules,setModules]=useState([]),[activeSlug,setActiveSlug]=useState(""),[module,setModule]=useState(null),[items,setItems]=useState([]),[loading,setLoading]=useState(true);
  const [search,setSearch]=useState(""),[page,setPage]=useState(1),[open,setOpen]=useState(false),[editing,setEditing]=useState(null),[form,setForm]=useState({}),[typeOpen,setTypeOpen]=useState(false),[typeName,setTypeName]=useState("");
  const loadModules=async()=>{const {data}=await axios.get(`${API}/custom/modules`);const rows=(data.items||[]).filter(m=>String(m.slug||"").startsWith("report-")||String(m.name||"").toLowerCase().includes("report"));setModules(rows);if(!activeSlug&&rows.length)setActiveSlug((rows.find(x=>x.slug==="report-attivita")||rows[0]).slug);return rows};
  const loadActive=async(slug)=>{if(!slug){setModule(null);setItems([]);return;}const {data}=await axios.get(`${API}/custom/${slug}`);setModule(data.module);setItems(data.items||[])};
  const load=async()=>{setLoading(true);try{const rows=await loadModules();const slug=activeSlug||(rows.find(x=>x.slug==="report-attivita")||rows[0])?.slug||"";if(slug){if(!activeSlug)setActiveSlug(slug);await loadActive(slug)}}catch(e){toast.error("Report non disponibili",{description:e?.response?.data?.detail||e.message})}finally{setLoading(false)}};
  useEffect(()=>{load()},[]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{if(activeSlug)loadActive(activeSlug).catch(e=>toast.error("Impossibile aprire il report",{description:e?.response?.data?.detail||e.message}));setPage(1);setSearch("")},[activeSlug]); // eslint-disable-line react-hooks/exhaustive-deps
  const fields=module?.fields?.length?module.fields:STANDARD_FIELDS;
  const filtered=useMemo(()=>{const q=search.trim().toLowerCase();if(!q)return items;return items.filter(x=>JSON.stringify(x.data||{}).toLowerCase().includes(q))},[items,search]);
  const perPage=25,totalPages=Math.max(1,Math.ceil(filtered.length/perPage)),paged=filtered.slice((page-1)*perPage,page*perPage);
  useEffect(()=>{if(page>totalPages)setPage(totalPages)},[page,totalPages]);
  const hoursTotal=useMemo(()=>filtered.reduce((s,x)=>s+Number(x.data?.ore??x.data?.h??0),0),[filtered]);
  // R56 — grafico generico: individua automaticamente il campo ore e la voce descrittiva.
  const hourField=useMemo(()=>fields.find(f=>["ore","h","hours","ore_lavorate"].includes(String(f.key||"").toLowerCase()))||fields.find(f=>/(^|_|\s)(ore|hours)(_|\s|$)/i.test(`${f.key||""} ${f.label||""}`)),[fields]);
  const groupField=useMemo(()=>{
    const preferred=["mansione","attivita","attività","nome","categoria","categorie","tags","tipo"];
    return fields.find(f=>f.key!==hourField?.key&&preferred.includes(String(f.key||"").toLowerCase()))||fields.find(f=>f.key!==hourField?.key&&f.showInList!==false&&["select","text"].includes(f.type));
  },[fields,hourField]);
  const chartData=useMemo(()=>{
    if(!hourField)return [];
    const totals=new Map();
    filtered.forEach(row=>{
      const rawHours=Number(row.data?.[hourField.key]??0);
      if(!Number.isFinite(rawHours)||rawHours<=0)return;
      const rawLabel=groupField?row.data?.[groupField.key]:"Totale";
      const label=Array.isArray(rawLabel)?rawLabel.map(x=>typeof x==="object"?(x?.name||x?.label||x?.id||""):String(x)).filter(Boolean).join(", "):(typeof rawLabel==="object"?(rawLabel?.name||rawLabel?.label||rawLabel?.id||"Altro"):String(rawLabel||"Altro"));
      totals.set(label,(totals.get(label)||0)+rawHours);
    });
    return Array.from(totals,([voce,ore])=>({voce,ore:Number(ore.toFixed(2))})).sort((a,b)=>b.ore-a.ore);
  },[filtered,hourField,groupField]);
  const startNew=()=>{setEditing(null);setForm(emptyFor(fields));setOpen(true)};
  const startEdit=x=>{setEditing(x.id);setForm({...emptyFor(fields),...(x.data||{})});setOpen(true)};
  const save=async e=>{e.preventDefault();try{editing?await axios.put(`${API}/custom/${activeSlug}/${editing}`,form):await axios.post(`${API}/custom/${activeSlug}`,form);toast.success(editing?"Report aggiornato":"Report creato");setOpen(false);await loadActive(activeSlug)}catch(err){toast.error("Salvataggio non riuscito",{description:err?.response?.data?.detail||err.message})}};
  const remove=async x=>{if(!(await appConfirm({title:"Elimina report",message:"Confermi l’eliminazione definitiva di questo report?",confirmLabel:"Elimina",danger:true})))return;await axios.delete(`${API}/custom/${activeSlug}/${x.id}`);await loadActive(activeSlug)};
  const createType=async()=>{const name=typeName.trim();if(!name)return;try{const {data}=await axios.post(`${API}/custom/modules`,{name,section:"amministrazione",fields:STANDARD_FIELDS,active:true,sort_order:110,allow_create:true,allow_edit:true,allow_delete:true});toast.success("Tipo report creato");setTypeOpen(false);setTypeName("");await loadModules();setActiveSlug(data.slug)}catch(e){toast.error("Creazione tipo report non riuscita",{description:e?.response?.data?.detail||e.message})}};
  const cols=fields.filter(f=>f.showInList!==false).slice(0,6);
  return <div className="max-w-[1600px] mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-4">
    <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-3"><div><div className="text-xs font-semibold tracking-[.16em] uppercase text-[#1A456B]">Amministrazione</div><h1 className="et-page-heading text-3xl sm:text-4xl">Report</h1><p className="text-sm text-slate-500 mt-1">Report giornalieri come in Notion: data, persona, mansione, ore lavorate e attività svolte. Puoi creare anche altri tipi di report.</p></div><div className="flex flex-wrap gap-2">{isAdmin&&<Button variant="outline" onClick={()=>navigate("/admin/moduli")}><SlidersHorizontal/> Personalizza report</Button>}{isAdmin&&<Button variant="outline" onClick={()=>setTypeOpen(true)}><Plus/> Nuovo tipo report</Button>}{module?.allow_create!==false&&<Button onClick={startNew}><Plus/> Nuovo report</Button>}</div></div>

    <div className="grid sm:grid-cols-3 gap-3"><div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="text-xs uppercase font-bold text-slate-500">Tipo report</div><div className="mt-2"><select className="h-11 w-full rounded-md border px-3 font-semibold" value={activeSlug} onChange={e=>setActiveSlug(e.target.value)}>{modules.map(m=><option key={m.slug} value={m.slug}>{m.name}</option>)}</select></div></div><div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase font-bold text-slate-500"><FileText/> Report visibili</div><div className="mt-1 text-3xl font-black">{filtered.length}</div></div><div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase font-bold text-slate-500"><Clock/> Ore totali</div><div className="mt-1 text-3xl font-black">{hoursTotal.toLocaleString("it-IT",{maximumFractionDigits:2})}</div></div></div>

    {hourField && chartData.length>0 && <section className="r56-report-chart" data-r56-hours-chart>
      <div className="r56-report-chart-head"><div><div className="r56-report-chart-kicker"><ChartBar size={15}/> Ore per voce</div><h2>Distribuzione ore</h2><p>{groupField ? `Somma delle ore per ${groupField.label || "voce"}.` : "Somma delle ore registrate."}</p></div><div className="r56-report-chart-total"><strong>{hoursTotal.toLocaleString("it-IT",{maximumFractionDigits:2})}</strong><span>ore totali</span></div></div>
      <div style={{height:Math.max(260,chartData.length*38)}}>
        <ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} layout="vertical" margin={{top:8,right:24,bottom:8,left:8}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:11}}/><YAxis type="category" dataKey="voce" width={150} tick={{fontSize:11}}/><Tooltip formatter={(v)=>[`${Number(v).toLocaleString("it-IT",{maximumFractionDigits:2})} h`,"Ore"]}/><Bar dataKey="ore" fill="#2d6ea3" radius={[0,6,6,0]}/></BarChart></ResponsiveContainer>
      </div>
    </section>}

    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm"><div className="p-3 border-b flex flex-col sm:flex-row gap-2 sm:items-center"><Input value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}} placeholder="Cerca persona, mansione, attività, note…" className="h-11 sm:max-w-xl"/><div className="sm:ml-auto text-sm text-slate-500">Pagina {page} di {totalPages}</div></div>{loading?<div className="p-12 text-center text-slate-500">Caricamento…</div>:!module?<div className="p-12 text-center"><FileText size={36} className="mx-auto text-slate-300"/><div className="font-bold mt-3">Nessun tipo di report disponibile</div>{isAdmin&&<Button className="mt-3" onClick={()=>setTypeOpen(true)}>Crea il primo report</Button>}</div>:<div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50"><tr>{cols.map(f=><th key={f.key} className="text-left p-3 whitespace-nowrap">{f.label}</th>)}<th className="p-3 text-right">Azioni</th></tr></thead><tbody>{paged.map(x=><tr key={x.id} className="border-t hover:bg-slate-50">{cols.map(f=><td key={f.key} className="p-3 align-top">{labelValue(x.data?.[f.key],f)}</td>)}<td className="p-2"><div className="flex justify-end">{module.allow_edit!==false&&<Button variant="ghost" size="icon" onClick={()=>startEdit(x)}><PencilSimple/></Button>}{module.allow_delete!==false&&<Button variant="ghost" size="icon" className="text-red-600" onClick={()=>remove(x)}><Trash/></Button>}</div></td></tr>)}{!paged.length&&<tr><td colSpan={cols.length+1} className="p-10 text-center text-slate-500">Nessun report.</td></tr>}</tbody></table></div>}<div className="border-t p-3 flex justify-between items-center"><Button variant="outline" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Precedente</Button><span className="text-sm text-slate-500">{filtered.length} record</span><Button variant="outline" disabled={page>=totalPages} onClick={()=>setPage(p=>p+1)}>Successiva</Button></div></div>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto"><DialogHeader><DialogTitle>{editing?"Modifica report":"Nuovo report"}</DialogTitle></DialogHeader><form onSubmit={save}><div className="grid sm:grid-cols-2 gap-4 py-3">{fields.map(f=><div key={f.key} className={f.full||f.type==="textarea"?"sm:col-span-2":""}><Label>{f.label}{f.required?" *":""}</Label>{f.type==="textarea"?<Textarea rows={5} className="mt-1" value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>:f.type==="select"?<select className="mt-1 h-11 w-full rounded-md border px-3" value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))}><option value="">Seleziona…</option>{(f.options||[]).map(o=><option key={o}>{o}</option>)}</select>:<Input className="mt-1 h-11" type={f.type==="date"?"date":f.type==="number"?"number":"text"} step={f.type==="number"?"0.25":undefined} value={form[f.key]??""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>}</div>)}</div><DialogFooter><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Annulla</Button><Button type="submit">Salva report</Button></DialogFooter></form></DialogContent></Dialog>

    <Dialog open={typeOpen} onOpenChange={setTypeOpen}><DialogContent className="max-w-lg"><DialogHeader><DialogTitle>Nuovo tipo report</DialogTitle></DialogHeader><div><Label>Nome</Label><Input className="mt-1" value={typeName} onChange={e=>setTypeName(e.target.value)} placeholder="Es. Report manutenzioni"/></div><p className="text-sm text-slate-500">Verranno creati i campi base Data, Persona, Mansione, Ore lavorate e Note. Dal Costruttore moduli potrai poi aggiungere o togliere qualsiasi campo.</p><DialogFooter><Button variant="outline" onClick={()=>setTypeOpen(false)}>Annulla</Button><Button onClick={createType}>Crea</Button></DialogFooter></DialogContent></Dialog>
  </div>
}
