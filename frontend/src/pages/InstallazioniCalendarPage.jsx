import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarBlank, CaretLeft, CaretRight, Clock, MapPin, User, Wrench, Package, FileText, CheckCircle, WarningCircle, PencilSimple, EnvelopeSimple } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import RecordDocuments from "../components/RecordDocuments";
import InstallationReportDialog from "../components/InstallationReportDialog";
import InstallationWeather from "../components/InstallationWeather";
import RegistryPage from "./RegistryPage";
import { useAuth } from "../lib/AuthContext";

const F = (key, label, extra = {}) => ({ key, label, ...extra });
const CLIENT_LOOKUP = { lookupResource: "clienti", lookupLabel: (x) => x?.ragione_sociale || x?.nome || "Cliente" };
const SITE_LOOKUP = { lookupResource: "sedi", lookupLabel: (x) => [x?.nome, x?.comune].filter(Boolean).join(" · ") || x?.indirizzo || "Sede" };
const COMMESSA_LOOKUP = { lookupEndpoint: "crm/lookups/commesse", lookupKey: "commesse", lookupLabel: (x) => [x?.number ? `#${x.number}` : null, x?.cliente].filter(Boolean).join(" · ") || "Commessa" };
const TECH_LOOKUP = { lookupEndpoint: "crm/lookups/technicians", lookupKey: "technicians", lookupLabel: (x) => x?.full_name || x?.username || x?.email || "Tecnico" };

const statusCls = {
  "Da programmare": "bg-slate-100 text-slate-700 border-slate-200",
  "Programmata": "bg-amber-100 text-amber-900 border-amber-300",
  "Confermata / Da installare": "bg-emerald-100 text-emerald-900 border-emerald-300",
  "Installata": "bg-emerald-200 text-emerald-950 border-emerald-400",
  "Completata": "bg-emerald-700 text-white border-emerald-800",
  "In sospeso": "bg-red-100 text-red-800 border-red-300",
  "Sospesa": "bg-red-100 text-red-800 border-red-300",
  "Annullata": "bg-red-50 text-red-700 border-red-200",
};

function fmtDate(d) {
  if (!d) return "Da programmare";
  try { return new Date(`${d}T12:00:00`).toLocaleDateString("it-IT", { weekday: "long", day: "2-digit", month: "long" }); } catch { return d; }
}
function monthKey(d) { return d ? String(d).slice(0, 7) : ""; }
function monthLabel(value) {
  const [y,m] = value.split("-").map(Number);
  return new Date(y, m-1, 1).toLocaleDateString("it-IT", { month: "long", year: "numeric" });
}
function shiftMonth(value, delta) {
  const [y,m] = value.split("-").map(Number);
  const d = new Date(y, m-1+delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
}

export default function InstallazioniCalendarPage() {
  const { user, hasPermission, isAdmin, isTecnico } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [docs, setDocs] = useState(null);
  const [reportTarget, setReportTarget] = useState(null);
  const [tab, setTab] = useState("calendar");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0,7));
  const [saving, setSaving] = useState(false);
  const [edit, setEdit] = useState({ stato: "", note: "", istruzioni_intervento: "" });
  const canCreate = hasPermission("installazioni", "create");
  const canEdit = hasPermission("installazioni", "edit");
  const canManage = canCreate || isAdmin || hasPermission("installazioni", "view_all");

  const load = async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/crm/installazioni`); setItems(data.items || []); }
    catch (e) { toast.error("Impossibile caricare le installazioni", { description: e?.response?.data?.detail || e?.message }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const monthItems = useMemo(() => items.filter(x => !x.data || monthKey(x.data) === month), [items, month]);
  const grouped = useMemo(() => {
    const map = new Map();
    for (const x of monthItems) {
      const k = x.data || "zz-da-programmare";
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(x);
    }
    return [...map.entries()].sort(([a],[b]) => a.localeCompare(b));
  }, [monthItems]);

  const openDetail = (x) => {
    setSelected(x);
    setEdit({ stato: x.stato || "Da programmare", note: x.note || "", istruzioni_intervento: x.istruzioni_intervento || "" });
  };
  const save = async () => {
    if (!selected || !canEdit) return;
    setSaving(true);
    try {
      const payload = isTecnico ? { stato: edit.stato, note: edit.note } : { stato: edit.stato, note: edit.note, istruzioni_intervento: edit.istruzioni_intervento };
      const { data } = await axios.put(`${API}/crm/installazioni/${selected.id}`, payload);
      toast.success("Installazione aggiornata");
      setSelected(data);
      await load();
    } catch (e) { toast.error("Aggiornamento non riuscito", { description: e?.response?.data?.detail || e?.message }); }
    finally { setSaving(false); }
  };
  const openReportPdf = async () => {
    if (!selected?.id) return;
    try {
      const { data } = await axios.get(`${API}/installation-reports/${selected.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      toast.error("Report non disponibile", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const sendReportToCustomer = async () => {
    if (!selected?.report_installazione_document_id || isTecnico) return;
    try {
      const { data } = await axios.post(`${API}/installation-reports/${selected.id}/send`, {});
      toast.success("Report inviato al cliente", { description: data?.recipient || "Email inviata" });
    } catch (e) {
      toast.error("Invio non riuscito", { description: e?.response?.data?.detail || e?.message });
    }
  };

  if (tab === "manage") {
    return <div className="space-y-3">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 pt-4 flex justify-end"><Button variant="outline" onClick={() => setTab("calendar")}><CalendarBlank size={17}/> Calendario</Button></div>
      <RegistryPage
        resource="installazioni" title="Gestione installazioni" subtitle=""
        newLabel="Nuova installazione"
        fields={[
          F("commessa_id", "Commessa", { ...COMMESSA_LOOKUP, required: true, fillFromLookup: { cliente_id: "cliente_id", sede_id: "sede_id", ordine_cliente_id: "ordine_cliente_id" } }),
          F("sede_id", "Sede", { ...SITE_LOOKUP, disabled: true }),
          F("tecnico_user_id", "Tecnico assegnato", { ...TECH_LOOKUP, required: true }),
          F("data", "Data", { type: "date" }),
          F("ora", "Ora", { type: "time" }),
          F("durata_prevista", "Durata prevista"),
          F("stato", "Stato", { options: ["Da programmare","Programmata","Confermata / Da installare","In sospeso","Installata","Completata","Annullata"], default: "Da programmare" }),
          F("istruzioni_intervento", "Cosa bisogna fare", { type: "textarea", full: true }),
          F("note", "Note", { type: "textarea", full: true }),
        ]}
        columns={[
          F("data", "Data"), F("ora", "Ora"), F("cliente_id", "Cliente", CLIENT_LOOKUP), F("sede_id", "Sede", SITE_LOOKUP), F("tecnico_user_id", "Tecnico", TECH_LOOKUP), F("stato", "Stato")
        ]}
      />
    </div>;
  }

  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 space-y-4" data-testid="installazioni-calendar-page">
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
      <div>
        <div className="text-xs font-semibold tracking-[.14em] uppercase text-[#1A456B]">Installazioni</div>
        <h1 className="font-display text-2xl sm:text-3xl font-black text-slate-900">Calendario interventi</h1>
        <div className="text-sm text-slate-500 mt-1">{user?.role === "tecnico" ? "Le installazioni assegnate a te" : "Programmazione e attività tecniche"}</div>
      </div>
      <div className="flex gap-2 flex-wrap">
        {canManage && <Button variant="outline" onClick={() => setTab("manage")}><PencilSimple size={17}/> Gestione</Button>}
      </div>
    </div>

    <div className="et-card p-3 sm:p-4 flex items-center justify-between gap-3">
      <Button variant="outline" size="icon" onClick={() => setMonth(m => shiftMonth(m,-1))}><CaretLeft size={18}/></Button>
      <div className="text-center"><div className="font-black text-slate-900 capitalize">{monthLabel(month)}</div><div className="text-xs text-slate-500">{monthItems.filter(x=>x.data).length} interventi programmati</div></div>
      <Button variant="outline" size="icon" onClick={() => setMonth(m => shiftMonth(m,1))}><CaretRight size={18}/></Button>
    </div>

    {loading ? <div className="et-card p-10 text-center text-slate-500">Caricamento…</div> : grouped.length === 0 ? <div className="et-card p-10 text-center text-slate-500">Nessuna installazione nel periodo selezionato.</div> : (
      <div className="space-y-5">
        {grouped.map(([date, rows]) => <section key={date}>
          <div className="flex items-center gap-2 mb-2"><CalendarBlank size={18} className="text-[#1A456B]"/><h2 className="font-black text-slate-900 capitalize">{date === "zz-da-programmare" ? "Da programmare" : fmtDate(date)}</h2><span className="text-xs text-slate-400">{rows.length}</span></div>
          <div className="grid xl:grid-cols-2 gap-3">
            {rows.map(x => <button key={x.id} onClick={() => openDetail(x)} className={`text-left et-card p-4 hover:shadow-md transition-all border-l-4 ${x.stato === "Programmata" ? "border-l-amber-400" : x.stato === "Confermata / Da installare" || x.stato === "Installata" ? "border-l-emerald-500" : x.stato === "Completata" ? "border-l-emerald-800" : x.stato === "In sospeso" || x.stato === "Sospesa" ? "border-l-red-500" : "border-l-slate-300"}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><div className="font-black text-lg text-slate-900 truncate">{x.cliente_nome || x.cliente || "Installazione"}</div><div className="text-sm text-slate-500 mt-0.5">{x.sede_nome || x.sede || x.indirizzo || "Sede da verificare"}</div></div>
                <Badge className={statusCls[x.stato] || "bg-slate-100 text-slate-700"}>{x.stato || "Da programmare"}</Badge>
              </div>
              <div className="mt-3 grid sm:grid-cols-3 gap-2 text-sm">
                <div className="rounded-lg bg-slate-50 p-2"><Clock size={15} className="inline mr-1"/>{x.ora || "Orario da definire"}</div>
                <div className="rounded-lg bg-slate-50 p-2"><User size={15} className="inline mr-1"/>{x.tecnico || "Tecnico da assegnare"}</div>
                <div className="rounded-lg bg-slate-50 p-2"><Package size={15} className="inline mr-1"/>{(x.prodotti_da_installare || []).length} prodotti</div>
              </div>
              <InstallationWeather date={x.data} address={x.sede_indirizzo_completo || x.sede_indirizzo || x.indirizzo || x.sede || ""} comune={x.sede_comune} provincia={x.sede_provincia} cap={x.sede_cap} compact className="mt-3"/>
              {(x.istruzioni_intervento || x.note) && <div className="mt-3 text-sm text-slate-700 line-clamp-2">{x.istruzioni_intervento || x.note}</div>}
            </button>)}
          </div>
        </section>)}
      </div>
    )}

    {selected && <Dialog open onOpenChange={(v)=>!v&&setSelected(null)}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="text-xl">Intervento · {selected.cliente_nome || selected.cliente || "Installazione"}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="rounded-xl border border-slate-200 p-3"><div className="text-[11px] uppercase font-bold text-slate-400">Quando</div><div className="font-bold mt-1">{fmtDate(selected.data)} {selected.ora ? `· ${selected.ora}` : ""}</div></div>
            <div className="rounded-xl border border-slate-200 p-3"><div className="text-[11px] uppercase font-bold text-slate-400">Tecnico</div><div className="font-bold mt-1">{selected.tecnico || "Da assegnare"}</div></div>
            <div className="rounded-xl border border-slate-200 p-3 sm:col-span-2"><div className="text-[11px] uppercase font-bold text-slate-400">Cliente / sede</div><div className="font-bold mt-1">{selected.cliente_nome || selected.cliente || "—"}</div><div className="text-sm text-slate-600">{selected.sede_nome || selected.sede || "—"}</div>{(selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo) && <a className="mt-2 inline-flex items-center gap-1.5 text-sm font-bold text-[#1A456B] hover:underline" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo)}`} target="_blank" rel="noreferrer"><MapPin size={16} weight="fill"/>{selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo} · Apri in Google Maps</a>}</div>
          </div>

          <InstallationWeather date={selected.data} address={selected.sede_indirizzo_completo || selected.sede_indirizzo || selected.indirizzo || selected.sede || ""} comune={selected.sede_comune} provincia={selected.sede_provincia} cap={selected.sede_cap}/>

          <div className="rounded-xl border border-slate-200 p-4">
            <div className="font-black flex items-center gap-2"><Package size={18}/> Prodotti da installare</div>
            <div className="mt-3 space-y-2">{(selected.prodotti_da_installare || []).length ? selected.prodotti_da_installare.map((p,i)=><div key={i} className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2"><span className="font-semibold">{p.nome}</span><span className="font-black">× {p.quantita}</span></div>) : <div className="text-sm text-slate-500">Nessun prodotto indicato.</div>}</div>
          </div>

          <div className="rounded-xl border-2 border-red-200 bg-red-50/70 p-4">
            <div className="font-black flex items-center gap-2 text-red-700"><Wrench size={18} weight="fill"/> Cosa bisogna fare</div>
            {(selected.attivita_da_eseguire || []).length > 0 && <div className="mt-3 space-y-2">{selected.attivita_da_eseguire.map((a,i)=><div key={i} className="rounded-lg border border-red-100 bg-white px-3 py-2 text-sm text-red-800"><b>{a.descrizione}</b>{a.quantita ? ` · q.tà ${a.quantita}` : ""}</div>)}</div>}
            <div className="mt-3 text-sm whitespace-pre-wrap font-semibold text-red-800">{selected.istruzioni_intervento || selected.note || "Nessuna istruzione aggiuntiva."}</div>
          </div>

          {canEdit && <div className="rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="font-black">Aggiorna intervento</div>
            <div><Label>Stato</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-3" value={edit.stato} onChange={e=>setEdit(v=>({...v,stato:e.target.value}))}>{(isTecnico ? ["Installata","Annullata"] : ["Da programmare","Programmata","Confermata / Da installare","In sospeso","Installata","Completata","Annullata"]).map(s=><option key={s}>{s}</option>)}</select></div>
            <div><Label>Note intervento</Label><Textarea className="mt-1" rows={3} value={edit.note} onChange={e=>setEdit(v=>({...v,note:e.target.value}))}/></div>
            <Button onClick={save} disabled={saving} className="w-full sm:w-auto bg-[#1A456B] hover:bg-[#163B5C] text-white"><CheckCircle size={17}/>{saving?"Salvataggio…":"Salva aggiornamento"}</Button>
          </div>}

          <div className="grid sm:grid-cols-2 gap-2">
            <Button variant="outline" className="w-full h-12" onClick={()=>setDocs(selected)}><FileText size={18}/> Carica documenti o foto</Button>
            {selected.report_installazione_document_id ? <>
              <Button variant="outline" className="w-full h-12" onClick={openReportPdf}><FileText size={18}/> Apri PDF</Button>
              {!isTecnico && <Button variant="outline" className="w-full h-12" onClick={sendReportToCustomer}><EnvelopeSimple size={18}/> Invia report al cliente</Button>}
              <Button className="w-full h-12 bg-[#1A456B] hover:bg-[#163B5C] text-white sm:col-span-2" onClick={()=>setReportTarget(selected)}><PencilSimple size={18}/> Modifica report</Button>
            </> : <Button className="w-full h-12 bg-[#1A456B] hover:bg-[#163B5C] text-white" onClick={()=>setReportTarget(selected)}><PencilSimple size={18}/> Compila report pre e post installazione</Button>}
          </div>
        </div>
      </DialogContent>
    </Dialog>}

    {docs && <RecordDocuments open={true} onOpenChange={(v)=>!v&&setDocs(null)} resource="installazioni" recordId={docs.id} module="installazioni" title="Documenti e foto intervento"/>}
    {reportTarget && <InstallationReportDialog open={true} onOpenChange={(v)=>!v&&setReportTarget(null)} installation={reportTarget} onGenerated={(result)=>{ setSelected(prev=>prev?{...prev,report_installazione_document_id:result?.document_id||prev.report_installazione_document_id}:prev); load(); }}/>}
  </div>;
}
