import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { CalendarBlank, CaretLeft, CaretRight, Clock, MapPin, Wrench } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";

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

export default function InterventiTecniciPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(() => localDateKey().slice(0,7));
  const today = localDateKey();

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/crm/interventi-tecnici`);
      setItems(data.items || []);
    } catch (error) {
      toast.error("Impossibile caricare gli interventi tecnici", { description: error?.response?.data?.detail || error?.message });
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

  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 space-y-4" data-testid="interventi-tecnici-page">
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
      <div>
        <div className="text-xs font-semibold tracking-[.14em] uppercase text-[#1A456B]">Tecnico</div>
        <h1 className="font-display text-2xl font-black text-slate-900">Interventi tecnici</h1>
        <div className="text-sm text-slate-500 mt-1">Interventi tecnici di RICCARDO importati dal calendario, storici e futuri.</div>
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
        {rows.map((x) => <article key={x.id} className="et-card border-l-4 border-l-[#2d6ea3] p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><div className="text-[11px] uppercase tracking-wide font-bold text-slate-400 capitalize">{fmtDate(x.data)}</div><div className="font-black text-base text-slate-900 mt-0.5">{x.nominativo || x.titolo || x.calendar_title || "Intervento tecnico"}</div></div>
            <span className="text-xs font-bold rounded-full border border-slate-200 bg-slate-50 px-2 py-1">{x.stato || "Programmato"}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-700">
            <span className="rounded-lg bg-slate-50 px-2 py-1.5"><Clock size={14} className="inline mr-1"/>{x.ora || "Orario da definire"}</span>
            <span className="rounded-lg bg-slate-50 px-2 py-1.5"><Wrench size={14} className="inline mr-1"/>{x.tecnico || "RICCARDO"}</span>
          </div>
          {(x.indirizzo_libero || x.comune_libero) && <div className="mt-2 text-xs text-slate-500"><MapPin size={14} className="inline mr-1"/>{[x.indirizzo_libero, x.comune_libero, x.provincia_libera].filter(Boolean).join(" · ")}</div>}
          {(x.descrizione || x.note_tecniche || x.descrizione_importata) && <div className="mt-2 text-sm text-slate-700 whitespace-pre-line line-clamp-3">{cleanText(x.descrizione || x.note_tecniche || x.descrizione_importata)}</div>}
        </article>)}
      </div>
    </section>)}
  </div>;
}
