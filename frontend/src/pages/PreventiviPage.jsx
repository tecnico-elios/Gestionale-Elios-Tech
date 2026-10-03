import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plus, MagnifyingGlass, PencilSimple, Trash, Package, FileText, DownloadSimple, PaperPlaneTilt, CheckCircle, WarningCircle, CopySimple, ClockCounterClockwise } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import RecordDocuments from "../components/RecordDocuments";
import { useAuth } from "../lib/AuthContext";
import { appConfirm } from "../lib/appConfirm";

const EMPTY = {
  numero: "",
  cliente_id: "",
  nominativo: "",
  telefono: "",
  email: "",
  sopralluogo_id: "",
  sede_id: "",
  data: new Date().toISOString().slice(0,10),
  validita_giorni: 30,
  condizioni_pagamento: "",
  tempi_consegna: "",
  stato: "Bozza",
  note: "",
  righe: [],
};

const euro = (n) => Number(n || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const clientName = (c) => c?.ragione_sociale || [c?.nome,c?.cognome].filter(Boolean).join(" ") || "Cliente";
const errText = (e) => typeof e?.response?.data?.detail === "string" ? e.response.data.detail : e?.message || "Errore";

export default function PreventiviPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("preventivi", "create");
  const canEdit = hasPermission("preventivi", "edit");
  const canDelete = hasPermission("preventivi", "delete");
  const [items,setItems] = useState([]);
  const [clients,setClients] = useState([]);
  const [surveys,setSurveys] = useState([]);
  const [sites,setSites] = useState([]);
  const [products,setProducts] = useState([]);
  const [search,setSearch] = useState("");
  const [dialog,setDialog] = useState({open:false,item:null});
  const [docs,setDocs] = useState(null);
  const [actionBusy,setActionBusy] = useState("");
  const [revisions,setRevisions] = useState(null);

  const load = async () => {
    try {
      const [p,c,s,si,pr] = await Promise.all([
        axios.get(`${API}/crm/preventivi`),
        axios.get(`${API}/crm/clienti`),
        axios.get(`${API}/crm/sopralluoghi`),
        axios.get(`${API}/crm/sedi`),
        axios.get(`${API}/products`),
      ]);
      setItems(p.data.items || []); setClients(c.data.items || []); setSurveys(s.data.items || []); setSites(si.data.items || []);
      setProducts((pr.data.items || []).filter(x => x.active !== false));
    } catch(e) { toast.error("Errore caricamento preventivi", {description:errText(e)}); }
  };
  useEffect(()=>{ load(); },[]);

  const names = useMemo(()=>Object.fromEntries(clients.map(c=>[c.id,clientName(c)])),[clients]);
  const shown = useMemo(()=>{
    const q=search.trim().toLowerCase(); if(!q) return items;
    return items.filter(x => `${x.numero||""} ${names[x.cliente_id]||x.nominativo||""} ${x.stato||""}`.toLowerCase().includes(q));
  },[items,search,names]);

  const remove = async(id) => {
    if (!(await appConfirm({ title: "Elimina preventivo", message: "Confermi l’eliminazione del preventivo?", confirmLabel: "Elimina", danger: true }))) return;
    try { await axios.delete(`${API}/crm/preventivi/${id}`); toast.success("Preventivo eliminato"); load(); }
    catch(e){ toast.error("Eliminazione non riuscita",{description:errText(e)}); }
  };

  const downloadPdf = async (quote) => {
    setActionBusy(`pdf:${quote.id}`);
    try {
      const res = await axios.get(`${API}/crm/preventivi/${quote.id}/pdf`, { responseType: "blob" });
      const disp = res.headers?.["content-disposition"] || "";
      const match = disp.match(/filename="?([^";]+)"?/i);
      const revision = res.headers?.["x-quote-revision"] || quote.pdf_revision || 1;
      const filename = match?.[1] || `${quote.numero || "Preventivo"}.pdf`;
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 500);
      toast.success("PDF generato");
      await load();
    } catch(e) { toast.error("Generazione PDF non riuscita", {description:errText(e)}); }
    finally { setActionBusy(""); }
  };

  const markSent = async (quote) => {
    setActionBusy(`sent:${quote.id}`);
    try { await axios.post(`${API}/crm/preventivi/${quote.id}/mark-sent`); toast.success("Preventivo segnato come inviato"); await load(); }
    catch(e) { toast.error("Operazione non riuscita", {description:errText(e)}); }
    finally { setActionBusy(""); }
  };

  const acceptQuote = async (quote) => {
    if (!(await appConfirm({ title: "Accetta preventivo", message: `Confermi il preventivo ${quote.numero || ""}?`, confirmLabel: "Accetta" }))) return;
    setActionBusy(`accept:${quote.id}`);
    try {
      const {data} = await axios.post(`${API}/crm/preventivi/${quote.id}/accept`);
      const cm = data?.commessa;
      toast.success("Preventivo accettato", {description: cm?.number ? `Commessa #${cm.number} creata/aggiornata automaticamente` : "Commessa creata/aggiornata"});
      await load();
    } catch(e) { toast.error("Conferma non riuscita", {description:errText(e)}); }
    finally { setActionBusy(""); }
  };

  const createRevision = async (quote) => {
    if (!(await appConfirm({ title: "Nuova revisione", message: `Creare una nuova revisione del preventivo ${quote.numero || ""}?`, confirmLabel: "Crea revisione" }))) return;
    setActionBusy(`revision:${quote.id}`);
    try {
      const {data} = await axios.post(`${API}/crm/preventivi/${quote.id}/revision`);
      toast.success(`Creata Rev. ${data.quote_revision || 2}`, {description:"La nuova revisione è modificabile e resta collegata alla stessa commessa."});
      await load();
      setDialog({open:true,item:data});
    } catch(e) { toast.error("Creazione revisione non riuscita", {description:errText(e)}); }
    finally { setActionBusy(""); }
  };

  const openRevisions = async (quote) => {
    setActionBusy(`history:${quote.id}`);
    try {
      const {data} = await axios.get(`${API}/crm/preventivi/${quote.id}/revisions`);
      setRevisions({quote, items:data.items || []});
    } catch(e) { toast.error("Storico revisioni non disponibile", {description:errText(e)}); }
    finally { setActionBusy(""); }
  };

  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-5">
      <div><div className="text-xs font-semibold tracking-[.16em] uppercase text-blue-600">Gestionale Elios Tech</div><h1 className="font-display text-3xl font-bold text-slate-900 mt-1">Preventivi</h1><p className="text-slate-500 mt-1">Preventivi strutturati: materiali e servizi alimentano automaticamente ordine e commessa.</p></div>
      {canCreate && <Button className="h-12" onClick={()=>setDialog({open:true,item:null})}><Plus size={18}/> Nuovo preventivo</Button>}
    </div>
    <div className="bg-white border border-slate-200 rounded-md">
      <div className="p-3 border-b border-slate-200 flex items-center gap-2"><MagnifyingGlass size={18} className="text-slate-400"/><Input className="h-12 max-w-md" placeholder="Cerca numero, cliente o stato..." value={search} onChange={e=>setSearch(e.target.value)}/><span className="ml-auto text-sm text-slate-500">{shown.length} preventivi</span></div>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50"><tr><th className="text-left px-4 py-3">Numero</th><th className="text-left px-4 py-3">Cliente / contatto</th><th className="text-left px-4 py-3">Data</th><th className="text-left px-4 py-3">Totale</th><th className="text-left px-4 py-3">Stato</th><th className="px-4 py-3 text-right">Azioni</th></tr></thead><tbody>
        {shown.map(x=><tr key={x.id} className="border-t border-slate-100 hover:bg-slate-50/70"><td className="px-4 py-3 font-semibold"><div>{x.numero||"—"}</div><div className="text-[10px] mt-1 text-slate-500 font-semibold">Rev. {x.quote_revision || 1}</div>{x.pdf_revision ? <div className={`text-[10px] mt-0.5 ${x.pdf_outdated ? "text-amber-700" : "text-slate-400"}`}>{x.pdf_outdated ? "PDF da rigenerare" : "PDF aggiornato"}</div> : <div className="text-[10px] mt-0.5 text-slate-400">PDF non generato</div>}</td><td className="px-4 py-3">{names[x.cliente_id]||x.nominativo||"—"}</td><td className="px-4 py-3">{x.data||"—"}</td><td className="px-4 py-3 font-semibold">€ {euro(x.totale ?? x.importo)}</td><td className="px-4 py-3"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold border ${x.stato==="Accettato"?"bg-emerald-50 text-emerald-700 border-emerald-200":x.stato==="Inviato"?"bg-blue-50 text-blue-700 border-blue-200":x.stato==="Rifiutato"?"bg-red-50 text-red-700 border-red-200":"bg-slate-50 text-slate-700 border-slate-200"}`}>{x.stato||"—"}</span>{x.stato==="Accettato"&&<div className="text-[10px] text-slate-400 mt-1">Revisione commerciale {x.quote_revision || 1} accettata</div>}</td><td className="px-4 py-2"><div className="flex justify-end gap-1 flex-wrap"><Button variant="ghost" size="icon" onClick={()=>downloadPdf(x)} disabled={!!actionBusy} title={x.pdf_outdated?"Rigenera PDF aggiornato":"Genera / scarica PDF"}><DownloadSimple/></Button>{canEdit&&x.stato!=="Accettato"&&<Button variant="ghost" size="icon" onClick={()=>markSent(x)} disabled={!!actionBusy || !x.pdf_revision || x.pdf_outdated} title={!x.pdf_revision||x.pdf_outdated?"Genera prima il PDF aggiornato":"Segna come inviato"}><PaperPlaneTilt/></Button>}{canEdit&&x.stato!=="Accettato"&&x.stato!=="Rifiutato"&&<Button variant="ghost" size="icon" className="text-emerald-700" onClick={()=>acceptQuote(x)} disabled={!!actionBusy || !x.pdf_revision || x.pdf_outdated} title={!x.pdf_revision||x.pdf_outdated?"Genera prima il PDF aggiornato":"Accetta e crea commessa"}><CheckCircle/></Button>}{x.stato==="Accettato"&&canEdit&&<Button variant="ghost" size="icon" className="text-blue-700" onClick={()=>createRevision(x)} disabled={!!actionBusy || !!x.superseded_by_revision_id} title={x.superseded_by_revision_id?"Esiste già una revisione successiva":"Crea nuova revisione"}><CopySimple/></Button>}<Button variant="ghost" size="icon" onClick={()=>openRevisions(x)} disabled={!!actionBusy} title="Storico revisioni"><ClockCounterClockwise/></Button><Button variant="ghost" size="icon" onClick={()=>setDocs(x)} title="Documenti"><FileText/></Button>{canEdit&&x.stato!=="Accettato"&&<Button variant="ghost" size="icon" onClick={()=>setDialog({open:true,item:x})} title="Modifica"><PencilSimple/></Button>}{canDelete&&x.stato!=="Accettato"&&<Button variant="ghost" size="icon" className="text-red-600" onClick={()=>remove(x.id)} title="Elimina"><Trash/></Button>}</div></td></tr>)}
        {!shown.length&&<tr><td colSpan="6" className="p-10 text-center text-slate-500">Nessun preventivo presente.</td></tr>}
      </tbody></table></div>
    </div>
    {dialog.open && <QuoteDialog open={dialog.open} item={dialog.item} clients={clients} surveys={surveys} sites={sites} products={products} onClose={()=>setDialog({open:false,item:null})} onSaved={()=>{setDialog({open:false,item:null});load();}} />}
    {docs && <RecordDocuments resource="preventivi" recordId={docs.id} title={`Documenti preventivo · ${docs.numero||""}`} module="preventivi" open={!!docs} onOpenChange={(v)=>!v&&setDocs(null)} />}
    {revisions && <RevisionHistoryDialog data={revisions} onClose={()=>setRevisions(null)} onEdit={(rev)=>{setRevisions(null);setDialog({open:true,item:rev});}} onDownload={downloadPdf} />}
  </div>;
}

function RevisionHistoryDialog({data,onClose,onEdit,onDownload}) {
  const items = data?.items || [];
  return <Dialog open={true} onOpenChange={(v)=>!v&&onClose()}>
    <DialogContent className="max-w-2xl w-[95vw] max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Storico revisioni · {data?.quote?.numero || "Preventivo"}</DialogTitle>
      </DialogHeader>
      <div className="space-y-3">
        {items.map((r)=><div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div className="font-bold text-slate-900">Rev. {r.quote_revision || 1}</div>
              <div className="text-xs text-slate-500 mt-1">{r.data || "—"} · € {euro(r.totale ?? r.importo)}</div>
            </div>
            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold border ${r.stato==="Accettato"?"bg-emerald-50 text-emerald-700 border-emerald-200":r.stato==="Inviato"?"bg-blue-50 text-blue-700 border-blue-200":"bg-slate-50 text-slate-700 border-slate-200"}`}>{r.stato || "Bozza"}</span>
          </div>
          <div className="mt-3 flex gap-2 flex-wrap">
            <Button size="sm" variant="outline" onClick={()=>onDownload(r)}><DownloadSimple size={15}/> PDF</Button>
            {r.stato!=="Accettato"&&<Button size="sm" variant="outline" onClick={()=>onEdit(r)}><PencilSimple size={15}/> Apri / modifica</Button>}
          </div>
        </div>)}
      </div>
      <DialogFooter><Button variant="outline" onClick={onClose}>Chiudi</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}

function QuoteDialog({open,item,clients,surveys,sites,products,onClose,onSaved}) {
  const [form,setForm]=useState(item?{...EMPTY,...item,righe:Array.isArray(item.righe)?item.righe:[]}:{...EMPTY});
  const [saving,setSaving]=useState(false);
  const [clientSearch,setClientSearch]=useState("");
  useEffect(()=>{ if(open){setForm(item?{...EMPTY,...item,righe:Array.isArray(item.righe)?item.righe:[]}:{...EMPTY}); setClientSearch(item?.cliente_id ? clientName(clients.find(c=>c.id===item.cliente_id)) : "");}},[open,item,clients]);
  const set=(k,v)=>setForm(p=>({...p,[k]:v}));
  const rows=Array.isArray(form.righe)?form.righe:[];
  const filteredClients=useMemo(()=>{const q=clientSearch.trim().toLowerCase(); if(!q)return clients.slice(0,20); return clients.filter(c=>`${clientName(c)} ${c.telefono||""} ${c.email||""} ${c.partita_iva||""}`.toLowerCase().includes(q)).slice(0,20)},[clientSearch,clients]);
  const filteredSurveys=surveys.filter(s=>!form.cliente_id || String(s.cliente_id||"")===String(form.cliente_id));
  const filteredSites=sites.filter(s=>!form.cliente_id || String(s.cliente_id||"")===String(form.cliente_id));
  const addRow=(tipo="materiale")=>set("righe",[...rows,{tipo_riga:tipo,product_page_id:"",product_name:"",product_code:"",descrizione:"",quantity:1,unit:"pz",prezzo_unitario:0,sconto:0,iva:22}]);
  const updateRow=(i,patch)=>set("righe",rows.map((r,n)=>n===i?{...r,...patch}:r));
  const removeRow=(i)=>set("righe",rows.filter((_,n)=>n!==i));
  const chooseProduct=(i,id)=>{const p=products.find(x=>String(x.id)===String(id)); updateRow(i,p?{product_page_id:p.id,product_name:p.name,product_code:p.code||"",descrizione:p.name,tipo_gestione:p.tipo_gestione||"a_quantita",unit:p.unit||"pz"}:{product_page_id:"",product_name:"",product_code:""});};
  const lineTotal=(r)=>Number(r.quantity||0)*Number(r.prezzo_unitario||0)*(1-Number(r.sconto||0)/100);
  const imponibile=rows.reduce((a,r)=>a+lineTotal(r),0);
  const ivaTot=rows.reduce((a,r)=>a+lineTotal(r)*Number(r.iva||0)/100,0);
  const totale=imponibile+ivaTot;
  const selectSurvey=(id)=>{const s=surveys.find(x=>String(x.id)===String(id)); setForm(p=>({...p,sopralluogo_id:id,cliente_id:p.cliente_id||s?.cliente_id||"",sede_id:p.sede_id||s?.sede_id||""}));};
  const save=async(e)=>{e.preventDefault(); if(!form.cliente_id&&!String(form.nominativo||"").trim()) return toast.error("Seleziona un cliente oppure inserisci almeno il nominativo del contatto"); if(!rows.length) return toast.error("Inserisci almeno una riga nel preventivo"); setSaving(true); try{
      const cleanRows=rows.filter(r=>Number(r.quantity)>0 && (r.product_page_id || String(r.descrizione||r.product_name||"").trim())).map(r=>({...r,quantity:Number(r.quantity),prezzo_unitario:Number(r.prezzo_unitario||0),sconto:Number(r.sconto||0),iva:Number(r.iva||0)}));
      if(!cleanRows.length) throw new Error("Nessuna riga valida");
      const payload={...form,righe:cleanRows,imponibile,iva_totale:ivaTot,totale,importo:totale};
      const {data}= item?.id ? await axios.put(`${API}/crm/preventivi/${item.id}`,payload) : await axios.post(`${API}/crm/preventivi`,payload);
      toast.success(data?.commessa ? "Preventivo salvato e commessa creata" : "Preventivo salvato"); onSaved?.();
    }catch(e){toast.error("Salvataggio non riuscito",{description:errText(e)})}finally{setSaving(false)}};

  return <Dialog open={open} onOpenChange={v=>!v&&onClose()}><DialogContent className="max-w-6xl max-h-[95vh] overflow-y-auto"><DialogHeader><DialogTitle>{item?.id?`Modifica preventivo · Rev. ${item.quote_revision || 1}`:"Nuovo preventivo"}</DialogTitle></DialogHeader><form onSubmit={save} className="space-y-5">
    <div className="rounded-md border border-slate-200 p-4"><h3 className="font-bold mb-3">Destinatario</h3><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 relative"><Label>Cerca cliente</Label><Input className="mt-1 h-12" value={clientSearch} onChange={e=>{setClientSearch(e.target.value); if(form.cliente_id)set("cliente_id","")}} placeholder="Scrivi nome, azienda, telefono, email o P.IVA..."/>{clientSearch&&!form.cliente_id&&<div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-56 overflow-auto">{filteredClients.map(c=><button type="button" key={c.id} onClick={()=>{set("cliente_id",c.id);setClientSearch(clientName(c));}} className="block w-full text-left px-3 py-2 hover:bg-slate-50"><b>{clientName(c)}</b><div className="text-xs text-slate-500">{[c.telefono,c.email,c.partita_iva].filter(Boolean).join(" · ")}</div></button>)}</div>}</div>
      <div><Label>Oppure nominativo non ancora cliente</Label><Input className="mt-1 h-12" value={form.nominativo||""} onChange={e=>set("nominativo",e.target.value)} placeholder="Prospect / privato / azienda"/></div>
      <div><Label>Telefono</Label><Input className="mt-1 h-12" value={form.telefono||""} onChange={e=>set("telefono",e.target.value)}/></div><div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={form.email||""} onChange={e=>set("email",e.target.value)}/></div>
      <div><Label>Sede</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.sede_id||""} onChange={e=>set("sede_id",e.target.value)}><option value="">Da definire</option>{filteredSites.map(s=><option key={s.id} value={s.id}>{[s.nome,s.indirizzo,s.comune].filter(Boolean).join(" · ")}</option>)}</select></div>
      <div><Label>Sopralluogo collegato</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.sopralluogo_id||""} onChange={e=>selectSurvey(e.target.value)}><option value="">Nessuno</option>{filteredSurveys.map(s=><option key={s.id} value={s.id}>{[s.data,s.tecnico,s.stato].filter(Boolean).join(" · ")}</option>)}</select></div>
      <div><Label>Numero</Label><Input className="mt-1 h-12" value={form.numero||""} onChange={e=>set("numero",e.target.value)} placeholder="Automatico se vuoto"/></div><div><Label>Data *</Label><Input required type="date" className="mt-1 h-12" value={form.data||""} onChange={e=>set("data",e.target.value)}/></div><div><Label>Validità (giorni)</Label><Input type="number" min="1" className="mt-1 h-12" value={form.validita_giorni||30} onChange={e=>set("validita_giorni",e.target.value)}/></div>
      <div><Label>Condizioni di pagamento</Label><Input className="mt-1 h-12" value={form.condizioni_pagamento||""} onChange={e=>set("condizioni_pagamento",e.target.value)} placeholder="Es. 50% ordine, saldo fine lavori"/></div>
      <div><Label>Tempi di consegna / esecuzione</Label><Input className="mt-1 h-12" value={form.tempi_consegna||""} onChange={e=>set("tempi_consegna",e.target.value)} placeholder="Es. 20 giorni lavorativi"/></div>
      <div><Label>Stato</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato} onChange={e=>set("stato",e.target.value)}>{["Bozza","Da inviare","Inviato","In trattativa","Accettato","Rifiutato","Scaduto"].map(x=><option key={x} disabled={x==="Inviato"||x==="Accettato"}>{x}</option>)}</select><div className="mt-1 text-[11px] text-slate-500">“Inviato” e “Accettato” si impostano dai pulsanti del preventivo per mantenere PDF, revisione e commessa coerenti.</div></div>
    </div></div>

    <div className="rounded-md border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2 mb-3"><div><h3 className="font-bold">Righe preventivo</h3><p className="text-xs text-slate-500">Il materiale alimenta la commessa e il picking. Servizi, installazione e progettazione restano economici ma non scalano il magazzino.</p></div><div className="flex gap-2"><Button type="button" variant="outline" onClick={()=>addRow("materiale")}><Plus size={15}/> Materiale</Button><Button type="button" variant="outline" onClick={()=>addRow("servizio")}><Plus size={15}/> Servizio</Button></div></div>
      <div className="space-y-3">{rows.map((r,i)=><div key={i} className="grid lg:grid-cols-[130px_1.4fr_1.4fr_90px_100px_90px_80px_44px] gap-2 border border-slate-100 rounded-md p-3 items-end">
        <div><Label>Tipo</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 px-2" value={r.tipo_riga||"materiale"} onChange={e=>updateRow(i,{tipo_riga:e.target.value})}><option value="materiale">Materiale</option><option value="servizio">Servizio</option><option value="installazione">Installazione</option><option value="progettazione">Progettazione</option><option value="trasporto">Trasporto</option><option value="manodopera">Manodopera</option></select></div>
        <div><Label>{(r.tipo_riga||"materiale")==="materiale"?"Prodotto catalogo":"Voce / servizio"}</Label>{(r.tipo_riga||"materiale")==="materiale"?<select className="mt-1 h-11 w-full rounded-md border border-slate-300 px-2" value={r.product_page_id||""} onChange={e=>chooseProduct(i,e.target.value)}><option value="">Voce libera / seleziona…</option>{products.map(p=><option key={p.id} value={p.id}>{p.code?`${p.code} · `:""}{p.name}</option>)}</select>:<Input className="mt-1 h-11" value={r.descrizione||""} onChange={e=>updateRow(i,{descrizione:e.target.value,product_name:e.target.value})}/>}</div>
        <div><Label>Descrizione</Label><Input className="mt-1 h-11" value={r.descrizione||r.product_name||""} onChange={e=>updateRow(i,{descrizione:e.target.value})}/></div>
        <div><Label>Q.tà</Label><Input type="number" min="0.01" step="0.01" className="mt-1 h-11" value={r.quantity??1} onChange={e=>updateRow(i,{quantity:e.target.value})}/></div>
        <div><Label>Prezzo €</Label><Input type="number" min="0" step="0.01" className="mt-1 h-11" value={r.prezzo_unitario??0} onChange={e=>updateRow(i,{prezzo_unitario:e.target.value})}/></div>
        <div><Label>Sconto %</Label><Input type="number" min="0" max="100" step="0.01" className="mt-1 h-11" value={r.sconto??0} onChange={e=>updateRow(i,{sconto:e.target.value})}/></div>
        <div><Label>IVA %</Label><Input type="number" min="0" step="1" className="mt-1 h-11" value={r.iva??22} onChange={e=>updateRow(i,{iva:e.target.value})}/></div>
        <Button type="button" variant="ghost" size="icon" className="h-11 w-11 text-red-600" onClick={()=>removeRow(i)}><Trash/></Button>
        <div className="lg:col-span-8 text-right text-sm font-semibold text-slate-600">Riga: € {euro(lineTotal(r))} + IVA</div>
      </div>)}{!rows.length&&<div className="py-6 text-center text-slate-400 text-sm">Aggiungi almeno una riga materiale o servizio.</div>}</div>
      <div className="mt-4 ml-auto max-w-sm border-t border-slate-200 pt-3 space-y-1 text-sm"><div className="flex justify-between"><span>Imponibile</span><b>€ {euro(imponibile)}</b></div><div className="flex justify-between"><span>IVA</span><b>€ {euro(ivaTot)}</b></div><div className="flex justify-between text-lg"><span>Totale</span><b>€ {euro(totale)}</b></div></div>
    </div>
    <div><Label>Note</Label><Textarea className="mt-1" rows={3} value={form.note||""} onChange={e=>set("note",e.target.value)}/></div>
    {item?.pdf_revision&&item?.pdf_outdated&&<div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 flex gap-2"><WarningCircle size={19}/><span>Il preventivo Rev. {item.quote_revision || 1} è stato modificato dopo la generazione del PDF. Salva le modifiche e rigenera il PDF prima dell’invio o dell’accettazione.</span></div>} {form.stato==="Accettato"&&<div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 flex gap-2"><Package size={19}/><span>Questo preventivo è già accettato. La commessa collegata resta la fonte operativa per materiali e servizi.</span></div>}
    <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving?"Salvataggio…":"Salva preventivo"}</Button></DialogFooter>
  </form></DialogContent></Dialog>;
}
