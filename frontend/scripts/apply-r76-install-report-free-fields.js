const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'src', 'components', 'InstallationReportDialog.jsx');
let text = fs.readFileSync(file, 'utf8');

function replaceOnce(oldText, newText, label) {
  if (!text.includes(oldText)) throw new Error(`R76 frontend: ${label} non trovato`);
  text = text.replace(oldText, newText);
}

if (!text.includes('data:"", cliente:"", indirizzo:"", tecnico:"", seriali:[]')) {
  replaceOnce(
    'const EMPTY = {\n  societa_installatrice:"", telefono:"", email:"",',
    'const EMPTY = {\n  data:"", cliente:"", indirizzo:"", tecnico:"", seriali:[],\n  societa_installatrice:"", telefono:"", email:"",',
    'campi anagrafici EMPTY'
  );
}

if (!text.includes('const serialText = (form.seriali||[]).join(", ");')) {
  replaceOnce(
    '  const diametri = ["20 mm","25 mm","30 mm","32 mm","40 mm","50 mm","63 mm"];',
    '  const diametri = ["20 mm","25 mm","30 mm","32 mm","40 mm","50 mm","63 mm"];\n  const serialText = (form.seriali||[]).join(", ");',
    'ancora seriali'
  );
}

const oldSummary = `      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div><div className="text-[11px] uppercase font-bold text-slate-400">Data</div><div className="font-bold">{form.data||"—"}</div></div>
        <div><div className="text-[11px] uppercase font-bold text-slate-400">Cliente</div><div className="font-bold">{form.cliente||"—"}</div></div>
        <div><div className="text-[11px] uppercase font-bold text-slate-400">Tecnico</div><div className="font-bold">{form.tecnico||"—"}</div></div>
        <div><div className="text-[11px] uppercase font-bold text-slate-400">Seriali</div><div className="font-bold">{(form.seriali||[]).join(", ")||"—"}</div></div>
        <div className="sm:col-span-2 lg:col-span-4"><div className="text-[11px] uppercase font-bold text-slate-400">Indirizzo installazione</div><div className="font-bold">{form.indirizzo||"—"}</div></div>
      </div>`;

const newSummary = `      <section className="et-card p-4 space-y-3">
        <div>
          <h3 className="font-black text-lg">Dati report</h3>
          <p className="text-sm text-slate-600">I dati vengono precompilati dall'installazione solo come base: puoi modificarli liberamente e il PDF userà esattamente i valori inseriti qui.</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div><Label>Data</Label><Input className="mt-1" value={form.data||""} onChange={e=>set("data",e.target.value)} placeholder="GG/MM/AAAA"/></div>
          <div><Label>Cliente / riferimento</Label><Input className="mt-1" value={form.cliente||""} onChange={e=>set("cliente",e.target.value)}/></div>
          <div><Label>Tecnico</Label><Input className="mt-1" value={form.tecnico||""} onChange={e=>set("tecnico",e.target.value)}/></div>
          <div><Label>Seriali</Label><Input className="mt-1" value={serialText} onChange={e=>set("seriali",e.target.value.split(",").map(x=>x.trim()).filter(Boolean))} placeholder="SN1, SN2, SN3"/></div>
          <div className="sm:col-span-2 lg:col-span-4"><Label>Indirizzo installazione</Label><Input className="mt-1" value={form.indirizzo||""} onChange={e=>set("indirizzo",e.target.value)}/></div>
        </div>
      </section>`;

if (!text.includes('I dati vengono precompilati dall\'installazione solo come base')) {
  replaceOnce(oldSummary, newSummary, 'riepilogo anagrafico');
}

fs.writeFileSync(file, text);
console.log('[R76 frontend] dati report installazione liberamente modificabili.');
