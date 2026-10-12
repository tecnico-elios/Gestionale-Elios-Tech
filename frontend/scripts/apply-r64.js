const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
function read(rel) { return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function write(rel, text) { fs.writeFileSync(path.join(ROOT, rel), text, 'utf8'); }
function replaceOnce(text, from, to, label) {
  if (text.includes(to)) return text;
  if (!text.includes(from)) throw new Error(`[R64] ${label}: blocco non trovato`);
  return text.replace(from, to);
}

// ---------------------------------------------------------------------------
// Pulizia dati: testo esplicito sul significato di "Elimina tutto".
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/AdminExtraTabs.jsx';
  let s = read(rel);
  s = replaceOnce(
    s,
    'Usa questa funzione per eliminare i dati delle prove e ripartire pulito. <b>Utenti, impostazioni, configurazioni, Log sistema e Audit attività restano invariati.</b> Notion non viene toccato.',
    'Usa questa funzione per ripartire realmente da zero. <b>Elimina tutto</b> rimuove tutti i dati operativi: Clienti, Sedi, Ordini, Commesse, Calendario, Installazioni, Interventi tecnici, Assistenze, Magazzino, movimenti, documenti, report, allegati e dati importati. <b>Restano soltanto utenti, permessi, impostazioni/struttura del gestionale e log di sistema.</b> Se una migrazione non è ancora stata finalizzata, anche il suo stato temporaneo viene azzerato per consentire un nuovo import pulito.',
    'descrizione reset totale'
  );
  write(rel, s);
}

// ---------------------------------------------------------------------------
// Calendario: dopo la finalizzazione non mostra più alcun comando di import.
// ---------------------------------------------------------------------------
{
  const rel = 'src/pages/CalendarPage.jsx';
  let s = read(rel);
  s = replaceOnce(
    s,
    '{isAdmin && <Button variant="outline" onClick={() => setMigrationOpen((v) => !v)}>{migration.finalized ? <CheckCircle size={16} className="text-emerald-600" /> : <UploadSimple size={16} />} {migration.finalized ? "Calendario autonomo" : "Importazione"}</Button>}',
    '{isAdmin && !migration.finalized && <Button variant="outline" onClick={() => setMigrationOpen((v) => !v)}><UploadSimple size={16} /> Importazione</Button>}',
    'nascondi import calendario finalizzato'
  );
  s = replaceOnce(
    s,
    '{isAdmin && migrationOpen && <div className="r51-calendar-filter-panel">',
    '{isAdmin && !migration.finalized && migrationOpen && <div className="r51-calendar-filter-panel">',
    'nascondi pannello migrazione calendario finalizzato'
  );
  write(rel, s);
}

// ---------------------------------------------------------------------------
// Notion: la voce di menu scompare appena la migrazione viene finalizzata.
// ---------------------------------------------------------------------------
{
  const rel = 'src/components/AppLayout.jsx';
  let s = read(rel);
  s = replaceOnce(
    s,
    '  const [sectionResetKey, setSectionResetKey] = useState(0);',
    '  const [sectionResetKey, setSectionResetKey] = useState(0);\n  const [notionFinalized, setNotionFinalized] = useState(false);',
    'stato notion finalizzato'
  );
  s = replaceOnce(
    s,
    '  const navSettings = useMemo(() => Object.fromEntries((navigationConfig || []).map((x) => [x.key, x])), [navigationConfig]);',
    '  useEffect(() => {\n    if (!isAdmin) { setNotionFinalized(false); return undefined; }\n    let active = true;\n    const loadNotionState = async () => {\n      try {\n        const { data } = await axios.get(`${API}/admin/notion/config`);\n        if (active) setNotionFinalized(!!data?.completed);\n      } catch (_) {}\n    };\n    loadNotionState();\n    const onFinalized = () => loadNotionState();\n    window.addEventListener("elios:notion-finalized", onFinalized);\n    return () => { active = false; window.removeEventListener("elios:notion-finalized", onFinalized); };\n  }, [isAdmin]);\n\n  const navSettings = useMemo(() => Object.fromEntries((navigationConfig || []).map((x) => [x.key, x])), [navigationConfig]);',
    'caricamento stato notion menu'
  );
  s = replaceOnce(
    s,
    '    { to: "/admin/moduli", label: "Costruttore gestionale", icon: SlidersHorizontal, testid: "nav-module-builder", order: 920 },\n    { to: "/admin/migrazione-notion", label: "Importazione da Notion", icon: Database, testid: "nav-notion-migration", order: 930 },',
    '    { to: "/admin/moduli", label: "Costruttore gestionale", icon: SlidersHorizontal, testid: "nav-module-builder", order: 920 },\n    ...(!notionFinalized ? [{ to: "/admin/migrazione-notion", label: "Importazione da Notion", icon: Database, testid: "nav-notion-migration", order: 930 }] : []),',
    'menu notion condizionale'
  );
  write(rel, s);
}

// Aggiorna immediatamente il menu quando l'Admin chiude Notion.
{
  const rel = 'src/pages/NotionMigrationPage.jsx';
  let s = read(rel);
  s = replaceOnce(
    s,
    '      setResult(null);\n      await load();',
    '      setResult(null);\n      await load();\n      window.dispatchEvent(new Event("elios:notion-finalized"));',
    'evento notion finalizzato'
  );
  write(rel, s);
}

console.log('[R64] reset totale esplicito e comandi Notion/Calendar nascosti dopo finalizzazione.');
