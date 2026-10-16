const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'src', 'components', 'StandaloneInstallationReportDialog.jsx');
let text = fs.readFileSync(file, 'utf8');

const oldGenerate = '  const generate=async()=>{setBusy(true);try{const id=await ensureId();await axios.put(`${API}/free-reports/${id}`,{data:form});const {data}=await axios.post(`${API}/free-reports/${id}/generate`,{data:form});setDocId(data.document_id);toast.success(data.updated_existing?"Report aggiornato e PDF sostituito":"Report salvato e PDF generato");onSaved?.();onOpenChange(false);}catch(e){toast.error("Generazione non riuscita",{description:e?.response?.data?.detail||e.message})}finally{setBusy(false)}};';
const newGenerate = `  const generate=async()=>{\n    if(!form.firma_cliente||!form.firma_tecnico){\n      const mancanti=[];\n      if(!form.firma_cliente)mancanti.push("firma cliente");\n      if(!form.firma_tecnico)mancanti.push("firma tecnico");\n      toast.error("Completa le firme prima di generare il PDF",{description:\`Manca: \${mancanti.join(" e ")}\`});\n      return;\n    }\n    const preview=window.open("","_blank");\n    setBusy(true);\n    try{\n      const id=await ensureId();\n      await axios.put(\`${API}/free-reports/\${id}\`,{data:form});\n      const {data}=await axios.post(\`${API}/free-reports/\${id}/generate\`,{data:form});\n      setDocId(data.document_id);\n      const pdf=await axios.get(\`${API}/free-reports/\${id}/pdf\`,{responseType:"blob"});\n      const u=URL.createObjectURL(pdf.data);\n      if(preview){preview.location.href=u;}else{window.open(u,"_blank","noopener,noreferrer");}\n      setTimeout(()=>URL.revokeObjectURL(u),60000);\n      toast.success(data.updated_existing?"Report aggiornato e PDF aperto":"Report salvato, PDF generato e aperto");\n      onSaved?.();\n      onOpenChange(false);\n    }catch(e){\n      if(preview&&!preview.closed)preview.close();\n      toast.error("Generazione non riuscita",{description:e?.response?.data?.detail||e.message});\n    }finally{setBusy(false)}\n  };`;

if (!text.includes('PDF generato e aperto')) {
  if (!text.includes(oldGenerate)) throw new Error('R71: funzione generate originale non trovata');
  text = text.replace(oldGenerate, newGenerate);
}

const oldButton = 'disabled={busy||!form.firma_cliente||!form.firma_tecnico}';
if (text.includes(oldButton)) text = text.replace(oldButton, 'disabled={busy}');

fs.writeFileSync(file, text);
console.log('[R71 frontend] generazione PDF standalone corretta: firme validate, generate chiamato e PDF aperto.');
