const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
function read(rel) { return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function write(rel, text) { fs.writeFileSync(path.join(ROOT, rel), text, 'utf8'); }
function replaceOnce(text, from, to, label) {
  if (text.includes(to)) return text;
  if (!text.includes(from)) throw new Error(`[R62] ${label}: blocco non trovato`);
  return text.replace(from, to);
}
function replaceRegex(text, regex, replacement, label) {
  if (!regex.test(text)) throw new Error(`[R62] ${label}: blocco non trovato`);
  return text.replace(regex, replacement);
}

// ---------------------------------------------------------------------------
// Rotta e menu Interventi tecnici sotto Installazioni.
// ---------------------------------------------------------------------------
{
  const rel = 'src/App.js';
  let s = read(rel);
  s = replaceOnce(
    s,
    'import { SopralluoghiPage, InstallazioniPage, AssistenzaPage } from "@/pages/BusinessPages";',
    'import { SopralluoghiPage, InstallazioniPage, AssistenzaPage } from "@/pages/BusinessPages";\nimport InterventiTecniciPage from "@/pages/InterventiTecniciPage";',
    'technical page import'
  );
  s = replaceOnce(
    s,
    '<Route path="/installazioni" element={<ProtectedRoute permission="installazioni"><InstallazioniPage /></ProtectedRoute>} />\n                      <Route path="/assistenza"',
    '<Route path="/installazioni" element={<ProtectedRoute permission="installazioni"><InstallazioniPage /></ProtectedRoute>} />\n                      <Route path="/interventi-tecnici" element={<ProtectedRoute permission="installazioni"><InterventiTecniciPage /></ProtectedRoute>} />\n                      <Route path="/assistenza"',
    'technical page route'
  );
  write(rel, s);
}

{
  const rel = 'src/components/AppLayout.jsx';
  let s = read(rel);
  s = replaceOnce(
    s,
    '  { key: "installazioni", to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni", section: "tecnico", order: 30 },\n  { key: "assistenza",',
    '  { key: "installazioni", to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni", section: "tecnico", order: 30 },\n  { key: "interventi_tecnici", to: "/interventi-tecnici", label: "Interventi tecnici", icon: Wrench, testid: "nav-interventi-tecnici", module: "installazioni", section: "tecnico", order: 35 },\n  { key: "assistenza",',
    'technical nav item'
  );
  s = replaceOnce(
    s,
    '  "/installazioni": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Programmazione degli interventi, tecnici assegnati, attività e avanzamento installazioni." },\n  "/assistenza":',
    '  "/installazioni": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Programmazione delle installazioni assegnate a ENRICO e RICCARDO." },\n  "/interventi-tecnici": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Interventi tecnici di RICCARDO, storici e futuri, separati dalle installazioni." },\n  "/assistenza":',
    'technical page metadata'
  );
  write(rel, s);
}

// ---------------------------------------------------------------------------
// Installazioni: vista mese compatta, Oggi -> Future -> Passate, due colonne.
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/InstallazioniCalendarPage.jsx';
  let s = read(rel);

  s = replaceOnce(
    s,
    'function monthKey(d) { return d ? String(d).slice(0, 7) : ""; }',
    `function localDateKey() {\n  const d = new Date();\n  return \`${'${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}'}\`;\n}\nfunction cleanDisplayText(value) {\n  return String(value || "")\n    .replace(/<br\\s*\\/?\\s*>/gi, "\\n")\n    .replace(/<[^>]+>/g, "")\n    .replace(/&nbsp;/gi, " ")\n    .replace(/&amp;/gi, "&")\n    .replace(/&lt;/gi, "<")\n    .replace(/&gt;/gi, ">")\n    .replace(/\\n{3,}/g, "\\n\\n")\n    .trim();\n}\nfunction monthKey(d) { return d ? String(d).slice(0, 7) : ""; }`,
    'date and text helpers'
  );

  s = replaceOnce(
    s,
    '  const [month, setMonth] = useState(() => new Date().toISOString().slice(0,7));',
    '  const [month, setMonth] = useState(() => localDateKey().slice(0,7));\n  const [periodFilter, setPeriodFilter] = useState("all");',
    'installation month/filter state'
  );

  s = replaceRegex(
    s,
    /  const monthItems = useMemo\(\(\) => items\.filter[\s\S]*?\n  \}, \[monthItems\]\);/,
    `  const todayKey = localDateKey();
  const monthItems = useMemo(() => items.filter((x) => x.data && monthKey(x.data) === month), [items, month]);
  const unplannedItems = useMemo(() => items.filter((x) => !x.data), [items]);
  const sections = useMemo(() => {
    const sortTime = (a,b) => String(a.ora || "").localeCompare(String(b.ora || ""));
    const todayRows = monthItems.filter((x) => x.data === todayKey).sort(sortTime);
    const futureRows = monthItems.filter((x) => x.data > todayKey).sort((a,b) => \`${'${a.data} ${a.ora || ""}'}\`.localeCompare(\`${'${b.data} ${b.ora || ""}'}\`));
    const pastRows = monthItems.filter((x) => x.data < todayKey).sort((a,b) => \`${'${b.data} ${b.ora || ""}'}\`.localeCompare(\`${'${a.data} ${a.ora || ""}'}\`));
    const out = [];
    if ((periodFilter === "all" || periodFilter === "today") && todayRows.length) out.push(["Oggi", todayRows]);
    if ((periodFilter === "all" || periodFilter === "future") && futureRows.length) out.push(["Prossime del mese", futureRows]);
    if ((periodFilter === "all" || periodFilter === "past") && pastRows.length) out.push(["Passate del mese", pastRows]);
    if (periodFilter === "all" && unplannedItems.length) out.push(["Da programmare", unplannedItems]);
    return out;
  }, [monthItems, unplannedItems, todayKey, periodFilter]);`,
    'installation sections ordering'
  );

  s = replaceRegex(
    s,
    /    <div className="et-card p-3 sm:p-4 flex items-center justify-between gap-3">[\s\S]*?<\/div>\n\n    \{loading \?/, 
    `    <div className="et-card p-3 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <Button variant="outline" size="icon" onClick={() => { setMonth((m) => shiftMonth(m,-1)); setPeriodFilter("all"); }}><CaretLeft size={18}/></Button>
        <div className="text-center"><div className="font-black text-slate-900 capitalize">{monthLabel(month)}</div><div className="text-xs text-slate-500">{monthItems.length} installazioni nel mese</div></div>
        <Button variant="outline" size="icon" onClick={() => { setMonth((m) => shiftMonth(m,1)); setPeriodFilter("all"); }}><CaretRight size={18}/></Button>
      </div>
      <div className="flex flex-wrap justify-center gap-1.5">
        {[["all","Tutte"],["today","Oggi"],["future","Future"],["past","Passate"]].map(([key,label]) => <button type="button" key={key} onClick={() => setPeriodFilter(key)} className={\`h-8 rounded-lg border px-3 text-xs font-bold transition ${'${periodFilter === key ? "border-[#1A456B] bg-[#1A456B] text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}'}\`}>{label}</button>)}
      </div>
    </div>

    {loading ?`,
    'compact month selector and filters'
  );

  s = replaceRegex(
    s,
    /\{loading \? <div className="et-card p-10 text-center text-slate-500">Caricamento…<\/div> : grouped\.length === 0 \? <div className="et-card p-10 text-center text-slate-500">Nessuna installazione nel periodo selezionato\.<\/div> : \([\s\S]*?\n    \)\}\n\n    \{selected &&/,
    `{loading ? <div className="et-card p-8 text-center text-slate-500">Caricamento…</div> : sections.length === 0 ? <div className="et-card p-8 text-center text-slate-500">Nessuna installazione nel filtro selezionato.</div> : (
      <div className="space-y-4">
        {sections.map(([label, rows]) => <section key={label} className="space-y-2">
          <div className="flex items-center gap-2"><CalendarBlank size={17} className="text-[#1A456B]"/><h2 className="font-black text-slate-900">{label}</h2><span className="text-xs text-slate-400">{rows.length}</span></div>
          <div className="grid lg:grid-cols-2 gap-2.5">
            {rows.map((x) => <button key={x.id} onClick={() => openDetail(x)} className={\`text-left et-card p-3 hover:shadow-md transition-all border-l-4 ${'${x.stato === "Programmata" ? "border-l-amber-400" : x.stato === "Confermata / Da installare" || x.stato === "Installata" ? "border-l-emerald-500" : x.stato === "Completata" ? "border-l-emerald-800" : x.stato === "In sospeso" || x.stato === "Sospesa" ? "border-l-red-500" : "border-l-slate-300"}'}\`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><div className="text-[10px] uppercase tracking-wide font-bold text-slate-400 capitalize">{x.data ? fmtDate(x.data) : "Da programmare"}</div><div className="font-black text-base text-slate-900 truncate mt-0.5">{x.cliente_nome || x.cliente || x.nominativo || x.calendar_title || "Installazione"}</div><div className="text-xs text-slate-500 mt-0.5 truncate">{x.sede_nome || x.sede || x.indirizzo_libero || x.indirizzo || "Sede da verificare"}</div></div>
                <Badge className={statusCls[x.stato] || "bg-slate-100 text-slate-700"}>{x.stato || "Da programmare"}</Badge>
              </div>
              <div className="mt-2 grid sm:grid-cols-3 gap-1.5 text-xs">
                <div className="rounded-lg bg-slate-50 px-2 py-1.5"><Clock size={14} className="inline mr-1"/>{x.ora || "Da definire"}</div>
                <div className="rounded-lg bg-slate-50 px-2 py-1.5"><User size={14} className="inline mr-1"/>{x.tecnico || "Da assegnare"}</div>
                <div className="rounded-lg bg-slate-50 px-2 py-1.5"><Package size={14} className="inline mr-1"/>{(x.prodotti_da_installare || []).length} prodotti</div>
              </div>
              <InstallationWeather date={x.data} address={x.sede_indirizzo_completo || x.sede_indirizzo || x.indirizzo_libero || x.indirizzo || x.sede || ""} comune={x.sede_comune || x.comune_libero} provincia={x.sede_provincia || x.provincia_libera} cap={x.sede_cap || x.cap_libero} compact className="mt-2"/>
              {(x.istruzioni_intervento || x.note) && <div className="mt-2 text-xs text-slate-700 line-clamp-2 whitespace-pre-line">{cleanDisplayText(x.istruzioni_intervento || x.note)}</div>}
            </button>)}
          </div>
        </section>)}
      </div>
    )}

    {selected &&`,
    'balanced installation cards'
  );

  s = s.split('{selected.istruzioni_intervento || selected.note || "Nessuna istruzione aggiuntiva."}').join('{cleanDisplayText(selected.istruzioni_intervento || selected.note) || "Nessuna istruzione aggiuntiva."}');
  write(rel, s);
}

console.log('[R62] installazioni mese compatte, Interventi tecnici e navigazione applicati.');
