import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus,
  MagnifyingGlass,
  ArrowLeft,
  ShoppingCart,
  FileText,
  MapPin,
  UsersThree,
  Wrench,
  Headset,
  ClipboardText,
  Package,
  PencilSimple,
  Trash,
  CheckCircle,
  CopySimple,
  Buildings,
  IdentificationCard,
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import RecordDocuments from "../components/RecordDocuments";
import InstallationWeather from "../components/InstallationWeather";
import { useAuth } from "../lib/AuthContext";



const CLIENT_EMPTY = {
  tipo: "Azienda",
  ragione_sociale: "",
  partita_iva: "",
  codice_fiscale: "",
  referente: "",
  telefono: "",
  email: "",
  indirizzo: "",
  cap: "",
  comune: "",
  provincia: "",
  agente: "",
  provenienza_cliente: "",
  note: "",
  assistenza_smart: false,
  backend_elios_tech: false,
  scadenza_backend: "",
  scadenza_assistenza_smart: "",
  id_wallbox: "",
  password_wallbox: "",
  numero_caso_wallbox: "",
  electromaps: false,
  eviaggio: false,
  nextcharge: false,
  plugshare: false,
  recensione_google: false,
};

const ORDER_EMPTY = {
  numero: "",
  data: new Date().toISOString().slice(0, 10),
  sede_id: "",
  preventivo_id: "",
  stato_commerciale: "Bozza",
  stato_contratto: "Da predisporre",
  data_firma: "",
  modalita_pagamento: "Acquisto",
  importo: "",
  prodotti: "",
  righe: [],
  qty_wallbox: "",
  stato_finanziaria: "Non richiesta",
  finanziaria: "",
  numero_pratica_finanziaria: "",
  data_invio_finanziaria: "",
  data_esito_finanziaria: "",
  motivo_esito_finanziaria: "",
  importo_finanziato: "",
  anticipo: "",
  durata_mesi: "",
  rata_canone: "",
  referente_finanziaria: "",
  note_finanziaria: "",
  stato_amministrativo: "Da fatturare",
  stato_logistico: "Da preparare",
  stato_installazione: "Da valutare",
  note: "",
};

function errText(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" • ");
  return e?.message || "Errore";
}

function customerName(c) {
  return c?.nome_struttura || c?.ragione_sociale || [c?.nome, c?.cognome].filter(Boolean).join(" ") || "Cliente";
}

function statusClass(value) {
  const v = String(value || "").toLowerCase();
  if (v.includes("approv") || v.includes("complet") || v.includes("sald") || v.includes("consegn") || v.includes("installato")) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (v.includes("respint") || v.includes("annull") || v.includes("recesso")) return "bg-red-50 text-red-700 border-red-200";
  if (v.includes("attesa") || v.includes("istruttoria") || v.includes("integrazione") || v.includes("parziale")) return "bg-amber-50 text-amber-800 border-amber-200";
  return "bg-slate-50 text-slate-700 border-slate-200";
}

function StatusBadge({ children }) {
  if (!children) return <span className="text-slate-400">—</span>;
  return <Badge variant="outline" className={statusClass(children)}>{children}</Badge>;
}

function Field({ label, value }) {
  return <div><div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">{label}</div><div className="text-sm text-slate-800 mt-0.5 whitespace-pre-wrap break-words">{value === false || value === 0 ? String(value) : (value || "—")}</div></div>;
}

function formatDateIT(value) {
  if (!value) return "—";
  const raw = String(value).slice(0, 10);
  const [y,m,d] = raw.split("-");
  return y && m && d ? `${d}/${m}/${y}` : value;
}

function daysTo(value) {
  if (!value) return null;
  const end = new Date(`${String(value).slice(0,10)}T23:59:59`);
  if (Number.isNaN(end.getTime())) return null;
  return Math.ceil((end.getTime() - Date.now()) / 86400000);
}

function ServiceCard({ title, active, expiry, noExpiryLabel, icon: Icon = CheckCircle }) {
  const days = daysTo(expiry);
  const expired = active && days != null && days < 0;
  const soon = active && days != null && days >= 0 && days <= 30;
  const tone = !active ? "border-slate-200 bg-slate-50" : expired ? "border-red-200 bg-red-50" : soon ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50";
  const text = !active ? "Non attivo" : expired ? "Scaduto" : soon ? `Scade tra ${days} gg` : "Attivo";
  return <div className={`rounded-2xl border p-4 ${tone}`}>
    <div className="flex items-start justify-between gap-3">
      <div><div className="text-xs uppercase tracking-wider font-bold text-slate-500">{title}</div><div className="text-xl font-bold text-slate-950 mt-1">{text}</div></div>
      <Icon size={24} className={active ? (expired ? "text-red-600" : soon ? "text-amber-600" : "text-emerald-600") : "text-slate-400"}/>
    </div>
    <div className="text-sm text-slate-600 mt-3">{expiry ? <>Scadenza <b>{formatDateIT(expiry)}</b></> : (active ? (noExpiryLabel || "Nessuna scadenza registrata") : "Servizio non attivo")}</div>
  </div>;
}

function CopyValue({ label, value }) {
  const copy = async () => {
    if (!value) return;
    try { await navigator.clipboard.writeText(String(value)); toast.success(`${label} copiato`); }
    catch { toast.error("Impossibile copiare"); }
  };
  return <div className="rounded-xl border border-slate-200 bg-white p-3 min-w-0">
    <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">{label}</div>
    <div className="flex items-center gap-2 mt-1"><div className="font-semibold text-slate-900 break-all flex-1">{value || "—"}</div>{value && <button type="button" onClick={copy} className="shrink-0 h-8 px-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600" title={`Copia ${label}`}><CopySimple size={15}/></button>}</div>
  </div>;
}

function BoolPill({ label, active }) {
  return <div className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2 ${active ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}><span className="text-sm font-medium">{label}</span><span className={`text-xs font-bold ${active ? "text-emerald-700" : "text-slate-400"}`}>{active ? "ATTIVO" : "NO"}</span></div>;
}

function ClientFormDialog({ open, onClose, client, onSaved }) {
  const [form, setForm] = useState(client ? { ...CLIENT_EMPTY, ...client } : { ...CLIENT_EMPTY });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setForm(client ? { ...CLIENT_EMPTY, ...client } : { ...CLIENT_EMPTY }); }, [open, client]);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const save = async (e) => {
    e.preventDefault();
    if (!form.ragione_sociale.trim()) return toast.error("Inserisci la ragione sociale o il nome del cliente");
    setSaving(true);
    try {
      const response = client?.id
        ? await axios.put(`${API}/crm/clienti/${client.id}`, form)
        : await axios.post(`${API}/crm/clienti`, form);
      toast.success(client?.id ? "Cliente aggiornato" : "Cliente creato");
      onSaved?.(response.data); onClose();
    } catch (e) { toast.error("Salvataggio cliente non riuscito", { description: errText(e) }); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
    <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto">
      <DialogHeader><DialogTitle>{client?.id ? "Modifica cliente" : "Nuovo cliente"}</DialogTitle></DialogHeader>
      <form onSubmit={save} className="space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Tipo cliente</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.tipo} onChange={(e) => set("tipo", e.target.value)}><option>Azienda</option><option>Privato</option></select></div>
          <div><Label>{form.tipo === "Privato" ? "Nome e cognome *" : "Ragione sociale *"}</Label><Input className="mt-1 h-12" required value={form.ragione_sociale} onChange={(e) => set("ragione_sociale", e.target.value)} /></div>
          <div><Label>Partita IVA</Label><Input className="mt-1 h-12" value={form.partita_iva} onChange={(e) => set("partita_iva", e.target.value)} /></div>
          <div><Label>Codice fiscale</Label><Input className="mt-1 h-12" value={form.codice_fiscale} onChange={(e) => set("codice_fiscale", e.target.value)} /></div>
          <div><Label>Referente principale</Label><Input className="mt-1 h-12" value={form.referente} onChange={(e) => set("referente", e.target.value)} /></div>
          <div><Label>Telefono</Label><Input className="mt-1 h-12" value={form.telefono} onChange={(e) => set("telefono", e.target.value)} /></div>
          <div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={form.email} onChange={(e) => set("email", e.target.value)} /></div>
          <div><Label>Agente</Label><Input className="mt-1 h-12" value={form.agente} onChange={(e) => set("agente", e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Indirizzo</Label><Input className="mt-1 h-12" value={form.indirizzo} onChange={(e) => set("indirizzo", e.target.value)} /></div>
          <div><Label>CAP</Label><Input className="mt-1 h-12" value={form.cap} onChange={(e) => set("cap", e.target.value)} /></div>
          <div><Label>Comune</Label><Input className="mt-1 h-12" value={form.comune} onChange={(e) => set("comune", e.target.value)} /></div>
          <div><Label>Provincia</Label><Input className="mt-1 h-12" value={form.provincia} onChange={(e) => set("provincia", e.target.value)} /></div>
          <div><Label>Provenienza cliente</Label><Input className="mt-1 h-12" value={form.provenienza_cliente} onChange={(e) => set("provenienza_cliente", e.target.value)} placeholder="Lead, referenza, cliente attivo…" /></div>
          <div><Label>ID Wallbox</Label><Input className="mt-1 h-12" value={form.id_wallbox} onChange={(e) => set("id_wallbox", e.target.value)} /></div>
          <div><Label>Password Wallbox</Label><Input className="mt-1 h-12" value={form.password_wallbox} onChange={(e) => set("password_wallbox", e.target.value)} /></div>
          <div><Label>Scadenza Backend</Label><Input type="date" className="mt-1 h-12" value={form.scadenza_backend || ""} onChange={(e) => set("scadenza_backend", e.target.value)} /></div>
          <div><Label>Scadenza Assistenza SMART</Label><Input type="date" className="mt-1 h-12" value={form.scadenza_assistenza_smart || ""} onChange={(e) => set("scadenza_assistenza_smart", e.target.value)} /></div>
          <div><Label>Numero caso Wallbox</Label><Input className="mt-1 h-12" value={form.numero_caso_wallbox} onChange={(e) => set("numero_caso_wallbox", e.target.value)} /></div>
          <div className="sm:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-3 rounded-xl border border-slate-200 p-3">{[["assistenza_smart","Assistenza SMART"],["backend_elios_tech","Backend Elios Tech"],["electromaps","Electromaps"],["eviaggio","Eviaggio"],["nextcharge","Nextcharge"],["plugshare","Plugshare"],["recensione_google","Recensione Google"]].map(([k,l])=><label key={k} className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" className="h-4 w-4" checked={!!form[k]} onChange={(e)=>set(k,e.target.checked)}/>{l}</label>)}</div>
          <div className="sm:col-span-2"><Label>Note</Label><Textarea className="mt-1" rows={4} value={form.note} onChange={(e) => set("note", e.target.value)} /></div>
        </div>
        <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving ? "Salvataggio…" : client?.id ? "Salva modifiche" : "Salva e apri cliente"}</Button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}

function OrderDialog({ open, onClose, clientId, sites, quotes = [], order, onSaved }) {
  const [form, setForm] = useState(order ? { ...ORDER_EMPTY, ...order } : { ...ORDER_EMPTY });
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState([]);
  const [localSites, setLocalSites] = useState(sites || []);
  const [siteOpen, setSiteOpen] = useState(false);
  const [siteSaving, setSiteSaving] = useState(false);
  const [siteDraft, setSiteDraft] = useState({ nome: "Sede installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" });

  useEffect(() => {
    if (!open) return;
    setForm(order ? { ...ORDER_EMPTY, ...order, righe: Array.isArray(order.righe) ? order.righe : [] } : { ...ORDER_EMPTY, righe: [] });
    setLocalSites(sites || []);
    axios.get(`${API}/products`).then(({ data }) => setProducts((data.items || []).filter((x) => x.active !== false))).catch(() => setProducts([]));
  }, [open, order, sites]);

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const setPayment = (value) => setForm((p) => {
    if (value === "Acquisto") return { ...p, modalita_pagamento: value, stato_finanziaria: "Non richiesta", finanziaria: "" };
    return {
      ...p,
      modalita_pagamento: value,
      finanziaria: value === "Altro finanziamento / noleggio" ? (p.finanziaria || "") : value,
      stato_finanziaria: !p.stato_finanziaria || p.stato_finanziaria === "Non richiesta" ? "Da preparare" : p.stato_finanziaria,
    };
  });
  const isFinance = form.modalita_pagamento !== "Acquisto";
  const rows = Array.isArray(form.righe) ? form.righe : [];
  const addRow = () => set("righe", [...rows, { tipo_riga: "materiale", product_page_id: "", product_name: "", product_code: "", descrizione: "", tipo_gestione: "", quantity: 1 }]);
  const updateRow = (index, patch) => set("righe", rows.map((r, i) => i === index ? { ...r, ...patch } : r));
  const selectProduct = (index, productId) => {
    const product = products.find((x) => String(x.id) === String(productId));
    updateRow(index, product ? {
      product_page_id: product.id,
      product_name: product.name,
      product_code: product.code || "",
      tipo_gestione: product.tipo_gestione || "a_quantita",
      unit: product.unit || "pz",
    } : { product_page_id: "", product_name: "", product_code: "", tipo_gestione: "" });
  };
  const removeRow = (index) => set("righe", rows.filter((_, i) => i !== index));
  const applyQuote = (quoteId) => {
    const quote = quotes.find((x) => String(x.id) === String(quoteId));
    if (!quote) return set("preventivo_id", "");
    setForm((p) => ({
      ...p,
      preventivo_id: quote.id,
      sede_id: p.sede_id || quote.sede_id || "",
      importo: quote.totale ?? quote.importo ?? p.importo,
      righe: Array.isArray(quote.righe) ? quote.righe.map((r) => ({ ...r })) : p.righe,
      note: p.note || (quote.numero ? `Da preventivo ${quote.numero}` : ""),
    }));
  };

  const createSite = async () => {
    if (!siteDraft.nome.trim() || !siteDraft.indirizzo.trim() || !siteDraft.comune.trim()) {
      return toast.error("Nome sede, indirizzo e comune sono obbligatori");
    }
    setSiteSaving(true);
    try {
      const { data } = await axios.post(`${API}/crm/sedi`, { cliente_id: clientId, tipo: "Installazione", ...siteDraft });
      setLocalSites((prev) => [...prev, data]);
      set("sede_id", data.id);
      setSiteOpen(false);
      setSiteDraft({ nome: "Sede installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" });
      toast.success("Sede creata e selezionata");
    } catch (e) { toast.error("Creazione sede non riuscita", { description: errText(e) }); }
    finally { setSiteSaving(false); }
  };

  const save = async (e) => {
    e.preventDefault(); setSaving(true);
    try {
      const cleanRows = rows
        .filter((r) => Number(r.quantity) > 0 && (r.product_page_id || String(r.descrizione || r.product_name || "").trim()))
        .map((r) => ({ ...r, quantity: Number(r.quantity) }));
      const payload = {
        ...form,
        cliente_id: clientId,
        righe: cleanRows,
        importo: form.importo === "" ? null : Number(form.importo),
        qty_wallbox: form.qty_wallbox === "" ? null : Number(form.qty_wallbox),
        importo_finanziato: form.importo_finanziato === "" ? null : Number(form.importo_finanziato),
        anticipo: form.anticipo === "" ? null : Number(form.anticipo),
        durata_mesi: form.durata_mesi === "" ? null : Number(form.durata_mesi),
        rata_canone: form.rata_canone === "" ? null : Number(form.rata_canone),
      };
      if (!isFinance) Object.assign(payload, {
        stato_finanziaria: "Non richiesta", finanziaria: "", numero_pratica_finanziaria: "",
        data_invio_finanziaria: "", data_esito_finanziaria: "", motivo_esito_finanziaria: "",
        importo_finanziato: null, anticipo: null, durata_mesi: null, rata_canone: null,
        referente_finanziaria: "", note_finanziaria: "",
      });
      const response = order?.id
        ? await axios.put(`${API}/crm/ordini-clienti/${order.id}`, payload)
        : await axios.post(`${API}/crm/ordini-clienti`, payload);
      const savedOrder = response.data;
      let commessaMessage = "";
      if (form.stato_commerciale === "Ordine confermato" && savedOrder?.id) {
        try {
          const { data: cmmResult } = await axios.post(`${API}/commesse/from-order/${savedOrder.id}`);
          commessaMessage = cmmResult?.created ? " · Commessa creata automaticamente" : " · Commessa aggiornata";
        } catch (commessaErr) {
          toast.warning("Ordine salvato, ma la commessa non è ancora attivabile", { description: errText(commessaErr) });
        }
      }
      toast.success(`${order?.id ? "Ordine aggiornato" : "Ordine creato"}${commessaMessage}`);
      onSaved?.(); onClose();
    } catch (e) { toast.error("Salvataggio ordine non riuscito", { description: errText(e) }); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
    <DialogContent className="max-w-5xl max-h-[94vh] overflow-y-auto">
      <DialogHeader><DialogTitle>{order?.id ? "Modifica ordine" : "Nuovo ordine"}</DialogTitle></DialogHeader>
      <form onSubmit={save} className="space-y-5">
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div><Label>Numero ordine</Label><Input className="mt-1 h-12" value={form.numero} onChange={(e) => set("numero", e.target.value)} placeholder="Automatico se lasciato vuoto" /></div>
          <div><Label>Data ordine *</Label><Input type="date" required className="mt-1 h-12" value={form.data} onChange={(e) => set("data", e.target.value)} /></div>
          <div><Label>Preventivo collegato</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.preventivo_id || ""} onChange={(e)=>applyQuote(e.target.value)}><option value="">Nessuno / ordine diretto</option>{quotes.map((q)=><option key={q.id} value={q.id}>{[q.numero,q.data,q.stato].filter(Boolean).join(" · ")}</option>)}</select><div className="mt-1 text-[11px] text-slate-500">Selezionandolo, prodotti e importo vengono importati dal preventivo.</div></div>
          <div>
            <Label>Sede di installazione</Label>
            <select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.sede_id} onChange={(e) => set("sede_id", e.target.value)}>
              <option value="">Da definire</option>{localSites.map((site) => <option key={site.id} value={site.id}>{[site.nome, site.indirizzo, site.comune].filter(Boolean).join(" · ")}</option>)}
            </select>
            <button type="button" onClick={() => setSiteOpen((v) => !v)} className="mt-2 text-xs font-semibold text-blue-700 hover:text-blue-900">+ Crea una nuova sede</button>
          </div>
          <div><Label>Stato commerciale</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_commerciale} onChange={(e) => set("stato_commerciale", e.target.value)}>{["Bozza","Attesa firma","Contratto firmato","Ordine confermato","Sospeso","Annullato / Recesso"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div><Label>Stato contratto</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_contratto} onChange={(e) => set("stato_contratto", e.target.value)}>{["Da predisporre","Da firmare","Firmato","Annullato"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div><Label>Data firma</Label><Input type="date" className="mt-1 h-12" value={form.data_firma} onChange={(e) => set("data_firma", e.target.value)} /></div>
          <div><Label>Modalità di pagamento</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.modalita_pagamento} onChange={(e) => setPayment(e.target.value)}>{["Acquisto","Cofidis","Noleggio Grenke","DLL","Italfinance","Sella","Fastrent","PEAC","Altro finanziamento / noleggio"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div><Label>Importo ordine (€)</Label><Input type="number" step="0.01" min="0" className="mt-1 h-12" value={form.importo} onChange={(e) => set("importo", e.target.value)} /></div>
          <div><Label>Quantità Wallbox</Label><Input type="number" min="0" className="mt-1 h-12" value={form.qty_wallbox} onChange={(e) => set("qty_wallbox", e.target.value)} /></div>
        </div>

        {siteOpen && <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <div className="font-bold text-sm mb-3">Nuova sede di installazione</div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div><Label>Nome sede *</Label><Input className="mt-1 h-12" value={siteDraft.nome} onChange={(e)=>setSiteDraft((p)=>({...p,nome:e.target.value}))}/></div>
            <div className="lg:col-span-2"><Label>Indirizzo *</Label><Input className="mt-1 h-12" value={siteDraft.indirizzo} onChange={(e)=>setSiteDraft((p)=>({...p,indirizzo:e.target.value}))}/></div>
            <div><Label>Civico</Label><Input className="mt-1 h-12" value={siteDraft.civico} onChange={(e)=>setSiteDraft((p)=>({...p,civico:e.target.value}))}/></div>
            <div><Label>CAP</Label><Input className="mt-1 h-12" value={siteDraft.cap} onChange={(e)=>setSiteDraft((p)=>({...p,cap:e.target.value}))}/></div>
            <div><Label>Comune *</Label><Input className="mt-1 h-12" value={siteDraft.comune} onChange={(e)=>setSiteDraft((p)=>({...p,comune:e.target.value}))}/></div>
            <div><Label>Provincia</Label><Input className="mt-1 h-12" value={siteDraft.provincia} onChange={(e)=>setSiteDraft((p)=>({...p,provincia:e.target.value}))}/></div>
            <div><Label>Telefono</Label><Input className="mt-1 h-12" value={siteDraft.telefono} onChange={(e)=>setSiteDraft((p)=>({...p,telefono:e.target.value}))}/></div>
          </div>
          <div className="mt-3 flex justify-end"><Button type="button" variant="outline" onClick={createSite} disabled={siteSaving}>{siteSaving ? "Creazione…" : "Crea e seleziona sede"}</Button></div>
        </div>}

        <div className="rounded-md border border-slate-200 p-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div><h3 className="font-bold">Righe ordine</h3><p className="text-xs text-slate-500">Materiali e servizi restano strutturati. Quando l’ordine è confermato, la stessa commessa viene creata o aggiornata automaticamente.</p></div>
            <Button type="button" variant="outline" onClick={addRow}><Plus size={16}/> Aggiungi prodotto</Button>
          </div>
          <div className="space-y-2">
            {rows.map((row, index) => <div key={index} className="grid grid-cols-1 lg:grid-cols-[130px_1fr_1fr_110px_48px] gap-2 items-end border border-slate-100 rounded-md p-2">
              <div><Label>Tipo</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-2" value={row.tipo_riga || "materiale"} onChange={(e)=>updateRow(index,{tipo_riga:e.target.value})}><option value="materiale">Materiale</option><option value="servizio">Servizio</option><option value="installazione">Installazione</option><option value="progettazione">Progettazione</option><option value="trasporto">Trasporto</option><option value="manodopera">Manodopera</option></select></div>
              <div><Label>{(row.tipo_riga || "materiale") === "materiale" ? "Prodotto" : "Voce"}</Label>{(row.tipo_riga || "materiale") === "materiale" ? <select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={row.product_page_id || ""} onChange={(e)=>selectProduct(index,e.target.value)}><option value="">Seleziona prodotto…</option>{products.map((product)=><option key={product.id} value={product.id}>{product.code ? `${product.code} · ` : ""}{product.name}</option>)}</select> : <Input className="mt-1 h-12" value={row.descrizione || row.product_name || ""} onChange={(e)=>updateRow(index,{descrizione:e.target.value,product_name:e.target.value})} />}</div>
              <div><Label>Descrizione</Label><Input className="mt-1 h-12" value={row.descrizione || row.product_name || ""} onChange={(e)=>updateRow(index,{descrizione:e.target.value})}/></div>
              <div><Label>Quantità</Label><Input type="number" min="0.01" step="0.01" className="mt-1 h-12" value={row.quantity ?? 1} onChange={(e)=>updateRow(index,{quantity:e.target.value})}/></div>
              <Button type="button" variant="ghost" size="icon" className="h-12 w-12 text-red-600" onClick={()=>removeRow(index)} aria-label="Rimuovi prodotto"><Trash size={17}/></Button>
            </div>)}
            {rows.length === 0 && <div className="text-sm text-slate-400 py-3 text-center">Nessun prodotto inserito.</div>}
          </div>
          <div className="mt-3"><Label>Note configurazione / prodotti non a catalogo</Label><Textarea className="mt-1" rows={2} value={form.prodotti} onChange={(e) => set("prodotti", e.target.value)} /></div>
        </div>

        {isFinance && <div className="rounded-md border border-blue-200 bg-blue-50/40 p-4">
          <h3 className="font-bold text-slate-900 mb-3">Avanzamento finanziaria</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div><Label>Finanziaria</Label><Input className="mt-1 h-12" value={form.finanziaria || form.modalita_pagamento} onChange={(e) => set("finanziaria", e.target.value)} /></div>
            <div><Label>Stato pratica</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_finanziaria} onChange={(e) => set("stato_finanziaria", e.target.value)}>{["Da preparare","Da inviare","Inviata","In istruttoria","Integrazione richiesta","Approvata","Respinta","Annullata","Erogata / Contratto attivo"].map((x)=><option key={x}>{x}</option>)}</select></div>
            <div><Label>Numero pratica</Label><Input className="mt-1 h-12" value={form.numero_pratica_finanziaria} onChange={(e) => set("numero_pratica_finanziaria", e.target.value)} /></div>
            <div><Label>Importo finanziato (€)</Label><Input type="number" min="0" step="0.01" className="mt-1 h-12" value={form.importo_finanziato} onChange={(e)=>set("importo_finanziato",e.target.value)}/></div>
            <div><Label>Anticipo (€)</Label><Input type="number" min="0" step="0.01" className="mt-1 h-12" value={form.anticipo} onChange={(e)=>set("anticipo",e.target.value)}/></div>
            <div><Label>Durata (mesi)</Label><Input type="number" min="0" className="mt-1 h-12" value={form.durata_mesi} onChange={(e)=>set("durata_mesi",e.target.value)}/></div>
            <div><Label>Rata / canone (€)</Label><Input type="number" min="0" step="0.01" className="mt-1 h-12" value={form.rata_canone} onChange={(e)=>set("rata_canone",e.target.value)}/></div>
            <div><Label>Referente finanziaria</Label><Input className="mt-1 h-12" value={form.referente_finanziaria} onChange={(e)=>set("referente_finanziaria",e.target.value)}/></div>
            <div><Label>Data invio</Label><Input type="date" className="mt-1 h-12" value={form.data_invio_finanziaria} onChange={(e) => set("data_invio_finanziaria", e.target.value)} /></div>
            <div><Label>Data esito</Label><Input type="date" className="mt-1 h-12" value={form.data_esito_finanziaria} onChange={(e) => set("data_esito_finanziaria", e.target.value)} /></div>
            <div className="sm:col-span-2"><Label>Esito / motivo rifiuto</Label><Input className="mt-1 h-12" value={form.motivo_esito_finanziaria} onChange={(e) => set("motivo_esito_finanziaria", e.target.value)} /></div>
            <div className="sm:col-span-2 lg:col-span-3"><Label>Note pratica</Label><Textarea className="mt-1" rows={2} value={form.note_finanziaria} onChange={(e)=>set("note_finanziaria",e.target.value)}/></div>
          </div>
          <p className="text-xs text-slate-500 mt-3">Il gestionale registra solo l'avanzamento della pratica. I documenti della finanziaria non vengono caricati qui.</p>
        </div>}

        <div className="grid sm:grid-cols-3 gap-4">
          <div><Label>Stato amministrativo</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_amministrativo} onChange={(e) => set("stato_amministrativo", e.target.value)}>{["Da fatturare","Fatturato","Saldo parziale","Saldato"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div><Label>Stato logistico</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_logistico} onChange={(e) => set("stato_logistico", e.target.value)}>{["Da preparare","Materiale parziale","Materiale disponibile","Picking","Pronto alla spedizione","Spedito","Consegnato"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div><Label>Stato installazione</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.stato_installazione} onChange={(e) => set("stato_installazione", e.target.value)}>{["Da valutare","Sopralluogo necessario","Da programmare","Programmata","In corso","Sospesa","Completata"].map((x)=><option key={x}>{x}</option>)}</select></div>
          <div className="sm:col-span-3"><Label>Note ordine</Label><Textarea className="mt-1" rows={3} value={form.note} onChange={(e) => set("note", e.target.value)} /></div>
        </div>
        <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving ? "Salvataggio…" : "Salva ordine"}</Button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}

function SmallCreateDialog({ open, onClose, title, fields, endpoint, base, onSaved }) {
  const [form, setForm] = useState({ ...base });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setForm({ ...base }); }, [open, base]);
  const save = async (e) => {
    e.preventDefault(); setSaving(true);
    try { await axios.post(endpoint, form); toast.success(`${title} creato`); onSaved?.(); onClose(); }
    catch (e) { toast.error("Salvataggio non riuscito", { description: errText(e) }); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader><form onSubmit={save} className="space-y-4"><div className="grid sm:grid-cols-2 gap-4">{fields.map((f) => <div key={f.key} className={f.full ? "sm:col-span-2" : ""}><Label>{f.label}{f.required ? " *" : ""}</Label>{f.type === "textarea" ? <Textarea className="mt-1" required={f.required} value={form[f.key] || ""} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))} /> : <Input type={f.type || "text"} className="mt-1 h-12" required={f.required} value={form[f.key] || ""} onChange={(e) => setForm((p) => ({ ...p, [f.key]: e.target.value }))} />}</div>)}</div><DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving ? "Salvataggio…" : "Salva"}</Button></DialogFooter></form></DialogContent></Dialog>;
}

function ClientDetail({ clientId, onBack, onReloadList }) {
  const { hasPermission } = useAuth();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("panoramica");
  const [editClient, setEditClient] = useState(false);
  const [orderDialog, setOrderDialog] = useState({ open: false, order: null });
  const [simpleDialog, setSimpleDialog] = useState(null);
  const [docs, setDocs] = useState(null);
  const canEdit = hasPermission("ordini_clienti", "edit");
  const canCreate = hasPermission("ordini_clienti", "create");
  const canCreateCommessa = hasPermission("commesse", "create");
  const createOrOpenCommessa = async (order) => {
    try {
      const { data: result } = await axios.post(`${API}/commesse/from-order/${order.id}`);
      const cmm = result?.commessa;
      if (!cmm?.id) throw new Error("Commessa non disponibile");
      toast.success(result.created ? "Commessa creata" : "Commessa già presente");
      window.location.href = `/commesse?open=${encodeURIComponent(cmm.id)}`;
    } catch (e) {
      toast.error("Impossibile creare la commessa", { description: errText(e) });
    }
  };
  const load = async () => {
    try { setData((await axios.get(`${API}/crm/clienti/${clientId}/dossier`)).data); }
    catch (e) { toast.error("Impossibile aprire il cliente", { description: errText(e) }); }
  };
  useEffect(() => { load(); }, [clientId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!data) return <div className="p-8 text-slate-500">Caricamento cliente…</div>;
  const c = data.cliente;
  const n = data.notion?.status === "found" ? data.notion : {};
  const fromNotion = data.notion?.status === "found";
  const notionOrLocal = (key) => fromNotion && n[key] !== null && n[key] !== undefined && n[key] !== "" ? n[key] : c[key];
  const backendActive = fromNotion && n.backend_elios_tech !== null && n.backend_elios_tech !== undefined ? !!n.backend_elios_tech : !!c.backend_elios_tech;
  const smartActive = fromNotion && n.assistenza_smart !== null && n.assistenza_smart !== undefined ? !!n.assistenza_smart : !!c.assistenza_smart;
  const backendExpiry = notionOrLocal("scadenza_backend");
  const smartExpiry = c.scadenza_assistenza_smart || "";
  const wbId = notionOrLocal("id_wallbox");
  const wbPassword = notionOrLocal("password_wallbox");
  const wbCase = notionOrLocal("numero_caso_wallbox");
  const productCodes = Array.isArray(n.codici_prodotto) && n.codici_prodotto.length ? n.codici_prodotto : (Array.isArray(c.codici_prodotto) ? c.codici_prodotto : []);
  const serials = Array.isArray(n.sn_wb) && n.sn_wb.length ? n.sn_wb : (Array.isArray(c.sn_wb) ? c.sn_wb : []);
  const qrCodes = Array.isArray(n.qr_codes) && n.qr_codes.length ? n.qr_codes : (Array.isArray(c.qr_codes) ? c.qr_codes : []);
  const localProductRows = (data.ordini || []).flatMap((o) => Array.isArray(o.righe) ? o.righe : []);
  const tabs = [
    ["panoramica", "Panoramica"], ["anagrafica", "Dati cliente"], ["referenti", "Referenti e sedi"], ["ordini", "Ordini"], ["tecnico", "Tecnico"], ["assistenza", "Assistenza"], ["backend", "Backend e portali"], ["storico", "Storico"],
  ];
  const createContact = () => setSimpleDialog({ title: "Nuovo referente", endpoint: `${API}/crm/contatti`, base: { cliente_id: clientId, nome: "", cognome: "", ruolo: "", telefono: "", email: "" }, fields: [{key:"nome",label:"Nome",required:true},{key:"cognome",label:"Cognome"},{key:"ruolo",label:"Ruolo"},{key:"telefono",label:"Telefono"},{key:"email",label:"Email",type:"email"}] });
  const createSite = () => setSimpleDialog({ title: "Nuova sede", endpoint: `${API}/crm/sedi`, base: { cliente_id: clientId, nome: "Sede installazione", tipo: "Installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" }, fields: [{key:"nome",label:"Nome sede",required:true},{key:"indirizzo",label:"Indirizzo",required:true},{key:"civico",label:"Civico"},{key:"cap",label:"CAP"},{key:"comune",label:"Comune",required:true},{key:"provincia",label:"Provincia"},{key:"telefono",label:"Telefono"}] });

  const overviewOrder = data.ordini?.[0];
  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 sm:py-7">
    <div className="flex flex-col gap-4 mb-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-2"><ArrowLeft size={16} /> Elios Tech Ordini</button>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-slate-950 truncate">{customerName(c)}</h1>
          <div className="flex flex-wrap gap-2 mt-2"><StatusBadge>{c.tipo}</StatusBadge>{overviewOrder && <StatusBadge>{overviewOrder.stato_commerciale || overviewOrder.stato}</StatusBadge>}{overviewOrder?.stato_finanziaria && overviewOrder.stato_finanziaria !== "Non richiesta" && <StatusBadge>{overviewOrder.stato_finanziaria}</StatusBadge>}</div>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">{canEdit && <Button variant="outline" onClick={() => setEditClient(true)}><PencilSimple size={16} /> Modifica</Button>}{canCreate && <Button onClick={() => setOrderDialog({ open: true, order: null })}><Plus size={17} /> Nuovo ordine</Button>}</div>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2 snap-x" aria-label="Sezioni cliente">{tabs.map(([k,l]) => <button key={k} onClick={() => setTab(k)} className={`h-11 min-w-max snap-start whitespace-nowrap px-4 rounded-xl border text-sm font-semibold transition-colors ${tab===k ? "bg-[#3F82F7] border-[#2F6FED] text-white shadow-sm" : "bg-white border-slate-200 text-slate-600 hover:border-[#3F82F7] hover:text-[#245FC7]"}`}>{l}</button>)}</div>
    </div>

    {tab === "panoramica" && <div className="space-y-5">
      <section className="rounded-3xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-blue-600"><IdentificationCard size={17}/> Dossier operativo cliente</div>
            <div className="mt-2 text-sm text-slate-600">{[notionOrLocal("referente"), notionOrLocal("telefono"), notionOrLocal("email")].filter(Boolean).join(" · ") || "Contatti da completare"}</div>
            <div className="mt-1 text-sm text-slate-500">{[notionOrLocal("indirizzo"), notionOrLocal("comune"), notionOrLocal("provincia")].filter(Boolean).join(" · ") || "Sede da completare"}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            {fromNotion && <Badge variant="outline" className="bg-violet-50 text-violet-700 border-violet-200">Dati Notion importati</Badge>}
            {(n.stato_cliente || c.stato_cliente) && <StatusBadge>{n.stato_cliente || c.stato_cliente}</StatusBadge>}
            <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-200">{data.sedi?.length || 0} sedi</Badge>
            <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-200">{n.qty_wb ?? data.installazioni?.length ?? 0} WB</Badge>
          </div>
        </div>
      </section>

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
        <ServiceCard title="Backend Elios Tech" active={backendActive} expiry={backendExpiry} icon={Buildings}/>
        <ServiceCard title="Assistenza SMART" active={smartActive} expiry={smartExpiry} noExpiryLabel={fromNotion ? "Attiva · Notion non contiene una scadenza SMART" : "Attiva · nessuna scadenza registrata"} icon={Headset}/>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="text-xs uppercase tracking-wider font-bold text-slate-500">Wallbox / impianto</div><div className="text-3xl font-bold mt-2 text-slate-950">{n.qty_wb ?? (serials.length || "—")}</div><div className="text-sm text-slate-500 mt-2">{serials.length ? `${serials.length} seriali disponibili` : "Seriali non presenti"}</div></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="text-xs uppercase tracking-wider font-bold text-slate-500">Assistenze aperte</div><div className="text-3xl font-bold mt-2 text-slate-950">{(data.assistenza || []).filter((x)=>!["Risolta","Chiusa","Completata"].includes(x.stato)).length}</div><div className="text-sm text-slate-500 mt-2">Ticket / interventi da gestire</div></div>
      </div>

      <section className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3 mb-3"><div><div className="font-bold text-slate-950">Accesso tecnico immediato</div><div className="text-xs text-slate-500 mt-0.5">Dati in chiaro per assistenza senza perdere tempo.</div></div>{wbCase && <StatusBadge>{`Caso ${wbCase}`}</StatusBadge>}</div>
        <div className="grid md:grid-cols-3 gap-3"><CopyValue label="ID Wallbox" value={wbId}/><CopyValue label="Password" value={wbPassword}/><CopyValue label="Numero caso WB" value={wbCase}/></div>
      </section>

      <div className="grid xl:grid-cols-3 gap-4">
        <section className="xl:col-span-2 bg-white border border-slate-200 rounded-2xl p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3 mb-4"><div><h2 className="font-bold text-lg">Prodotti e impianto</h2><div className="text-xs text-slate-500">Prodotti venduti, seriali e QR associati al cliente.</div></div><button className="text-sm font-semibold text-blue-700" onClick={()=>setTab("ordini")}>Vedi ordini</button></div>
          <div className="grid sm:grid-cols-3 gap-3 mb-4"><Field label="QTY Wallbox" value={n.qty_wb ?? c.qty_wb ?? "—"}/><Field label="Installatore" value={n.installatore || c.installatore_notion}/><Field label="Stato cliente" value={n.stato_cliente || c.stato_cliente}/></div>
          {(productCodes.length > 0 || localProductRows.length > 0) ? <div className="space-y-2">
            {productCodes.map((code,i)=><div key={`n-${code}-${i}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"><div className="font-semibold text-sm">{code}</div><span className="text-[11px] font-bold uppercase tracking-wide text-violet-600">Notion</span></div>)}
            {!productCodes.length && localProductRows.map((r,i)=><div key={`l-${i}`} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"><div><div className="font-semibold text-sm">{r.product_name || "Prodotto"}</div><div className="text-xs text-slate-500">{r.product_code || ""}</div></div><b>{r.quantity || 0}</b></div>)}
          </div> : <div className="text-sm text-slate-500 py-3">Nessun prodotto associato.</div>}
          {(serials.length > 0 || qrCodes.length > 0) && <div className="grid md:grid-cols-2 gap-4 mt-5 pt-4 border-t border-slate-100"><div><div className="text-xs uppercase tracking-wide font-bold text-slate-500 mb-2">Seriali WB</div><div className="flex flex-wrap gap-2">{serials.map((x)=><span key={x} className="px-2.5 py-1 rounded-lg bg-slate-100 text-xs font-mono font-semibold">{x}</span>)}</div></div><div><div className="text-xs uppercase tracking-wide font-bold text-slate-500 mb-2">Codici QR</div><div className="flex flex-wrap gap-2">{qrCodes.map((x)=><span key={x} className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 text-xs font-mono font-semibold">{x}</span>)}</div></div></div>}
        </section>

        <section className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3 mb-4"><div><h2 className="font-bold text-lg">Sedi</h2><div className="text-xs text-slate-500">Luoghi collegati al cliente.</div></div><button className="text-sm font-semibold text-blue-700" onClick={()=>setTab("referenti")}>Gestisci</button></div>
          <div className="space-y-2">{(data.sedi || []).slice(0,4).map((x)=><div key={x.id} className="rounded-xl border border-slate-100 p-3"><div className="font-semibold text-sm flex items-center gap-2"><MapPin size={15} className="text-blue-600"/>{x.nome || "Sede"}</div><div className="text-xs text-slate-500 mt-1">{[x.indirizzo,x.civico,x.cap,x.comune,x.provincia].filter(Boolean).join(" · ") || "Indirizzo da completare"}</div></div>)}{!data.sedi?.length && <div className="text-sm text-slate-500">Nessuna sede registrata.</div>}</div>
        </section>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5"><h2 className="font-bold text-lg mb-4">Dati commerciali</h2><div className="grid sm:grid-cols-2 gap-4"><Field label="Ragione sociale" value={n.ragione_sociale || customerName(c)}/><Field label="Agente" value={n.agente || c.agente}/><Field label="Provenienza" value={n.provenienza_cliente || c.provenienza_cliente}/><Field label="Stato cliente" value={n.stato_cliente}/><Field label="Data firma" value={formatDateIT(n.data_firma)}/><Field label="Pagamento" value={n.pagamento || overviewOrder?.modalita_pagamento}/><Field label="Capitale" value={n.capitale != null ? `€ ${Number(n.capitale).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}` : "—"}/><Field label="Ordini locali" value={data.ordini?.length || 0}/></div></section>
        <section className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5"><h2 className="font-bold text-lg mb-4">Portali e servizi collegati</h2><div className="grid sm:grid-cols-2 gap-2"><BoolPill label="Electromaps" active={fromNotion ? !!n.electromaps : !!c.electromaps}/><BoolPill label="Eviaggio" active={fromNotion ? !!n.eviaggio : !!c.eviaggio}/><BoolPill label="Nextcharge" active={fromNotion ? !!n.nextcharge : !!c.nextcharge}/><BoolPill label="Plugshare" active={fromNotion ? !!n.plugshare : !!c.plugshare}/><BoolPill label="Recensione Google" active={fromNotion ? !!n.recensione_google : !!c.recensione_google}/></div></section>
      </div>

      <section className="bg-white border border-slate-200 rounded-2xl p-4"><div className="flex items-center justify-between mb-3"><h2 className="font-bold">Ultime attività</h2><button className="text-sm text-blue-700 font-semibold" onClick={()=>setTab("storico")}>Vedi tutto</button></div><div className="space-y-2">{(data.timeline || []).slice(0,6).map((x,i)=><div key={`${x.type}-${x.id}-${i}`} className="flex gap-3 border-l-2 border-slate-200 pl-3 py-1"><div className="min-w-0"><div className="text-sm font-semibold">{x.label}</div><div className="text-xs text-slate-500">{x.date || ""}{x.detail ? ` · ${x.detail}` : ""}</div></div></div>)}{!data.timeline?.length && <div className="text-sm text-slate-500">Nessuna attività registrata.</div>}</div></section>
    </div>}

    {tab === "anagrafica" && <div className="grid xl:grid-cols-3 gap-4">
      <section className="xl:col-span-2 bg-white border border-slate-200 rounded-2xl p-5"><h2 className="font-bold mb-4">Anagrafica completa</h2><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4"><Field label="Tipo" value={c.tipo}/><Field label="Ragione sociale / Nome" value={n.ragione_sociale || customerName(c)}/><Field label="Referente" value={n.referente || c.referente}/><Field label="Partita IVA" value={c.partita_iva}/><Field label="Codice fiscale" value={c.codice_fiscale}/><Field label="Telefono" value={n.telefono || c.telefono}/><Field label="Email" value={n.email || c.email}/><Field label="Indirizzo" value={n.indirizzo || c.indirizzo}/><Field label="Comune" value={n.comune || c.comune}/><Field label="Provincia" value={n.provincia || c.provincia}/><Field label="Agente" value={n.agente || c.agente}/><Field label="Provenienza" value={n.provenienza_cliente || c.provenienza_cliente}/><Field label="Stato Notion" value={n.stato_cliente}/><Field label="Data firma" value={formatDateIT(n.data_firma)}/><Field label="Pagamento" value={n.pagamento}/><div className="sm:col-span-2 lg:col-span-3"><Field label="Note" value={c.note}/></div></div></section>
      <section className="bg-white border border-slate-200 rounded-2xl p-5"><h2 className="font-bold mb-4">Origine dati</h2><div className="space-y-3"><div className={`rounded-xl border p-3 ${fromNotion ? "bg-violet-50 border-violet-200" : "bg-slate-50 border-slate-200"}`}><div className="font-semibold text-sm">Eliostech Ordini / Notion</div><div className="text-xs text-slate-600 mt-1">{fromNotion ? "Dati importati da Notion e salvati nel gestionale." : data.notion?.status === "multiple" ? "Trovate più schede: occorre disambiguare la ragione sociale." : data.notion?.status === "not_configured" ? "Dati Notion non ancora importati nel gestionale." : "Nessun dato Notion importato per questa ragione sociale."}</div></div><Button variant="outline" className="w-full" onClick={()=>setDocs({resource:"clienti",recordId:c.id,title:`Documenti · ${customerName(c)}`,module:"ordini_clienti"})}><FileText size={16}/> Archivio gestionale</Button></div></section>
    </div>}

    {tab === "referenti" && <div className="grid lg:grid-cols-2 gap-4">
      <section className="bg-white border border-slate-200 rounded-md p-4"><div className="flex items-center justify-between mb-3"><h2 className="font-bold flex items-center gap-2"><UsersThree size={18}/> Referenti</h2>{canCreate && <Button size="sm" onClick={createContact}><Plus size={15}/> Aggiungi</Button>}</div><div className="space-y-2">{(data.contatti||[]).map((x)=><div key={x.id} className="border border-slate-100 rounded-md p-3"><div className="font-semibold">{[x.nome,x.cognome].filter(Boolean).join(" ") || "Referente"}</div><div className="text-xs text-slate-500 mt-1">{[x.ruolo,x.telefono,x.email].filter(Boolean).join(" · ")}</div></div>)}{!data.contatti?.length && <div className="text-sm text-slate-500">Nessun referente.</div>}</div></section>
      <section className="bg-white border border-slate-200 rounded-md p-4"><div className="flex items-center justify-between mb-3"><h2 className="font-bold flex items-center gap-2"><MapPin size={18}/> Sedi</h2>{canCreate && <Button size="sm" onClick={createSite}><Plus size={15}/> Aggiungi</Button>}</div><div className="space-y-2">{(data.sedi||[]).map((x)=><div key={x.id} className="border border-slate-100 rounded-md p-3"><div className="font-semibold">{x.nome || "Sede"}</div><div className="text-xs text-slate-500 mt-1">{[x.indirizzo,x.civico,x.cap,x.comune,x.provincia].filter(Boolean).join(" · ")}</div></div>)}{!data.sedi?.length && <div className="text-sm text-slate-500">Nessuna sede.</div>}</div></section>
    </div>}

    {tab === "ordini" && <div className="space-y-3">{canCreate && <div className="flex justify-end"><Button onClick={()=>setOrderDialog({open:true,order:null})}><Plus size={16}/> Nuovo ordine</Button></div>}{(data.ordini||[]).map((o)=><div key={o.id} className="bg-white border border-slate-200 rounded-md p-4"><div className="flex flex-col lg:flex-row lg:items-start justify-between gap-3"><div><div className="text-lg font-bold">{o.numero || "Ordine"}</div><div className="text-sm text-slate-500">{o.data || ""}{o.modalita_pagamento ? ` · ${o.modalita_pagamento}` : ""}{o.importo != null ? ` · € ${Number(o.importo).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}` : ""}</div></div><div className="flex flex-wrap gap-2">{canEdit && <Button variant="outline" size="sm" onClick={()=>setOrderDialog({open:true,order:o})}><PencilSimple size={15}/> Modifica</Button>}{canCreateCommessa && <Button size="sm" onClick={()=>createOrOpenCommessa(o)}><Package size={15}/> Crea / apri commessa</Button>}<Button variant="outline" size="sm" onClick={()=>setDocs({resource:"ordini-clienti",recordId:o.id,title:`Documenti ordine · ${o.numero || customerName(c)}`,module:"ordini_clienti"})}><FileText size={15}/> Contratto e documenti</Button></div></div><div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3 mt-4"><div><div className="text-xs text-slate-400">Commerciale</div><StatusBadge>{o.stato_commerciale || o.stato}</StatusBadge></div><div><div className="text-xs text-slate-400">Contratto</div><StatusBadge>{o.stato_contratto}</StatusBadge></div><div><div className="text-xs text-slate-400">Finanziaria</div><StatusBadge>{o.stato_finanziaria}</StatusBadge></div><div><div className="text-xs text-slate-400">Amministrativo</div><StatusBadge>{o.stato_amministrativo}</StatusBadge></div><div><div className="text-xs text-slate-400">Logistica</div><StatusBadge>{o.stato_logistico}</StatusBadge></div><div><div className="text-xs text-slate-400">Installazione</div><StatusBadge>{o.stato_installazione}</StatusBadge></div></div>{Array.isArray(o.righe) && o.righe.length > 0 && <div className="mt-3 rounded-md border border-slate-100 bg-slate-50 p-3"><div className="text-xs uppercase tracking-wide font-semibold text-slate-500 mb-2">Prodotti venduti</div><div className="space-y-1">{o.righe.map((r,i)=><div key={`${r.product_page_id || i}-${i}`} className="text-sm flex justify-between gap-3"><span>{r.product_code ? `${r.product_code} · ` : ""}{r.product_name || "Prodotto"}</span><b>{r.quantity || 0}</b></div>)}</div></div>}{o.prodotti && <div className="mt-3 text-sm"><span className="font-semibold">Note configurazione:</span> {o.prodotti}</div>}{o.stato_finanziaria && o.stato_finanziaria !== "Non richiesta" && <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 p-3 text-sm"><b>Pratica finanziaria:</b> {[o.finanziaria || o.modalita_pagamento, o.numero_pratica_finanziaria, o.stato_finanziaria, o.motivo_esito_finanziaria].filter(Boolean).join(" · ")}{(o.importo_finanziato != null || o.durata_mesi || o.rata_canone != null) && <div className="mt-1 text-xs text-slate-600">{[o.importo_finanziato != null ? `Finanziato € ${Number(o.importo_finanziato).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}` : "", o.durata_mesi ? `${o.durata_mesi} mesi` : "", o.rata_canone != null ? `Rata/canone € ${Number(o.rata_canone).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2})}` : ""].filter(Boolean).join(" · ")}</div>}</div>}</div>)}{!data.ordini?.length && <div className="text-sm text-slate-500 bg-white border border-slate-200 rounded-md p-8 text-center">Nessun ordine presente per questo cliente.</div>}</div>}

    {tab === "tecnico" && <div className="grid lg:grid-cols-3 gap-4">{[
      ["Sopralluoghi", data.sopralluoghi, ClipboardText, "sopralluoghi", "sopralluoghi", "Foto e report"],
      ["Preventivi", data.preventivi, FileText, "preventivi", "preventivi", "Documenti preventivo"],
      ["Installazioni", data.installazioni, Wrench, "installazioni", "installazioni", "Foto e report"],
    ].map(([title,items,Icon,resource,module,docsLabel])=><section key={title} className="bg-white border border-slate-200 rounded-md p-4"><h2 className="font-bold flex items-center gap-2 mb-3"><Icon size={18}/>{title}</h2><div className="space-y-2">{(items||[]).map((x)=><div key={x.id} className="border border-slate-100 rounded p-3"><div className="text-sm font-semibold">{x.numero || x.data || title.slice(0,-1)}</div><div className="text-xs text-slate-500 mt-1">{[x.data,x.tecnico,x.stato].filter(Boolean).join(" · ")}</div>{resource === "installazioni" && <InstallationWeather date={x.data} site={(data.sedi || []).find((s)=>String(s.id)===String(x.sede_id))} address={x.sede_indirizzo_completo || x.sede_indirizzo || x.indirizzo || ""}/>}<div className="mt-2"><Button variant="outline" size="sm" onClick={()=>setDocs({resource,recordId:x.id,title:`${docsLabel} · ${x.numero || customerName(c)}`,module})}><FileText size={15}/>{docsLabel}</Button></div></div>)}{!items?.length && <div className="text-sm text-slate-500">Nessun record.</div>}</div></section>)}</div>}

    {tab === "assistenza" && <div className="space-y-3">{(data.assistenza||[]).map((x)=><div key={x.id} className="bg-white border border-slate-200 rounded-md p-4"><div className="flex items-center justify-between gap-3"><div><div className="font-bold">{x.numero || "Assistenza"} · {x.tipo || "Remota"}</div><div className="text-sm text-slate-500">{[x.data,x.tecnico].filter(Boolean).join(" · ")}</div></div><StatusBadge>{x.stato}</StatusBadge></div><div className="text-sm mt-3 whitespace-pre-wrap">{x.descrizione || x.note || "—"}</div><div className="mt-3"><Button variant="outline" size="sm" onClick={()=>setDocs({resource:"assistenza",recordId:x.id,title:`Documenti assistenza · ${x.numero || customerName(c)}`,module:"assistenza"})}><FileText size={15}/> Foto e report</Button></div></div>)}{!data.assistenza?.length && <div className="text-sm text-slate-500 bg-white border border-slate-200 rounded-md p-8 text-center">Nessuna assistenza registrata.</div>}</div>}

    {tab === "backend" && <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-3"><ServiceCard title="Backend Elios Tech" active={backendActive} expiry={backendExpiry} icon={Buildings}/><ServiceCard title="Assistenza SMART" active={smartActive} expiry={smartExpiry} noExpiryLabel={fromNotion ? "Attiva · Notion non contiene una scadenza SMART" : "Attiva · nessuna scadenza registrata"} icon={Headset}/></div>
      <section className="bg-white border border-slate-200 rounded-2xl p-5"><h2 className="font-bold mb-4">Credenziali e caso Wallbox</h2><div className="grid md:grid-cols-3 gap-3"><CopyValue label="ID Wallbox" value={wbId}/><CopyValue label="Password" value={wbPassword}/><CopyValue label="Numero caso WB" value={wbCase}/></div></section>
      <div className="grid lg:grid-cols-2 gap-4"><section className="bg-white border border-slate-200 rounded-2xl p-5"><h2 className="font-bold mb-4">Portali e pubblicazione</h2><div className="grid sm:grid-cols-2 gap-2"><BoolPill label="Electromaps" active={fromNotion ? !!n.electromaps : !!c.electromaps}/><BoolPill label="Eviaggio" active={fromNotion ? !!n.eviaggio : !!c.eviaggio}/><BoolPill label="Nextcharge" active={fromNotion ? !!n.nextcharge : !!c.nextcharge}/><BoolPill label="Plugshare" active={fromNotion ? !!n.plugshare : !!c.plugshare}/><BoolPill label="Recensione Google" active={fromNotion ? !!n.recensione_google : !!c.recensione_google}/></div></section>
      <section className="bg-white border border-slate-200 rounded-2xl p-5"><h2 className="font-bold mb-2">Documenti importati</h2><div className="text-sm text-slate-500 mb-4">Contratti, fatture e report sono salvati localmente nel gestionale: non serve più aprirli da Notion.</div><div className="grid grid-cols-2 gap-2 mb-4">{[["Contratti",n.contratto],["Fatture",n.fattura],["Report installazione",n.report_installazione],["Report fotografici",n.report_fotografico]].map(([label,files])=><div key={label} className="rounded-xl border border-slate-100 bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="text-xl font-bold text-slate-900 mt-1">{Array.isArray(files) ? files.length : 0}</div></div>)}</div><Button variant="outline" className="w-full" onClick={()=>setDocs({resource:"clienti",recordId:c.id,title:`Documenti · ${customerName(c)}`,module:"ordini_clienti"})}><FileText size={16}/> Apri archivio documenti</Button></section></div>
    </div>}

    {tab === "storico" && <section className="bg-white border border-slate-200 rounded-md p-4"><h2 className="font-bold mb-4">Timeline completa</h2><div className="space-y-3">{(data.timeline||[]).map((x,i)=><div key={`${x.type}-${x.id}-${i}`} className="relative border-l-2 border-slate-200 pl-4 pb-2"><div className="text-sm font-semibold">{x.label}</div><div className="text-xs text-slate-500 mt-0.5">{x.date || ""}{x.detail ? ` · ${x.detail}` : ""}</div></div>)}{!data.timeline?.length && <div className="text-sm text-slate-500">Nessuna attività registrata.</div>}</div></section>}

    <ClientFormDialog open={editClient} onClose={()=>setEditClient(false)} client={c} onSaved={async()=>{await load(); onReloadList?.();}} />
    <OrderDialog open={orderDialog.open} onClose={()=>setOrderDialog({open:false,order:null})} clientId={clientId} sites={data.sedi||[]} quotes={data.preventivi||[]} order={orderDialog.order} onSaved={load} />
    {simpleDialog && <SmallCreateDialog open title={simpleDialog.title} endpoint={simpleDialog.endpoint} base={simpleDialog.base} fields={simpleDialog.fields} onClose={()=>setSimpleDialog(null)} onSaved={load} />}
    {docs && <RecordDocuments open onOpenChange={(v)=>!v&&setDocs(null)} resource={docs.resource} recordId={docs.recordId} title={docs.title} module={docs.module} />}
  </div>;
}

export default function EliosTechOrdiniPage() {
  const { hasPermission } = useAuth();
  const [clients, setClients] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [clientDialog, setClientDialog] = useState(false);
  const [sort, setSort] = useState({ key: "data_firma", dir: "desc" });
  const canCreate = hasPermission("ordini_clienti", "create");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/crm/clienti-summary`);
      setClients(data.items || []);
    } catch (e) {
      toast.error("Impossibile caricare Elios Tech Ordini", { description: errText(e) });
    } finally { setLoading(false); }
  };
  useEffect(()=>{load();},[]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const target = new URLSearchParams(window.location.search).get("cliente");
    if (target) setSelected(target);
  }, []);

  const setSortKey = (key) => setSort((prev) => prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "data_firma" || key === "capitale" || key === "qty_wb" || key === "ordini_count" ? "desc" : "asc" });
  const sortLabel = (label, key) => <button type="button" onClick={(e)=>{e.stopPropagation();setSortKey(key);}} className="inline-flex items-center gap-1.5 font-semibold hover:text-blue-700 whitespace-nowrap">{label}<span className={`text-[11px] ${sort.key===key ? "text-blue-600" : "text-slate-300"}`}>{sort.key===key ? (sort.dir==="asc" ? "▲" : "▼") : "↕"}</span></button>;
  const money = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) ? "—" : `€ ${Number(v).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const comparable = (c, key) => {
    if (["capitale","qty_wb","ordini_count"].includes(key)) return Number(c?.[key] ?? -Infinity);
    if (key === "data_firma") return String(c?.data_firma || "0000-00-00");
    if (key === "cliente") return customerName(c).toLocaleLowerCase("it");
    if (key === "localita") return `${c?.comune || ""} ${c?.provincia || ""}`.toLocaleLowerCase("it");
    return String(c?.[key] || "").toLocaleLowerCase("it");
  };
  const shown = useMemo(()=>{
    const q=query.trim().toLowerCase();
    const filtered = q ? clients.filter((c)=>[customerName(c),c.partita_iva,c.codice_fiscale,c.telefono,c.email,c.comune,c.provincia,c.agente,c.pagamento,c.data_firma].some((v)=>String(v||"").toLowerCase().includes(q))) : [...clients];
    filtered.sort((a,b)=>{
      const av=comparable(a,sort.key), bv=comparable(b,sort.key);
      if (av===bv) return customerName(a).localeCompare(customerName(b), "it");
      const r = av > bv ? 1 : -1;
      return sort.dir === "asc" ? r : -r;
    });
    return filtered;
  },[clients,query,sort]);

  if (selected) return <ClientDetail clientId={selected} onBack={()=>setSelected(null)} onReloadList={load} />;
  return <div className="max-w-[1600px] mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-4" data-testid="elios-tech-ordini-page">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3"><div><div className="et-eyebrow">Amministrazione</div><h1 className="et-page-heading text-3xl sm:text-4xl mt-1">Elios Tech Ordini</h1><div className="text-sm text-slate-500 mt-1">{clients.length} clienti · ordinati per data firma più recente</div></div>{canCreate && <Button className="h-12" onClick={()=>setClientDialog(true)}><Plus size={18}/> Nuovo cliente</Button>}</div>
    <div className="flex flex-col lg:flex-row lg:items-center gap-3">
      <div className="relative max-w-2xl flex-1"><MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><Input className="pl-10 h-12" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Cerca cliente, email, comune, agente, pagamento o data…"/></div>
      <div className="text-xs text-slate-500">{shown.length} risultati</div>
    </div>
    {loading ? <div className="py-12 text-center text-slate-500">Caricamento…</div> : <>
      <div className="md:hidden space-y-2">{shown.map((c)=><button key={c.id} onClick={()=>setSelected(c.id)} className="w-full text-left bg-white border border-slate-200 rounded-xl p-4 shadow-sm"><div className="flex items-start gap-3"><div className="shrink-0 rounded-lg bg-blue-50 border border-blue-100 px-2.5 py-2 text-center min-w-[88px]"><div className="text-[10px] uppercase font-bold tracking-wide text-blue-500">Data firma</div><div className="text-sm font-bold text-blue-900 mt-0.5">{formatDateIT(c.data_firma)}</div></div><div className="min-w-0 flex-1"><div className="font-bold text-slate-900 truncate">{customerName(c)}</div><div className="text-xs text-slate-500 mt-1">{[c.comune,c.provincia,c.agente].filter(Boolean).join(" · ") || "—"}</div><div className="text-xs text-slate-500 mt-1">{c.pagamento || "Pagamento non indicato"}</div></div></div><div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-slate-100"><div><div className="text-[10px] uppercase text-slate-400">Ordini</div><div className="font-bold">{c.ordini_count||0}</div></div><div><div className="text-[10px] uppercase text-slate-400">WB</div><div className="font-bold">{c.qty_wb ?? "—"}</div></div><div><div className="text-[10px] uppercase text-slate-400">Capitale</div><div className="font-bold text-xs">{money(c.capitale)}</div></div></div></button>)}</div>
      <div className="hidden md:block bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm"><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 border-b border-slate-200"><tr><th className="text-left p-3">{sortLabel("Data firma","data_firma")}</th><th className="text-left p-3">{sortLabel("Cliente / Struttura","cliente")}</th><th className="text-left p-3">{sortLabel("Pagamento","pagamento")}</th><th className="text-right p-3">{sortLabel("Capitale","capitale")}</th><th className="text-center p-3">{sortLabel("Q.tà WB","qty_wb")}</th><th className="text-left p-3">{sortLabel("Località","localita")}</th><th className="text-left p-3">{sortLabel("Agente","agente")}</th><th className="text-center p-3">{sortLabel("Ordini","ordini_count")}</th><th className="text-left p-3">{sortLabel("Stato","ultimo_stato")}</th></tr></thead><tbody>{shown.map((c)=><tr key={c.id} onClick={()=>setSelected(c.id)} className="border-b border-slate-100 hover:bg-blue-50/40 cursor-pointer transition-colors"><td className="p-3"><div className="font-bold text-slate-900 whitespace-nowrap">{formatDateIT(c.data_firma)}</div></td><td className="p-3 min-w-[250px]"><div className="font-semibold text-slate-950">{customerName(c)}</div><div className="text-xs text-slate-400 mt-0.5">{c.partita_iva || c.codice_fiscale || c.email || "—"}</div></td><td className="p-3 text-slate-700 whitespace-nowrap">{c.pagamento || "—"}</td><td className="p-3 text-right font-semibold whitespace-nowrap">{money(c.capitale)}</td><td className="p-3 text-center font-bold">{c.qty_wb ?? "—"}</td><td className="p-3 text-slate-600 whitespace-nowrap">{[c.comune,c.provincia].filter(Boolean).join(" · ") || "—"}</td><td className="p-3 text-slate-600 whitespace-nowrap">{c.agente || "—"}</td><td className="p-3 text-center font-semibold">{c.ordini_count||0}</td><td className="p-3"><StatusBadge>{c.ultimo_stato}</StatusBadge></td></tr>)}{shown.length===0&&<tr><td colSpan="9" className="text-center p-10 text-slate-400">Nessun cliente trovato.</td></tr>}</tbody></table></div></div>
    </>}
    <ClientFormDialog open={clientDialog} onClose={()=>setClientDialog(false)} onSaved={async(created)=>{await load(); if (created?.id) setSelected(created.id);}} />
  </div>;
}
