import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Plus, PencilSimple, Trash, MagnifyingGlass, FileText, UploadSimple } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { appConfirm } from "../lib/appConfirm";

const emptyFor = (fields=[]) => Object.fromEntries(fields.map(f=>[f.key, f.type === "checkbox" ? false : f.type === "file" ? [] : ""]));
const show = (v, f) => {
  if (f?.type === "checkbox") return v ? "Sì" : "No";
  if (f?.type === "currency" && v !== "" && v != null) return `€ ${Number(v).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  if (f?.type === "file") return Array.isArray(v) && v.length ? `${v.length} file` : "—";
  if (Array.isArray(v)) return v.map(x=>typeof x==="object"?(x.name||x.label||x.id||JSON.stringify(x)):String(x)).join(", ") || "—";
  if (typeof v === "object" && v) return v.name || v.label || JSON.stringify(v);
  return v == null || v === "" ? "—" : String(v);
};

export default function CustomModulePage(){
  const { slug } = useParams();
  const [module,setModule]=useState(null), [items,setItems]=useState([]), [loading,setLoading]=useState(true);
  const [search,setSearch]=useState(""), [open,setOpen]=useState(false), [editing,setEditing]=useState(null), [form,setForm]=useState({});
  const load=async()=>{setLoading(true);try{const {data}=await axios.get(`${API}/custom/${slug}`);setModule(data.module);setItems(data.items||[]);}catch(e){toast.error("Modulo non disponibile");}finally{setLoading(false)}};
  useEffect(()=>{load()},[slug]); // eslint-disable-line react-hooks/exhaustive-deps
  const fields=module?.fields||[];
  const columns=fields.filter(f=>f.showInList!==false).slice(0,9);
  const searchable=useMemo(()=>new Set(fields.filter(f=>f.searchable!==false).map(f=>f.key)),[fields]);
  const shown=useMemo(()=>{const q=search.trim().toLowerCase(); return !q?items:items.filter(x=>Object.entries(x.data||{}).filter(([k])=>searchable.has(k)).map(([,v])=>JSON.stringify(v)).join(" ").toLowerCase().includes(q));},[items,search,searchable]);
  const startNew=()=>{setEditing(null);setForm(emptyFor(fields));setOpen(true)};
  const startEdit=(x)=>{setEditing(x.id);setForm({...emptyFor(fields),...(x.data||{})});setOpen(true)};
  const save=async(e)=>{e.preventDefault();try{editing?await axios.put(`${API}/custom/${slug}/${editing}`,form):await axios.post(`${API}/custom/${slug}`,form);toast.success(editing?"Modifica salvata":"Record creato");setOpen(false);await load();}catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e?.message})}};
  const remove=async(x)=>{if(!(await appConfirm({title:"Elimina record",message:"Confermi l’eliminazione definitiva del record?",confirmLabel:"Elimina",danger:true})))return;await axios.delete(`${API}/custom/${slug}/${x.id}`);await load()};
  const openAttachment=async(a)=>{try{const r=await axios.get(`${API}/custom/attachment/${a.id}`,{responseType:"blob"});const url=URL.createObjectURL(r.data);window.open(url,"_blank","noopener,noreferrer");setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){toast.error("File non disponibile")}};
  const uploadAttachment=async(field,file)=>{if(!editing||!file)return;const fd=new FormData();fd.append("file",file);try{await axios.post(`${API}/custom/${slug}/${editing}/file/${field.key}`,fd,{headers:{"Content-Type":"multipart/form-data"}});toast.success("File caricato");const {data}=await axios.get(`${API}/custom/${slug}`);setItems(data.items||[]);const rec=(data.items||[]).find(x=>x.id===editing);if(rec)setForm({...emptyFor(fields),...(rec.data||{})});}catch(e){toast.error("Caricamento non riuscito",{description:e?.response?.data?.detail||e?.message})}};
  const deleteAttachment=async(field,a)=>{if(!(await appConfirm({title:"Elimina file",message:`Eliminare ${a.name||"questo file"}?`,confirmLabel:"Elimina",danger:true})))return;try{await axios.delete(`${API}/custom/attachment/${a.id}`);setForm(p=>({...p,[field.key]:(p[field.key]||[]).filter(x=>x.id!==a.id)}));toast.success("File eliminato");await load()}catch(e){toast.error("Eliminazione file non riuscita")}};
  if(loading) return <div className="p-8 text-center text-slate-500">Caricamento…</div>;
  if(!module) return <div className="p-8">Modulo non trovato.</div>;
  return <div className="max-w-[1500px] mx-auto px-3 sm:px-6 py-5">
    <div className="flex items-end justify-between gap-3 mb-5"><div><div className="text-xs font-semibold tracking-[.16em] uppercase text-blue-600">Modulo gestionale</div><h1 className="font-display text-3xl font-bold mt-1">{module.name}</h1>{module.description&&<p className="text-slate-500 mt-1">{module.description}</p>}</div>{module.allow_create!==false&&<Button onClick={startNew}><Plus/> Nuovo</Button>}</div>
    <div className="bg-white border rounded-xl overflow-hidden"><div className="p-3 border-b flex gap-2 items-center"><MagnifyingGlass className="text-slate-400"/><Input className="max-w-xl h-12" value={search} onChange={e=>setSearch(e.target.value)} placeholder={`Cerca in ${module.name.toLowerCase()}...`}/>{module.show_counter!==false&&<span className="ml-auto text-sm text-slate-500">{shown.length} record</span>}</div>
    <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50"><tr>{columns.map(f=><th key={f.key} className="text-left px-4 py-3 whitespace-nowrap">{f.label}</th>)}<th className="px-4 py-3 text-right">Azioni</th></tr></thead><tbody>{shown.map(x=><tr key={x.id} className="border-t hover:bg-slate-50">{columns.map(f=><td key={f.key} className={`px-4 ${module.list_density==="compact"?"py-2":module.list_density==="spacious"?"py-5":"py-3"}`}>{f.type==="file"&&Array.isArray(x.data?.[f.key])&&x.data[f.key].length?<div className="flex flex-wrap gap-1">{x.data[f.key].slice(0,2).map(a=><button type="button" key={a.id||a.name} onClick={()=>openAttachment(a)} className="inline-flex items-center gap-1 text-xs text-blue-700 hover:underline"><FileText size={14}/>{a.name||"File"}</button>)}</div>:show(x.data?.[f.key],f)}</td>)}<td className="px-4 py-2"><div className="flex justify-end">{module.allow_edit!==false&&<Button variant="ghost" size="icon" onClick={()=>startEdit(x)}><PencilSimple/></Button>}{module.allow_delete!==false&&<Button variant="ghost" size="icon" className="text-red-600" onClick={()=>remove(x)}><Trash/></Button>}</div></td></tr>)}{!shown.length&&<tr><td colSpan={columns.length+1} className="p-10 text-center text-slate-500">Nessun record.</td></tr>}</tbody></table></div></div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto"><DialogHeader><DialogTitle>{editing?`Modifica ${module.name}`:`Nuovo ${module.name}`}</DialogTitle></DialogHeader><form onSubmit={save}><div className="grid sm:grid-cols-2 gap-4 py-3">{fields.map(f=><div key={f.key} className={f.full||f.type==="textarea"||f.type==="file"?"sm:col-span-2":""}><Label>{f.label}{f.required?" *":""}</Label>{f.type==="textarea"?<Textarea className="mt-1" rows={4} value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>:f.type==="checkbox"?<label className="mt-1 h-12 border rounded-md px-3 flex items-center gap-3"><input type="checkbox" checked={!!form[f.key]} onChange={e=>setForm(p=>({...p,[f.key]:e.target.checked}))}/><span>{form[f.key]?"Sì":"No"}</span></label>:f.type==="select"?<select className="mt-1 h-12 w-full border rounded-md px-3" value={form[f.key]||""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}><option value="">Seleziona…</option>{(f.options||[]).map(o=><option key={o}>{o}</option>)}</select>:f.type==="file"?<div className="mt-1 rounded-lg border p-3"><div className="flex flex-wrap gap-2">{(Array.isArray(form[f.key])?form[f.key]:[]).map(a=><div key={a.id||a.name} className="inline-flex items-center gap-2 rounded-lg border bg-slate-50 px-2 py-1.5 text-xs"><button type="button" className="inline-flex items-center gap-1 text-blue-700" onClick={()=>openAttachment(a)}><FileText/>{a.name||"File"}</button>{editing&&<button type="button" className="text-red-600" onClick={()=>deleteAttachment(f,a)}>×</button>}</div>)}</div>{editing?<label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold hover:bg-slate-50"><UploadSimple/> Carica file<input type="file" className="hidden" onChange={e=>{const file=e.target.files?.[0];if(file)uploadAttachment(f,file);e.target.value=""}}/></label>:<div className="mt-2 text-xs text-slate-500">Salva prima il record, poi potrai allegare i file.</div>}</div>:<Input className="mt-1 h-12" type={f.type==="currency"||f.type==="number"?"number":f.type==="date"?"date":f.type==="time"?"time":f.type||"text"} step={f.type==="currency"?"0.01":undefined} value={form[f.key]??""} onChange={e=>setForm(p=>({...p,[f.key]:e.target.value}))} required={f.required}/>}</div>)}</div><DialogFooter><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Annulla</Button><Button type="submit">Salva</Button></DialogFooter></form></DialogContent></Dialog>
  </div>
}
