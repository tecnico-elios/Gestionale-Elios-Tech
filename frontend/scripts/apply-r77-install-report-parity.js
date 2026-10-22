const fs = require('fs');
const path = require('path');

const reportPath = path.join(__dirname, '..', 'src', 'components', 'InstallationReportDialog.jsx');
const layoutPath = path.join(__dirname, '..', 'src', 'components', 'AppLayout.jsx');
let text = fs.readFileSync(reportPath, 'utf8');
let layout = fs.readFileSync(layoutPath, 'utf8');

function replaceOnce(oldText, newText, label) {
  if (!text.includes(oldText)) throw new Error(`R77 frontend: ${label} non trovato`);
  text = text.replace(oldText, newText);
}

// Il report collegato a Installazioni deve avere le stesse opzioni del report Tecnico.
if (!text.includes('const [pdfPages,setPdfPages]')) {
  replaceOnce(
    '  const [docId,setDocId] = useState(null);',
    '  const [docId,setDocId] = useState(null);\n  const [pdfPages,setPdfPages] = useState("all");',
    'stato pagine PDF'
  );
}

if (!text.includes('setPdfPages(data?.pdf_pages||"all")')) {
  replaceOnce(
    '      setDocId(data?.generated_document_id||null);',
    '      setDocId(data?.generated_document_id||null);\n      setPdfPages(data?.pdf_pages||"all");',
    'caricamento pagine PDF'
  );
}

const oldSave = '  const save = async()=>{ setBusy(true); try{ await axios.put(`${API}/installation-reports/${installation.id}`,{data:form}); toast.success("Report salvato"); }catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e.message});}finally{setBusy(false);} };';
const newSave = '  const save = async()=>{ setBusy(true); try{ await axios.put(`${API}/installation-reports/${installation.id}`,{data:form,pdf_pages:pdfPages}); toast.success("Report salvato"); }catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e.message});}finally{setBusy(false);} };';
if (text.includes(oldSave)) text = text.replace(oldSave, newSave);

// Genera e apre subito il PDF, come nel report standalone. Le firme sono facoltative.
const genStart = text.indexOf('  const generate = async()=>{');
const genEnd = text.indexOf('\n  const openTemplate =', genStart);
if (genStart < 0 || genEnd < 0) throw new Error('R77 frontend: funzione generate non trovata');
const newGenerate = [
  '  const generate = async()=>{',
  '    const preview=window.open("","_blank");',
  '    setBusy(true);',
  '    try{',
  '      await axios.put(`${API}/installation-reports/${installation.id}`,{data:form,pdf_pages:pdfPages});',
  '      const {data}=await axios.post(`${API}/installation-reports/${installation.id}/generate`,{data:form,pdf_pages:pdfPages});',
  '      setDocId(data.document_id);',
  '      const pdf=await axios.get(`${API}/installation-reports/${installation.id}/pdf`,{responseType:"blob"});',
  '      const u=URL.createObjectURL(pdf.data);',
  '      if(preview){preview.location.href=u;}else{window.open(u,"_blank","noopener,noreferrer");}',
  '      setTimeout(()=>URL.revokeObjectURL(u),60000);',
  '      toast.success(form.firma_cliente?"Report salvato, PDF generato e aperto":"PDF generato senza firma cliente: pronto da inviare per la firma");',
  '      onGenerated?.(data);',
  '      onOpenChange(false);',
  '    }catch(e){',
  '      if(preview&&!preview.closed)preview.close();',
  '      toast.error("Generazione non riuscita",{description:e?.response?.data?.detail||e.message});',
  '    }finally{setBusy(false);}',
  '  };'
].join('\n');
text = text.slice(0, genStart) + newGenerate + text.slice(genEnd);

if (!text.includes('loadTechnicianSignature')) {
  const serialAnchor = '  const serialText = (form.seriali||[]).join(", ");';
  if (!text.includes(serialAnchor)) throw new Error('R77 frontend: ancora seriali R76 non trovata');
  const loader = `  const loadTechnicianSignature=(e)=>{\n    const file=e.target.files?.[0];\n    if(!file)return;\n    if(!file.type.startsWith("image/")){toast.error("Seleziona un file immagine");return;}\n    if(file.size>5*1024*1024){toast.error("Immagine firma troppo grande",{description:"Dimensione massima 5 MB"});return;}\n    const reader=new FileReader();\n    reader.onload=()=>set("firma_tecnico",String(reader.result||""));\n    reader.onerror=()=>toast.error("Impossibile leggere l'immagine della firma");\n    reader.readAsDataURL(file);\n  };\n`;
  text = text.replace(serialAnchor, loader + serialAnchor);
}

const oldFirme = '      <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Firme</h3><p className="text-sm text-slate-600">Le firme vengono riportate sul modello ufficiale del report.</p><SignaturePad label="Firma Cliente" value={form.firma_cliente} onChange={v=>set("firma_cliente",v)}/><SignaturePad label="Firma Tecnico" value={form.firma_tecnico} onChange={v=>set("firma_tecnico",v)}/></section>';
const newFirme = `      <section className="et-card p-4 space-y-3"><h3 className="font-black text-lg">Pagine da salvare nel PDF</h3><p className="text-sm text-slate-600">Scegli quali pagine del modello ufficiale includere.</p><div className="grid sm:grid-cols-2 gap-3"><label className={\`rounded-xl border p-4 cursor-pointer \${pdfPages==="all"?"border-slate-900 bg-slate-50":"border-slate-200"}\`}><input type="radio" name="install-pdf-pages" value="all" checked={pdfPages==="all"} onChange={()=>setPdfPages("all")} className="mr-2"/><span className="font-semibold">Tutte e 3 le pagine</span></label><label className={\`rounded-xl border p-4 cursor-pointer \${pdfPages==="2-3"?"border-slate-900 bg-slate-50":"border-slate-200"}\`}><input type="radio" name="install-pdf-pages" value="2-3" checked={pdfPages==="2-3"} onChange={()=>setPdfPages("2-3")} className="mr-2"/><span className="font-semibold">Solo pagine 2 e 3</span></label></div></section>\n      <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Firme</h3><p className="text-sm text-slate-600">La firma cliente è facoltativa: puoi generare il PDF senza firma e inviarlo al cliente. Le firme presenti vengono riportate sul modello ufficiale.</p><SignaturePad label="Firma Cliente" value={form.firma_cliente} onChange={v=>set("firma_cliente",v)}/><div className="space-y-3"><SignaturePad label="Firma Tecnico" value={form.firma_tecnico} onChange={v=>set("firma_tecnico",v)}/><div><Label>Oppure carica la firma tecnico da immagine</Label><Input type="file" accept="image/png,image/jpeg,image/webp" className="mt-1" onChange={loadTechnicianSignature}/><p className="mt-1 text-xs text-slate-500">PNG, JPG/JPEG o WEBP. L'immagine caricata sostituisce la firma disegnata.</p></div></div></section>`;
if (!text.includes('name="install-pdf-pages"')) {
  if (!text.includes(oldFirme)) throw new Error('R77 frontend: sezione firme Installazioni non trovata');
  text = text.replace(oldFirme, newFirme);
}

text = text.replace('disabled={busy||!form.firma_cliente||!form.firma_tecnico}', 'disabled={busy}');

// Nel menu Tecnico la voce deve chiamarsi semplicemente Report.
layout = layout.replace('key: "report_liberi", to: "/report-liberi", label: "Report liberi"', 'key: "report_liberi", to: "/report-liberi", label: "Report"');
layout = layout.replace('Report tecnici liberi e indipendenti, compilabili con campi personalizzati senza collegamenti obbligatori.', 'Report pre e post installazione compilabile liberamente, senza collegamento obbligatorio a cliente o installazione.');

fs.writeFileSync(reportPath, text);
fs.writeFileSync(layoutPath, layout);
console.log('[R77 frontend] report Installazioni allineato al report Tecnico.');
