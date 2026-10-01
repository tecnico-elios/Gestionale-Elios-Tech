import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Plus, PencilSimple, Trash, MagnifyingGlass } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { appConfirm } from "../lib/appConfirm";

const emptyFor = (fields=[]) => Object.fromEntries(fields.map(f=>[f.key, f.type === "checkbox" ? false : ""]));
const show = (v, f) => {
  if (f?.type === "checkbox") return v ? "Sì" : "No";
  if (f?.type === "currency" && v !== "" && v != null) return `€ ${Number(v).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  return v == null || v === "" ? "—" : String(v);
};

export default function CustomModulePage(){
  const { slug } = useParams();
  const [module,setModule]=useState(null), [items,setItems]=useState([]), [loading,setLoading]=useState(true);
  const [search,setSearch]=useState(""), [open,setOpen]=useState(false), [editing,setEditing]=useState(null), [form,setForm]=useState({});
  const load=async()=>{setLoading(true);try{const {data}=await axios.get(`${API}/custom/${slug}`);setModule(data.module);setItems(data.items||[]);}catch(e){toast.error("Modulo non disponibile");}finally{setLoading(false)}};
  useEffect(()=>{load()},[slug]); // eslint-disable-line react-hooks/exhaustive-deps
  const fields=module?.fields||[];
  const columns=fields.filter(f=>f.showInList!==false).slice(0,7);
  const shown=useMemo(()=>{const q=search.trim().toLowerCase(); return !q?items:items.filter(x=>Object.values(x.data||{}).join(" ").toLowerCase().includes(q));},[items,search]);
  const startNew=()=>{setEditing(null);setForm(emptyFor(fields));setOpen(true)};
  const startEdit=(x)=>{setEditing(x.id);setForm({...emptyFor(fields),...(x.data||{})});setOpen(true)};
  const save=async(e)=>{e.preventDefault();try{editing?await axios.put(`${API}/custom/${slug}/${editing}`,form):await axios.post(`${API}/custom/${slug}`,form);toast.success(editing?"Modifica salvata":"Record creato");setOpen(false);load();}catch(e){toast.error("Salvataggio non riuscito")}};
  const remove=async(x)=>{if(!(await appConfirm({title:"Elimina record",message:"Confermi l’eliminazione?",confirmLabel:"Elimina",danger:true})))return;await axios.delete(`${API}/custom/${slug}/${x.id}`);load()};
  if(loading) return <div className="p-8 text-center text-slate-500">Caricamento…</div>;
  if(!module) return <div className="p-8">Modulo non trovato.</div>;
  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5">
    <div className="flex items-end justify-between gap-3 mb-5"><div><div className="text-xs font-semibold tracking-[.16em] uppercase text-blue-600">Modulo personalizzato</div><h1 className="font-display text-3xl font-bold mt-1">{module.name}</h1>{module.description&&<p className="text-slate-500 mt-1">{module.description}</p>}</div><Button onClick={startNew}><Plus/> Nuovo</Button></div>
    <div className="bg-white border rounded-md"><div className="p-3 border-b flex gap-2 items-center"><MagnifyingGlass className="text-slate-400"/><Input className="max-w-md h-12" value={search} onChange={e=>setSearch(e.target.value)} placeholder={`Cerca in ${module.name.toLowerCase()}...`}/><span className="ml-auto text-sm text-slate-500">{shown.length} record</span></div>
    <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50"><tr>{columns.map(f=><th key={f.key} className="text-left px-4 py-3">{f.label}</th>)}<th className="px-4 py-3 text-right">Azioni</th></tr></thead><tbody>{shown.map(x=><tr key={x.id} className="border-t hover:bg-slate-50">{columns.map(f=><td key={f.key} className="px-4 py-3">{show(x.data?.[f.key],f)}</td>)}<td className="px-4 py-2"><div className="flex justify-end"><Button variant="ghost" size="icon" onClick={()=>startEdit(x)}><PencilSimple/></Button><Button variant="ghost" size="icon" className="text-red-600" onClick={()=>remove(x)}><Trash/></Button></div></td></tr>)}{!shown.length&&<tr><td colSpan={columns.length+1} className="p-10 text-center text-slate-500">Nessun record.</td></tr>}</tbody></table></div></div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>{editing?`Modifica ${module.name}`:`Nuovo ${module.name}`}</DialogTitle></DialogHeader><form onSubmit={save}><div className="grid sm:grid-cols-2 gap-4 py-3">{fields.map(f=><div key={f.key} className={f.full?"sm:col-span-2":""}><Label>{f.label}{f.required?" *":""}</Label>{f.type==="textarea"?<Textarea className="mt-1" rows={4} value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>:f.type==="checkbox"?<label className="mt-1 h-12 border rounded-md px-3 flex items-center gap-3"><input type="checkbox" checked={!!form[f.key]} onChange={e=>setForm(p=>({...p,[f.key]:e.target.checked}))}/><span>{form[f.key]?"Sì":"No"}</span></label>:f.type==="select"?<select className="mt-1 h-12 w-full border rounded-md px-3" value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}><option value="">Seleziona…</option>{(f.options||[]).map(o=><option key={o}>{o}</option>)}</select>:<Input className="mt-1 h-12" type={f.type==="currency"?"number":(f.type||"text")} step={f.type==="currency"?"0.01":undefined} value={form[f.key]??""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>}</div>)}</div><DialogFooter><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Annulla</Button><Button type="submit">Salva</Button></DialogFooter></form></DialogContent></Dialog>
  </div>
}
