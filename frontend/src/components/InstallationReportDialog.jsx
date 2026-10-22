import { API } from "../lib/apiBase";
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { CheckCircle, DownloadSimple, FloppyDisk, PenNib } from "@phosphor-icons/react";

function SignaturePad({ label, value, onChange }) {
  const ref = useRef(null);
  const drawing = useRef(false);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    ctx.clearRect(0,0,c.width,c.height);
    if (value) {
      const img = new Image();
      img.onload = () => ctx.drawImage(img,0,0,c.width,c.height);
      img.src = value;
    }
  }, [value]);
  const pos = (e) => {
    const r = ref.current.getBoundingClientRect();
    const p = e.touches?.[0] || e;
    return {x:(p.clientX-r.left)*(ref.current.width/r.width), y:(p.clientY-r.top)*(ref.current.height/r.height)};
  };
  const start = (e) => { e.preventDefault(); drawing.current = true; const p=pos(e); const ctx=ref.current.getContext("2d"); ctx.beginPath(); ctx.moveTo(p.x,p.y); };
  const move = (e) => { if(!drawing.current) return; e.preventDefault(); const p=pos(e); const ctx=ref.current.getContext("2d"); ctx.lineWidth=2; ctx.lineCap="round"; ctx.strokeStyle="#0f172a"; ctx.lineTo(p.x,p.y); ctx.stroke(); };
  const end = () => { if(!drawing.current) return; drawing.current=false; onChange(ref.current.toDataURL("image/png")); };
  const clear = () => { const c=ref.current; c.getContext("2d").clearRect(0,0,c.width,c.height); onChange(""); };
  return <div>
    <div className="flex items-center justify-between mb-1"><Label>{label}</Label><button type="button" onClick={clear} className="text-xs font-semibold text-slate-500 hover:text-red-600">Cancella firma</button></div>
    <canvas ref={ref} width={620} height={150} onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end} onTouchStart={start} onTouchMove={move} onTouchEnd={end} className="w-full h-36 rounded-xl border-2 border-dashed border-slate-300 bg-white touch-none" />
  </div>;
}

const EMPTY = {
  data:"", cliente:"", indirizzo:"", tecnico:"", seriali:[],
  societa_installatrice:"", telefono:"", email:"",
  quadro_idoneo:false, quadro_non_conforme:false, surriscaldamento:false, protezioni_assenti:false,
  sezione_cavi_non_idonea:false, messa_terra_non_conforme:false, altro_verifica:"", criticita:"", nessuna_criticita:false,
  scelta_cliente:"", prodotti:[], tipo_installazione:"", orario_inizio:"", orario_fine:"", cavo_fg16:"", cavo_fg16_mt:"",
  cavo_rs485_qta:"", raccorderia_qta:"", quadretto_qta:"", tubazione_misura:"", tubazione_qta:"", guaina_misura:"", guaina_qta:"", clips_qta:"",
  stand_mono_qta:"", stand_dual_qta:"", cable_dock_qta:"", meter:false, meter_clamps:false, scavo_mt:"", plinto_qta:"", fori_qta:"",
  accessori_note:"", lavori_extra:"", costo_lavori_extra:"", firma_cliente:"", firma_tecnico:""
};

function Check({checked,onChange,label}) { return <label className="flex items-start gap-2 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={!!checked} onChange={e=>onChange(e.target.checked)}/><span>{label}</span></label>; }

export default function InstallationReportDialog({ open, onOpenChange, installation, onGenerated }) {
  const [form,setForm] = useState(EMPTY);
  const [loading,setLoading] = useState(false);
  const [busy,setBusy] = useState(false);
  const [docId,setDocId] = useState(null);
  const [pdfPages,setPdfPages] = useState("all");
  const set = (k,v)=>setForm(f=>({...f,[k]:v}));
  const toggleProduct = (p)=>setForm(f=>({...f, prodotti:(f.prodotti||[]).includes(p)?f.prodotti.filter(x=>x!==p):[...(f.prodotti||[]),p]}));
  const diametri = ["20 mm","25 mm","30 mm","32 mm","40 mm","50 mm","63 mm"];
  const loadTechnicianSignature=(e)=>{
    const file=e.target.files?.[0];
    if(!file)return;
    if(!file.type.startsWith("image/")){toast.error("Seleziona un file immagine");return;}
    if(file.size>5*1024*1024){toast.error("Immagine firma troppo grande",{description:"Dimensione massima 5 MB"});return;}
    const reader=new FileReader();
    reader.onload=()=>set("firma_tecnico",String(reader.result||""));
    reader.onerror=()=>toast.error("Impossibile leggere l'immagine della firma");
    reader.readAsDataURL(file);
  };
  const serialText = (form.seriali||[]).join(", ");

  useEffect(()=>{
    if(!open || !installation?.id) return;
    setLoading(true);
    axios.get(`${API}/installation-reports/${installation.id}`).then(({data})=>{
      setForm({...EMPTY,...(data?.data||{})});
      setDocId(data?.generated_document_id||null);
      setPdfPages(data?.pdf_pages||"all");
    }).catch(e=>toast.error("Impossibile caricare il report",{description:e?.response?.data?.detail||e.message})).finally(()=>setLoading(false));
  },[open,installation?.id]);

  const save = async()=>{ setBusy(true); try{ await axios.put(`${API}/installation-reports/${installation.id}`,{data:form,pdf_pages:pdfPages}); toast.success("Report salvato"); }catch(e){toast.error("Salvataggio non riuscito",{description:e?.response?.data?.detail||e.message});}finally{setBusy(false);} };
  const generate = async()=>{
    const preview=window.open("","_blank");
    setBusy(true);
    try{
      await axios.put(`${API}/installation-reports/${installation.id}`,{data:form,pdf_pages:pdfPages});
      const {data}=await axios.post(`${API}/installation-reports/${installation.id}/generate`,{data:form,pdf_pages:pdfPages});
      setDocId(data.document_id);
      const pdf=await axios.get(`${API}/installation-reports/${installation.id}/pdf`,{responseType:"blob"});
      const u=URL.createObjectURL(pdf.data);
      if(preview){preview.location.href=u;}else{window.open(u,"_blank","noopener,noreferrer");}
      setTimeout(()=>URL.revokeObjectURL(u),60000);
      toast.success(form.firma_cliente?"Report salvato, PDF generato e aperto":"PDF generato senza firma cliente: pronto da inviare per la firma");
      onGenerated?.(data);
      onOpenChange(false);
    }catch(e){
      if(preview&&!preview.closed)preview.close();
      toast.error("Generazione non riuscita",{description:e?.response?.data?.detail||e.message});
    }finally{setBusy(false);}
  };
  const openTemplate = async()=>{ try{ const {data}=await axios.get(`${API}/installation-reports/template`,{responseType:"blob"}); const u=URL.createObjectURL(data); window.open(u,"_blank","noopener,noreferrer"); setTimeout(()=>URL.revokeObjectURL(u),60000);}catch(e){toast.error("Modello non disponibile",{description:e?.response?.data?.detail||e.message});} };
  const download = async()=>{ try{ const {data}=await axios.get(`${API}/installation-reports/${installation.id}/pdf`,{responseType:"blob"}); const u=URL.createObjectURL(data); window.open(u,"_blank","noopener,noreferrer"); setTimeout(()=>URL.revokeObjectURL(u),60000);}catch(e){toast.error("Report non disponibile",{description:e?.response?.data?.detail||e.message});} };

  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="w-[calc(100vw-1rem)] sm:w-[calc(100vw-2rem)] max-w-5xl max-h-[96dvh] overflow-y-auto p-3 sm:p-6">
    <DialogHeader><DialogTitle className="text-xl flex items-center gap-2"><PenNib/> Report pre e post installazione</DialogTitle></DialogHeader>
    {loading?<div className="py-16 text-center text-slate-500">Caricamento…</div>:<div className="space-y-5">
      <div className="flex justify-end"><Button type="button" variant="outline" onClick={openTemplate}>Apri modello ufficiale</Button></div>
      <section className="et-card p-4 space-y-3">
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
      </section>

      <section className="et-card p-4 space-y-3"><h3 className="font-black text-lg">Pre-installazione · verifica impianto esistente</h3>
        <div className="grid sm:grid-cols-3 gap-3"><div><Label>Società installatrice</Label><Input className="mt-1" value={form.societa_installatrice||""} onChange={e=>set("societa_installatrice",e.target.value)}/></div><div><Label>Telefono cliente</Label><Input className="mt-1" value={form.telefono||""} onChange={e=>set("telefono",e.target.value)}/></div><div><Label>Email cliente</Label><Input className="mt-1" value={form.email||""} onChange={e=>set("email",e.target.value)}/></div></div>
        <div className="grid sm:grid-cols-2 gap-2">
          <Check label="Quadro elettrico in condizioni idonee" checked={form.quadro_idoneo} onChange={v=>set("quadro_idoneo",v)}/>
          <Check label="Quadro elettrico non conforme / deteriorato / obsoleto" checked={form.quadro_non_conforme} onChange={v=>set("quadro_non_conforme",v)}/>
          <Check label="Presenza di segni di surriscaldamento o bruciature" checked={form.surriscaldamento} onChange={v=>set("surriscaldamento",v)}/>
          <Check label="Protezioni assenti o non adeguate" checked={form.protezioni_assenti} onChange={v=>set("protezioni_assenti",v)}/>
          <Check label="Sezione cavi non verificabile o non idonea" checked={form.sezione_cavi_non_idonea} onChange={v=>set("sezione_cavi_non_idonea",v)}/>
          <Check label="Messa a terra non verificabile / non conforme" checked={form.messa_terra_non_conforme} onChange={v=>set("messa_terra_non_conforme",v)}/>
        </div>
        <Input value={form.altro_verifica||""} onChange={e=>set("altro_verifica",e.target.value)} placeholder="Altro"/>
        <Textarea value={form.criticita||""} onChange={e=>set("criticita",e.target.value)} placeholder="Criticità riscontrate" rows={3}/>
        <Check label="Nessuna criticità riscontrata" checked={form.nessuna_criticita} onChange={v=>set("nessuna_criticita",v)}/>
        <div><Label>Scelta del cliente</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 px-3" value={form.scelta_cliente||""} onChange={e=>set("scelta_cliente",e.target.value)}><option value="">Seleziona…</option><option value="autorizza">Autorizza l'installazione assumendosi ogni responsabilità per l'impianto esistente</option><option value="adeguamento">Richiede interventi di adeguamento prima dell'installazione</option><option value="rinvia">Rinvia l'installazione</option></select></div>
      </section>

      <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Post-installazione · dati tecnici</h3>
        <div><Label>Prodotto installato</Label><div className="mt-2 flex flex-wrap gap-3">{["Pro","Pro Socket","Max","Copper"].map(p=><Check key={p} label={p} checked={(form.prodotti||[]).includes(p)} onChange={()=>toggleProduct(p)}/>)}</div></div>
        <div className="grid sm:grid-cols-3 gap-3"><div><Label>Tipo installazione</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 px-3" value={form.tipo_installazione||""} onChange={e=>set("tipo_installazione",e.target.value)}><option value="">Seleziona…</option><option>Su Muro</option><option>Su Stand</option></select></div><div><Label>Orario inizio lavori</Label><Input type="time" className="mt-1 h-12" value={form.orario_inizio||""} onChange={e=>set("orario_inizio",e.target.value)}/></div><div><Label>Orario fine lavori</Label><Input type="time" className="mt-1 h-12" value={form.orario_fine||""} onChange={e=>set("orario_fine",e.target.value)}/></div></div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div><Label>Cavo FG16</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 px-3" value={form.cavo_fg16||""} onChange={e=>set("cavo_fg16",e.target.value)}><option value="">Nessuno</option><option>4mmq</option><option>6mmq</option><option>10mmq</option><option>16mmq</option></select></div>
          <div><Label>Metri cavo FG16</Label><Input type="number" min="0" step="0.1" className="mt-1 h-12" value={form.cavo_fg16_mt||""} onChange={e=>set("cavo_fg16_mt",e.target.value)}/></div>
          <div><Label>Cavo RS485 · metri</Label><Input type="number" min="0" step="0.1" className="mt-1 h-12" value={form.cavo_rs485_qta||""} onChange={e=>set("cavo_rs485_qta",e.target.value)}/></div>
          <div><Label>Raccorderia · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.raccorderia_qta||""} onChange={e=>set("raccorderia_qta",e.target.value)}/></div>
          <div><Label>Quadretto Diff. e Magn. · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.quadretto_qta||""} onChange={e=>set("quadretto_qta",e.target.value)}/></div>
          <div><Label>Tubazione rigida · misura</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 px-3" value={form.tubazione_misura||""} onChange={e=>set("tubazione_misura",e.target.value)}><option value="">Nessuna</option>{diametri.map(d=><option key={d}>{d}</option>)}</select></div>
          <div><Label>Tubazione rigida · metri</Label><Input type="number" min="0" step="0.1" className="mt-1 h-12" value={form.tubazione_qta||""} onChange={e=>set("tubazione_qta",e.target.value)}/></div>
          <div><Label>Guaina · misura</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 px-3" value={form.guaina_misura||""} onChange={e=>set("guaina_misura",e.target.value)}><option value="">Nessuna</option>{diametri.map(d=><option key={d}>{d}</option>)}</select></div>
          <div><Label>Guaina · metri</Label><Input type="number" min="0" step="0.1" className="mt-1 h-12" value={form.guaina_qta||""} onChange={e=>set("guaina_qta",e.target.value)}/></div>
          <div><Label>Clips + Viti · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.clips_qta||""} onChange={e=>set("clips_qta",e.target.value)}/></div>
          <div><Label>Stand Mono · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.stand_mono_qta||""} onChange={e=>set("stand_mono_qta",e.target.value)}/></div>
          <div><Label>Stand Dual · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.stand_dual_qta||""} onChange={e=>set("stand_dual_qta",e.target.value)}/></div>
          <div><Label>Cable Dock · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.cable_dock_qta||""} onChange={e=>set("cable_dock_qta",e.target.value)}/></div>
          <div><Label>Scavo · metri</Label><Input type="number" min="0" step="0.1" className="mt-1 h-12" value={form.scavo_mt||""} onChange={e=>set("scavo_mt",e.target.value)}/></div>
          <div><Label>Plinto / Staffa · pezzi</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.plinto_qta||""} onChange={e=>set("plinto_qta",e.target.value)}/></div>
          <div><Label>Fori · quantità</Label><Input type="number" min="0" step="1" className="mt-1 h-12" value={form.fori_qta||""} onChange={e=>set("fori_qta",e.target.value)}/></div>
        </div>
        <div className="flex flex-wrap gap-5"><Check label="Meter" checked={form.meter} onChange={v=>set("meter",v)}/><Check label="Meter Clamps" checked={form.meter_clamps} onChange={v=>set("meter_clamps",v)}/></div>
        <Textarea rows={4} value={form.accessori_note||""} onChange={e=>set("accessori_note",e.target.value)} placeholder="Accessori / Note"/>
        <div className="grid sm:grid-cols-[1fr_220px] gap-3"><Textarea rows={3} value={form.lavori_extra||""} onChange={e=>set("lavori_extra",e.target.value)} placeholder="Lavori Extra"/><div><Label>Costo lavori extra</Label><Input className="mt-1 h-12" value={form.costo_lavori_extra||""} onChange={e=>set("costo_lavori_extra",e.target.value)} placeholder="€"/></div></div>
      </section>

      <section className="et-card p-4 space-y-3"><h3 className="font-black text-lg">Pagine da salvare nel PDF</h3><p className="text-sm text-slate-600">Scegli quali pagine del modello ufficiale includere.</p><div className="grid sm:grid-cols-2 gap-3"><label className={`rounded-xl border p-4 cursor-pointer ${pdfPages==="all"?"border-slate-900 bg-slate-50":"border-slate-200"}`}><input type="radio" name="install-pdf-pages" value="all" checked={pdfPages==="all"} onChange={()=>setPdfPages("all")} className="mr-2"/><span className="font-semibold">Tutte e 3 le pagine</span></label><label className={`rounded-xl border p-4 cursor-pointer ${pdfPages==="2-3"?"border-slate-900 bg-slate-50":"border-slate-200"}`}><input type="radio" name="install-pdf-pages" value="2-3" checked={pdfPages==="2-3"} onChange={()=>setPdfPages("2-3")} className="mr-2"/><span className="font-semibold">Solo pagine 2 e 3</span></label></div></section>
      <section className="et-card p-4 space-y-4"><h3 className="font-black text-lg">Firme</h3><p className="text-sm text-slate-600">La firma cliente è facoltativa: puoi generare il PDF senza firma e inviarlo al cliente. Le firme presenti vengono riportate sul modello ufficiale.</p><SignaturePad label="Firma Cliente" value={form.firma_cliente} onChange={v=>set("firma_cliente",v)}/><div className="space-y-3"><SignaturePad label="Firma Tecnico" value={form.firma_tecnico} onChange={v=>set("firma_tecnico",v)}/><div><Label>Oppure carica la firma tecnico da immagine</Label><Input type="file" accept="image/png,image/jpeg,image/webp" className="mt-1" onChange={loadTechnicianSignature}/><p className="mt-1 text-xs text-slate-500">PNG, JPG/JPEG o WEBP. L'immagine caricata sostituisce la firma disegnata.</p></div></div></section>

      <div className="sticky bottom-0 -mx-3 sm:-mx-6 px-3 sm:px-6 py-3 bg-white/95 backdrop-blur border-t border-slate-200 flex flex-col sm:flex-row sm:flex-wrap sm:justify-end gap-2"><Button className="h-12 w-full sm:w-auto" variant="outline" onClick={()=>onOpenChange(false)} disabled={busy}>Chiudi</Button><Button className="h-12 w-full sm:w-auto" variant="outline" onClick={save} disabled={busy}><FloppyDisk/> Salva bozza</Button>{docId&&<Button className="h-12 w-full sm:w-auto" variant="outline" onClick={download}><DownloadSimple/> Apri PDF</Button>}<Button className="h-12 w-full sm:w-auto" onClick={generate} disabled={busy}><CheckCircle/> Salva e genera PDF</Button></div>

    </div>}
  </DialogContent></Dialog>;
}
