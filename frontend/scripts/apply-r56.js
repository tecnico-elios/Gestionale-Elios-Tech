const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'src');

function read(rel) { return fs.readFileSync(path.join(ROOT, rel), 'utf8'); }
function write(rel, text) { fs.writeFileSync(path.join(ROOT, rel), text, 'utf8'); }
function mustReplace(text, from, to, label) {
  if (!text.includes(from)) throw new Error(`[R56] ${label}: blocco non trovato`);
  return text.replace(from, to);
}

// ---------------- REPORT: grafico ore per voce ----------------
{
  const rel = 'src/pages/ReportsPage.jsx';
  let s = read(rel);
  if (!s.includes('data-r56-hours-chart')) {
    s = mustReplace(
      s,
      'import { Plus, PencilSimple, Trash, FileText, Clock, CalendarBlank, SlidersHorizontal } from "@phosphor-icons/react";',
      'import { Plus, PencilSimple, Trash, FileText, Clock, CalendarBlank, SlidersHorizontal, ChartBar } from "@phosphor-icons/react";',
      'Reports icon import'
    );
    s = mustReplace(
      s,
      'import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";',
      'import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";\nimport { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";',
      'Reports recharts import'
    );
    const hoursLine = '  const hoursTotal=useMemo(()=>filtered.reduce((s,x)=>s+Number(x.data?.ore??x.data?.h??0),0),[filtered]);';
    const logic = `${hoursLine}\n  // R56 — grafico generico: individua automaticamente il campo ore e la voce descrittiva.\n  const hourField=useMemo(()=>fields.find(f=>["ore","h","hours","ore_lavorate"].includes(String(f.key||"").toLowerCase()))||fields.find(f=>/(^|_|\\s)(ore|hours)(_|\\s|$)/i.test(\`${'${f.key||""} ${f.label||""}'}\`)),[fields]);\n  const groupField=useMemo(()=>{\n    const preferred=["mansione","attivita","attività","nome","categoria","categorie","tags","tipo"];\n    return fields.find(f=>f.key!==hourField?.key&&preferred.includes(String(f.key||"").toLowerCase()))||fields.find(f=>f.key!==hourField?.key&&f.showInList!==false&&["select","text"].includes(f.type));\n  },[fields,hourField]);\n  const chartData=useMemo(()=>{\n    if(!hourField)return [];\n    const totals=new Map();\n    filtered.forEach(row=>{\n      const rawHours=Number(row.data?.[hourField.key]??0);\n      if(!Number.isFinite(rawHours)||rawHours<=0)return;\n      const rawLabel=groupField?row.data?.[groupField.key]:"Totale";\n      const label=Array.isArray(rawLabel)?rawLabel.map(x=>typeof x==="object"?(x?.name||x?.label||x?.id||""):String(x)).filter(Boolean).join(", "):(typeof rawLabel==="object"?(rawLabel?.name||rawLabel?.label||rawLabel?.id||"Altro"):String(rawLabel||"Altro"));\n      totals.set(label,(totals.get(label)||0)+rawHours);\n    });\n    return Array.from(totals,([voce,ore])=>({voce,ore:Number(ore.toFixed(2))})).sort((a,b)=>b.ore-a.ore);\n  },[filtered,hourField,groupField]);`;
    s = mustReplace(s, hoursLine, logic, 'Reports chart logic');
    const tableMarker = '    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">';
    const chart = `    {hourField && chartData.length>0 && <section className="r56-report-chart" data-r56-hours-chart>\n      <div className="r56-report-chart-head"><div><div className="r56-report-chart-kicker"><ChartBar size={15}/> Ore per voce</div><h2>Distribuzione ore</h2><p>{groupField ? \`Somma delle ore per ${'${groupField.label || "voce"}'}.\` : "Somma delle ore registrate."}</p></div><div className="r56-report-chart-total"><strong>{hoursTotal.toLocaleString("it-IT",{maximumFractionDigits:2})}</strong><span>ore totali</span></div></div>\n      <div style={{height:Math.max(260,chartData.length*38)}}>\n        <ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} layout="vertical" margin={{top:8,right:24,bottom:8,left:8}}><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tick={{fontSize:11}}/><YAxis type="category" dataKey="voce" width={150} tick={{fontSize:11}}/><Tooltip formatter={(v)=>[\`${'${Number(v).toLocaleString("it-IT",{maximumFractionDigits:2})}'} h\`,"Ore"]}/><Bar dataKey="ore" fill="#2d6ea3" radius={[0,6,6,0]}/></BarChart></ResponsiveContainer>\n      </div>\n    </section>}\n\n${tableMarker}`;
    s = mustReplace(s, tableMarker, chart, 'Reports chart placement');
    write(rel, s);
  }
}

// ---------------- CLIENTI / ORDINI: struttura compatta ----------------
{
  const rel = 'src/pages/EliosTechOrdiniPage.jsx';
  let s = read(rel);
  if (!s.includes('data-r56-orders-overview')) {
    const pagePos = s.indexOf('data-testid="elios-tech-ordini-page"');
    const start = s.indexOf('    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">', pagePos);
    const end = s.indexOf('    <div className="rounded-2xl border border-slate-200 bg-white p-3 sm:p-4', start);
    if (pagePos < 0 || start < 0 || end < 0) throw new Error('[R56] Clienti/Ordini: blocco overview non trovato');
    const overview = `    <section className="r56-orders-overview" data-r56-orders-overview>\n      <div className="r56-orders-overview-main">\n        <div><div className="r56-overline">Archivio operativo</div><div className="r56-orders-overview-title">Clienti e ordini</div><p>Elenco ordinato dalla firma più recente. Ricerca, filtri e stato nello stesso flusso.</p></div>\n        <div className="r56-orders-metrics">\n          <div><strong>{activeOrders}</strong><span>ordini</span></div>\n          <div><strong>{clients.length}</strong><span>clienti</span></div>\n          <div><strong>{followUps}</strong><span>da seguire</span></div>\n        </div>\n      </div>\n      {canCreate && <Button className="h-10" onClick={()=>setClientDialog(true)}><Plus size={17}/> Aggiungi cliente</Button>}\n    </section>\n`;
    s = s.slice(0,start) + overview + s.slice(end);
    const loadingMarker = '    {loading ? <div className="py-12 text-center text-slate-500">Caricamento…</div> : <>';
    const withHeading = `    <div className="r56-list-heading"><div><strong>Archivio per data</strong><span>Firma più recente prima</span></div><span>{shown.length} risultati</span></div>\n${loadingMarker}`;
    s = mustReplace(s, loadingMarker, withHeading, 'Clienti/Ordini list heading');
    write(rel, s);
  }
}

// ---------------- COMMESSE: barra stati + lista pulita ----------------
{
  const rel = 'src/pages/CommessePage.jsx';
  let s = read(rel);
  if (!s.includes('data-r56-commesse-toolbar')) {
    const listPos = s.indexOf('function CommesseList');
    const start = s.indexOf('      <div className="commesse-hero et-card-elevated', listPos);
    const end = s.indexOf('      {loading ? (', start);
    if (listPos < 0 || start < 0 || end < 0) throw new Error('[R56] Commesse: header/KPI non trovato');
    const block = `      <section className="r56-commesse-toolbar" data-r56-commesse-toolbar>\n        <div><div className="r56-overline">Gestione commesse</div><div className="r56-commesse-title">Preparazione e avanzamento</div><p>Stato, priorità, materiale e spedizione in una sola vista.</p></div>\n        {onCreate && <Button onClick={onCreate} className="h-10 px-4" data-testid="commessa-new-btn"><Plus size={16}/> Nuova commessa</Button>}\n      </section>\n      <div className="r56-commesse-statusbar" data-testid="commesse-overview">\n        <button className={!filterStato?"is-active":""} onClick={()=>setFilterStato("")}><span>Tutte</span><strong>{Object.values(kpi||{}).reduce((sum,v)=>sum+(Number(v)||0),0)}</strong></button>\n        {["da_preparare","in_preparazione","parziale","pronta"].map(s=><button key={s} onClick={()=>setFilterStato(filterStato===s?"":s)} className={filterStato===s?"is-active":""} data-testid={\`kpi-${'${s}'}\`}><span>{STATO_LABEL[s].txt}</span><strong>{kpi[s]??0}</strong></button>)}\n      </div>\n      <div className="r56-list-heading"><div><strong>Commesse</strong><span>{filterStato ? STATO_LABEL[filterStato]?.txt : "Tutti gli stati"}</span></div><span>{items.length} visibili</span></div>\n`;
    s = s.slice(0,start) + block + s.slice(end);
    write(rel, s);
  }
}

// ---------------- MIGRAZIONE NOTION: etichette consegne ----------------
{
  const rel = 'src/pages/NotionMigrationPage.jsx';
  let s = read(rel);
  s = s.replace('["receipts_ds_id", "Entrate / Arrivi Elios Tech"]','["receipts_ds_id", "Entrate / Arrivi / Consegne in entrata Elios Tech"]');
  s = s.replace('["tracker_ds_id", "Uscite / Spedizioni Elios Tech"]','["tracker_ds_id", "Uscite / Spedizioni / Consegne in uscita Elios Tech"]');
  s = s.replace('["verona_receipts_ds_id", "Entrate Verona"]','["verona_receipts_ds_id", "Entrate / Consegne in entrata Verona"]');
  s = s.replace('["verona_tracker_ds_id", "Uscite Verona"]','["verona_tracker_ds_id", "Uscite / Consegne in uscita Verona"]');
  write(rel, s);
}

// ---------------- CALENDARIO: mostra conteggio lead esclusi ----------------
{
  const rel = 'src/pages/CalendarPage.jsx';
  let s = read(rel);
  const old = '{migration.last_result?.parsed != null && <div className="text-xs text-slate-500 mt-2">Ultimo import: {migration.last_result.parsed} letti · {migration.last_result.imported || 0} nuovi · {migration.last_result.updated || 0} aggiornati</div>}';
  const neu = '{migration.last_result?.parsed != null && <div className="text-xs text-slate-500 mt-2">Ultimo import: {migration.last_result.parsed} letti · {migration.last_result.imported || 0} nuovi · {migration.last_result.updated || 0} aggiornati{migration.last_result.skipped_leads ? ` · ${migration.last_result.skipped_leads} Lead esclusi` : ""}</div>}';
  if (s.includes(old)) s = s.replace(old, neu);
  write(rel, s);
}

console.log('[R56] UI, report, commesse, clienti/ordini e migrazioni aggiornati.');
