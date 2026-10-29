from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: attesa 1 occorrenza, trovate {count}\n--- target ---\n{old[:500]}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Sopralluoghi: il testo libero resta prospect; non creare clienti dal form.
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '      F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", inlineCreateClient: true, clearOnChange: ["sede_id"] }),',
    '      F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", clearOnChange: ["sede_id"], help: "Se non selezioni un cliente esistente, il nominativo resta un prospect e non viene creata alcuna anagrafica cliente." }),',
)
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''    columns={[
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("sede_id", "Sede", SITE_LOOKUP),
      F("data", "Data"),
      F("tecnico", "Tecnico"),
      F("stato", "Stato"),
    ]}
  />
  );
};''',
    '''    columns={[
      F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, fallbackKey: "nominativo" }),
      F("sede_id", "Sede", SITE_LOOKUP),
      F("data", "Data"),
      F("tecnico", "Tecnico"),
      F("stato", "Stato"),
    ]}
  />
  );
};''',
)

# 2) RegistryPage: mostra il prospect nelle tabelle e messaggio coerente senza pulsante crea-cliente.
replace_once(
    "frontend/src/pages/RegistryPage.jsx",
    '''  const displayCell = (column, row) => {
    if (lookupKey(column)) return resolveLookup(column, row[column.key]);
    if (fields.some((field) => field.key === column.key && field.type === "date")) return formatDateIT(row[column.key]) || "—";
    return (row[column.key] ?? "—") || "—";
  };''',
    '''  const displayCell = (column, row) => {
    if (lookupKey(column)) {
      const rawValue = row[column.key];
      if (!rawValue && column.fallbackKey && row[column.fallbackKey]) return row[column.fallbackKey];
      const resolved = resolveLookup(column, rawValue);
      if (resolved === "Record non trovato" && column.fallbackKey && row[column.fallbackKey]) return row[column.fallbackKey];
      return resolved;
    }
    if (fields.some((field) => field.key === column.key && field.type === "date")) return formatDateIT(row[column.key]) || "—";
    return (row[column.key] ?? "—") || "—";
  };''',
)
replace_once(
    "frontend/src/pages/RegistryPage.jsx",
    '''                        {f.allowFreeText && !form[f.key] && lookupTextValue(f) && <div className="text-xs text-amber-700 mt-1">Puoi lasciarlo come prospect oppure usare “Aggiungi nuovo cliente” per creare subito l’anagrafica e la sede.</div>}''',
    '''                        {f.allowFreeText && !form[f.key] && lookupTextValue(f) && <div className="text-xs text-amber-700 mt-1">{f.inlineCreateClient ? "Puoi lasciarlo come prospect oppure creare subito l’anagrafica cliente." : "Verrà salvato come prospect. Non viene creata alcuna anagrafica cliente."}</div>}''',
)

# 3) Preventivi: il campo Cliente è ricerca + prospect, senza creazione anagrafica inline.
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''  const [clientCreateOpen,setClientCreateOpen]=useState(false);
  const [clientCreating,setClientCreating]=useState(false);
  const [clientDraft,setClientDraft]=useState({tipo:"Azienda",ragione_sociale:"",telefono:"",email:""});
''',
    '',
)
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''      setClientSearch(item?.cliente_id ? clientName((clients||[]).find(c=>c.id===item.cliente_id)) : "");
      setClientCreateOpen(false); setSiteCreateOpen(false);''',
    '''      setClientSearch(item?.cliente_id ? clientName((clients||[]).find(c=>c.id===item.cliente_id)) : (item?.nominativo || ""));
      setSiteCreateOpen(false);''',
)
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''  const selectClient=(c)=>{
    setForm(p=>({...p,cliente_id:c.id,nominativo:"",sede_id:"",telefono:p.telefono||c.telefono||"",email:p.email||c.email||""}));
    setClientSearch(clientName(c));
    setClientCreateOpen(false);
  };

  const createClient=async()=>{
    const name=String(clientDraft.ragione_sociale||"").trim();
    if(!name) return toast.error("Ragione sociale / nome cliente obbligatorio");
    const email=norm(clientDraft.email); const phone=norm(clientDraft.telefono).replace(/\\s+/g,"");
    const existing=localClients.find(c=>norm(clientName(c))===norm(name)||(email&&norm(c.email)===email)||(phone&&norm(c.telefono).replace(/\\s+/g,"")===phone));
    if(existing){ selectClient(existing); toast.info("Cliente già presente: selezionata l'anagrafica esistente"); return; }
    setClientCreating(true);
    try{
      const payload={tipo:clientDraft.tipo||"Azienda",ragione_sociale:name,telefono:String(clientDraft.telefono||"").trim(),email:String(clientDraft.email||"").trim()};
      const {data}=await axios.post(`${API}/crm/clienti`,payload);
      setLocalClients(p=>[...p,data]); selectClient(data); toast.success("Cliente creato e selezionato");
    }catch(e){toast.error("Creazione cliente non riuscita",{description:errText(e)})}finally{setClientCreating(false)}
  };
''',
    '''  const selectClient=(c)=>{
    setForm(p=>({...p,cliente_id:c.id,nominativo:"",sede_id:"",sopralluogo_id:"",telefono:p.telefono||c.telefono||"",email:p.email||c.email||""}));
    setClientSearch(clientName(c));
  };
''',
)
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''  const selectSurvey=(id)=>{const s=surveys.find(x=>String(x.id)===String(id)); setForm(p=>({...p,sopralluogo_id:id,cliente_id:p.cliente_id||s?.cliente_id||"",sede_id:p.sede_id||s?.sede_id||""}));};''',
    '''  const selectSurvey=(id)=>{
    const s=surveys.find(x=>String(x.id)===String(id));
    if(!s){ set("sopralluogo_id",id); return; }
    const linkedClient=s.cliente_id ? localClients.find(c=>String(c.id)===String(s.cliente_id)) : null;
    setForm(p=>({...p,
      sopralluogo_id:id,
      cliente_id:s.cliente_id||p.cliente_id||"",
      nominativo:s.cliente_id ? "" : (s.nominativo||p.nominativo||""),
      telefono:p.telefono||s.telefono||"",
      email:p.email||s.email||"",
      sede_id:s.sede_id||p.sede_id||"",
    }));
    if(linkedClient) setClientSearch(clientName(linkedClient));
    else if(s.nominativo) setClientSearch(s.nominativo);
  };''',
)
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''    if (!(await appConfirm({ title: "Accetta preventivo", message: `Confermi il preventivo ${quote.numero || ""}?`, confirmLabel: "Accetta" }))) return;''',
    '''    const acceptMessage = quote.cliente_id
      ? `Confermi il preventivo ${quote.numero || ""}?`
      : `Confermi il preventivo ${quote.numero || ""}? Il prospect ${quote.nominativo ? `“${quote.nominativo}”` : ""} verrà registrato come cliente solo ora e verrà creata la commessa.`;
    if (!(await appConfirm({ title: "Accetta preventivo", message: acceptMessage, confirmLabel: "Accetta" }))) return;''',
)
replace_once(
    "frontend/src/pages/PreventiviPage.jsx",
    '''      <div className="lg:col-span-2 relative"><Label>Cliente</Label><Input className="mt-1 h-12" value={clientSearch} onChange={e=>{setClientSearch(e.target.value); if(form.cliente_id)setForm(p=>({...p,cliente_id:"",sede_id:""}))}} placeholder="Scrivi nome, azienda, telefono, email o P.IVA..." autoComplete="off"/>{clientSearch&&!form.cliente_id&&<div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-64 overflow-auto">{filteredClients.map(c=><button type="button" key={c.id} onMouseDown={e=>e.preventDefault()} onClick={()=>selectClient(c)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-100"><b>{clientName(c)}</b><div className="text-xs text-slate-500">{[c.telefono,c.email,c.partita_iva].filter(Boolean).join(" · ")}</div></button>)}{!filteredClients.length&&<div className="px-3 py-2 text-sm text-slate-500">Nessun cliente esistente trovato.</div>}<button type="button" onMouseDown={e=>e.preventDefault()} onClick={()=>{setClientDraft({tipo:"Azienda",ragione_sociale:clientSearch,telefono:form.telefono||"",email:form.email||""});setClientCreateOpen(true)}} className="block w-full text-left px-3 py-3 font-semibold text-blue-700 hover:bg-blue-50">+ Aggiungi nuovo cliente</button></div>}<p className="text-[11px] text-slate-500 mt-1">Digita per cercare. Se non esiste, puoi crearlo qui senza uscire dal preventivo.</p></div>
      <div><Label>Oppure nominativo non ancora cliente</Label><Input className="mt-1 h-12" value={form.nominativo||""} onChange={e=>set("nominativo",e.target.value)} placeholder="Prospect / privato / azienda"/></div>

      {clientCreateOpen&&<div className="lg:col-span-3 rounded-md border border-blue-200 bg-blue-50/50 p-4"><div className="font-semibold text-slate-900 mb-3">Nuovo cliente</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3"><div><Label>Tipo</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-2" value={clientDraft.tipo} onChange={e=>setClientDraft(p=>({...p,tipo:e.target.value}))}><option>Azienda</option><option>Privato</option></select></div><div><Label>Ragione sociale / Nome *</Label><Input className="mt-1 h-11" value={clientDraft.ragione_sociale} onChange={e=>setClientDraft(p=>({...p,ragione_sociale:e.target.value}))}/></div><div><Label>Telefono</Label><Input className="mt-1 h-11" value={clientDraft.telefono} onChange={e=>setClientDraft(p=>({...p,telefono:e.target.value}))}/></div><div><Label>Email</Label><Input type="email" className="mt-1 h-11" value={clientDraft.email} onChange={e=>setClientDraft(p=>({...p,email:e.target.value}))}/></div></div><div className="flex justify-end gap-2 mt-3"><Button type="button" variant="outline" onClick={()=>setClientCreateOpen(false)}>Annulla</Button><Button type="button" onClick={createClient} disabled={clientCreating}>{clientCreating?"Creazione…":"Crea e seleziona"}</Button></div></div>}
''',
    '''      <div className="lg:col-span-3 relative"><Label>Cliente / prospect</Label><Input className="mt-1 h-12" value={clientSearch} onChange={e=>{const text=e.target.value;setClientSearch(text);setForm(p=>({...p,cliente_id:"",nominativo:text,sede_id:"",...(p.cliente_id?{sopralluogo_id:""}:{})}))}} placeholder="Scrivi nome, azienda, telefono, email o P.IVA..." autoComplete="off"/>{clientSearch&&!form.cliente_id&&<div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-64 overflow-auto">{filteredClients.map(c=><button type="button" key={c.id} onMouseDown={e=>e.preventDefault()} onClick={()=>selectClient(c)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-100"><b>{clientName(c)}</b><div className="text-xs text-slate-500">{[c.telefono,c.email,c.partita_iva].filter(Boolean).join(" · ")}</div></button>)}{!filteredClients.length&&<div className="px-3 py-3 text-sm text-amber-700">Nessun cliente registrato trovato: il nominativo verrà salvato come prospect.</div>}</div>}<p className="text-[11px] text-slate-500 mt-1">Seleziona un cliente esistente dai risultati. Se non lo selezioni, il testo resta un prospect e non crea alcuna anagrafica cliente.</p></div>
''',
)

# 4) Smoke test: sopralluogo e preventivo prospect NON devono creare clienti.
replace_once(
    "backend/integration_smoke.py",
    '''    inv = expect("GET", "/api/inventory", status=(200, 503), token=token)
    if inv.status_code == 503:
        print("[INFO] Inventario non configurato nel DB effimero: comportamento atteso")

    # CRUD Clienti.
''',
    '''    inv = expect("GET", "/api/inventory", status=(200, 503), token=token)
    if inv.status_code == 503:
        print("[INFO] Inventario non configurato nel DB effimero: comportamento atteso")

    # R11: sopralluoghi e preventivi di prospect non devono creare automaticamente un Cliente.
    clients_before_prospect = SYNC_DB.crm_clienti.count_documents({})
    prospect_survey = expect(
        "POST", "/api/crm/sopralluoghi", token=token,
        json={
            "nominativo": "Prospect Audit Non Cliente", "telefono": "+39 333 777 8899",
            "email": "prospect.audit@example.com", "indirizzo_libero": "Via Prospect 10, Piacenza",
            "data": "2026-10-24", "stato": "Da programmare",
        },
    ).json()
    assert prospect_survey.get("id") and not prospect_survey.get("cliente_id"), prospect_survey
    assert SYNC_DB.crm_clienti.count_documents({}) == clients_before_prospect

    prospect_quote = expect(
        "POST", "/api/crm/preventivi", token=token,
        json={
            "nominativo": "Prospect Audit Non Cliente", "telefono": "+39 333 777 8899",
            "email": "prospect.audit@example.com", "sopralluogo_id": prospect_survey["id"],
            "data": "2026-10-24", "stato": "Bozza",
            "righe": [{"tipo_riga": "servizio", "descrizione": "Offerta prospect", "quantity": 1, "prezzo_unitario": 100, "iva": 22}],
        },
    ).json()
    assert prospect_quote.get("id") and not prospect_quote.get("cliente_id"), prospect_quote
    assert prospect_quote.get("nominativo") == "Prospect Audit Non Cliente", prospect_quote
    assert SYNC_DB.crm_clienti.count_documents({}) == clients_before_prospect
    expect("DELETE", f"/api/crm/preventivi/{prospect_quote['id']}", token=token)
    expect("DELETE", f"/api/crm/sopralluoghi/{prospect_survey['id']}", token=token)

    # CRUD Clienti.
''',
)

Path("VERSION").write_text("R11\n", encoding="utf-8")
print("R11 patch applicata con successo")
