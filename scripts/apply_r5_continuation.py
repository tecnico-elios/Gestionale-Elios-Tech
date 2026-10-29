from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new, label):
    text = read(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: atteso 1 match per {label}, trovati {count}")
    write(rel, text.replace(old, new, 1))


def insert_before(rel, marker, addition, label):
    text = read(rel)
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{rel}: atteso 1 marker per {label}, trovati {count}")
    write(rel, text.replace(marker, addition + marker, 1))


def replace_between(rel, start_marker, end_marker, replacement, label):
    text = read(rel)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{rel}: start marker non trovato per {label}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{rel}: end marker non trovato per {label}")
    write(rel, text[:start] + replacement + text[end:])


# -----------------------------------------------------------------------------
# 1) Sopralluoghi: autocomplete cliente + creazione cliente inline.
#    La sede era già creabile inline: dopo la creazione cliente il flusso resta
#    interamente dentro lo stesso popup.
# -----------------------------------------------------------------------------
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    'F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", clearOnChange: ["sede_id"] }),',
    'F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", inlineCreateClient: true, clearOnChange: ["sede_id"] }),',
    "abilita creazione cliente inline nei sopralluoghi",
)

registry = "frontend/src/pages/RegistryPage.jsx"
replace_once(
    registry,
    '  const [siteSaving, setSiteSaving] = useState(false);\n  const [documentsTarget, setDocumentsTarget] = useState(null);',
    '''  const [siteSaving, setSiteSaving] = useState(false);
  const [clientCreate, setClientCreate] = useState({ open: false, fieldKey: "" });
  const [clientDraft, setClientDraft] = useState({ tipo: "Azienda", ragione_sociale: "", telefono: "", email: "", indirizzo: "", cap: "", comune: "", provincia: "" });
  const [clientSaving, setClientSaving] = useState(false);
  const [documentsTarget, setDocumentsTarget] = useState(null);''',
    "stato creazione cliente",
)

client_helpers = r'''  const openClientCreate = (field) => {
    const typed = String(lookupTextValue(field) || "").trim();
    setClientDraft({ tipo: "Azienda", ragione_sociale: typed, telefono: "", email: "", indirizzo: "", cap: "", comune: "", provincia: "" });
    setClientCreate({ open: true, fieldKey: field.key });
  };

  const saveInlineClient = async () => {
    const field = fields.find((x) => x.key === clientCreate.fieldKey);
    if (!field) return;
    const name = String(clientDraft.ragione_sociale || "").trim();
    if (!name) {
      toast.error("Ragione sociale / nome cliente obbligatorio");
      return;
    }
    const norm = (v) => String(v || "").trim().toLocaleLowerCase("it-IT");
    const email = norm(clientDraft.email);
    const phone = norm(clientDraft.telefono).replace(/\s+/g, "");
    const existing = (lookups.clienti || []).find((c) => {
      const sameName = norm(optionLabel(c, field)) === norm(name);
      const sameEmail = email && norm(c.email) === email;
      const samePhone = phone && norm(c.telefono).replace(/\s+/g, "") === phone;
      return sameName || sameEmail || samePhone;
    });
    if (existing) {
      chooseLookup(field, existing);
      setClientCreate({ open: false, fieldKey: "" });
      toast.info("Cliente già presente: ho selezionato l'anagrafica esistente");
      return;
    }
    setClientSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(clientDraft).map(([k, v]) => [k, typeof v === "string" ? v.trim() : v])
      );
      const { data } = await axios.post(`${API}/crm/clienti`, payload);
      setLookups((prev) => ({ ...prev, clienti: [...(prev.clienti || []), data] }));
      changeField(field, data.id);
      setLookupSearch((prev) => ({ ...prev, [field.key]: optionLabel(data, field) }));
      if (field.allowFreeText && field.freeTextTarget) {
        setForm((prev) => ({ ...prev, [field.freeTextTarget]: "" }));
      }
      setClientCreate({ open: false, fieldKey: "" });
      toast.success("Cliente creato e selezionato");
    } catch (e) {
      toast.error("Creazione cliente non riuscita", { description: errorText(e) });
    } finally {
      setClientSaving(false);
    }
  };

'''
insert_before(registry, "  const openSiteCreate = (field) => {", client_helpers, "helper cliente inline")

old_dropdown = '''                            {lookupOptions(f).length ? lookupOptions(f).map((o) => {
                              const key = f.lookupValueKey || "id";
                              return <button type="button" key={o[key]} onMouseDown={(e)=>e.preventDefault()} onClick={()=>chooseLookup(f,o)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                                <div className="font-semibold text-sm text-slate-900">{optionLabel(o,f)}</div>
                              </button>;
                            }) : <div className="px-3 py-3 text-sm text-slate-500">{f.allowFreeText && lookupTextValue(f) ? `Nessun cliente esistente: puoi salvare “${lookupTextValue(f)}” come nuovo prospect.` : "Nessun risultato"}</div>}
'''
new_dropdown = '''                            {lookupOptions(f).length ? lookupOptions(f).map((o) => {
                              const key = f.lookupValueKey || "id";
                              return <button type="button" key={o[key]} onMouseDown={(e)=>e.preventDefault()} onClick={()=>chooseLookup(f,o)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                                <div className="font-semibold text-sm text-slate-900">{optionLabel(o,f)}</div>
                              </button>;
                            }) : <div className="px-3 py-3 text-sm text-slate-500">{f.allowFreeText && lookupTextValue(f) ? `Nessun cliente esistente per “${lookupTextValue(f)}”.` : "Nessun risultato"}</div>}
                            {f.inlineCreateClient && lookupTextValue(f).trim() && !form[f.key] && (
                              <button type="button" onMouseDown={(e)=>e.preventDefault()} onClick={() => openClientCreate(f)} className="block w-full text-left px-3 py-3 font-semibold text-blue-700 hover:bg-blue-50 border-t border-slate-100">
                                + Aggiungi nuovo cliente
                              </button>
                            )}
'''
replace_once(registry, old_dropdown, new_dropdown, "opzione aggiungi cliente autocomplete")
replace_once(
    registry,
    '{f.allowFreeText && !form[f.key] && lookupTextValue(f) && <div className="text-xs text-amber-700 mt-1">Nuovo prospect: verrà salvato il nominativo senza creare ancora il cliente.</div>}',
    '{f.allowFreeText && !form[f.key] && lookupTextValue(f) && <div className="text-xs text-amber-700 mt-1">Puoi lasciarlo come prospect oppure usare “Aggiungi nuovo cliente” per creare subito l’anagrafica e la sede.</div>}',
    "messaggio prospect",
)

client_dialog = r'''      <Dialog open={clientCreate.open} onOpenChange={(v) => setClientCreate((prev) => ({ ...prev, open: v }))}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Nuovo cliente</DialogTitle></DialogHeader>
          <div className="grid sm:grid-cols-2 gap-4 py-2">
            <div>
              <Label>Tipo</Label>
              <select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={clientDraft.tipo} onChange={(e) => setClientDraft((x) => ({ ...x, tipo: e.target.value }))}>
                <option value="Azienda">Azienda</option><option value="Privato">Privato</option>
              </select>
            </div>
            <div>
              <Label>Ragione sociale / Nome cliente *</Label>
              <Input className="mt-1 h-12" value={clientDraft.ragione_sociale} onChange={(e) => setClientDraft((x) => ({ ...x, ragione_sociale: e.target.value }))} />
            </div>
            <div><Label>Telefono</Label><Input className="mt-1 h-12" value={clientDraft.telefono} onChange={(e) => setClientDraft((x) => ({ ...x, telefono: e.target.value }))} /></div>
            <div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={clientDraft.email} onChange={(e) => setClientDraft((x) => ({ ...x, email: e.target.value }))} /></div>
            <div className="sm:col-span-2"><Label>Indirizzo</Label><Input className="mt-1 h-12" value={clientDraft.indirizzo} onChange={(e) => setClientDraft((x) => ({ ...x, indirizzo: e.target.value }))} /></div>
            <div><Label>CAP</Label><Input className="mt-1 h-12" value={clientDraft.cap} onChange={(e) => setClientDraft((x) => ({ ...x, cap: e.target.value }))} /></div>
            <div><Label>Comune</Label><Input className="mt-1 h-12" value={clientDraft.comune} onChange={(e) => setClientDraft((x) => ({ ...x, comune: e.target.value }))} /></div>
            <div><Label>Provincia</Label><Input className="mt-1 h-12" value={clientDraft.provincia} onChange={(e) => setClientDraft((x) => ({ ...x, provincia: e.target.value }))} /></div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setClientCreate({ open: false, fieldKey: "" })}>Annulla</Button>
            <Button type="button" onClick={saveInlineClient} disabled={clientSaving}>{clientSaving ? "Salvataggio…" : "Crea e seleziona"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

'''
insert_before(registry, "      <Dialog open={siteCreate.open}", client_dialog, "dialog creazione cliente")


# -----------------------------------------------------------------------------
# 2) Preventivi: sostituisce il solo QuoteDialog con una versione che mantiene
#    tutte le funzioni commerciali e aggiunge creazione cliente/sede inline.
# -----------------------------------------------------------------------------
preventivi = "frontend/src/pages/PreventiviPage.jsx"
text = read(preventivi)
idx = text.find("function QuoteDialog(")
if idx < 0:
    raise RuntimeError("PreventiviPage.jsx: QuoteDialog non trovato")

new_quote_dialog = r'''function QuoteDialog({open,item,clients,surveys,sites,products,onClose,onSaved}) {
  const [form,setForm]=useState(item?{...EMPTY,...item,righe:Array.isArray(item.righe)?item.righe:[]}:{...EMPTY});
  const [saving,setSaving]=useState(false);
  const [clientSearch,setClientSearch]=useState("");
  const [localClients,setLocalClients]=useState(clients||[]);
  const [localSites,setLocalSites]=useState(sites||[]);
  const [clientCreateOpen,setClientCreateOpen]=useState(false);
  const [clientCreating,setClientCreating]=useState(false);
  const [clientDraft,setClientDraft]=useState({tipo:"Azienda",ragione_sociale:"",telefono:"",email:""});
  const [siteCreateOpen,setSiteCreateOpen]=useState(false);
  const [siteCreating,setSiteCreating]=useState(false);
  const [siteDraft,setSiteDraft]=useState({nome:"Sede installazione",indirizzo:"",civico:"",cap:"",comune:"",provincia:"",telefono:""});

  useEffect(()=>{
    if(open){
      setForm(item?{...EMPTY,...item,righe:Array.isArray(item.righe)?item.righe:[]}:{...EMPTY});
      setLocalClients(clients||[]); setLocalSites(sites||[]);
      setClientSearch(item?.cliente_id ? clientName((clients||[]).find(c=>c.id===item.cliente_id)) : "");
      setClientCreateOpen(false); setSiteCreateOpen(false);
    }
  },[open,item,clients,sites]);

  const set=(k,v)=>setForm(p=>({...p,[k]:v}));
  const norm=(v)=>String(v||"").trim().toLocaleLowerCase("it-IT");
  const rows=Array.isArray(form.righe)?form.righe:[];
  const filteredClients=useMemo(()=>{
    const q=clientSearch.trim().toLowerCase();
    if(!q) return localClients.slice(0,20);
    return localClients.filter(c=>`${clientName(c)} ${c.telefono||""} ${c.email||""} ${c.partita_iva||""}`.toLowerCase().includes(q)).slice(0,20);
  },[clientSearch,localClients]);
  const filteredSurveys=surveys.filter(s=>!form.cliente_id || String(s.cliente_id||"")===String(form.cliente_id));
  const filteredSites=localSites.filter(s=>!form.cliente_id || String(s.cliente_id||"")===String(form.cliente_id));

  const selectClient=(c)=>{
    setForm(p=>({...p,cliente_id:c.id,nominativo:"",sede_id:"",telefono:p.telefono||c.telefono||"",email:p.email||c.email||""}));
    setClientSearch(clientName(c));
    setClientCreateOpen(false);
  };

  const createClient=async()=>{
    const name=String(clientDraft.ragione_sociale||"").trim();
    if(!name) return toast.error("Ragione sociale / nome cliente obbligatorio");
    const email=norm(clientDraft.email); const phone=norm(clientDraft.telefono).replace(/\s+/g,"");
    const existing=localClients.find(c=>norm(clientName(c))===norm(name)||(email&&norm(c.email)===email)||(phone&&norm(c.telefono).replace(/\s+/g,"")===phone));
    if(existing){ selectClient(existing); toast.info("Cliente già presente: selezionata l'anagrafica esistente"); return; }
    setClientCreating(true);
    try{
      const payload={tipo:clientDraft.tipo||"Azienda",ragione_sociale:name,telefono:String(clientDraft.telefono||"").trim(),email:String(clientDraft.email||"").trim()};
      const {data}=await axios.post(`${API}/crm/clienti`,payload);
      setLocalClients(p=>[...p,data]); selectClient(data); toast.success("Cliente creato e selezionato");
    }catch(e){toast.error("Creazione cliente non riuscita",{description:errText(e)})}finally{setClientCreating(false)}
  };

  const createSite=async()=>{
    if(!form.cliente_id) return toast.error("Seleziona o crea prima il cliente");
    if(!String(siteDraft.nome||"").trim()||!String(siteDraft.indirizzo||"").trim()||!String(siteDraft.comune||"").trim()) return toast.error("Nome sede, indirizzo e comune sono obbligatori");
    const existing=localSites.find(s=>String(s.cliente_id||"")===String(form.cliente_id)&&norm(s.nome)===norm(siteDraft.nome)&&norm(s.indirizzo)===norm(siteDraft.indirizzo)&&norm(s.comune)===norm(siteDraft.comune));
    if(existing){ set("sede_id",existing.id); setSiteCreateOpen(false); toast.info("Sede già presente: selezionata quella esistente"); return; }
    setSiteCreating(true);
    try{
      const {data}=await axios.post(`${API}/crm/sedi`,{cliente_id:form.cliente_id,tipo:"Installazione",...siteDraft});
      setLocalSites(p=>[...p,data]); set("sede_id",data.id); setSiteCreateOpen(false); toast.success("Sede creata e selezionata");
    }catch(e){toast.error("Creazione sede non riuscita",{description:errText(e)})}finally{setSiteCreating(false)}
  };

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

  return <Dialog open={open} onOpenChange={v=>!v&&onClose()}><DialogContent className="max-w-6xl max-h-[95vh] overflow-y-auto"><DialogHeader><DialogTitle>{item?.id?`Modifica preventivo · Rev. ${item.quote_revision || 1}`:"Crea preventivo"}</DialogTitle></DialogHeader><form onSubmit={save} className="space-y-5">
    <div className="rounded-md border border-slate-200 p-4"><h3 className="font-bold mb-3">Destinatario</h3><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 relative"><Label>Cliente</Label><Input className="mt-1 h-12" value={clientSearch} onChange={e=>{setClientSearch(e.target.value); if(form.cliente_id)setForm(p=>({...p,cliente_id:"",sede_id:""}))}} placeholder="Scrivi nome, azienda, telefono, email o P.IVA..." autoComplete="off"/>{clientSearch&&!form.cliente_id&&<div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-64 overflow-auto">{filteredClients.map(c=><button type="button" key={c.id} onMouseDown={e=>e.preventDefault()} onClick={()=>selectClient(c)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-100"><b>{clientName(c)}</b><div className="text-xs text-slate-500">{[c.telefono,c.email,c.partita_iva].filter(Boolean).join(" · ")}</div></button>)}{!filteredClients.length&&<div className="px-3 py-2 text-sm text-slate-500">Nessun cliente esistente trovato.</div>}<button type="button" onMouseDown={e=>e.preventDefault()} onClick={()=>{setClientDraft({tipo:"Azienda",ragione_sociale:clientSearch,telefono:form.telefono||"",email:form.email||""});setClientCreateOpen(true)}} className="block w-full text-left px-3 py-3 font-semibold text-blue-700 hover:bg-blue-50">+ Aggiungi nuovo cliente</button></div>}<p className="text-[11px] text-slate-500 mt-1">Digita per cercare. Se non esiste, puoi crearlo qui senza uscire dal preventivo.</p></div>
      <div><Label>Oppure nominativo non ancora cliente</Label><Input className="mt-1 h-12" value={form.nominativo||""} onChange={e=>set("nominativo",e.target.value)} placeholder="Prospect / privato / azienda"/></div>

      {clientCreateOpen&&<div className="lg:col-span-3 rounded-md border border-blue-200 bg-blue-50/50 p-4"><div className="font-semibold text-slate-900 mb-3">Nuovo cliente</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div><Label>Tipo</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-2" value={clientDraft.tipo} onChange={e=>setClientDraft(p=>({...p,tipo:e.target.value}))}><option>Azienda</option><option>Privato</option></select></div><div><Label>Ragione sociale / Nome *</Label><Input className="mt-1 h-11" value={clientDraft.ragione_sociale} onChange={e=>setClientDraft(p=>({...p,ragione_sociale:e.target.value}))}/></div><div><Label>Telefono</Label><Input className="mt-1 h-11" value={clientDraft.telefono} onChange={e=>setClientDraft(p=>({...p,telefono:e.target.value}))}/></div><div><Label>Email</Label><Input type="email" className="mt-1 h-11" value={clientDraft.email} onChange={e=>setClientDraft(p=>({...p,email:e.target.value}))}/></div></div><div className="flex justify-end gap-2 mt-3"><Button type="button" variant="outline" onClick={()=>setClientCreateOpen(false)}>Annulla</Button><Button type="button" onClick={createClient} disabled={clientCreating}>{clientCreating?"Creazione…":"Crea e seleziona"}</Button></div></div>}

      <div><Label>Telefono</Label><Input className="mt-1 h-12" value={form.telefono||""} onChange={e=>set("telefono",e.target.value)}/></div><div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={form.email||""} onChange={e=>set("email",e.target.value)}/></div>
      <div><Label>Sede</Label><div className="flex gap-2 mt-1"><select className="h-12 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3" value={form.sede_id||""} onChange={e=>set("sede_id",e.target.value)} disabled={!form.cliente_id}><option value="">{form.cliente_id?"Da definire":"Seleziona prima il cliente"}</option>{filteredSites.map(s=><option key={s.id} value={s.id}>{[s.nome,s.indirizzo,s.comune].filter(Boolean).join(" · ")}</option>)}</select>{form.cliente_id&&<Button type="button" variant="outline" className="h-12 px-3" onClick={()=>{setSiteDraft({nome:"Sede installazione",indirizzo:"",civico:"",cap:"",comune:"",provincia:"",telefono:""});setSiteCreateOpen(true)}}>+ Nuova</Button>}</div></div>
      <div><Label>Sopralluogo collegato</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.sopralluogo_id||""} onChange={e=>selectSurvey(e.target.value)}><option value="">Nessuno</option>{filteredSurveys.map(s=><option key={s.id} value={s.id}>{[s.data,s.tecnico,s.stato].filter(Boolean).join(" · ")}</option>)}</select></div>
      <div><Label>Numero</Label><Input className="mt-1 h-12" value={form.numero||""} onChange={e=>set("numero",e.target.value)} placeholder="Automatico se vuoto"/></div>

      {siteCreateOpen&&<div className="lg:col-span-3 rounded-md border border-emerald-200 bg-emerald-50/40 p-4"><div className="font-semibold text-slate-900 mb-3">Nuova sede</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div><Label>Nome sede *</Label><Input className="mt-1 h-11" value={siteDraft.nome} onChange={e=>setSiteDraft(p=>({...p,nome:e.target.value}))}/></div><div><Label>Indirizzo *</Label><Input className="mt-1 h-11" value={siteDraft.indirizzo} onChange={e=>setSiteDraft(p=>({...p,indirizzo:e.target.value}))}/></div><div><Label>Civico</Label><Input className="mt-1 h-11" value={siteDraft.civico} onChange={e=>setSiteDraft(p=>({...p,civico:e.target.value}))}/></div><div><Label>Comune *</Label><Input className="mt-1 h-11" value={siteDraft.comune} onChange={e=>setSiteDraft(p=>({...p,comune:e.target.value}))}/></div><div><Label>CAP</Label><Input className="mt-1 h-11" value={siteDraft.cap} onChange={e=>setSiteDraft(p=>({...p,cap:e.target.value}))}/></div><div><Label>Provincia</Label><Input className="mt-1 h-11" value={siteDraft.provincia} onChange={e=>setSiteDraft(p=>({...p,provincia:e.target.value}))}/></div><div><Label>Telefono sede</Label><Input className="mt-1 h-11" value={siteDraft.telefono} onChange={e=>setSiteDraft(p=>({...p,telefono:e.target.value}))}/></div></div><div className="flex justify-end gap-2 mt-3"><Button type="button" variant="outline" onClick={()=>setSiteCreateOpen(false)}>Annulla</Button><Button type="button" onClick={createSite} disabled={siteCreating}>{siteCreating?"Creazione…":"Crea e seleziona"}</Button></div></div>}

      <div><Label>Data *</Label><Input required type="date" className="mt-1 h-12" value={form.data||""} onChange={e=>set("data",e.target.value)}/></div><div><Label>Validità (giorni)</Label><Input type="number" min="1" className="mt-1 h-12" value={form.validita_giorni||30} onChange={e=>set("validita_giorni",e.target.value)}/></div>
      <div><Label>Condizioni di pagamento</Label><Input className="mt-1 h-12" value={form.condizioni_pagamento||""} onChange={e=>set("condizioni_pagamento",e.target.value)} placeholder="Es. 50% ordine, saldo fine lavori"/></div>
      <div><Label>Tempi di consegna / esecuzione</Label><Input className="mt-1 h-12" value={form.tempi_consegna||""} onChange={e=>set("tempi_consegna",e.target.value)} placeholder="Es. 20 giorni lavorativi"/></div>
      <div><Label>Stato</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato} onChange={e=>set("stato",e.target.value)}>{["Bozza","Da inviare","Inviato","In trattativa","Accettato","Rifiutato","Scaduto"].map(x=><option key={x} disabled={x==="Inviato"||x==="Accettato"}>{x}</option>)}</select><div className="mt-1 text-[11px] text-slate-500">“Inviato” e “Accettato” si impostano dai pulsanti del preventivo per mantenere PDF, revisione e commessa coerenti.</div></div>
    </div></div>

    <div className="rounded-md border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2 mb-3"><div><h3 className="font-bold">Righe preventivo</h3><p className="text-xs text-slate-500">Il materiale alimenta la commessa e il picking. Servizi, installazione e progettazione restano economici ma non scalano il magazzino.</p></div><div className="flex gap-2"><Button type="button" variant="outline" onClick={()=>addRow("materiale")}><Plus size={15}/> Materiale</Button><Button type="button" variant="outline" onClick={()=>addRow("servizio")}><Plus size={15}/> Servizio</Button></div></div>
      <div className="space-y-3">{rows.map((r,i)=><div key={i} className="grid lg:grid-cols-[130px_1.4fr_1.4fr_90px_100px_90px_80px_44px] gap-2 border border-slate-100 rounded-md p-3 items-end">
        <div><Label>Tipo</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 px-2" value={r.tipo_riga||"materiale"} onChange={e=>updateRow(i,{tipo_riga:e.target.value})}><option value="materiale">Materiale</option><option value="servizio">Servizio</option><option value="installazione">Installazione</option><option value="progettazione">Progettazione</option><option value="trasporto">Trasporto</option><option value="manodopera">Manodopera</option></select></div>
        <div><Label>{(r.tipo_riga||"materiale")==="materiale"?"Prodotto catalogo":"Voce / servizio"}</Label>{(r.tipo_riga||"materiale")==="materiale"?<select className="mt-1 h-11 w-full rounded-md border border-slate-300 px-2" value={r.product_page_id||""} onChange={e=>chooseProduct(i,e.target.value)}><option value="">Voce libera / seleziona…</option>{products.map(p=><option key={p.id} value={p.id}>{p.code?`${p.code} · `:""}{p.name}</option>)}</select>:<Input className="mt-1 h-11" value={r.product_name||""} onChange={e=>updateRow(i,{product_name:e.target.value})}/>}</div>
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
    {item?.pdf_revision&&item?.pdf_outdated&&<div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 flex gap-2"><WarningCircle size={19}/><span>Il preventivo Rev. {item.quote_revision || 1} è stato modificato dopo la generazione del PDF. Salva le modifiche e rigenera il PDF prima dell’invio o dell’accettazione.</span></div>}
    {form.stato==="Accettato"&&<div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 flex gap-2"><Package size={19}/><span>Questo preventivo è già accettato. La commessa collegata resta la fonte operativa per materiali e servizi.</span></div>}
    <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving?"Salvataggio…":"Salva preventivo"}</Button></DialogFooter>
  </form></DialogContent></Dialog>;
}
'''
write(preventivi, text[:idx] + new_quote_dialog)


# -----------------------------------------------------------------------------
# 3) Spedizioni: ricerca sull'anagrafica Clienti, nuovo cliente/sede inline,
#    ma resta consentito un nominativo libero. Nessun client id viene più passato
#    per errore come order_page_id.
# -----------------------------------------------------------------------------
checklist = "frontend/src/pages/ChecklistPage.jsx"
replace_once(
    checklist,
    '''  const [cliente, setCliente] = useState("");
  // F14 (autocomplete) — ID locale dell'ordine cliente selezionato dal picker.
  //   Se null: nessun ordine selezionato (blocco sync su richiesta backend).
  const [clienteOrderId, setClienteOrderId] = useState(null);
  const [clienteSuggestions, setClienteSuggestions] = useState([]);
  const [clienteOpen, setClienteOpen] = useState(false);
  const [clienteLoading, setClienteLoading] = useState(false);
  const [shippingDate, setShippingDate] = useState(todayISO());
  const [notes, setNotes] = useState("");
''',
    '''  const [cliente, setCliente] = useState("");
  const [clienteClientId, setClienteClientId] = useState(null);
  const [clienteSuggestions, setClienteSuggestions] = useState([]);
  const [clienteOpen, setClienteOpen] = useState(false);
  const [clienteLoading, setClienteLoading] = useState(false);
  const [clientCreateOpen, setClientCreateOpen] = useState(false);
  const [clientSaving, setClientSaving] = useState(false);
  const [clientDraft, setClientDraft] = useState({ tipo: "Azienda", ragione_sociale: "", telefono: "", email: "" });
  const [sedeId, setSedeId] = useState("");
  const [sedeLabel, setSedeLabel] = useState("");
  const [siteOptions, setSiteOptions] = useState([]);
  const [siteCreateOpen, setSiteCreateOpen] = useState(false);
  const [siteSaving, setSiteSaving] = useState(false);
  const [siteDraft, setSiteDraft] = useState({ nome: "Sede installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" });
  const [shippingDate, setShippingDate] = useState(todayISO());
  const [notes, setNotes] = useState("");
''',
    "stato cliente/sede spedizioni",
)

shipment_helpers = r'''  const clientDisplayName = (c) => c?.ragione_sociale || [c?.nome, c?.cognome].filter(Boolean).join(" ") || c?.nome_struttura || "Cliente";
  const siteDisplayName = (s) => [s?.nome, [s?.indirizzo, s?.civico].filter(Boolean).join(" "), s?.comune].filter(Boolean).join(" · ") || "Sede";
  const normText = (v) => String(v || "").trim().toLocaleLowerCase("it-IT");

  const loadSitesForClient = async (clientId) => {
    if (!clientId) { setSiteOptions([]); return; }
    try {
      const { data } = await axios.get(`${API}/crm/sedi`, { params: { q: clientId } });
      setSiteOptions((data.items || []).filter((s) => String(s.cliente_id || "") === String(clientId)));
    } catch {
      setSiteOptions([]);
    }
  };

  const selectShippingClient = async (c) => {
    const label = clientDisplayName(c);
    setCliente(label);
    setClienteClientId(c.id);
    setClienteOpen(false);
    setClienteSuggestions([]);
    setSedeId(""); setSedeLabel(""); setSiteCreateOpen(false);
    await loadSitesForClient(c.id);
  };

  const createShippingClient = async () => {
    const name = String(clientDraft.ragione_sociale || "").trim();
    if (!name) return toast.error("Ragione sociale / nome cliente obbligatorio");
    const email = normText(clientDraft.email);
    const phone = normText(clientDraft.telefono).replace(/\s+/g, "");
    const existing = clienteSuggestions.find((c) => normText(clientDisplayName(c)) === normText(name) || (email && normText(c.email) === email) || (phone && normText(c.telefono).replace(/\s+/g, "") === phone));
    if (existing) {
      await selectShippingClient(existing);
      setClientCreateOpen(false);
      toast.info("Cliente già presente: selezionata l'anagrafica esistente");
      return;
    }
    setClientSaving(true);
    try {
      const { data } = await axios.post(`${API}/crm/clienti`, {
        tipo: clientDraft.tipo || "Azienda",
        ragione_sociale: name,
        telefono: String(clientDraft.telefono || "").trim(),
        email: String(clientDraft.email || "").trim(),
      });
      await selectShippingClient(data);
      setClientCreateOpen(false);
      toast.success("Cliente creato e selezionato");
    } catch (e) {
      toast.error("Creazione cliente non riuscita", { description: e?.response?.data?.detail || e?.message || "" });
    } finally { setClientSaving(false); }
  };

  const createShippingSite = async () => {
    if (!clienteClientId) return toast.error("Seleziona o crea prima il cliente");
    if (!String(siteDraft.nome || "").trim() || !String(siteDraft.indirizzo || "").trim() || !String(siteDraft.comune || "").trim()) return toast.error("Nome sede, indirizzo e comune sono obbligatori");
    const existing = siteOptions.find((s) => normText(s.nome) === normText(siteDraft.nome) && normText(s.indirizzo) === normText(siteDraft.indirizzo) && normText(s.comune) === normText(siteDraft.comune));
    if (existing) {
      setSedeId(existing.id); setSedeLabel(siteDisplayName(existing)); setSiteCreateOpen(false);
      toast.info("Sede già presente: selezionata quella esistente");
      return;
    }
    setSiteSaving(true);
    try {
      const { data } = await axios.post(`${API}/crm/sedi`, { cliente_id: clienteClientId, tipo: "Installazione", ...siteDraft });
      setSiteOptions((p) => [...p, data]); setSedeId(data.id); setSedeLabel(siteDisplayName(data)); setSiteCreateOpen(false);
      toast.success("Sede creata e selezionata");
    } catch (e) {
      toast.error("Creazione sede non riuscita", { description: e?.response?.data?.detail || e?.message || "" });
    } finally { setSiteSaving(false); }
  };

'''
insert_before(checklist, "  // F8 — Sostituisce la data locale con quella del server nel tz configurato.", shipment_helpers, "helper cliente/sede spedizioni")

replace_once(checklist, "    if (!clienteOrderId && cliente.trim()) {", "    if (!clienteClientId && cliente.trim()) {", "conferma nominativo libero")
replace_once(
    checklist,
    '''        structure: cliente.trim(),
        order_page_id: clienteOrderId || null,
        taken_by: operatorName,''',
    '''        structure: cliente.trim(),
        order_page_id: null,
        cliente_id: clienteClientId || null,
        sede_id: sedeId || null,
        sede_label: sedeLabel || null,
        taken_by: operatorName,''',
    "payload spedizione cliente/sede",
)
replace_once(
    checklist,
    '''      setCliente("");
      setClienteOrderId(null);
      setClienteSuggestions([]);''',
    '''      setCliente("");
      setClienteClientId(null);
      setClienteSuggestions([]);
      setSedeId("");
      setSedeLabel("");
      setSiteOptions([]);
      setClientCreateOpen(false);
      setSiteCreateOpen(false);''',
    "reset cliente/sede spedizione",
)

new_general_section = r'''        {/* Dati generali */}
        <section className="bg-white border border-slate-200 rounded-md p-4 sm:p-6">
          <div className="text-xs tracking-[0.1em] uppercase text-slate-500 font-semibold mb-4">Dati Generali</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
            <div>
              <Label htmlFor="warehouse" className="text-slate-700 text-sm font-semibold"><Package size={14} className="inline mr-1" /> Magazzino di partenza</Label>
              <select id="warehouse" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} className="h-12 mt-1 w-full rounded-md border border-slate-200 bg-white px-3 text-base">
                {WAREHOUSES.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>

            <div>
              <Label htmlFor="cliente" className="text-slate-700 text-sm font-semibold"><Buildings size={14} className="inline mr-1" /> Cliente</Label>
              <div className="relative mt-1">
                <Input
                  id="cliente"
                  data-testid="input-structure"
                  value={cliente}
                  onChange={(e) => {
                    const v = e.target.value;
                    setCliente(v); setClienteClientId(null); setSedeId(""); setSedeLabel(""); setSiteOptions([]); setClienteOpen(true);
                    if (window.__cliSug) clearTimeout(window.__cliSug);
                    window.__cliSug = setTimeout(async () => {
                      const q = v.trim();
                      if (q.length < 2) { setClienteSuggestions([]); return; }
                      setClienteLoading(true);
                      try {
                        const { data } = await axios.get(`${API}/crm/clienti`, { params: { q } });
                        setClienteSuggestions(data.items || []);
                      } catch { setClienteSuggestions([]); }
                      finally { setClienteLoading(false); }
                    }, 220);
                  }}
                  onFocus={() => cliente.trim().length >= 2 && setClienteOpen(true)}
                  onBlur={() => setTimeout(() => setClienteOpen(false), 180)}
                  autoComplete="off"
                  placeholder="Scrivi nome o azienda..."
                  className="h-12 text-base pr-9"
                />
                {clienteClientId && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-emerald-600" title="Cliente collegato"><Check size={16} weight="bold" /></span>}
                {clienteOpen && cliente.trim().length >= 2 && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-xl max-h-72 overflow-auto" data-testid="cliente-suggestions">
                    {clienteLoading && <div className="px-3 py-2 text-xs text-slate-400">Cerco…</div>}
                    {!clienteLoading && clienteSuggestions.length === 0 && <div className="px-3 py-3 text-sm text-slate-500" data-testid="cliente-no-results">Nessun cliente esistente trovato</div>}
                    {clienteSuggestions.map((c) => <button key={c.id} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => selectShippingClient(c)} className="w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-100 min-h-[44px]" data-testid={`cliente-sug-${c.id}`}><div className="font-semibold text-sm text-slate-900">{clientDisplayName(c)}</div><div className="text-xs text-slate-500 truncate">{[c.telefono,c.email,c.partita_iva].filter(Boolean).join(" · ")}</div></button>)}
                    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => { setClientDraft({ tipo:"Azienda", ragione_sociale:cliente, telefono:"", email:"" }); setClientCreateOpen(true); setClienteOpen(false); }} className="w-full text-left px-3 py-3 font-semibold text-blue-700 hover:bg-blue-50">+ Aggiungi nuovo cliente</button>
                  </div>
                )}
              </div>
              {!clienteClientId && cliente.trim().length >= 2 && <p className="text-[11px] text-amber-700 mt-1">Puoi selezionare/creare il cliente oppure continuare come nominativo libero.</p>}
            </div>

            <div>
              <Label className="text-slate-700 text-sm font-semibold"><Buildings size={14} className="inline mr-1" /> Sede / destinazione</Label>
              <div className="flex gap-2 mt-1">
                <select value={sedeId} onChange={(e) => { const id=e.target.value; setSedeId(id); const s=siteOptions.find(x=>String(x.id)===String(id)); setSedeLabel(s?siteDisplayName(s):""); }} disabled={!clienteClientId} className="h-12 min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-2 text-sm disabled:bg-slate-100">
                  <option value="">{clienteClientId ? "Da definire" : "Seleziona cliente"}</option>
                  {siteOptions.map((s)=><option key={s.id} value={s.id}>{siteDisplayName(s)}</option>)}
                </select>
                {clienteClientId && <Button type="button" variant="outline" className="h-12 px-3" onClick={() => { setSiteDraft({nome:"Sede installazione",indirizzo:"",civico:"",cap:"",comune:"",provincia:"",telefono:""}); setSiteCreateOpen(true); }}>+</Button>}
              </div>
            </div>

            <div>
              <Label className="text-slate-700 text-sm font-semibold"><User size={14} className="inline mr-1" /> Operatore</Label>
              <div className="h-12 mt-1 px-3 flex items-center border border-slate-200 bg-slate-50 rounded-md text-slate-900 font-semibold" data-testid="operator-readonly" title="L'operatore è determinato dal login (non modificabile)">{operatorName || "—"}<span className="ml-auto text-[10px] uppercase tracking-wider text-slate-400">auto</span></div>
            </div>

            <div>
              <Label htmlFor="date" className="text-slate-700 text-sm font-semibold"><CalendarBlank size={14} className="inline mr-1" /> Data</Label>
              <Input id="date" data-testid="input-date" type="date" value={shippingDate} onChange={(e) => setShippingDate(e.target.value)} className="h-12 mt-1 text-base" />
            </div>
          </div>

          {clientCreateOpen && <div className="mt-4 rounded-md border border-blue-200 bg-blue-50/50 p-4"><div className="font-semibold text-slate-900 mb-3">Nuovo cliente</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div><Label>Tipo</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-2" value={clientDraft.tipo} onChange={(e)=>setClientDraft(p=>({...p,tipo:e.target.value}))}><option>Azienda</option><option>Privato</option></select></div><div><Label>Ragione sociale / Nome *</Label><Input className="mt-1 h-11" value={clientDraft.ragione_sociale} onChange={(e)=>setClientDraft(p=>({...p,ragione_sociale:e.target.value}))}/></div><div><Label>Telefono</Label><Input className="mt-1 h-11" value={clientDraft.telefono} onChange={(e)=>setClientDraft(p=>({...p,telefono:e.target.value}))}/></div><div><Label>Email</Label><Input type="email" className="mt-1 h-11" value={clientDraft.email} onChange={(e)=>setClientDraft(p=>({...p,email:e.target.value}))}/></div></div><div className="flex justify-end gap-2 mt-3"><Button type="button" variant="outline" onClick={()=>setClientCreateOpen(false)}>Annulla</Button><Button type="button" onClick={createShippingClient} disabled={clientSaving}>{clientSaving?"Creazione…":"Crea e seleziona"}</Button></div></div>}

          {siteCreateOpen && <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50/40 p-4"><div className="font-semibold text-slate-900 mb-3">Nuova sede</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div><Label>Nome sede *</Label><Input className="mt-1 h-11" value={siteDraft.nome} onChange={(e)=>setSiteDraft(p=>({...p,nome:e.target.value}))}/></div><div><Label>Indirizzo *</Label><Input className="mt-1 h-11" value={siteDraft.indirizzo} onChange={(e)=>setSiteDraft(p=>({...p,indirizzo:e.target.value}))}/></div><div><Label>Civico</Label><Input className="mt-1 h-11" value={siteDraft.civico} onChange={(e)=>setSiteDraft(p=>({...p,civico:e.target.value}))}/></div><div><Label>Comune *</Label><Input className="mt-1 h-11" value={siteDraft.comune} onChange={(e)=>setSiteDraft(p=>({...p,comune:e.target.value}))}/></div><div><Label>CAP</Label><Input className="mt-1 h-11" value={siteDraft.cap} onChange={(e)=>setSiteDraft(p=>({...p,cap:e.target.value}))}/></div><div><Label>Provincia</Label><Input className="mt-1 h-11" value={siteDraft.provincia} onChange={(e)=>setSiteDraft(p=>({...p,provincia:e.target.value}))}/></div><div><Label>Telefono sede</Label><Input className="mt-1 h-11" value={siteDraft.telefono} onChange={(e)=>setSiteDraft(p=>({...p,telefono:e.target.value}))}/></div></div><div className="flex justify-end gap-2 mt-3"><Button type="button" variant="outline" onClick={()=>setSiteCreateOpen(false)}>Annulla</Button><Button type="button" onClick={createShippingSite} disabled={siteSaving}>{siteSaving?"Creazione…":"Crea e seleziona"}</Button></div></div>}
        </section>'''
replace_between(checklist, "        {/* Dati generali */}", "\n\n        {/* ScannerBar sempre in alto */}", new_general_section, "dati generali spedizioni")

replace_once(
    checklist,
    '{ label: "Cliente", value: cliente.trim() },\n          { label: "Preso da (Operatore loggato)", value: operatorName },',
    '{ label: "Cliente", value: cliente.trim() },\n          { label: "Sede", value: sedeLabel || "—" },\n          { label: "Preso da (Operatore loggato)", value: operatorName },',
    "riepilogo sede spedizione",
)
replace_once(
    checklist,
    'Il cliente/struttura <b>{cliente}</b> non è collegato a un ordine cliente registrato. Continuare comunque?',
    'Il nominativo <b>{cliente}</b> non è collegato all’anagrafica clienti. Puoi continuare comunque oppure tornare indietro e usare “Aggiungi nuovo cliente”.',
    "testo nominativo libero",
)

if "clienteOrderId" in read(checklist):
    raise RuntimeError("ChecklistPage.jsx: è rimasto un riferimento legacy clienteOrderId")
if "`${API}/orders/search`" in read(checklist):
    raise RuntimeError("ChecklistPage.jsx: è rimasta la ricerca errata /orders/search")


# -----------------------------------------------------------------------------
# 4) Backend spedizioni: persiste il collegamento facoltativo cliente/sede.
# -----------------------------------------------------------------------------
server = "backend/server.py"
replace_once(
    server,
    '''    order_page_id: Optional[str] = None
    model_config = ConfigDict(extra="ignore")
    operator: str''',
    '''    order_page_id: Optional[str] = None
    cliente_id: Optional[str] = None
    sede_id: Optional[str] = None
    sede_label: Optional[str] = None
    model_config = ConfigDict(extra="ignore")
    operator: str''',
    "campi cliente/sede ChecklistPayload",
)
replace_once(
    server,
    '''    shipping_date: str
    structure: str
    taken_by: str = ""
    items: List[ProductItem]''',
    '''    shipping_date: str
    structure: str
    cliente_id: Optional[str] = None
    sede_id: Optional[str] = None
    sede_label: Optional[str] = None
    taken_by: str = ""
    items: List[ProductItem]''',
    "campi cliente/sede ChecklistRecord",
)
replace_once(
    server,
    '''        shipping_date=payload.shipping_date,
        structure=payload.structure,
        taken_by=payload.taken_by,''',
    '''        shipping_date=payload.shipping_date,
        structure=payload.structure,
        cliente_id=payload.cliente_id,
        sede_id=payload.sede_id,
        sede_label=payload.sede_label,
        taken_by=payload.taken_by,''',
    "persistenza cliente/sede spedizione",
)


# -----------------------------------------------------------------------------
# 5) Fatturato/Wallbox: endpoint analitico per singolo ordine.
#    I clienti legacy senza ordini restano visibili una sola volta come fallback.
# -----------------------------------------------------------------------------
crm = "backend/routes/crm_routes.py"
analytics_endpoint = r'''    @router.get("/ordini-insights")
    async def ordini_insights(current=Depends(dep)):
        """Dataset analitico non aggregato: una riga per ordine e per la sua data reale.

        Evita l'errore del vecchio riepilogo clienti che sommava tutti gli ordini di un
        cliente e attribuiva il totale all'ultima data firma. I record legacy presenti
        solo sull'anagrafica cliente vengono mantenuti come fallback, senza duplicare
        i clienti che hanno già ordini reali.
        """
        clients_task = db.crm_clienti.find(
            {"archived": {"$ne": True}},
            {"_id": 0, "id": 1, "ragione_sociale": 1, "nome_struttura": 1, "nome": 1, "cognome": 1,
             "data_firma": 1, "capitale": 1, "qty_wb": 1}
        ).to_list(length=10000)
        orders_task = db.crm_ordini_clienti.find(
            {},
            {"_id": 0, "id": 1, "numero": 1, "cliente_id": 1, "nominativo": 1, "cliente": 1,
             "data_firma": 1, "data": 1, "importo": 1, "qty_wb": 1,
             "stato": 1, "stato_commerciale": 1, "stato_finanziaria": 1}
        ).to_list(length=20000)
        clients, orders = await asyncio.gather(clients_task, orders_task)

        def client_name(c: Dict[str, Any]) -> str:
            return str(c.get("ragione_sociale") or c.get("nome_struttura") or " ".join(x for x in [c.get("nome"), c.get("cognome")] if x) or "Cliente").strip()

        by_id = {str(c.get("id") or ""): c for c in clients}
        clients_with_orders = {str(o.get("cliente_id") or "") for o in orders if o.get("cliente_id")}
        items: List[Dict[str, Any]] = []
        for o in orders:
            cid = str(o.get("cliente_id") or "")
            c = by_id.get(cid) or {}
            date = str(o.get("data_firma") or o.get("data") or "")[:10]
            items.append({
                "id": o.get("id"), "ordine_id": o.get("id"), "numero": o.get("numero"),
                "cliente_id": cid or None,
                "cliente": client_name(c) if c else (o.get("nominativo") or o.get("cliente") or "Cliente"),
                "data_firma": date,
                "fatturato": float(o.get("importo") or 0),
                "wallbox": float(o.get("qty_wb") or 0),
                "stato": o.get("stato_commerciale") or o.get("stato") or "",
                "stato_finanziaria": o.get("stato_finanziaria") or "",
                "source": "ordine",
            })

        for c in clients:
            cid = str(c.get("id") or "")
            if cid in clients_with_orders:
                continue
            amount = c.get("capitale")
            wb = c.get("qty_wb")
            date = str(c.get("data_firma") or "")[:10]
            if not date and amount in (None, "", 0, 0.0) and wb in (None, "", 0, 0.0):
                continue
            items.append({
                "id": f"legacy:{cid}", "ordine_id": None, "numero": None,
                "cliente_id": cid, "cliente": client_name(c), "data_firma": date,
                "fatturato": float(amount or 0), "wallbox": float(wb or 0),
                "stato": "", "stato_finanziaria": "", "source": "legacy_cliente",
            })

        items.sort(key=lambda x: (str(x.get("data_firma") or ""), str(x.get("numero") or x.get("id") or "")), reverse=True)
        return {"items": items, "count": len(items)}

'''
insert_before(crm, '    @router.get("/clienti-summary")', analytics_endpoint, "endpoint ordini insights")

insights = "frontend/src/pages/CommesseInsightsPage.jsx"
new_insights = r'''import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from "recharts";
import { ChartBar, Lightning, CalendarBlank, TrendUp, Receipt } from "@phosphor-icons/react";

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
        const { data } = await axios.get(`${API}/crm/ordini-insights`);
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
    const out = MONTHS.map((name, i) => ({ name, month: i + 1, fatturato: 0, wallbox: 0, ordini: 0 }));
    for (const r of filtered) {
      const m = getMonth(r.data_firma);
      if (m == null || m < 0 || m > 11) continue;
      out[m].fatturato += Number(r.fatturato || 0);
      out[m].wallbox += Number(r.wallbox || 0);
      out[m].ordini += r.source === "ordine" ? 1 : 0;
    }
    return out;
  }, [filtered]);
  const yearly = useMemo(() => years.slice().sort((a, b) => a - b).map((y) => {
    const yr = rows.filter((r) => getYear(r.data_firma) === y);
    return {
      year: String(y),
      fatturato: yr.reduce((s, r) => s + Number(r.fatturato || 0), 0),
      wallbox: yr.reduce((s, r) => s + Number(r.wallbox || 0), 0),
    };
  }), [rows, years]);

  const annualRevenue = filtered.reduce((s, r) => s + Number(r.fatturato || 0), 0);
  const annualWb = filtered.reduce((s, r) => s + Number(r.wallbox || 0), 0);
  const orderCount = filtered.filter((r) => r.source === "ordine").length;
  const uniqueClients = new Set(filtered.filter((r) => Number(mode === "fatturato" ? r.fatturato : r.wallbox) > 0).map((r) => r.cliente_id || r.cliente)).size;
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
        <div className="r52-commandbar-subtitle">Ogni ordine è attribuito alla propria data firma/data ordine. I valori non vengono più spostati sull'ultima data del cliente; i record legacy senza ordine restano come fallback.</div>
      </div>
      <div className="r52-commandbar-actions">
        <CalendarBlank size={17} className="text-slate-400" />
        <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold">
          {years.length ? years.map((y) => <option key={y} value={y}>{y}</option>) : <option value={year}>{year}</option>}
        </select>
      </div>
    </div>

    {loading ? <div className="r52-empty-state">Caricamento dati…</div> : !filtered.length ? <div className="r52-empty-state">Nessun dato disponibile per {year}.</div> : <>
      <div className="r52-insight-metrics-grid">
        <Metric label={isRevenue ? "Valore ordini anno" : "Wallbox anno"} value={isRevenue ? euro(annualRevenue) : annualWb.toLocaleString("it-IT")} sub={String(year)} Icon={Icon} />
        <Metric label="Ordini registrati" value={String(orderCount)} sub="con data nel periodo" Icon={Receipt} />
        <Metric label="Mesi con attività" value={String(activeMonths)} sub="su 12 mesi" Icon={CalendarBlank} />
        <Metric label={isRevenue ? "Clienti con valore" : "Clienti con wallbox"} value={String(uniqueClients)} sub="clienti distinti" Icon={TrendUp} />
      </div>

      <section className="r52-panel r52-chart-panel">
        <div className="r52-panel-heading"><div><div className="r52-section-kicker">Mensile</div><h2>{isRevenue ? "Valore ordini per mese" : "Wallbox per mese"}</h2><p>Distribuzione calcolata sulla data del singolo ordine.</p></div><Icon size={23} className="text-[#1A456B]" /></div>
        <div className="r52-chart-body"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthly} margin={{ top: 12, right: 12, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7edf3" /><XAxis dataKey="name" /><YAxis allowDecimals={!isRevenue ? false : undefined} tickFormatter={yTick} /><Tooltip formatter={tooltipFormatter} /><Bar dataKey={dataKey} fill="#2d6ea3" radius={[7, 7, 0, 0]} /></BarChart></ResponsiveContainer></div>
      </section>

      <section className="r52-panel r52-chart-panel">
        <div className="r52-panel-heading"><div><div className="r52-section-kicker">Storico</div><h2>{isRevenue ? "Andamento valore ordini annuale" : "Andamento wallbox annuale"}</h2><p>Confronto tra gli anni presenti nel database, senza aggregazioni per ultima data cliente.</p></div></div>
        <div className="r52-chart-body smaller"><ResponsiveContainer width="100%" height="100%"><LineChart data={yearly} margin={{ top: 12, right: 18, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e7edf3" /><XAxis dataKey="year" /><YAxis allowDecimals={!isRevenue ? false : undefined} tickFormatter={yTick} /><Tooltip formatter={tooltipFormatter} /><Line type="monotone" dataKey={dataKey} stroke="#2d6ea3" strokeWidth={3} dot={{ r: 4, fill: "#f6c344", stroke: "#1a456b", strokeWidth: 2 }} /></LineChart></ResponsiveContainer></div>
      </section>
    </>}
  </div>;
}
'''
write(insights, new_insights)


# -----------------------------------------------------------------------------
# 6) Versione e controlli strutturali locali del patcher.
# -----------------------------------------------------------------------------
write("VERSION", "R5\n")

checks = {
    "frontend/src/pages/ChecklistPage.jsx": ["/crm/clienti", "+ Aggiungi nuovo cliente", "sede_label: sedeLabel || null"],
    "frontend/src/pages/PreventiviPage.jsx": ["Crea e seleziona", "+ Nuova", "localSites"],
    "frontend/src/pages/RegistryPage.jsx": ["inlineCreateClient", "saveInlineClient", "Nuovo cliente"],
    "backend/routes/crm_routes.py": ["/ordini-insights", "source\": \"legacy_cliente"],
    "frontend/src/pages/CommesseInsightsPage.jsx": ["/crm/ordini-insights", "Ordini registrati"],
}
for rel, needles in checks.items():
    body = read(rel)
    for needle in needles:
        if needle not in body:
            raise RuntimeError(f"{rel}: controllo finale mancante: {needle}")

print("R5 patch applicata correttamente")
