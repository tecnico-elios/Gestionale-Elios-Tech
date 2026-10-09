const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
function read(rel) { return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function write(rel, text) { fs.writeFileSync(path.join(ROOT, rel), text, 'utf8'); }
function replaceOnce(text, from, to, label) {
  if (text.includes(to)) return text;
  if (!text.includes(from)) throw new Error(`[R59] ${label}: blocco non trovato`);
  return text.replace(from, to);
}

// ---------------------------------------------------------------------------
// CALENDARIO — ruoli operativi liberi + gestione delegabile dall'Admin.
// R59 gira DOPO R58, quindi parte dalla versione trasformata con i quattro ruoli.
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/CalendarPage.jsx';
  let s = read(rel);

  s = replaceOnce(
    s,
    'const PERSON_ROLES = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"];',
    'const DEFAULT_PERSON_ROLES = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"];',
    'calendar default role suggestions'
  );

  s = replaceOnce(
    s,
    '  const canCreate = hasPermission("calendar", "create") || isAdmin;\n  const canEdit = hasPermission("calendar", "edit") || isAdmin;',
    '  const canCreate = hasPermission("calendar", "create") || isAdmin;\n  const canEdit = hasPermission("calendar", "edit") || isAdmin;\n  const canManagePeopleRoles = isAdmin || hasPermission("calendar", "manage_people_roles");\n  const personRoles = useMemo(() => Array.from(new Set([\n    ...DEFAULT_PERSON_ROLES,\n    ...resources.map((r) => String(r.role || "").trim()).filter(Boolean),\n  ])).sort((a, b) => a.localeCompare(b, "it")), [resources]);',
    'calendar delegated people permission'
  );

  s = replaceOnce(
    s,
    '{isAdmin && <Button variant="outline" onClick={() => setResourceDlg(true)}><Gear size={16} /> Persone</Button>}',
    '{canManagePeopleRoles && <Button variant="outline" onClick={() => setResourceDlg(true)}><Gear size={16} /> Persone e ruoli</Button>}',
    'calendar people button permission'
  );

  s = replaceOnce(
    s,
    '<select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm" value={resource.role || "Tecnico"} onChange={(e) => updateResource(resource, { role: e.target.value })} aria-label={`Ruolo di ${resource.name}`}>{PERSON_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
    '<Input list="calendar-role-options" value={resource.role || ""} onChange={(e) => setResources((prev) => prev.map((x) => x.id === resource.id ? { ...x, role: e.target.value } : x))} onBlur={() => updateResource(resource, { role: resources.find((x) => x.id === resource.id)?.role || "Tecnico" })} placeholder="Ruolo operativo" aria-label={`Ruolo di ${resource.name}`} />',
    'free role existing person'
  );

  s = replaceOnce(
    s,
    '<select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm" value={newResource.role} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))}>{PERSON_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
    '<Input list="calendar-role-options" value={newResource.role || ""} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))} placeholder="Ruolo operativo" />',
    'free role new person'
  );

  // Le occorrenze residue sono il filtro ruolo: usa l'elenco dinamico ricavato dalle persone.
  s = s.split('PERSON_ROLES.map').join('personRoles.map');

  s = replaceOnce(
    s,
    '<DialogHeader><DialogTitle>Persone e calendari</DialogTitle></DialogHeader>\n        <div className="space-y-3">',
    '<DialogHeader><DialogTitle>Persone e ruoli del calendario</DialogTitle></DialogHeader>\n        <datalist id="calendar-role-options">{personRoles.map((role) => <option key={role} value={role} />)}</datalist>\n        <div className="rounded-xl border border-blue-100 bg-blue-50/60 px-3 py-2 text-xs text-slate-600">Il ruolo è libero: puoi scrivere, ad esempio, <b>Direttore tecnico</b>, <b>Direttore commerciale</b> o qualsiasi altra funzione aziendale. I nuovi ruoli salvati diventano automaticamente disponibili nei filtri.</div>\n        <div className="space-y-3">',
    'calendar free roles helper'
  );

  write(rel, s);
}

// ---------------------------------------------------------------------------
// UTENTI — l'Admin può delegare la sola gestione persone/ruoli del calendario.
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/AdminUsersPage.jsx';
  let s = read(rel);

  s = replaceOnce(
    s,
    '    setPerms((Array.isArray(src) ? src : []).filter((p) => p === "installazioni:view_all" || (p.includes(":") && allowedPrefixes.has(p.split(":")[0]))));',
    '    setPerms((Array.isArray(src) ? src : []).filter((p) => p === "installazioni:view_all" || p === "calendar:manage_people_roles" || (p.includes(":") && allowedPrefixes.has(p.split(":")[0]))));',
    'admin preserve calendar special permission'
  );

  const installSpecial = '<label className="flex gap-3 items-start border rounded-lg p-3 bg-slate-50"><input type="checkbox" className="h-5 w-5 mt-0.5" checked={perms.includes("installazioni:view_all")} onChange={() => setPerms((p) => p.includes("installazioni:view_all") ? p.filter((x) => x !== "installazioni:view_all") : [...p, "installazioni:view_all", ...(p.includes("installazioni:view") ? [] : ["installazioni:view"])])} /><span><b className="text-sm">Installazioni · visualizza tutte</b><span className="block text-xs text-slate-500">Se disattivato, il tecnico vede solo le installazioni assegnate.</span></span></label>';
  const calendarSpecial = '<label className="flex gap-3 items-start border rounded-lg p-3 bg-blue-50/60 border-blue-100"><input type="checkbox" className="h-5 w-5 mt-0.5" checked={perms.includes("calendar:manage_people_roles")} onChange={() => setPerms((p) => p.includes("calendar:manage_people_roles") ? p.filter((x) => x !== "calendar:manage_people_roles") : [...p, "calendar:manage_people_roles", ...(p.includes("calendar:view") ? [] : ["calendar:view"])])} /><span><b className="text-sm">Calendario · gestisci persone e ruoli</b><span className="block text-xs text-slate-500">Consente di creare/modificare persone e ruoli operativi senza rendere l’utente Admin.</span></span></label>';
  if (!s.includes('Calendario · gestisci persone e ruoli')) {
    if (!s.includes(installSpecial)) throw new Error('[R59] checkbox permesso speciale installazioni non trovato');
    s = s.replace(installSpecial, `${calendarSpecial}${installSpecial}`);
  }

  write(rel, s);
}

// ---------------------------------------------------------------------------
// CLIENTI / ORDINI — PEC + SDI e filtri reali a scelta, non datalist ambigui.
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/EliosTechOrdiniPage.jsx';
  let s = read(rel);

  s = replaceOnce(
    s,
    '  email: "",\n  indirizzo: "",',
    '  email: "",\n  pec: "",\n  codice_sdi: "",\n  indirizzo: "",',
    'company PEC SDI state'
  );

  s = replaceOnce(
    s,
    '          <div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={form.email} onChange={(e) => set("email", e.target.value)} /></div>\n          <div><Label>Agente</Label>',
    '          <div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={form.email} onChange={(e) => set("email", e.target.value)} /></div>\n          {form.tipo === "Azienda" && <><div><Label>PEC</Label><Input type="email" className="mt-1 h-12" value={form.pec || ""} onChange={(e) => set("pec", e.target.value)} placeholder="pec@azienda.it" /></div><div><Label>Codice SDI</Label><Input className="mt-1 h-12 uppercase" maxLength={7} value={form.codice_sdi || ""} onChange={(e) => set("codice_sdi", e.target.value.toUpperCase())} placeholder="7 caratteri" /></div></>}\n          <div><Label>Agente</Label>',
    'company PEC SDI fields'
  );

  s = replaceOnce(
    s,
    '    let filtered = q ? clients.filter((c)=>[customerName(c),c.partita_iva,c.codice_fiscale,c.telefono,c.email,c.comune,c.provincia,c.agente,c.pagamento,c.data_firma,c.ultimo_stato,c.referente].some((v)=>String(v||"").toLowerCase().includes(q))) : [...clients];',
    '    let filtered = q ? clients.filter((c)=>[customerName(c),c.partita_iva,c.codice_fiscale,c.telefono,c.email,c.pec,c.codice_sdi,c.sdi,c.comune,c.provincia,c.agente,c.pagamento,c.data_firma,c.ultimo_stato,c.referente,...Object.values(c||{}).filter((v)=>["string","number"].includes(typeof v))].some((v)=>String(v||"").toLowerCase().includes(q))) : [...clients];',
    'client search all relevant fields'
  );

  s = replaceOnce(
    s,
    '      <div className="grid sm:grid-cols-3 gap-2">\n        <div><Input list="pay-filter" className="h-10" value={paymentFilter} onChange={e=>setPaymentFilter(e.target.value)} placeholder="Filtra pagamento…"/><datalist id="pay-filter">{paymentOptions.map(x=><option key={x} value={x}/>)}</datalist></div>\n        <div><Input list="agent-filter" className="h-10" value={agentFilter} onChange={e=>setAgentFilter(e.target.value)} placeholder="Filtra agente…"/><datalist id="agent-filter">{agentOptions.map(x=><option key={x} value={x}/>)}</datalist></div>\n        <div><Input list="status-filter" className="h-10" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} placeholder="Filtra stato…"/><datalist id="status-filter">{statusOptions.map(x=><option key={x} value={x}/>)}</datalist></div>\n      </div>',
    '      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-2">\n        <select className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" value={paymentFilter} onChange={e=>setPaymentFilter(e.target.value)}><option value="">Tutti i pagamenti</option>{paymentOptions.map(x=><option key={x} value={x}>{x}</option>)}</select>\n        <select className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" value={agentFilter} onChange={e=>setAgentFilter(e.target.value)}><option value="">Tutti gli agenti</option>{agentOptions.map(x=><option key={x} value={x}>{x}</option>)}</select>\n        <select className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}><option value="">Tutti gli stati</option>{statusOptions.map(x=><option key={x} value={x}>{x}</option>)}</select>\n        <Button type="button" variant="outline" className="h-10" onClick={()=>{setPaymentFilter("");setAgentFilter("");setStatusFilter("");setQuery("");}}>Azzera filtri</Button>\n      </div>',
    'real orders filters'
  );

  s = replaceOnce(
    s,
    '<Field label="Email" value={n.email || c.email}/><Field label="Indirizzo" value={n.indirizzo || c.indirizzo}/>',
    '<Field label="Email" value={n.email || c.email}/><Field label="PEC" value={n.pec || c.pec}/><Field label="Codice SDI" value={n.codice_sdi || n.sdi || c.codice_sdi || c.sdi}/><Field label="Indirizzo" value={n.indirizzo || c.indirizzo}/>',
    'company PEC SDI details'
  );

  write(rel, s);
}

console.log('[R59] calendario delegabile, ruoli liberi, PEC/SDI e filtri Clienti/Ordini applicati.');
