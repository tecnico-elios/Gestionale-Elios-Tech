import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import {
  CaretLeft, CaretRight, Plus, MapPin, Wrench, ClipboardText,
  Headset, UsersThree, Gear, Trash, PencilSimple, ArrowSquareOut,
  SlidersHorizontal, MagnifyingGlass, FloppyDisk,
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import InstallationWeather from "../components/InstallationWeather";

const pad = (n) => String(n).padStart(2, "0");
const localIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
const dateKey = (value) => String(value || "").slice(0, 10);
const parseLocal = (value) => { const d = new Date(value); return Number.isNaN(d.getTime()) ? new Date() : d; };
const timeKey = (value) => { const d = parseLocal(value); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const startOfWeek = (d) => { const x = startOfDay(d); return addDays(x, -((x.getDay() + 6) % 7)); };
const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);
const startOfMonthGrid = (d) => startOfWeek(new Date(d.getFullYear(), d.getMonth(), 1));
const fmtDay = (d) => d.toLocaleDateString("it-IT", { weekday: "short", day: "2-digit", month: "2-digit" });
const fmtMonth = (d) => d.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
const sameDay = (a, b) => dateKey(a) === dateKey(b);
const normalizeCategory = (value) => String(value || "Attività").toLowerCase() === "commerciale" ? "Attività" : (value || "Attività");
const hexToRgba = (hex, alpha = 0.13) => {
  const h = String(hex || "#64748b").replace("#", "");
  if (h.length !== 6) return `rgba(100,116,139,${alpha})`;
  const n = parseInt(h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
};
const iconFor = (cat) => cat === "Installazione" ? Wrench : cat === "Sopralluogo" ? ClipboardText : cat === "Assistenza" ? Headset : UsersThree;

const defaultCalendarLists = {
  calendar_categories: ["Installazione", "Sopralluogo", "Assistenza", "Riunione", "Formazione", "Attività", "Altro"],
  calendar_statuses: ["Da confermare", "Confermato", "In corso", "Completato", "Annullato"],
  calendar_priorities: ["Bassa", "Normale", "Alta", "Urgente"],
};

function EventCard({ event, onOpen, onDragStart, compact = false }) {
  const Icon = iconFor(event.category);
  const color = event.resource_color || "#64748b";
  return (
    <button
      type="button"
      draggable={!event.recurrence_instance}
      onDragStart={(e) => onDragStart?.(e, event)}
      onClick={() => onOpen(event)}
      className={`w-full text-left rounded-md border px-2 py-1.5 hover:shadow-sm overflow-hidden ${compact ? "text-[11px]" : "text-xs"}`}
      style={{ borderLeft: `4px solid ${color}`, backgroundColor: hexToRgba(color, 0.10) }}
      title={`${event.title}${event.resource_name ? ` · ${event.resource_name}` : ""}`}
    >
      <div className="flex items-center gap-1 font-bold text-slate-900 min-w-0"><Icon size={13} /><span className="truncate">{event.title}</span></div>
      {!event.all_day && <div className="text-slate-600 mt-0.5">{timeKey(event.start)}{event.resource_name ? ` · ${event.resource_name}` : ""}</div>}
    </button>
  );
}

export default function CalendarPage() {
  const { isAdmin, hasPermission } = useAuth();
  const navigate = useNavigate();
  const [view, setView] = useState("week");
  const [cursor, setCursor] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedResources, setSelectedResources] = useState(null);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [detail, setDetail] = useState(null);
  const [editor, setEditor] = useState(null);
  const [resourceDlg, setResourceDlg] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [openHours, setOpenHours] = useState(() => new Set());
  const [dragging, setDragging] = useState(null);
  const [clients, setClients] = useState([]);
  const [sites, setSites] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [configLists, setConfigLists] = useState(defaultCalendarLists);
  const [search, setSearch] = useState("");

  const canCreate = hasPermission("calendar", "create") || isAdmin;
  const canEdit = hasPermission("calendar", "edit") || isAdmin;

  const range = useMemo(() => {
    if (view === "day") { const s = startOfDay(cursor); return [s, addDays(s, 1)]; }
    if (view === "week") { const s = startOfWeek(cursor); return [s, addDays(s, 7)]; }
    const s = startOfMonthGrid(cursor);
    return [s, addDays(s, 42)];
  }, [cursor, view]);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/calendar/events`, { params: { start: localIso(range[0]), end: localIso(range[1]) } });
      setEvents((data.items || []).map((e) => ({ ...e, category: normalizeCategory(e.category) })));
      setResources(data.resources || []);
    } catch (e) {
      toast.error("Calendario non disponibile", { description: e?.response?.data?.detail || e?.message });
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [range[0].getTime(), range[1].getTime()]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const loadLookups = () => Promise.allSettled([
      axios.get(`${API}/crm/clienti`),
      axios.get(`${API}/crm/sedi`),
      axios.get(`${API}/commesse`),
      axios.get(`${API}/custom/config/lists`),
    ]).then(([c, s, j, l]) => {
      if (c.status === "fulfilled") setClients(c.value.data?.items || []);
      if (s.status === "fulfilled") setSites(s.value.data?.items || []);
      if (j.status === "fulfilled") setJobs(j.value.data?.items || []);
      if (l.status === "fulfilled") {
        const values = l.value.data?.values || {};
        const cats = (values.calendar_categories || defaultCalendarLists.calendar_categories).filter((x) => String(x).toLowerCase() !== "commerciale");
        setConfigLists((p) => ({ ...p, ...values, calendar_categories: cats }));
      }
    });
    loadLookups();
    const fn = () => loadLookups();
    window.addEventListener("elios:config-lists-changed", fn);
    return () => window.removeEventListener("elios:config-lists-changed", fn);
  }, []);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (Array.isArray(selectedResources) && !(e.resource_ids || []).some((id) => selectedResources.includes(id))) return false;
      if (selectedCategories.length && !selectedCategories.includes(e.category)) return false;
      if (q && !`${e.title || ""} ${e.description || ""} ${e.location || ""} ${e.resource_name || ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [events, selectedResources, selectedCategories, search]);

  const byDay = useMemo(() => {
    const m = {};
    for (const e of visible) {
      const k = dateKey(e.start);
      (m[k] || (m[k] = [])).push(e);
    }
    for (const k of Object.keys(m)) m[k].sort((a, b) => String(a.start).localeCompare(String(b.start)));
    return m;
  }, [visible]);

  const goToday = () => setCursor(new Date());
  const shift = (dir) => setCursor((c) => view === "month" ? addMonths(c, dir) : addDays(c, dir * (view === "week" ? 7 : 1)));
  const heading = view === "month" ? fmtMonth(cursor) : view === "week" ? `${fmtDay(range[0])} – ${fmtDay(addDays(range[1], -1))}` : cursor.toLocaleDateString("it-IT", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });

  const newEvent = (date = new Date()) => {
    const s = new Date(date);
    if (s.getHours() === 0) s.setHours(9, 0, 0, 0);
    const e = new Date(s); e.setHours(s.getHours() + 1);
    const categories = configLists.calendar_categories || defaultCalendarLists.calendar_categories;
    const statuses = configLists.calendar_statuses || defaultCalendarLists.calendar_statuses;
    const priorities = configLists.calendar_priorities || defaultCalendarLists.calendar_priorities;
    setEditor({
      key: null,
      title: "",
      start: localIso(s),
      end: localIso(e),
      category: categories[0] || "Attività",
      resource_ids: [],
      description: "",
      location: "",
      all_day: false,
      status: statuses[0] || "Da confermare",
      priority: priorities[1] || priorities[0] || "Normale",
      cliente_id: "",
      sede_id: "",
      commessa_id: "",
      meeting_link: "",
      reminder_minutes: 30,
      rrule: "",
    });
  };

  const editEvent = (e) => setEditor({ ...e, category: normalizeCategory(e.category), start: String(e.start).slice(0, 16), end: String(e.end || e.start).slice(0, 16), resource_ids: e.resource_ids || [] });

  const saveEvent = async () => {
    if (!editor?.title?.trim()) return toast.error("Inserisci il titolo");
    if (!editor?.start) return toast.error("Inserisci data e ora di inizio");
    if (editor.end && new Date(editor.end) < new Date(editor.start)) return toast.error("La fine non può precedere l'inizio");
    try {
      const payload = { ...editor, category: normalizeCategory(editor.category) };
      delete payload.source_record;
      delete payload.key;
      delete payload.resource_name;
      delete payload.resource_color;
      if (editor.key) await axios.put(`${API}/calendar/events/${encodeURIComponent(editor.key)}`, payload);
      else await axios.post(`${API}/calendar/events`, payload);
      toast.success(editor.key ? "Evento aggiornato" : "Evento creato");
      setEditor(null);
      setDetail(null);
      await load();
    } catch (e) {
      toast.error("Salvataggio non riuscito", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const deleteEvent = async () => {
    if (!editor?.key || !editor.key.startsWith("manual:")) return;
    try {
      await axios.delete(`${API}/calendar/events/${encodeURIComponent(editor.key)}`);
      toast.success("Evento eliminato");
      setEditor(null);
      setDetail(null);
      await load();
    } catch (e) {
      toast.error("Eliminazione non riuscita", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const dropOnDate = async (date) => {
    if (!dragging || !canEdit) return;
    const old = parseLocal(dragging.start);
    const target = new Date(date);
    if (target.getHours() === 0 && target.getMinutes() === 0) target.setHours(old.getHours(), old.getMinutes(), 0, 0);
    const oldEnd = parseLocal(dragging.end || dragging.start);
    const duration = Math.max(15, (oldEnd - old) / 60000);
    const end = new Date(target.getTime() + duration * 60000);
    try {
      await axios.put(`${API}/calendar/events/${encodeURIComponent(dragging.key)}`, { start: localIso(target), end: localIso(end) });
      setDragging(null);
      await load();
    } catch (e) {
      toast.error("Spostamento non riuscito", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const openSource = (ev) => {
    if (ev.source_type === "installazione") navigate("/installazioni");
    else if (ev.source_type === "sopralluogo") navigate("/sopralluoghi");
    else if (ev.source_type === "assistenza") navigate("/assistenza");
    else if (ev.source_type === "custom" && ev.module_slug) navigate(`/moduli/${ev.module_slug}`);
  };

  const days = view === "month" ? Array.from({ length: 42 }, (_, i) => addDays(range[0], i)) : view === "week" ? Array.from({ length: 7 }, (_, i) => addDays(range[0], i)) : [range[0]];
  const hours = Array.from({ length: 15 }, (_, i) => 7 + i);
  const toggleHour = (h) => setOpenHours((prev) => { const next = new Set(prev); if (next.has(h)) next.delete(h); else next.add(h); return next; });
  const allHoursOpen = openHours.size === hours.length;
  const toggleAllHours = () => setOpenHours(allHoursOpen ? new Set() : new Set(hours));

  return (
    <div className="max-w-[1600px] mx-auto px-3 sm:px-5 py-4 space-y-4" data-testid="company-calendar-page">
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
        <div><div className="text-xs font-semibold tracking-[.16em] uppercase text-[#1A456B]">Elios Tech</div><h1 className="font-display text-3xl font-black text-slate-900">Calendario</h1><p className="text-sm text-slate-500 mt-1">Calendario unico per installazioni, sopralluoghi, assistenze, riunioni e attività interne.</p></div>
        <div className="flex gap-2 flex-wrap">{isAdmin && <Button variant="outline" onClick={() => setResourceDlg(true)}><Gear size={17} /> Persone</Button>}<Button variant={filtersOpen ? "default" : "outline"} onClick={() => setFiltersOpen((v) => !v)}><SlidersHorizontal size={17} /> {filtersOpen ? "Chiudi filtri" : "Filtri"}</Button>{canCreate && <Button onClick={() => newEvent(cursor)}><Plus size={17} /> Nuovo evento</Button>}</div>
      </div>

      <div className="et-card p-3 space-y-3">
        <div className="flex flex-col xl:flex-row xl:items-center gap-3 justify-between">
          <div className="flex items-center gap-2 flex-wrap"><Button variant="outline" size="icon" onClick={() => shift(-1)}><CaretLeft /></Button><Button variant="outline" onClick={goToday}>Oggi</Button><Button variant="outline" size="icon" onClick={() => shift(1)}><CaretRight /></Button><div className="ml-1 font-black text-slate-900 capitalize">{heading}</div></div>
          <div className="flex flex-wrap items-center gap-2 self-start xl:self-auto">
            <div className="relative"><MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><Input className="h-9 pl-9 w-[220px]" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cerca nel calendario…" /></div>
            {view !== "month" && <Button variant="outline" onClick={toggleAllHours} className="h-9">{allHoursOpen ? "Compatta orari" : "Espandi orari"}</Button>}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-md">{[["day", "Giorno"], ["week", "Settimana"], ["month", "Mese"]].map(([k, l]) => <button key={k} onClick={() => setView(k)} className={`px-3 py-1.5 rounded text-sm font-semibold ${view === k ? "bg-white shadow text-slate-900" : "text-slate-600"}`}>{l}</button>)}</div>
          </div>
        </div>
        {!!resources.length && <div className="flex items-center gap-2 overflow-x-auto pb-1"><button type="button" onClick={() => setSelectedResources(null)} className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold ${selectedResources === null ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600"}`}>Tutti</button>{resources.map((r) => { const active = selectedResources === null || selectedResources.includes(r.id); const toggle = () => setSelectedResources((prev) => { const base = prev === null ? resources.map((x) => x.id) : prev; if (base.includes(r.id)) return base.filter((x) => x !== r.id); return [...base, r.id]; }); return <button type="button" key={r.id} onClick={toggle} className={`shrink-0 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${active ? "border-blue-300 bg-blue-50 text-blue-800" : "border-slate-200 bg-white text-slate-400 opacity-60"}`}><span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color || "#64748b" }} />{r.display_name || r.name}</button>; })}</div>}
      </div>

      <div className={`grid ${filtersOpen ? "xl:grid-cols-[250px_minmax(0,1fr)]" : "grid-cols-1"} gap-4`}>
        {filtersOpen && <aside className="et-card p-3 h-fit space-y-4"><div><div className="font-black text-sm mb-2">Calendari / persone</div><div className="flex gap-3 mb-2"><button className="text-xs text-blue-700" onClick={() => setSelectedResources(null)}>Mostra tutti</button><button className="text-xs text-slate-500" onClick={() => setSelectedResources([])}>Nascondi tutti</button></div><div className="space-y-1.5">{resources.map((r) => { const checked = selectedResources === null || selectedResources.includes(r.id); return <div key={r.id} className="flex items-center gap-2"><label className="flex min-w-0 flex-1 items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={checked} onChange={(e) => setSelectedResources((prev) => { const base = prev === null ? resources.map((x) => x.id) : prev; if (e.target.checked) return base.includes(r.id) ? base : [...base, r.id]; return base.filter((x) => x !== r.id); })} /><span className="h-3 w-3 rounded-sm" style={{ background: r.color || "#64748b" }} /><span className="truncate">{r.display_name || r.name}</span></label><button type="button" className="text-[10px] font-bold text-blue-700" onClick={() => setSelectedResources([r.id])}>SOLO</button></div>; })}</div></div><div><div className="font-black text-sm mb-2">Tipo attività</div><button className="text-xs text-blue-700 mb-2" onClick={() => setSelectedCategories([])}>Tutti</button><div className="space-y-1.5">{(configLists.calendar_categories || defaultCalendarLists.calendar_categories).map((c) => <label key={c} className="flex items-center gap-2 text-sm cursor-pointer"><input type="checkbox" checked={selectedCategories.includes(c)} onChange={(e) => setSelectedCategories((p) => e.target.checked ? [...p, c] : p.filter((x) => x !== c))} /><span>{c}</span></label>)}</div></div></aside>}

        <section className="et-card overflow-hidden min-w-0">
          {loading && <div className="p-8 text-center text-slate-500">Caricamento calendario…</div>}
          {!loading && visible.length === 0 && <div className="p-4 text-center text-sm text-slate-400 border-b">Nessun evento corrisponde ai filtri attivi.</div>}
          {!loading && view === "month" && <div className="grid grid-cols-7">{["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"].map((x) => <div key={x} className="p-2 text-center text-xs font-bold text-slate-500 bg-slate-50 border-b border-r">{x}</div>)}{days.map((d, i) => { const k = dateKey(localIso(d)); const inMonth = d.getMonth() === cursor.getMonth(); return <div key={i} onDoubleClick={() => canCreate && newEvent(d)} onDragOver={(e) => e.preventDefault()} onDrop={() => dropOnDate(d)} className={`min-h-[130px] border-r border-b p-1.5 ${inMonth ? "bg-white" : "bg-slate-50"}`}><div className={`text-xs font-bold mb-1 ${sameDay(localIso(d), localIso(new Date())) ? "inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white" : inMonth ? "text-slate-700" : "text-slate-400"}`}>{d.getDate()}</div><div className="space-y-1">{(byDay[k] || []).slice(0, 5).map((e) => <EventCard key={e.key} event={e} compact onOpen={setDetail} onDragStart={(ev, x) => { setDragging(x); ev.dataTransfer.effectAllowed = "move"; }} />)}{(byDay[k] || []).length > 5 && <div className="text-[11px] text-slate-500 px-1">+ {(byDay[k] || []).length - 5} altri</div>}</div></div>; })}</div>}
          {!loading && view !== "month" && <div className="overflow-auto max-h-[76vh]"><div className="min-w-[900px]" style={{ display: "grid", gridTemplateColumns: `70px repeat(${days.length}, minmax(130px,1fr))` }}><div className="sticky top-0 bg-white z-20 border-b border-r" />{days.map((d, i) => <div key={i} className="sticky top-0 bg-white z-20 p-2 text-center border-b border-r"><div className="text-xs uppercase text-slate-500">{d.toLocaleDateString("it-IT", { weekday: "short" })}</div><div className={`mx-auto mt-1 text-sm font-black ${sameDay(localIso(d), localIso(new Date())) ? "h-7 w-7 rounded-full bg-blue-600 text-white flex items-center justify-center" : ""}`}>{d.getDate()}</div></div>)}{hours.map((h) => { const opened = openHours.has(h); return <div key={`row-${h}`} className="contents"><button type="button" onClick={() => toggleHour(h)} className={`border-r border-b text-xs text-slate-500 text-right pr-2 flex items-start justify-end gap-1 pt-2 hover:bg-slate-50 ${opened ? "h-[92px]" : "h-[42px]"}`}><span className="font-bold text-slate-700">{pad(h)}:00</span><span className="text-[10px]">{opened ? "▾" : "▸"}</span></button>{days.map((d, di) => { const k = dateKey(localIso(d)); const evs = (byDay[k] || []).filter((e) => parseLocal(e.start).getHours() === h || (e.all_day && h === 7)); return <div key={`${h}-${di}`} onDoubleClick={() => { if (!canCreate) return; const x = new Date(d); x.setHours(h, 0, 0, 0); newEvent(x); }} onDragOver={(e) => e.preventDefault()} onDrop={() => { const x = new Date(d); x.setHours(h, 0, 0, 0); dropOnDate(x); }} className={`border-r border-b p-1 hover:bg-blue-50/30 ${opened ? "min-h-[92px]" : "h-[42px] overflow-hidden"}`}>{opened ? <div className="space-y-1">{evs.map((e) => <EventCard key={e.key} event={e} onOpen={setDetail} onDragStart={(ev, x) => { setDragging(x); ev.dataTransfer.effectAllowed = "move"; }} />)}</div> : <div className="h-full flex items-center gap-1 overflow-hidden">{evs.slice(0, 2).map((e) => <button type="button" key={e.key} onClick={(ev) => { ev.stopPropagation(); setDetail(e); }} className="max-w-[48%] truncate rounded-md border px-1.5 py-1 text-[10px] font-semibold text-slate-700 bg-white" style={{ borderLeft: `3px solid ${e.resource_color || "#64748b"}` }}>{timeKey(e.start)} {e.title}</button>)}{evs.length > 2 && <span className="text-[10px] font-bold text-slate-500 whitespace-nowrap">+{evs.length - 2}</span>}{evs.length === 0 && <span className="text-[10px] text-slate-300 px-1">libero</span>}</div>}</div>; })}</div>; })}</div></div>}
        </section>
      </div>

      <Dialog open={!!detail} onOpenChange={(v) => !v && setDetail(null)}><DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>{detail?.title}</DialogTitle></DialogHeader>{detail && <div className="space-y-4"><div className="grid sm:grid-cols-2 gap-3 text-sm"><div className="rounded-md bg-slate-50 p-3"><b>Quando</b><div className="mt-1">{parseLocal(detail.start).toLocaleString("it-IT")}{detail.end ? ` – ${parseLocal(detail.end).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}` : ""}</div></div><div className="rounded-md bg-slate-50 p-3"><b>Partecipanti</b><div className="mt-1 flex flex-wrap gap-1.5">{(detail.resource_ids || []).length ? (detail.resource_ids || []).map((id) => { const r = resources.find((x) => x.id === id); return <span key={id} className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 text-xs"><span className="h-2 w-2 rounded-full" style={{ background: r?.color || "#64748b" }} />{r?.display_name || r?.name || "Partecipante"}</span>; }) : <span className="text-slate-500">Non assegnato</span>}</div></div></div>{detail.location && <div><b className="text-sm">Luogo</b><div className="mt-1 flex items-start gap-2 text-sm"><MapPin className="mt-0.5" />{detail.location}</div></div>}{detail.description && <div><b className="text-sm">Note / descrizione</b><div className="mt-1 whitespace-pre-wrap text-sm bg-slate-50 rounded-md p-3 max-h-52 overflow-y-auto">{detail.description}</div></div>}{detail.meeting_link && <div><b className="text-sm">Riunione online</b><div className="mt-1"><a className="text-sm font-semibold text-blue-700 hover:underline" href={detail.meeting_link} target="_blank" rel="noreferrer">Apri collegamento riunione</a></div></div>}{detail.location && <InstallationWeather date={dateKey(detail.start)} address={detail.location} compact />}<div className="flex flex-wrap gap-2">{detail.location && <Button variant="outline" onClick={() => window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(detail.location)}`, "_blank", "noopener,noreferrer")}><MapPin /> Maps</Button>}{detail.source_type !== "manual" && <Button variant="outline" onClick={() => openSource(detail)}><ArrowSquareOut /> Apri modulo</Button>}{canEdit && !detail.recurrence_instance && <Button onClick={() => editEvent(detail)}><PencilSimple /> Modifica</Button>}</div></div>}</DialogContent></Dialog>

      <EventEditor open={!!editor} event={editor} setEvent={setEditor} resources={resources} clients={clients} sites={sites} jobs={jobs} configLists={configLists} onClose={() => setEditor(null)} onSave={saveEvent} onDelete={deleteEvent} canDelete={!!editor?.key?.startsWith("manual:")} />
      <ResourcesDialog open={resourceDlg} onClose={() => setResourceDlg(false)} resources={resources} onChanged={load} />
    </div>
  );
}

function EventEditor({ open, event, setEvent, resources, clients = [], sites = [], jobs = [], configLists = defaultCalendarLists, onClose, onSave, onDelete, canDelete }) {
  if (!event) return null;
  const patch = (k, v) => setEvent((p) => ({ ...p, [k]: v }));
  const sourceLocked = event.key && !event.key.startsWith("manual:");
  const clientName = (c) => c.ragione_sociale || c.nome_struttura || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente";
  const visibleSites = event.cliente_id ? sites.filter((x) => String(x.cliente_id || "") === String(event.cliente_id)) : sites;
  const visibleJobs = event.cliente_id ? jobs.filter((x) => String(x.cliente_id || "") === String(event.cliente_id)) : jobs;
  const toggleResource = (id) => patch("resource_ids", (event.resource_ids || []).includes(id) ? (event.resource_ids || []).filter((x) => x !== id) : [...(event.resource_ids || []), id]);
  const resolveFromList = (value, rows, labelFn, key) => { const found = rows.find((x) => labelFn(x).toLowerCase() === String(value).trim().toLowerCase()); patch(key, found?.id || ""); };
  const currentClient = clients.find((x) => String(x.id) === String(event.cliente_id));
  const currentSite = sites.find((x) => String(x.id) === String(event.sede_id));
  const currentJob = jobs.find((x) => String(x.id) === String(event.commessa_id));
  const categories = (configLists.calendar_categories || defaultCalendarLists.calendar_categories).filter((x) => String(x).toLowerCase() !== "commerciale");

  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto"><DialogHeader><DialogTitle>{event.key ? "Modifica evento" : "Nuovo evento"}</DialogTitle></DialogHeader><div className="grid sm:grid-cols-2 gap-4"><div className="sm:col-span-2"><Label>Titolo *</Label><Input className="mt-1" value={event.title || ""} onChange={(e) => patch("title", e.target.value)} disabled={sourceLocked} /></div><div><Label>Inizio *</Label><Input className="mt-1" type="datetime-local" value={String(event.start || "").slice(0, 16)} onChange={(e) => patch("start", e.target.value)} /></div><div><Label>Fine</Label><Input className="mt-1" type="datetime-local" value={String(event.end || event.start || "").slice(0, 16)} onChange={(e) => patch("end", e.target.value)} /></div>{!sourceLocked && <><div><Label>Tipo</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={normalizeCategory(event.category)} onChange={(e) => patch("category", e.target.value)}>{categories.map((x) => <option key={x}>{x}</option>)}</select></div><div><Label>Stato</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={event.status || "Da confermare"} onChange={(e) => patch("status", e.target.value)}>{(configLists.calendar_statuses || defaultCalendarLists.calendar_statuses).map((x) => <option key={x}>{x}</option>)}</select></div><div><Label>Priorità</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={event.priority || "Normale"} onChange={(e) => patch("priority", e.target.value)}>{(configLists.calendar_priorities || defaultCalendarLists.calendar_priorities).map((x) => <option key={x}>{x}</option>)}</select></div><label className="flex items-center gap-2 pt-6 text-sm font-semibold"><input type="checkbox" checked={!!event.all_day} onChange={(e) => patch("all_day", e.target.checked)} /> Tutto il giorno</label><div className="sm:col-span-2"><Label>Partecipanti</Label><div className="mt-1 rounded-xl border border-slate-200 bg-slate-50 p-2 flex flex-wrap gap-2 max-h-36 overflow-y-auto">{resources.map((r) => { const active = (event.resource_ids || []).includes(r.id); return <button type="button" key={r.id} onClick={() => toggleResource(r.id)} className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-semibold ${active ? "bg-white border-blue-300 text-blue-700 shadow-sm" : "bg-white border-slate-200 text-slate-600"}`}><span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color || "#64748b" }} />{r.display_name || r.name}{active && <span>×</span>}</button>; })}{!resources.length && <span className="text-sm text-slate-400">Nessuna persona configurata.</span>}</div></div><div><Label>Cliente</Label><Input list="calendar-clients" className="mt-1" defaultValue={currentClient ? clientName(currentClient) : ""} onBlur={(e) => resolveFromList(e.target.value, clients, clientName, "cliente_id")} placeholder="Scrivi per cercare…" /><datalist id="calendar-clients">{clients.map((c) => <option key={c.id} value={clientName(c)} />)}</datalist></div><div><Label>Sede</Label><Input list="calendar-sites" className="mt-1" defaultValue={currentSite ? (currentSite.nome || [currentSite.indirizzo, currentSite.comune].filter(Boolean).join(" · ")) : ""} onBlur={(e) => resolveFromList(e.target.value, visibleSites, (x) => x.nome || [x.indirizzo, x.comune].filter(Boolean).join(" · "), "sede_id")} placeholder="Scrivi per cercare…" /><datalist id="calendar-sites">{visibleSites.map((x) => <option key={x.id} value={x.nome || [x.indirizzo, x.comune].filter(Boolean).join(" · ")} />)}</datalist></div><div className="sm:col-span-2"><Label>Commessa</Label><Input list="calendar-jobs" className="mt-1" defaultValue={currentJob ? (currentJob.numero || currentJob.codice || currentJob.nome || "") : ""} onBlur={(e) => resolveFromList(e.target.value, visibleJobs, (x) => x.numero || x.codice || x.nome || "", "commessa_id")} placeholder="Scrivi numero o nome commessa…" /><datalist id="calendar-jobs">{visibleJobs.map((x) => <option key={x.id} value={x.numero || x.codice || x.nome || ""} />)}</datalist></div><div className="sm:col-span-2"><Label>Luogo</Label><Input className="mt-1" value={event.location || ""} onChange={(e) => patch("location", e.target.value)} /></div><div className="sm:col-span-2"><Label>Link riunione</Label><Input className="mt-1" value={event.meeting_link || ""} onChange={(e) => patch("meeting_link", e.target.value)} placeholder="https://…" /></div><div><Label>Promemoria</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={event.reminder_minutes ?? 30} onChange={(e) => patch("reminder_minutes", Number(e.target.value))}>{[[0, "Nessuno"], [10, "10 minuti prima"], [30, "30 minuti prima"], [60, "1 ora prima"], [1440, "1 giorno prima"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div><div><Label>Ricorrenza</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={event.rrule || ""} onChange={(e) => patch("rrule", e.target.value)}><option value="">Nessuna</option><option value="FREQ=DAILY">Giornaliera</option><option value="FREQ=WEEKLY">Settimanale</option><option value="FREQ=MONTHLY">Mensile</option></select></div><div className="sm:col-span-2"><Label>Descrizione / note</Label><Textarea className="mt-1 min-h-28" value={event.description || ""} onChange={(e) => patch("description", e.target.value)} /></div></>}</div><div className="flex justify-between gap-2 mt-4">{canDelete ? <Button variant="outline" className="text-red-600" onClick={onDelete}><Trash /> Elimina</Button> : <span />}<div className="flex gap-2"><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={onSave}>Salva</Button></div></div></DialogContent></Dialog>;
}

function ResourceRow({ resource, onChanged }) {
  const [name, setName] = useState(resource.name || "");
  const [color, setColor] = useState(resource.color || "#64748b");
  const [saving, setSaving] = useState(false);
  const dirty = name.trim() !== String(resource.name || "").trim() || color !== (resource.color || "#64748b");
  const save = async () => {
    if (!name.trim()) return toast.error("Nome obbligatorio");
    setSaving(true);
    try {
      await axios.put(`${API}/calendar/resources/${resource.id}`, { name: name.trim(), color });
      toast.success("Calendario aggiornato");
      await onChanged();
    } catch (e) {
      toast.error("Aggiornamento non riuscito", { description: e?.response?.data?.detail || e?.message });
    } finally { setSaving(false); }
  };
  const remove = async () => {
    try {
      await axios.delete(`${API}/calendar/resources/${resource.id}`);
      toast.success("Calendario disattivato");
      await onChanged();
    } catch (e) { toast.error("Operazione non riuscita", { description: e?.response?.data?.detail || e?.message }); }
  };
  return <div className="grid grid-cols-[44px_minmax(0,1fr)_44px_44px] gap-2 items-center border rounded-lg p-2"><input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="h-9 w-10 border rounded" /><div><Input value={name} onChange={(e) => setName(e.target.value)} className="h-9" /><div className="text-[10px] text-slate-400 mt-1">{resource.display_name && resource.display_name !== resource.name ? `Utente collegato: ${resource.display_name}` : "Calendario interno"}</div></div><Button variant="ghost" size="icon" disabled={!dirty || saving} onClick={save} title="Salva"><FloppyDisk /></Button><Button variant="ghost" size="icon" className="text-red-600" onClick={remove} title="Disattiva"><Trash /></Button></div>;
}

function ResourcesDialog({ open, onClose, resources, onChanged }) {
  const [name, setName] = useState("");
  const [color, setColor] = useState("#64748b");
  const add = async () => {
    if (!name.trim()) return;
    try {
      await axios.post(`${API}/calendar/resources`, { name: name.trim(), color });
      setName("");
      toast.success("Calendario creato");
      await onChanged();
    } catch (e) { toast.error("Creazione non riuscita", { description: e?.response?.data?.detail || e?.message }); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Calendari / persone</DialogTitle></DialogHeader><p className="text-sm text-slate-500">Modifica nome e colore dei calendari. La disattivazione li rimuove dalle viste future senza cancellare lo storico eventi.</p><div className="space-y-2">{resources.map((r) => <ResourceRow key={`${r.id}-${r.name}-${r.color}`} resource={r} onChanged={onChanged} />)}</div><div className="border-t pt-4"><div className="font-bold mb-2">Nuovo calendario/persona</div><div className="grid grid-cols-[44px_minmax(0,1fr)_auto] gap-2"><input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="h-10 w-10 border rounded" /><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Es. Federico Rossi" /><Button onClick={add}><Plus /> Aggiungi</Button></div></div></DialogContent></Dialog>;
}
