import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowsClockwise, MagnifyingGlass } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { useAuth } from "../lib/AuthContext";


const W = [
  { id: "elios-tech", name: "Magazzino Elios Tech" },
  { id: "verona", name: "Magazzino Verona" },
];
function errText(e){ const d=e?.response?.data?.detail; return typeof d === "string" ? d : e?.message || "Errore"; }

export default function TrasferimentiPage(){
  const { hasPermission } = useAuth();
  const [products,setProducts]=useState([]);
  const [history,setHistory]=useState([]);
  const [from,setFrom]=useState("elios-tech");
  const [to,setTo]=useState("verona");
  const [productId,setProductId]=useState("");
  const [quantity,setQuantity]=useState(1);
  const [serials,setSerials]=useState("");
  const [note,setNote]=useState("");
  const [search,setSearch]=useState("");
  const [busy,setBusy]=useState(false);
  const canCreate=hasPermission("movimenti","create") || hasPermission("movimenti","edit");
  const load=async()=>{
    try{
      const [p,h]=await Promise.all([axios.get(`${API}/inventory`,{params:{warehouse_id:from}}),axios.get(`${API}/warehouse/transfers`)]);
      setProducts(p.data.items||[]); setHistory(h.data.items||[]);
    }catch(e){toast.error("Impossibile caricare i trasferimenti",{description:errText(e)});}
  };
  useEffect(()=>{load();},[from]); // eslint-disable-line react-hooks/exhaustive-deps
  const product=products.find((x)=>x.id===productId);
  const filtered=useMemo(()=>{const q=search.trim().toLowerCase();return q?products.filter((x)=>`${x.name} ${x.code}`.toLowerCase().includes(q)):products;},[products,search]);
  const swap=()=>{setFrom(to);setTo(from);setProductId("");setSerials("");};
  const submit=async(e)=>{
    e.preventDefault(); if(!productId)return toast.error("Seleziona un prodotto");
    const sn=serials.split(/[\n,;]+/).map((x)=>x.trim()).filter(Boolean);
    if(product?.tipo_gestione==="a_seriale"&&!sn.length)return toast.error("Inserisci almeno un seriale da trasferire");
    if(!note.trim()) return toast.error("Inserisci la nota del trasferimento", {description:"La nota è obbligatoria per mantenere uno storico chiaro dello spostamento."});
    setBusy(true);
    try{
      await axios.post(`${API}/warehouse/transfers`,{product_id:productId,quantity:product?.tipo_gestione==="a_seriale"?sn.length:Number(quantity||0),serials:sn,from_warehouse_id:from,to_warehouse_id:to,note:note.trim()});
      toast.success("Trasferimento registrato", {description:`${product?.name || "Prodotto"}: ${from === "elios-tech" ? "Elios Tech" : "Verona"} → ${to === "elios-tech" ? "Elios Tech" : "Verona"}`});
      setProductId("");setQuantity(1);setSerials("");setNote("");
      // Il trasferimento è già concluso: un eventuale errore nel refresh non deve trasformare il successo in un falso errore.
      try { await load(); } catch (_) { toast.warning("Trasferimento eseguito", {description:"Aggiorna la pagina per ricaricare lo storico."}); }
    }catch(e){
      // In caso di errore di rete il server potrebbe aver già concluso il trasferimento.
      // Verifica lo storico prima di mostrare un falso errore all'operatore.
      if(!e?.response){
        try{
          const {data}=await axios.get(`${API}/warehouse/transfers`);
          const recent=(data.items||[]).find(x=>
            x.product_id===productId && x.from_warehouse_id===from && x.to_warehouse_id===to &&
            String(x.note||"").trim()===note.trim() && Math.abs(Number(x.quantity||0)-Number(product?.tipo_gestione==="a_seriale"?sn.length:Number(quantity||0)))<0.0001
          );
          if(recent){
            toast.success("Trasferimento registrato",{description:"Il server lo aveva già completato correttamente."});
            setProductId("");setQuantity(1);setSerials("");setNote("");setHistory(data.items||[]);
            setBusy(false); return;
          }
        }catch{}
      }
      toast.error("Trasferimento non riuscito",{description:errText(e)});
    }finally{setBusy(false);}
  };
  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-5">
    <div><div className="et-eyebrow">Gestione</div><h1 className="et-page-heading text-3xl sm:text-4xl mt-1">Trasferimenti</h1></div>
    {canCreate&&<form onSubmit={submit} className="bg-white border border-slate-200 rounded-md p-4 sm:p-5 space-y-4">
      <div className="grid sm:grid-cols-[1fr_auto_1fr] gap-3 items-end"><div><Label>Da</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={from} onChange={(e)=>{setFrom(e.target.value);if(e.target.value===to)setTo(e.target.value==="elios-tech"?"verona":"elios-tech");setProductId("");}}>{W.map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></div><Button type="button" variant="outline" className="h-12" onClick={swap}><ArrowsClockwise size={18}/></Button><div><Label>A</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={to} onChange={(e)=>setTo(e.target.value)}>{W.filter((w)=>w.id!==from).map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></div></div>
      <div><Label>Cerca prodotto nel deposito di origine</Label><div className="relative mt-1"><MagnifyingGlass size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><Input className="pl-9 h-12" value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Nome o codice prodotto"/></div><select className="mt-2 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={productId} onChange={(e)=>setProductId(e.target.value)}><option value="">Seleziona prodotto…</option>{filtered.map((p)=><option key={p.id} value={p.id}>{p.name} {p.code?`· ${p.code}`:""} · Disponibile {p.quantity} {p.unit||"pz"}</option>)}</select></div>
      {product&&product.tipo_gestione==="a_seriale"?<div><Label>Seriali da trasferire</Label><Textarea className="mt-1" rows={5} value={serials} onChange={(e)=>setSerials(e.target.value)} placeholder="Un seriale per riga, oppure separati da virgola"/><p className="text-xs text-slate-500 mt-1">Ogni seriale deve essere disponibile nel deposito di origine.</p></div>:<div><Label>Quantità da trasferire</Label><Input type="number" min="0.01" step="0.01" className="mt-1 h-12 max-w-xs" value={quantity} onChange={(e)=>setQuantity(e.target.value)}/></div>}
      <div><Label>Nota *</Label><Textarea className="mt-1 min-h-24" required value={note} onChange={(e)=>setNote(e.target.value)} placeholder="Motivo o riferimento del trasferimento (obbligatorio)"/></div>
      <div className="flex justify-end"><Button type="submit" disabled={busy} className="h-12">{busy?"Trasferimento…":"Conferma trasferimento"}</Button></div>
    </form>}
    <section className="bg-white border border-slate-200 rounded-md overflow-hidden"><div className="p-4 border-b border-slate-200"><h2 className="font-bold">Storico trasferimenti</h2></div><div className="divide-y divide-slate-100">{history.map((x)=><div key={x.id} className="p-4 grid sm:grid-cols-5 gap-2 text-sm"><div className="font-semibold">{x.product_name||"Prodotto"}</div><div>{x.quantity} {x.serials?.length?"seriali":(x.unit||"pz")}</div><div>{x.from_warehouse_name||x.from_warehouse_id}</div><div>{x.to_warehouse_name||x.to_warehouse_id}</div><div className="text-slate-500">{x.operator||"—"}</div>{x.serials?.length>0&&<div className="sm:col-span-5 text-xs text-slate-500">SN: {x.serials.join(", ")}</div>}{x.note&&<div className="sm:col-span-5 text-xs text-slate-600"><span className="font-semibold">Nota:</span> {x.note}</div>}</div>)}{history.length===0&&<div className="p-8 text-center text-slate-500">Nessun trasferimento registrato.</div>}</div></section>
  </div>;
}
