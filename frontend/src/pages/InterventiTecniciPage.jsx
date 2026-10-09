import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { CalendarBlank, CaretLeft, CaretRight, Clock, MapPin, Wrench, PencilSimple, Trash, Eye } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { useAuth } from "../lib/AuthContext";
import { appConfirm } from "../lib/appConfirm";

function localDateKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function monthKey(value) { return String(value || "").slice(0, 7); }
function shiftMonth(value, delta) {
  const [y,m] = value.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
}
function monthLabel(value) {
  const [y,m] = value.split("-").map(Number);
  return new Date(y, m-1, 1).toLocaleDateString("it-IT", { month: "long", year: "numeric" });
}
function fmtDate(value) {
  if (!value) return "Da programmare";
  return new Date(`${value}T12:00:00`).toLocaleDateString("it-IT", { weekday: "short", day: "2-digit", month: "short" });
}
function cleanText(value) {
  return String(value || "")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
function errorText(error) {
  return error?.response?.data?.detail || error?.message || "Errore imprevisto";
}

const EMPTY_FORM = {
  titolo: "",
  nominativo: "",
  data: "",
  ora: "",
  stato: "Programmato",
  tecnico: "RICCARDO",
  indirizzo_libero: "",
  comune_libero: "",
  provincia_libera: "",
  cap_libero: "",
  referente: "",
  telefono: "",
  descrizione: "",
  note_tecniche: "",
};

export default function InterventiTecniciPage() {
  const { hasPermission, isAdmin } = useAuth();
  const canEdit = isAdmin || hasPermission("installazioni", "edit");
  const canDelete = isAdmin || hasPermission("installazioni", "delete");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(() => localDateKey().slice(0,7));
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const today = localDateKey();

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/crm/interventi-tecnici`);
      setItems(data.items || []);
    } catch (error) {
      toast.error("Impossibile caricare gli interventi tecnici", { description: errorText(error) });
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const monthItems = useMemo(() => items.filter((x) => x.data && monthKey(x.data) === month), [items, month]);
  const sections = useMemo(() => {
    const todayRows = monthItems.filter((x) => x.data === today).sort((a,b) => String(a.ora||"").localeCompare(String(b.ora||"")));
    const future = monthItems.filter((x) => x.data > today).sort((a,b) => `${a.data} ${a.ora||""}`.localeCompare(`${b.data} ${b.ora||""}`));
    const past = monthItems.filter((x) => x.data < today).sort((a,b) => `${b.data} ${b.ora||""}`.localeCompare(`${a.data} ${a.ora||""}`));
    return [["Oggi", todayRows], ["Prossimi interventi", future], ["Interventi passati", past]].filter(([,rows]) => rows.length);
  }, [monthItems, today]);

  const openDetail = (item) => {
    setSelected(item);
    setEditing(false);
    setForm({ ...EMPTY_FORM, ...item, descrizione: cleanText(item.descrizione || item.descrizione_importata), note_tecniche: cleanText(item.note_tecniche) });
  };

  const save = async () => {
    if (!selected?.id) return;
    setSaving(true);
    try {
      const payload = {
        titolo: form.titolo,
        nominativo: form.nominativo,
        data: form.data,
        ora: form.ora,
        stato: form.stato,
        tecnico: form.tecnico,
        indirizzo_libero: form.indirizzo_libero,
        comune_libero: form.comune_libero,
        provincia_libera: form.provincia_libera,
        cap_libero: form.cap_libero,
        referente: form.referente,
        telefono: form.telefono,
        descrizione: form.descrizione,
        note_tecniche: form.note_tecniche,
        manual_override: true,
      };
      const { data } = await axios.put(`${API}/crm/interventi-tecnici/${selected.id}`, payload);
      setSelected(data);
      setEditing(false);
      toast.success("Intervento aggiornato");
      await load();
    } catch (error) {
      toast.error("Modifica non riuscita", { description: errorText(error) });
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!selected?.id) return;
    const ok = await appConfirm({
      title: "Elimina intervento tecnico",
      message: "Eliminare definitivamente questo intervento tecnico? Se proviene dal Calendario resterà escluso dalla sincronizzazione automatica.",
      confirmLabel: "Elimina",
      danger: true,
    });
    if (!ok) return;
    setDeleting(true);
    try {
      await axios.delete(`${API}/crm/interventi-tecnici/${selected.id}`);
      toast.success("Intervento eliminato");
      setSelected(null);
      setEditing(false);
      await load();
    } catch (error) {
      toast.error("Eliminazione non riuscita", { description: errorText(error) });
    } finally { setDeleting(false); }
  };

  const setField = (key, value) => setForm((x) => ({ ...x, [key]: value }));

  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 space-y-4" data-testid="interventi-tecnici-page">
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
      <div>
        <div className="text-xs font-semibold tracking-[.14em] uppercase text-[#1A456B]">Tecnico</div>
        <h1 className="font-display text-2xl font-black text-slate-900">Interventi tecnici</h1>
        <div className="text-sm text-slate-500 mt-1">Interventi tecnici di RICCARDO importati dal calendario, apribili e modificabili.</div>
      </div>
      <Button variant="outline" onClick={load}>Aggiorna</Button>
    </div>

    <div className="et-card p-3 flex items-center justify-between gap-3">
      <Button variant="outline" size="icon" onClick={() => setMonth((m) => shiftMonth(m,-1))}><CaretLeft size={18}/></Button>
      <div className="text-center"><div className="font-black text-slate-900 capitalize">{monthLabel(month)}</div><div className="text-xs text-slate-500">{monthItems.length} interventi nel mese</div></div>
      <Button variant="outline" size="icon" onClick={() => setMonth((m) => shiftMonth(m,1))}><CaretRight size={18}/></Button>
    </div>

    {loading ? <div className="et-card p-8 text-center text-slate-500">Caricamento…</div> : sections.length === 0 ? <div className="et-card p-8 text-center text-slate-500">Nessun intervento tecnico nel mese selezionato.</div> : sections.map(([label, rows]) => <section key={label} className="space-y-2">
      <div className="flex items-center gap-2"><CalendarBlank size={17} className="text-[#1A456B]"/><h2 className="font-black text-slate-900">{label}</h2><span className="text-xs text-slate-400">{rows.length}</span></div>
      <div className="grid lg:grid-cols-2 gap-2.5">
        {rows.map((x) => <article key={x.id} className="et-card border-l-4 border-l-[#2d6ea3] p-3 hover:shadow-md transition-shadow">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><div className="text-[11px] uppercase tracking-wide font-bold text-slate-400 capitalize">{fmtDate(x.data)}</div><div className="font-black text-base text-slate-900 mt-0.5">{x.nominativo || x.titolo || x.calendar_title || "Intervento tecnico"}</div></div>
            <span className="text-xs font-bold rounded-full border border-slate-200 bg-slate-50 px-2 py-1">{x.stato || "Programmato"}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-700">
            <span className="rounded-lg bg-slate-50 px-2 py-1.5"><Clock size={14} className="inline mr-1"/>{x.ora || "Orario da definire"}</span>
            <span className="rounded-lg bg-slate-50 px-2 py-1.5"><Wrench size={14} className="inline mr-1"/>{x.tecnico || "RICCARDO"}</span>
          </div>
          {(x.indirizzo_libero || x.comune_libero) && <div className="mt-2 text-xs text-slate-500"><MapPin size={14} className="inline mr-1"/>{[x.indirizzo_libero, x.comune_libero, x.provincia_libera].filter(Boolean).join(" · ")}</div>}
          {(x.descrizione || x.note_tecniche || x.descrizione_importata) && <div className="mt-2 text-sm text-slate-700 whitespace-pre-line line-clamp-2">{cleanText(x.descrizione || x.note_tecniche || x.descrizione_importata)}</div>}
          <div className="mt-3 flex justify-end"><Button type="button" variant="outline" size="sm" onClick={() => openDetail(x)}><Eye size={15}/> Apri</Button></div>
        </article>)}
      </div>
    </section>)}

    <Dialog open={!!selected} onOpenChange={(open) => { if (!open) { setSelected(null); setEditing(false); } }}>
      <DialogContent className="max-w-3xl max-h-[88vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{editing ? "Modifica intervento tecnico" : "Dettaglio intervento tecnico"}</DialogTitle></DialogHeader>
        {!editing ? <div className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            <div><div className="text-xs font-bold uppercase text-slate-400">Titolo</div><div className="font-semibold text-slate-900 mt-1">{selected?.nominativo || selected?.titolo || selected?.calendar_title || "Intervento tecnico"}</div></div>
            <div><div className="text-xs font-bold uppercase text-slate-400">Stato</div><div className="mt-1">{selected?.stato || "—"}</div></div>
            <div><div className="text-xs font-bold uppercase text-slate-400">Data e ora</div><div className="mt-1">{selected?.data || "—"} {selected?.ora || ""}</div></div>
            <div><div className="text-xs font-bold uppercase text-slate-400">Tecnico</div><div className="mt-1">{selected?.tecnico || "RICCARDO"}</div></div>
            <div className="sm:col-span-2"><div className="text-xs font-bold uppercase text-slate-400">Indirizzo</div><div className="mt-1">{[selected?.indirizzo_libero, selected?.cap_libero, selected?.comune_libero, selected?.provincia_libera].filter(Boolean).join(" · ") || "—"}</div></div>
            <div><div className="text-xs font-bold uppercase text-slate-400">Referente</div><div className="mt-1">{selected?.referente || "—"}</div></div>
            <div><div className="text-xs font-bold uppercase text-slate-400">Telefono</div><div className="mt-1">{selected?.telefono || "—"}</div></div>
          </div>
          {(selected?.descrizione || selected?.descrizione_importata) && <div><div className="text-xs font-bold uppercase text-slate-400">Descrizione</div><div className="mt-1 whitespace-pre-line text-sm text-slate-700">{cleanText(selected?.descrizione || selected?.descrizione_importata)}</div></div>}
          {selected?.note_tecniche && <div><div className="text-xs font-bold uppercase text-slate-400">Note tecniche</div><div className="mt-1 whitespace-pre-line text-sm text-slate-700">{cleanText(selected.note_tecniche)}</div></div>}
        </div> : <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Titolo / cliente</Label><Input className="mt-1" value={form.nominativo || form.titolo || ""} onChange={(e) => { setField("nominativo", e.target.value); setField("titolo", e.target.value); }} /></div>
          <div><Label>Stato</Label><select className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.stato || "Programmato"} onChange={(e) => setField("stato", e.target.value)}><option>Programmato</option><option>In lavorazione</option><option>Eseguito</option><option>Completato</option><option>Rinviato</option><option>Annullato</option></select></div>
          <div><Label>Data</Label><Input type="date" className="mt-1" value={form.data || ""} onChange={(e) => setField("data", e.target.value)} /></div>
          <div><Label>Ora</Label><Input type="time" className="mt-1" value={form.ora || ""} onChange={(e) => setField("ora", e.target.value)} /></div>
          <div><Label>Tecnico</Label><Input className="mt-1" value={form.tecnico || ""} onChange={(e) => setField("tecnico", e.target.value)} /></div>
          <div><Label>Referente</Label><Input className="mt-1" value={form.referente || ""} onChange={(e) => setField("referente", e.target.value)} /></div>
          <div><Label>Telefono</Label><Input className="mt-1" value={form.telefono || ""} onChange={(e) => setField("telefono", e.target.value)} /></div>
          <div><Label>CAP</Label><Input className="mt-1" value={form.cap_libero || ""} onChange={(e) => setField("cap_libero", e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Indirizzo</Label><Input className="mt-1" value={form.indirizzo_libero || ""} onChange={(e) => setField("indirizzo_libero", e.target.value)} /></div>
          <div><Label>Comune</Label><Input className="mt-1" value={form.comune_libero || ""} onChange={(e) => setField("comune_libero", e.target.value)} /></div>
          <div><Label>Provincia</Label><Input className="mt-1" value={form.provincia_libera || ""} onChange={(e) => setField("provincia_libera", e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Descrizione</Label><Textarea rows={5} className="mt-1" value={form.descrizione || ""} onChange={(e) => setField("descrizione", e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Note tecniche</Label><Textarea rows={4} className="mt-1" value={form.note_tecniche || ""} onChange={(e) => setField("note_tecniche", e.target.value)} /></div>
        </div>}
        <DialogFooter className="gap-2 sm:justify-between">
          <div>{canDelete && !editing && <Button variant="destructive" onClick={remove} disabled={deleting}><Trash size={16}/>{deleting ? "Eliminazione…" : "Elimina"}</Button>}</div>
          <div className="flex gap-2">
            {editing ? <><Button variant="outline" onClick={() => { setEditing(false); setForm({ ...EMPTY_FORM, ...selected }); }} disabled={saving}>Annulla</Button><Button onClick={save} disabled={saving}>{saving ? "Salvataggio…" : "Salva modifiche"}</Button></> : <>{canEdit && <Button onClick={() => setEditing(true)}><PencilSimple size={16}/> Modifica</Button>}</>}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>;
}
