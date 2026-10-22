import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowsClockwise, MagnifyingGlass, ArrowsLeftRight, Package } from "@phosphor-icons/react";
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
      try { await load(); } catch (_) { toast.warning("Trasferimento eseguito", {description:"Aggiorna la pagina per ricaricare lo storico."}); }
    }catch(e){
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

  return <div className="r52-transfers-workspace">
    <div className="r52-commandbar">
      <div><div className="r52-commandbar-title">Spostamenti tra depositi</div><div className="r52-commandbar-subtitle">Trasferisci quantità o seriali mantenendo una traccia completa dell'operazione.</div></div>
      <div className="r52-commandbar-actions"><span className="r52-transfer-count"><ArrowsLeftRight size={15}/>{history.length} registrati</span></div>
    </div>

    {canCreate&&<form onSubmit={submit} className="r52-panel r52-transfer-form">
      <div className="r52-panel-heading"><div><div className="r52-section-kicker">Nuovo movimento</div><h2>Trasferimento materiale</h2><p>Seleziona origine, destinazione e prodotto. La nota è obbligatoria.</p></div></div>
      <div className="r52-transfer-route">
        <div><Label>Da</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={from} onChange={(e)=>{setFrom(e.target.value);if(e.target.value===to)setTo(e.target.value==="elios-tech"?"verona":"elios-tech");setProductId("");}}>{W.map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></div>
        <Button type="button" variant="outline" className="r52-transfer-swap" onClick={swap} aria-label="Inverti depositi"><ArrowsClockwise size={19}/></Button>
        <div><Label>A</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={to} onChange={(e)=>setTo(e.target.value)}>{W.filter((w)=>w.id!==from).map((w)=><option key={w.id} value={w.id}>{w.name}</option>)}</select></div>
      </div>

      <div className="r52-transfer-product-block">
        <Label>Prodotto nel deposito di origine</Label>
        <div className="relative mt-1"><MagnifyingGlass size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><Input className="pl-9 h-11" value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Cerca nome o codice prodotto"/></div>
        <select className="mt-2 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={productId} onChange={(e)=>setProductId(e.target.value)}><option value="">Seleziona prodotto…</option>{filtered.map((p)=><option key={p.id} value={p.id}>{p.name} {p.code?`· ${p.code}`:""} · Disponibile {p.quantity} {p.unit||"pz"}</option>)}</select>
        {product && <div className="r52-selected-product"><Package size={17} weight="duotone"/><div><b>{product.name}</b><span>{product.code || "Senza codice"} · {product.tipo_gestione === "a_seriale" ? "gestione a seriale" : "gestione a quantità"}</span></div></div>}
      </div>

      <div className="r52-transfer-fields">
        {product&&product.tipo_gestione==="a_seriale"?<div><Label>Seriali</Label><Textarea className="mt-1" rows={5} value={serials} onChange={(e)=>setSerials(e.target.value)} placeholder="Un seriale per riga, oppure separati da virgola"/><p className="text-xs text-slate-500 mt-1">Ogni seriale deve essere disponibile nel deposito di origine.</p></div>:<div><Label>Quantità</Label><Input type="number" min="0.01" step="0.01" className="mt-1 h-12" value={quantity} onChange={(e)=>setQuantity(e.target.value)}/></div>}
        <div><Label>Nota *</Label><Textarea className="mt-1 min-h-24" required value={note} onChange={(e)=>setNote(e.target.value)} placeholder="Motivo o riferimento del trasferimento"/></div>
      </div>
      <div className="r52-transfer-submit"><Button type="submit" disabled={busy} className="h-12">{busy?"Trasferimento…":"Registra trasferimento"}</Button></div>
    </form>}

    <section className="r52-panel r52-panel-flush">
      <div className="r52-panel-heading"><div><div className="r52-section-kicker">Storico</div><h2>Trasferimenti registrati</h2><p>Ultimi spostamenti di materiale tra Elios Tech e Verona.</p></div><span className="r52-count-pill">{history.length}</span></div>
      <div className="r52-transfer-history">
        {history.map((x)=><div key={x.id} className="r52-transfer-history-row"><div className="r52-transfer-history-product"><Package size={17}/><div><b>{x.product_name||"Prodotto"}</b><span>{x.quantity} {x.serials?.length?"seriali":(x.unit||"pz")}</span></div></div><div className="r52-transfer-direction"><span>{x.from_warehouse_name||x.from_warehouse_id}</span><ArrowsLeftRight size={15}/><span>{x.to_warehouse_name||x.to_warehouse_id}</span></div><div className="r52-transfer-operator">{x.operator||"—"}</div>{x.serials?.length>0&&<div className="r52-transfer-detail">SN: {x.serials.join(", ")}</div>}{x.note&&<div className="r52-transfer-detail"><b>Nota:</b> {x.note}</div>}</div>)}
        {history.length===0&&<div className="r52-empty-state">Nessun trasferimento.</div>}
      </div>
    </section>
  </div>;
}