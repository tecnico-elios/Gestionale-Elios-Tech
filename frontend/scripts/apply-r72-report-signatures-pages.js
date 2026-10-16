const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'src', 'components', 'StandaloneInstallationReportDialog.jsx');
let text = fs.readFileSync(file, 'utf8');

// Stato scelta pagine PDF.
const stateAnchor = '  const [form,setForm]=useState({...EMPTY}); const [loading,setLoading]=useState(false); const [busy,setBusy]=useState(false); const [reportId,setReportId]=useState(null); const [docId,setDocId]=useState(null);';
if (!text.includes('const [pdfPages,setPdfPages]')) {
  if (!text.includes(stateAnchor)) throw new Error('R72 frontend: state anchor non trovato');
  text = text.replace(stateAnchor, stateAnchor + ' const [pdfPages,setPdfPages]=useState("all");');
}

// Caricamento/salvataggio della scelta pagine.
if (!text.includes('setPdfPages("all")')) {
  text = text.replace('setDocId(null);return;', 'setDocId(null);setPdfPages("all");return;');
}
if (!text.includes('setPdfPages(data?.pdf_pages||"all")')) {
  text = text.replace('setDocId(data?.generated_document_id||null)}', 'setDocId(data?.generated_document_id||null);setPdfPages(data?.pdf_pages||"all")}');
}

const oldEnsure = '  const ensureId=async()=>{if(reportId)return reportId;const {data}=await axios.post(`${API}/free-reports`,{data:form});setReportId(data.id);return data.id};';
const newEnsure = '  const ensureId=async()=>{if(reportId)return reportId;const {data}=await axios.post(`${API}/free-reports`,{data:form,pdf_pages:pdfPages});setReportId(data.id);return data.id};';
if (text.includes(oldEnsure)) text = text.replace(oldEnsure, newEnsure);

const oldSave = '  const save=async()=>{setBusy(true);try{const id=await ensureId();await axios.put(`${API}/free-reports/${id}`,{data:form});toast.success("Report salvato");onSaved?.();}catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e.message})}finally{setBusy(false)}};';
const newSave = '  const save=async()=>{setBusy(true);try{const id=await ensureId();await axios.put(`${API}/free-reports/${id}`,{data:form,pdf_pages:pdfPages});toast.success("Report salvato");onSaved?.();}catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e.message})}finally{setBusy(false)}};';
if (text.includes(oldSave)) text = text.replace(oldSave, newSave);

// Generazione consentita anche senza firma cliente; il PDF viene aperto subito.
const genStart = text.indexOf('  const generate=async()=>{');
const genEnd = text.indexOf('\n  const openTemplate=', genStart);
if (genStart < 0 || genEnd < 0) throw new Error('R72 frontend: funzione generate non trovata');
const newGenerate = [
  '  const generate=async()=>{',
  '    const preview=window.open("","_blank");',
  '    setBusy(true);',
  '    try{',
  '      const id=await ensureId();',
  '      await axios.put(`${API}/free-reports/${id}`,{data:form,pdf_pages:pdfPages});',
  '      const {data}=await axios.post(`${API}/free-reports/${id}/generate`,{data:form,pdf_pages:pdfPages});',
  '      setDocId(data.document_id);',
  '      const pdf=await axios.get(`${API}/free-reports/${id}/pdf`,{responseType:"blob"});',
  '      const u=URL.createObjectURL(pdf.data);',
  '      if(preview){preview.location.href=u;}else{window.open(u,"_blank","noopener,noreferrer");}',
  '      setTimeout(()=>URL.revokeObjectURL(u),60000);',
  '      toast.success(form.firma_cliente?"Report salvato, PDF generato e aperto":"PDF generato senza firma cliente: pronto da inviare per la firma");',
  '      onSaved?.();',
  '      onOpenChange(false);',
  '    }catch(e){',
  '      if(preview&&!preview.closed)preview.close();',
  '      toast.error("Generazione non riuscita",{description:e?.response?.data?.detail||e.message});',
  '    }finally{setBusy(false)}',
  '  };'
].join('\n');
text = text.slice(0, genStart) + newGenerate + text.slice(genEnd);

// Firma tecnico caricabile da immagine.
if (!text.includes('loadTechnicianSignature')) {
  const serialAnchor = '  const serialText=(form.seriali||[]).join(", ");';
  if (!text.includes(serialAnchor)) throw new Error('R72 frontend: serial anchor non trovato');
  const loader = `  const loadTechnicianSignature=(e)=>{\n    const file=e.target.files?.[0];\n    if(!file)return;\n    if(!file.type.startsWith("image/")){toast.error("Seleziona un file immagine");return;}\n    if(file.size>5*1024*1024){toast.error("Immagine firma troppo grande",{description:"Dimensione massima 5 MB"});return;}\n    const reader=new FileReader();\n    reader.onload=()=>set("firma_tecnico",String(reader.result||""));\n    reader.onerror=()=>toast.error("Impossibile leggere l'immagine della firma");\n    reader.readAsDataURL(file);\n  };\n`;
  text = text.replace(serialAnchor, loader + serialAnchor);
}

// Scelta pagine + caricamento firma tecnico.
const oldFirme = '    <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Firme</h3><p className="text-sm text-slate-600">Le firme vengono riportate sul modello ufficiale del report.</p><SignaturePad label="Firma Cliente" value={form.firma_cliente} onChange={v=>set("firma_cliente",v)}/><SignaturePad label="Firma Tecnico" value={form.firma_tecnico} onChange={v=>set("firma_tecnico",v)}/></section>';
const newFirme = `    <section className="et-card p-4 space-y-3"><h3 className="font-black text-lg">Pagine da salvare nel PDF</h3><p className="text-sm text-slate-600">Scegli quali pagine del modello ufficiale includere.</p><div className="grid sm:grid-cols-2 gap-3"><label className={\`rounded-xl border p-4 cursor-pointer \${pdfPages==="all"?"border-slate-900 bg-slate-50":"border-slate-200"}\`}><input type="radio" name="pdf-pages" value="all" checked={pdfPages==="all"} onChange={()=>setPdfPages("all")} className="mr-2"/><span className="font-semibold">Tutte e 3 le pagine</span></label><label className={\`rounded-xl border p-4 cursor-pointer \${pdfPages==="2-3"?"border-slate-900 bg-slate-50":"border-slate-200"}\`}><input type="radio" name="pdf-pages" value="2-3" checked={pdfPages==="2-3"} onChange={()=>setPdfPages("2-3")} className="mr-2"/><span className="font-semibold">Solo pagine 2 e 3</span></label></div></section>\n    <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Firme</h3><p className="text-sm text-slate-600">La firma cliente è facoltativa: puoi generare il PDF senza firma e inviarlo al cliente. Le firme presenti vengono riportate sul modello ufficiale.</p><SignaturePad label="Firma Cliente" value={form.firma_cliente} onChange={v=>set("firma_cliente",v)}/><div className="space-y-3"><SignaturePad label="Firma Tecnico" value={form.firma_tecnico} onChange={v=>set("firma_tecnico",v)}/><div><Label>Oppure carica la firma tecnico da immagine</Label><Input type="file" accept="image/png,image/jpeg,image/webp" className="mt-1" onChange={loadTechnicianSignature}/><p className="mt-1 text-xs text-slate-500">PNG, JPG/JPEG o WEBP. L'immagine caricata sostituisce la firma disegnata.</p></div></div></section>`;
if (!text.includes('Solo pagine 2 e 3')) {
  if (!text.includes(oldFirme)) throw new Error('R72 frontend: sezione firme non trovata');
  text = text.replace(oldFirme, newFirme);
}

fs.writeFileSync(file, text);
console.log('[R72 frontend] firma cliente facoltativa, firma tecnico da immagine e scelta pagine PDF abilitate.');
