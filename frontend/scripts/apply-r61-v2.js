const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
// Valore letterale usato solo per costruire i frammenti JSX senza interpolarli durante questo script.
const API = '${API}';
function read(rel) { return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function write(rel, text) { fs.writeFileSync(path.join(ROOT, rel), text, 'utf8'); }
function replaceOnce(text, from, to, label) {
  if (text.includes(to)) return text;
  if (!text.includes(from)) throw new Error(`[R61] ${label}: blocco non trovato`);
  return text.replace(from, to);
}

{
  const rel = 'src/pages/CalendarPage.jsx';
  let s = read(rel);
  s = replaceOnce(s,
    '  const canManagePeopleRoles = isAdmin || hasPermission("calendar", "manage_people_roles");\n  const personRoles = useMemo(() => Array.from(new Set([\n    ...DEFAULT_PERSON_ROLES,\n    ...resources.map((r) => String(r.role || "").trim()).filter(Boolean),\n  ])).sort((a, b) => a.localeCompare(b, "it")), [resources]);',
    '  const canManagePeopleRoles = isAdmin || hasPermission("calendar", "manage_people_roles");\n  const [roleOptions, setRoleOptions] = useState(DEFAULT_PERSON_ROLES);\n  const [newRole, setNewRole] = useState("");\n  const personRoles = roleOptions;',
    'controlled calendar roles state');

  s = replaceOnce(s,
    '  }, []);\n\n  useEffect(() => { load(); }, [load]);',
    '  }, []);\n\n  const loadRoles = useCallback(async () => {\n    try {\n      const { data } = await axios.get(`${API}/calendar/roles`);\n      const items = (data.items || []).filter(Boolean);\n      setRoleOptions(items);\n      setNewResource((p) => ({ ...p, role: items.some((x) => x === p.role) ? p.role : (items[0] || "Tecnico") }));\n    } catch (error) {\n      toast.error("Ruoli calendario non disponibili", { description: error?.response?.data?.detail || error?.message });\n    }\n  }, []);\n\n  useEffect(() => { load(); }, [load]);\n  useEffect(() => { loadRoles(); }, [loadRoles]);',
    'load controlled calendar roles');

  s = replaceOnce(s,
    '  const addResource = async () => {',
    '  const addRole = async () => {\n    const name = newRole.trim();\n    if (!name) return toast.error("Inserisci il nome del ruolo");\n    try {\n      const { data } = await axios.post(`${API}/calendar/roles`, { name });\n      setRoleOptions(data.items || []);\n      setNewRole("");\n      toast.success(data.created === false ? "Ruolo già presente" : "Ruolo creato");\n    } catch (error) { toast.error("Creazione ruolo non riuscita", { description: error?.response?.data?.detail || error?.message }); }\n  };\n\n  const removeRole = async (role) => {\n    const ok = await appConfirm({ title: "Elimina ruolo", message: `Eliminare il ruolo “${role}”? È possibile solo se non è assegnato a nessuna persona.`, confirmLabel: "Elimina", danger: true });\n    if (!ok) return;\n    try {\n      const { data } = await axios.delete(`${API}/calendar/roles/${encodeURIComponent(role)}`);\n      setRoleOptions(data.items || []);\n      toast.success("Ruolo eliminato");\n    } catch (error) { toast.error("Ruolo non eliminato", { description: error?.response?.data?.detail || error?.message }); }\n  };\n\n  const addResource = async () => {',
    'calendar role actions');

  s = replaceOnce(s,
    '<Input list="calendar-role-options" value={resource.role || ""} onChange={(e) => setResources((prev) => prev.map((x) => x.id === resource.id ? { ...x, role: e.target.value } : x))} onBlur={() => updateResource(resource, { role: resources.find((x) => x.id === resource.id)?.role || "Tecnico" })} placeholder="Ruolo operativo" aria-label={`Ruolo di ${resource.name}`} />',
    '<select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-800" value={resource.role || personRoles[0] || "Tecnico"} onChange={(e) => updateResource(resource, { role: e.target.value })} aria-label={`Ruolo di ${resource.name}`}>{personRoles.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
    'existing person controlled role select');

  s = replaceOnce(s,
    '<Input list="calendar-role-options" value={newResource.role || ""} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))} placeholder="Ruolo operativo" />',
    '<select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-800" value={newResource.role || personRoles[0] || "Tecnico"} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))}>{personRoles.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
    'new person controlled role select');

  s = replaceOnce(s,
    '<DialogHeader><DialogTitle>Persone e ruoli del calendario</DialogTitle></DialogHeader>\n        <datalist id="calendar-role-options">{personRoles.map((role) => <option key={role} value={role} />)}</datalist>\n        <div className="rounded-xl border border-blue-100 bg-blue-50/60 px-3 py-2 text-xs text-slate-600">Il ruolo è libero: puoi scrivere, ad esempio, <b>Direttore tecnico</b>, <b>Direttore commerciale</b> o qualsiasi altra funzione aziendale. I nuovi ruoli salvati diventano automaticamente disponibili nei filtri.</div>\n        <div className="space-y-3">',
    '<DialogHeader><DialogTitle>Persone e ruoli del calendario</DialogTitle></DialogHeader>\n        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3">\n          <div><div className="text-sm font-black text-slate-900">Ruoli disponibili</div><div className="text-xs text-slate-500 mt-0.5">I ruoli si creano qui una volta sola. Poi possono essere soltanto assegnati alle persone da un Admin o da chi ha ricevuto il permesso dedicato.</div></div>\n          <div className="flex flex-wrap gap-2">{personRoles.map((role) => <span key={role} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700">{role}<button type="button" className="text-slate-400 hover:text-red-600" onClick={() => removeRole(role)} aria-label={`Elimina ruolo ${role}`}><Trash size={13}/></button></span>)}</div>\n          <div className="flex gap-2"><Input value={newRole} onChange={(e) => setNewRole(e.target.value)} placeholder="Nuovo ruolo, es. Tecnico interno" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRole(); } }} /><Button type="button" onClick={addRole}><Plus size={15}/> Aggiungi ruolo</Button></div>\n        </div>\n        <div className="space-y-3">',
    'calendar role management panel');
  write(rel, s);
}

{
  const rel = 'src/pages/InstallazioniCalendarPage.jsx';
  let s = read(rel);
  s = s.split('x.sede_nome || x.sede || x.indirizzo || "Sede da verificare"').join('x.sede_nome || x.sede || x.indirizzo_libero || x.indirizzo || "Sede da verificare"');
  s = s.split('x.sede_indirizzo_completo || x.sede_indirizzo || x.indirizzo || x.sede || ""').join('x.sede_indirizzo_completo || x.sede_indirizzo || x.indirizzo_libero || x.indirizzo || x.sede || ""');
  s = s.split('comune={x.sede_comune} provincia={x.sede_provincia} cap={x.sede_cap}').join('comune={x.sede_comune || x.comune_libero} provincia={x.sede_provincia || x.provincia_libera} cap={x.sede_cap || x.cap_libero}');
  s = s.split('selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo').join('selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo_libero || selected.indirizzo');
  s = s.split('comune={selected.sede_comune} provincia={selected.sede_provincia} cap={selected.sede_cap}').join('comune={selected.sede_comune || selected.comune_libero} provincia={selected.sede_provincia || selected.provincia_libera} cap={selected.sede_cap || selected.cap_libero}');
  s = s.split('selected.cliente_nome || selected.cliente || "—"').join('selected.cliente_nome || selected.cliente || selected.nominativo || "—"');
  s = replaceOnce(s,
    '<div className="rounded-xl border border-slate-200 p-3"><div className="text-[11px] uppercase font-bold text-slate-400">Tecnico</div><div className="font-bold mt-1">{selected.tecnico || "Da assegnare"}</div></div>\n            <div className="rounded-xl border border-slate-200 p-3 sm:col-span-2">',
    '<div className="rounded-xl border border-slate-200 p-3"><div className="text-[11px] uppercase font-bold text-slate-400">Tecnico</div><div className="font-bold mt-1">{selected.tecnico || "Da assegnare"}</div></div>\n            {(selected.referente || selected.telefono) && <div className="rounded-xl border border-slate-200 p-3 sm:col-span-2"><div className="text-[11px] uppercase font-bold text-slate-400">Referente installazione</div><div className="font-bold mt-1">{selected.referente || "—"}</div>{selected.telefono && <div className="text-sm text-slate-600 mt-0.5">{selected.telefono}</div>}</div>}\n            <div className="rounded-xl border border-slate-200 p-3 sm:col-span-2">',
    'installation contact card');
  write(rel, s);
}

{
  const rel = 'src/pages/NotionMigrationPage.jsx';
  let s = read(rel);
  const oldBlock = `    startPolling();
    try {
      const { data } = await axios.post(\`${API}/admin/notion/import-all\`, {}, { timeout: 30 * 60 * 1000 });
      setResult(data);
      await readProgress();
      await load();
      window.dispatchEvent(new Event("elios:custom-modules-changed"));
      window.dispatchEvent(new Event("elios:navigation-changed"));
      window.dispatchEvent(new Event("elios:refresh-dashboard"));
      toast.success("Importazione completa terminata");
    } catch (e) {
      setProgress((p) => ({ ...(p || {}), state: "error", message: messageFromError(e) }));
      toast.error("Importazione completa fallita", { description: messageFromError(e) });
    } finally {
      stopPolling();
      setBusy("");
    }`;
  const newBlock = `    try {
      await axios.post(\`${API}/admin/notion/import-all/start\`, {});
      let finalStatus = null;
      for (let attempt = 0; attempt < 2400; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        const status = await readProgress();
        if (!status) continue;
        if (status.state === "completed") { finalStatus = status; break; }
        if (status.state === "error") throw new Error(status.message || "Migrazione Notion interrotta");
      }
      if (!finalStatus) throw new Error("La migrazione è ancora in corso sul server. Puoi riaprire questa pagina per verificarne lo stato.");
      setResult(finalStatus.result || null);
      await load();
      window.dispatchEvent(new Event("elios:custom-modules-changed"));
      window.dispatchEvent(new Event("elios:navigation-changed"));
      window.dispatchEvent(new Event("elios:refresh-dashboard"));
      toast.success("Importazione completa terminata");
    } catch (e) {
      const current = await readProgress();
      if (current?.state !== "running" && current?.state !== "queued") setProgress((p) => ({ ...(p || {}), state: "error", message: messageFromError(e) }));
      toast.error(current?.state === "running" || current?.state === "queued" ? "La migrazione continua sul server" : "Importazione completa fallita", { description: messageFromError(e) });
    } finally {
      stopPolling();
      setBusy("");
    }`;
  s = replaceOnce(s, oldBlock, newBlock, 'background Notion import frontend');
  write(rel, s);
}

{
  const rel = 'src/pages/AdminPage.jsx';
  let s = read(rel);
  const marker = 'function SystemPane() {';
  const dataTools = `function DataToolsPane() {
  const [backupBusy, setBackupBusy] = useState(false);
  const downloadBackup = async () => {
    setBackupBusy(true);
    try {
      const response = await axios.get(\`${API}/admin/backup/download\`, { responseType: "blob" });
      const disposition = response.headers?.["content-disposition"] || "";
      const match = disposition.match(/filename\\*?=(?:UTF-8''|\")?([^\";]+)/i);
      const filename = match ? decodeURIComponent(match[1].replace(/\"/g, "")) : \`Gestionale_Elios_Tech_backup_\${new Date().toISOString().slice(0,10)}.zip\`;
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("Backup completo creato");
    } catch (e) { toast.error("Backup non riuscito", { description: formatError(e) }); }
    finally { setBackupBusy(false); }
  };
  return <div className="space-y-5">
    <SectionCard title="Importazione iniziale da Notion" description="La migrazione si gestisce da un solo punto del gestionale.">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
        <div><div className="font-bold text-slate-900">Importazione da Notion</div><div className="text-sm text-slate-600 mt-1">Apri la procedura guidata unica per collegamento, anteprima, importazione e verifica finale.</div></div>
        <Link to="/admin/migrazione-notion" className="inline-flex h-10 items-center justify-center rounded-xl bg-[#1A456B] px-4 text-sm font-bold text-white hover:bg-[#163B5C] shrink-0">Apri importazione</Link>
      </div>
    </SectionCard>
    <SectionCard title="Esportazione movimenti" description="Scarica una copia CSV dello storico operativo locale."><ExportMovimentiTab /></SectionCard>
    <SectionCard title="Backup completo" description="Scarica un archivio ZIP con database, foto, contratti, report e altri allegati del gestionale.">
      <Button onClick={downloadBackup} disabled={backupBusy} className="h-11"><DownloadSimple size={18}/>{backupBusy ? "Creazione backup…" : "Scarica backup completo"}</Button>
    </SectionCard>
    <SectionCard title="Pulizia e ripristino dati" description="Elimina in modo controllato i dati delle prove senza perdere utenti, impostazioni, configurazioni e log."><DataResetTab /></SectionCard>
  </div>;
}

`;
  if (!s.includes('function DataToolsPane()')) {
    if (!s.includes(marker)) throw new Error('[R61] Admin DataTools marker non trovato');
    s = s.replace(marker, dataTools + marker);
  }
  s = replaceOnce(s, '    if (category === "data") return <NotionMigrationPane />;', '    if (category === "data") return <DataToolsPane />;', 'single Notion import point');
  write(rel, s);
}

console.log('[R61] ruoli controllati, import Notion unico/resiliente e installazioni leggibili applicati.');
