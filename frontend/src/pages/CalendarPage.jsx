import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import {
  CaretLeft, CaretRight, Plus, MapPin, Wrench, ClipboardText,
  Headset, Gear, Trash, PencilSimple, ArrowSquareOut,
  SlidersHorizontal, MagnifyingGlass, UploadSimple, CalendarBlank,
  Clock, CheckCircle, WarningCircle, ArrowClockwise,
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import InstallationWeather from "../components/InstallationWeather";
import { appConfirm } from "../lib/appConfirm";

const pad = (n) => String(n).padStart(2, "0");
const localIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
const inputIso = (d) => localIso(d).slice(0, 16);
const dateKey = (value) => {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => { const out = new Date(d); out.setDate(out.getDate() + n); return out; };
const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);
const startOfWeek = (d) => { const x = startOfDay(d); return addDays(x, -((x.getDay() + 6) % 7)); };
const startOfMonthGrid = (d) => startOfWeek(new Date(d.getFullYear(), d.getMonth(), 1));
const sameDay = (a, b) => dateKey(a) === dateKey(b);
const parseLocal = (value) => { const d = new Date(value); return Number.isNaN(d.getTime()) ? new Date() : d; };
const timeKey = (value) => { const d = parseLocal(value); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const fmtDate = (d) => d.toLocaleDateString("it-IT", { day: "2-digit", month: "short" });
const fmtDayLong = (d) => d.toLocaleDateString("it-IT", { weekday: "long" });
const fmtMonth = (d) => d.toLocaleDateString("it-IT", { month: "long", year: "numeric" });
const normalizeCategory = (value) => String(value || "Attività").toLowerCase() === "commerciale" ? "Attività" : (value || "Attività");
const DEFAULT_PERSON_ROLES = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"];

const CATEGORY_COLORS = {
  Installazione: "#2563eb",
  Sopralluogo: "#7c3aed",
  Assistenza: "#dc2626",
  Riunione: "#0f766e",
  Formazione: "#0369a1",
  Attività: "#475569",
  Altro: "#64748b",
};
const defaultLists = {
  calendar_categories: ["Installazione", "Sopralluogo", "Assistenza", "Riunione", "Formazione", "Attività", "Altro"],
  calendar_statuses: ["Da confermare", "Confermato", "In corso", "Completato", "Annullato"],
  calendar_priorities: ["Bassa", "Normale", "Alta", "Urgente"],
};

function eventColor(event) {
  return event.resource_color || CATEGORY_COLORS[normalizeCategory(event.category)] || "#64748b";
}

function iconFor(category) {
  const value = normalizeCategory(category);
  if (value === "Installazione") return Wrench;
  if (value === "Sopralluogo") return ClipboardText;
  if (value === "Assistenza") return Headset;
  return CalendarBlank;
}

function displayStatus(value) {
  return String(value || "").trim() || "—";
}

function EventCard({ event, onOpen, onDragStart, compact = false, canDrag = false }) {
  const Icon = iconFor(event.category);
  const color = eventColor(event);
  const start = event.all_day ? "Tutto il giorno" : timeKey(event.start);
  const end = event.all_day || !event.end ? "" : timeKey(event.end);
  return (
    <button
      type="button"
      draggable={canDrag && !event.recurrence_instance}
      onDragStart={(e) => onDragStart?.(e, event)}
      onClick={() => onOpen(event)}
      className="r51-event-card"
      style={{ borderLeftColor: color }}
      title={`${event.title}${event.resource_name ? ` · ${event.resource_name}` : ""}`}
    >
      <div className="r51-event-time">
        <span className="inline-flex items-center gap-1"><Clock size={11} /> {start}{end && end !== start ? `–${end}` : ""}</span>
        {event.priority === "Urgente" && <WarningCircle size={13} className="text-red-600" weight="fill" />}
      </div>
      <div className="r51-event-title flex items-start gap-1.5"><Icon size={13} className="shrink-0 mt-0.5" /><span>{event.title}</span></div>
      {!compact && (event.resource_name || event.location) && <div className="r51-event-meta">
        {event.resource_name && <div className="truncate">{event.resource_name}</div>}
        {event.location && <div className="truncate flex items-center gap-1"><MapPin size={10} />{event.location}</div>}
      </div>}
      <span className="r51-event-category">{normalizeCategory(event.category)}</span>
    </button>
  );
}

function WeekView({ days, byDay, onOpen, onNew, onDrop, onDragStart, canCreate, canEdit }) {
  const today = new Date();
  return <div className="r51-calendar-week-wrap">
    <div className="r51-calendar-week">
      {days.map((day) => {
        const items = byDay[dateKey(day)] || [];
        return <section
          key={dateKey(day)}
          className={`r51-calendar-day ${sameDay(day, today) ? "is-today" : ""}`}
          onDragOver={(e) => canEdit && e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); onDrop(day); }}
        >
          <div className="r51-calendar-day-head">
            <div>
              <div className="r51-calendar-day-name">{fmtDayLong(day)}</div>
              <div className="r51-calendar-day-date">{day.getDate()} <span className="text-sm font-semibold text-slate-400">{day.toLocaleDateString("it-IT", { month: "short" })}</span></div>
            </div>
            <span className="r51-calendar-count">{items.length}</span>
          </div>
          <div className="r51-calendar-day-body">
            {items.map((event) => <EventCard key={event.key || `${event.id}-${event.start}`} event={event} onOpen={onOpen} onDragStart={onDragStart} canDrag={canEdit} />)}
            {!items.length && <div className="py-5 px-2 text-center text-[11px] text-slate-400">Nessuna attività</div>}
            {canCreate && <button type="button" className="r51-calendar-add-slot" onClick={() => onNew(day)}><Plus size={13} /> Aggiungi</button>}
          </div>
        </section>;
      })}
    </div>
  </div>;
}

function MonthView({ days, byDay, month, onOpen, onNew, canCreate }) {
  const today = new Date();
  return <div className="overflow-x-auto pb-2">
    <div className="r51-calendar-month">
      {days.map((day) => {
        const items = byDay[dateKey(day)] || [];
        const outside = day.getMonth() !== month.getMonth();
        return <section key={dateKey(day)} className={`r51-calendar-month-cell ${sameDay(day, today) ? "is-today" : ""} ${outside ? "opacity-45" : ""}`}>
          <div className="flex items-center justify-between mb-2">
            <div><span className="text-[10px] uppercase font-bold text-slate-400">{day.toLocaleDateString("it-IT", { weekday: "short" })}</span><span className="ml-1.5 font-black text-slate-800">{day.getDate()}</span></div>
            {canCreate && <button type="button" className="h-7 w-7 inline-flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500" onClick={() => onNew(day)} aria-label="Aggiungi evento"><Plus size={13} /></button>}
          </div>
          <div className="space-y-1.5">{items.slice(0, 4).map((event) => <EventCard key={event.key || `${event.id}-${event.start}`} event={event} onOpen={onOpen} compact />)}{items.length > 4 && <div className="text-[10px] text-slate-500 font-semibold pl-1">+ {items.length - 4} altri</div>}</div>
        </section>;
      })}
    </div>
  </div>;
}

function DayView({ day, events, onOpen, onNew, canCreate, canEdit, onDragStart, onDrop }) {
  return <section className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5" onDragOver={(e) => canEdit && e.preventDefault()} onDrop={(e) => { e.preventDefault(); onDrop(day); }}>
    <div className="flex items-center justify-between gap-3 mb-4">
      <div><div className="r51-kicker">Agenda del giorno</div><h2 className="r51-section-title text-xl mt-1 capitalize">{day.toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long" })}</h2></div>
      {canCreate && <Button onClick={() => onNew(day)}><Plus size={16} /> Aggiungi attività</Button>}
    </div>
    <div className="r51-calendar-day-agenda">{events.map((event) => <EventCard key={event.key || `${event.id}-${event.start}`} event={event} onOpen={onOpen} onDragStart={onDragStart} canDrag={canEdit} />)}{!events.length && <div className="r51-empty">Nessuna attività prevista per questo giorno.</div>}</div>
  </section>;
}

export default function CalendarPage() {
  const { isAdmin, hasPermission } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [view, setView] = useState("week");
  const [cursor, setCursor] = useState(new Date());
  const [events, setEvents] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedResources, setSelectedResources] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedRoles, setSelectedRoles] = useState([]);
  const [detail, setDetail] = useState(null);
  const [editor, setEditor] = useState(null);
  const [resourceDlg, setResourceDlg] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [migrationOpen, setMigrationOpen] = useState(false);
  const [dragging, setDragging] = useState(null);
  const [clients, setClients] = useState([]);
  const [sites, setSites] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [configLists, setConfigLists] = useState(defaultLists);
  const [search, setSearch] = useState("");
  const [migration, setMigration] = useState({ imports_enabled: true, completed: false, ready_to_finalize: false, finalized: false });
  const [importing, setImporting] = useState(false);
  const [newResource, setNewResource] = useState({ name: "", color: "#2d6ea3", role: "Tecnico" });

  const canCreate = hasPermission("calendar", "create") || isAdmin;
  const canEdit = hasPermission("calendar", "edit") || isAdmin;
  const canManagePeopleRoles = isAdmin || hasPermission("calendar", "manage_people_roles");
  const [roleOptions, setRoleOptions] = useState(DEFAULT_PERSON_ROLES);
  const [newRole, setNewRole] = useState("");
  const personRoles = roleOptions;

  const range = useMemo(() => {
    if (view === "day") { const start = startOfDay(cursor); return [start, addDays(start, 1)]; }
    if (view === "week") { const start = startOfWeek(cursor); return [start, addDays(start, 7)]; }
    const start = startOfMonthGrid(cursor);
    return [start, addDays(start, 42)];
  }, [cursor, view]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const { data } = await axios.get(`${API}/calendar/events`, { params: { start: localIso(range[0]), end: localIso(range[1]) } });
      const loadedResources = data.resources || [];
      setResources(loadedResources);
      setEvents((data.items || []).map((event) => {
        const assigned = loadedResources.find((r) => (event.resource_ids || []).includes(r.id));
        return { ...event, category: normalizeCategory(event.category), resource_role: event.resource_role || assigned?.role || "" };
      }));
    } catch (error) {
      toast.error("Calendario non disponibile", { description: error?.response?.data?.detail || error?.message });
    } finally { if (!silent) setLoading(false); }
  }, [range]);

  const loadLookups = useCallback(async () => {
    const [c, s, j, l, m] = await Promise.allSettled([
      axios.get(`${API}/crm/clienti`),
      axios.get(`${API}/crm/sedi`),
      axios.get(`${API}/commesse`),
      axios.get(`${API}/custom/config/lists`),
      axios.get(`${API}/calendar/integration-state`),
    ]);
    if (c.status === "fulfilled") setClients(c.value.data?.items || []);
    if (s.status === "fulfilled") setSites(s.value.data?.items || []);
    if (j.status === "fulfilled") setJobs(j.value.data?.items || []);
    if (l.status === "fulfilled") {
      const values = l.value.data?.values || {};
      const categories = (values.calendar_categories || defaultLists.calendar_categories).filter((x) => String(x).toLowerCase() !== "commerciale");
      setConfigLists((prev) => ({ ...prev, ...values, calendar_categories: categories }));
    }
    if (m.status === "fulfilled") setMigration((prev) => ({ ...prev, ...(m.value.data || {}) }));
  }, []);

  const loadRoles = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/calendar/roles`);
      const items = (data.items || []).filter(Boolean);
      setRoleOptions(items);
      setNewResource((p) => ({ ...p, role: items.some((x) => x === p.role) ? p.role : (items[0] || "Tecnico") }));
    } catch (error) {
      toast.error("Ruoli calendario non disponibili", { description: error?.response?.data?.detail || error?.message });
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadRoles(); }, [loadRoles]);
  useEffect(() => {
    loadLookups();
    const onConfig = () => loadLookups();
    window.addEventListener("elios:config-lists-changed", onConfig);
    return () => window.removeEventListener("elios:config-lists-changed", onConfig);
  }, [loadLookups]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return events.filter((event) => {
      if (selectedResources.length && !(event.resource_ids || []).some((id) => selectedResources.includes(id))) return false;
      if (selectedCategories.length && !selectedCategories.includes(normalizeCategory(event.category))) return false;
      if (selectedRoles.length) {
        const eventRoles = (event.resource_ids || []).map((id) => resources.find((r) => r.id === id)?.role).filter(Boolean);
        if (!eventRoles.some((role) => selectedRoles.includes(role))) return false;
      }
      if (query && !`${event.title || ""} ${event.description || ""} ${event.location || ""} ${event.resource_name || ""} ${event.resource_role || ""}`.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [events, resources, selectedResources, selectedCategories, selectedRoles, search]);

  const byDay = useMemo(() => {
    const map = {};
    visible.forEach((event) => {
      const key = dateKey(event.start);
      if (!map[key]) map[key] = [];
      map[key].push(event);
    });
    Object.values(map).forEach((items) => items.sort((a, b) => String(a.start).localeCompare(String(b.start))));
    return map;
  }, [visible]);

  const days = useMemo(() => view === "month"
    ? Array.from({ length: 42 }, (_, index) => addDays(range[0], index))
    : view === "week"
      ? Array.from({ length: 7 }, (_, index) => addDays(range[0], index))
      : [range[0]], [view, range]);

  const stats = useMemo(() => ({
    total: visible.length,
    installazioni: visible.filter((event) => normalizeCategory(event.category) === "Installazione").length,
    assistenze: visible.filter((event) => normalizeCategory(event.category) === "Assistenza").length,
    pending: visible.filter((event) => ["da confermare", "programmata", "aperta", "in attesa"].includes(String(event.status || "").toLowerCase())).length,
  }), [visible]);

  const heading = view === "month"
    ? fmtMonth(cursor)
    : view === "week"
      ? `${fmtDate(range[0])} – ${fmtDate(addDays(range[1], -1))} ${addDays(range[1], -1).getFullYear()}`
      : cursor.toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  const shift = (direction) => setCursor((current) => view === "month" ? addMonths(current, direction) : addDays(current, direction * (view === "week" ? 7 : 1)));

  const newEvent = (date = new Date()) => {
    const start = new Date(date);
    if (start.getHours() === 0) start.setHours(9, 0, 0, 0);
    const end = new Date(start); end.setHours(start.getHours() + 1);
    setEditor({
      key: null, title: "", start: inputIso(start), end: inputIso(end),
      category: configLists.calendar_categories?.[0] || "Attività",
      resource_ids: [], description: "", location: "", all_day: false,
      status: configLists.calendar_statuses?.[0] || "Da confermare",
      priority: configLists.calendar_priorities?.[1] || "Normale",
      cliente_id: "", sede_id: "", commessa_id: "", meeting_link: "",
      reminder_minutes: 30, rrule: "",
    });
  };

  const editEvent = (event) => setEditor({
    ...event,
    category: normalizeCategory(event.category),
    start: String(event.start || "").slice(0, 16),
    end: String(event.end || event.start || "").slice(0, 16),
    resource_ids: event.resource_ids || [],
  });

  const saveEvent = async () => {
    if (!editor?.title?.trim()) return toast.error("Inserisci il titolo");
    if (!editor?.start) return toast.error("Inserisci data e ora di inizio");
    if (editor.end && new Date(editor.end) < new Date(editor.start)) return toast.error("La fine non può precedere l'inizio");
    try {
      const payload = { ...editor, category: normalizeCategory(editor.category) };
      ["key", "source_type", "source_id", "resource_name", "resource_color", "source_record", "recurrence_instance"].forEach((key) => delete payload[key]);
      if (editor.key) await axios.put(`${API}/calendar/events/${encodeURIComponent(editor.key)}`, payload);
      else await axios.post(`${API}/calendar/events`, payload);
      toast.success(editor.key ? "Evento aggiornato" : "Evento creato");
      setEditor(null); setDetail(null); await load(true);
    } catch (error) {
      toast.error("Salvataggio non riuscito", { description: error?.response?.data?.detail || error?.message });
    }
  };

  const deleteEvent = async () => {
    if (!editor?.key?.startsWith("manual:")) return;
    const ok = await appConfirm({ title: "Elimina evento", message: "Vuoi eliminare definitivamente questo evento dal calendario?", confirmLabel: "Elimina", danger: true });
    if (!ok) return;
    try {
      await axios.delete(`${API}/calendar/events/${encodeURIComponent(editor.key)}`);
      toast.success("Evento eliminato"); setEditor(null); setDetail(null); await load(true);
    } catch (error) { toast.error("Eliminazione non riuscita", { description: error?.response?.data?.detail || error?.message }); }
  };

  const dropOnDate = async (date) => {
    if (!dragging || !canEdit) return;
    const oldStart = parseLocal(dragging.start);
    const oldEnd = parseLocal(dragging.end || dragging.start);
    const target = new Date(date);
    target.setHours(oldStart.getHours(), oldStart.getMinutes(), 0, 0);
    const duration = Math.max(15, (oldEnd - oldStart) / 60000);
    const end = new Date(target.getTime() + duration * 60000);
    try {
      await axios.put(`${API}/calendar/events/${encodeURIComponent(dragging.key)}`, { start: localIso(target), end: localIso(end) });
      setDragging(null); await load(true);
    } catch (error) { toast.error("Spostamento non riuscito", { description: error?.response?.data?.detail || error?.message }); }
  };

  const openSource = (event) => {
    if (event.source_type === "installazione") navigate("/installazioni");
    else if (event.source_type === "sopralluogo") navigate("/sopralluoghi");
    else if (event.source_type === "assistenza") navigate("/assistenza");
    else if (event.source_type === "custom" && event.module_slug) navigate(`/moduli/${event.module_slug}`);
  };

  const toggleResource = (id) => setSelectedResources((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  const toggleCategory = (category) => setSelectedCategories((prev) => prev.includes(category) ? prev.filter((x) => x !== category) : [...prev, category]);
  const toggleRole = (role) => setSelectedRoles((prev) => prev.includes(role) ? prev.filter((x) => x !== role) : [...prev, role]);
  const clearFilters = () => { setSelectedResources([]); setSelectedCategories([]); setSelectedRoles([]); setSearch(""); };

  const importIcs = async (file) => {
    if (!file) return;
    setImporting(true);
    try {
      const form = new FormData(); form.append("file", file);
      const { data } = await axios.post(`${API}/calendar/import/ics`, form, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Calendario importato", { description: `${data.imported || 0} nuovi · ${data.updated || 0} aggiornati · ${data.linked_clients || 0} collegati a clienti` });
      await Promise.all([load(true), loadLookups()]);
    } catch (error) {
      toast.error("Importazione calendario non riuscita", { description: error?.response?.data?.detail || error?.message });
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const relinkImported = async () => {
    try {
      const { data } = await axios.post(`${API}/calendar/relink`);
      toast.success("Collegamenti aggiornati", { description: `${data.linked || 0} eventi collegati ai clienti` });
      await load(true);
    } catch (error) { toast.error("Collegamento non riuscito", { description: error?.response?.data?.detail || error?.message }); }
  };

  const finalizeCalendarMigration = async () => {
    const ok = await appConfirm({
      title: "Rendi il calendario autonomo",
      message: "Gli eventi importati resteranno nel gestionale come eventi locali. I riferimenti alla sorgente esterna verranno rimossi e non sarà più possibile fare altri import.",
      confirmLabel: "Concludi migrazione",
      danger: false,
    });
    if (!ok) return;
    try {
      const { data } = await axios.post(`${API}/calendar/migration/finalize`);
      toast.success("Calendario autonomo", { description: data.message });
      await Promise.all([load(true), loadLookups()]);
    } catch (error) { toast.error("Chiusura migrazione non riuscita", { description: error?.response?.data?.detail || error?.message }); }
  };

  const addRole = async () => {
    const name = newRole.trim();
    if (!name) return toast.error("Inserisci il nome del ruolo");
    try {
      const { data } = await axios.post(`${API}/calendar/roles`, { name });
      setRoleOptions(data.items || []);
      setNewRole("");
      toast.success(data.created === false ? "Ruolo già presente" : "Ruolo creato");
    } catch (error) { toast.error("Creazione ruolo non riuscita", { description: error?.response?.data?.detail || error?.message }); }
  };

  const removeRole = async (role) => {
    const ok = await appConfirm({ title: "Elimina ruolo", message: `Eliminare il ruolo “${role}”? È possibile solo se non è assegnato a nessuna persona.`, confirmLabel: "Elimina", danger: true });
    if (!ok) return;
    try {
      const { data } = await axios.delete(`${API}/calendar/roles/${encodeURIComponent(role)}`);
      setRoleOptions(data.items || []);
      toast.success("Ruolo eliminato");
    } catch (error) { toast.error("Ruolo non eliminato", { description: error?.response?.data?.detail || error?.message }); }
  };

  const addResource = async () => {
    if (!newResource.name.trim()) return toast.error("Inserisci il nome");
    try {
      await axios.post(`${API}/calendar/resources`, newResource);
      setNewResource({ name: "", color: "#2d6ea3", role: "Tecnico" });
      await load(true);
      toast.success("Calendario aggiunto");
    } catch (error) { toast.error("Creazione non riuscita", { description: error?.response?.data?.detail || error?.message }); }
  };

  const updateResource = async (resource, patch) => {
    const next = { ...resource, ...patch };
    setResources((prev) => prev.map((item) => item.id === resource.id ? next : item));
    try { await axios.put(`${API}/calendar/resources/${resource.id}`, { name: next.name, color: next.color, role: next.role, linked_user_id: next.linked_user_id, sort_order: next.sort_order }); }
    catch (error) { toast.error("Modifica calendario non riuscita", { description: error?.response?.data?.detail || error?.message }); await load(true); }
  };

  const removeResource = async (resource) => {
    const ok = await appConfirm({ title: "Nascondi calendario", message: `Nascondere ${resource.name}? Gli eventi non vengono cancellati.`, confirmLabel: "Nascondi", danger: true });
    if (!ok) return;
    try { await axios.delete(`${API}/calendar/resources/${resource.id}`); await load(true); }
    catch (error) { toast.error("Operazione non riuscita", { description: error?.response?.data?.detail || error?.message }); }
  };

  const clientName = (id) => { const c = clients.find((x) => String(x.id) === String(id)); return c?.ragione_sociale || [c?.nome, c?.cognome].filter(Boolean).join(" ") || ""; };
  const selectedSite = sites.find((x) => String(x.id) === String(detail?.sede_id));
  const editorSites = sites.filter((x) => !editor?.cliente_id || String(x.cliente_id) === String(editor.cliente_id));
  const editorJobs = jobs.filter((x) => !editor?.cliente_id || String(x.cliente_id) === String(editor.cliente_id));

  return <div className="max-w-[1660px] mx-auto px-3 sm:px-5 py-4 sm:py-6 space-y-4" data-testid="company-calendar-page">
    <div className="r51-calendar-hero">
      <div>
        <div className="r51-kicker">Elios Tech · pianificazione operativa</div>
        <h1 className="text-3xl sm:text-4xl mt-1">Calendario</h1>
        <div className="r51-calendar-period mt-2 capitalize">{heading}</div>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        {canManagePeopleRoles && <Button variant="outline" onClick={() => setResourceDlg(true)}><Gear size={16} /> Persone e ruoli</Button>}
        {isAdmin && !migration.finalized && <Button variant="outline" onClick={() => setMigrationOpen((v) => !v)}><UploadSimple size={16} /> Importazione</Button>}
        <Button variant={filtersOpen ? "default" : "outline"} onClick={() => setFiltersOpen((v) => !v)}><SlidersHorizontal size={16} /> Filtri</Button>
        {canCreate && <Button onClick={() => newEvent(new Date())}><Plus size={16} /> Aggiungi attività</Button>}
      </div>
    </div>

    <div className="r51-calendar-summary">
      <div className="r51-calendar-stat"><strong>{stats.total}</strong><span>Attività nel periodo</span></div>
      <div className="r51-calendar-stat"><strong>{stats.installazioni}</strong><span>Installazioni</span></div>
      <div className="r51-calendar-stat"><strong>{stats.assistenze}</strong><span>Assistenze</span></div>
      <div className="r51-calendar-stat"><strong>{stats.pending}</strong><span>Da seguire / confermare</span></div>
    </div>

    <div className="r51-toolbar">
      <div className="flex items-center gap-1">
        <button type="button" className="h-10 w-10 rounded-lg border border-slate-200 bg-white inline-flex items-center justify-center hover:bg-slate-50" onClick={() => shift(-1)} aria-label="Periodo precedente"><CaretLeft size={17} /></button>
        <Button variant="outline" onClick={() => setCursor(new Date())}>Oggi</Button>
        <button type="button" className="h-10 w-10 rounded-lg border border-slate-200 bg-white inline-flex items-center justify-center hover:bg-slate-50" onClick={() => shift(1)} aria-label="Periodo successivo"><CaretRight size={17} /></button>
      </div>
      <div className="r51-tabs">
        {[["day", "Giorno"], ["week", "Settimana"], ["month", "Mese"]].map(([key, label]) => <button type="button" key={key} className={`r51-tab ${view === key ? "is-active" : ""}`} onClick={() => setView(key)}>{label}</button>)}
      </div>
      <div className="relative min-w-[220px] flex-1 max-w-lg">
        <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input className="pl-9 h-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cerca cliente, attività, luogo, tecnico…" />
      </div>
      <Button variant="outline" onClick={() => load()} disabled={loading}><ArrowClockwise size={16} className={loading ? "animate-spin" : ""} /> Aggiorna</Button>
    </div>

    {filtersOpen && <div className="r51-calendar-filter-panel">
      <div className="flex items-start justify-between gap-3 mb-3"><div><div className="r51-section-title">Filtra la pianificazione</div><div className="text-xs text-slate-500 mt-0.5">Seleziona persone o tipologie per concentrarti sulle attività utili.</div></div><Button variant="ghost" size="sm" onClick={clearFilters}>Azzera</Button></div>
      <div className="grid xl:grid-cols-3 gap-4">
        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Persone / calendari</div><div className="flex flex-wrap gap-2">{resources.map((resource) => { const active = selectedResources.includes(resource.id); return <button type="button" key={resource.id} onClick={() => toggleResource(resource.id)} className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}><span className="r51-resource-dot" style={{ background: resource.color || "#64748b" }} /><span>{resource.name}</span>{resource.role && <span className="text-[10px] text-slate-400">· {resource.role}</span>}</button>; })}</div></div>
        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Ruolo operativo</div><div className="flex flex-wrap gap-2">{personRoles.map((role) => { const active = selectedRoles.includes(role); return <button type="button" key={role} onClick={() => toggleRole(role)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}>{role}</button>; })}</div></div>
        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Tipologia</div><div className="flex flex-wrap gap-2">{(configLists.calendar_categories || []).map((category) => { const active = selectedCategories.includes(category); return <button type="button" key={category} onClick={() => toggleCategory(category)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}>{category}</button>; })}</div></div>
      </div>
    </div>}

    {isAdmin && !migration.finalized && migrationOpen && <div className="r51-calendar-filter-panel">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><div className="r51-section-title">Migrazione calendario una tantum</div>{migration.finalized && <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-1"><CheckCircle size={13} /> Autonomo</span>}</div>
          <div className="text-sm text-slate-500 mt-1">Gli eventi importati vengono salvati nel database del gestionale. Dopo la verifica puoi chiudere la migrazione e rimuovere tutti i riferimenti alla sorgente esterna.</div>
          {migration.last_result?.parsed != null && <div className="text-xs text-slate-500 mt-2">Ultimo import: {migration.last_result.parsed} letti · {migration.last_result.imported || 0} nuovi · {migration.last_result.updated || 0} aggiornati{migration.last_result.skipped_leads ? ` · ${migration.last_result.skipped_leads} Lead esclusi` : ""}</div>}
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          {!migration.finalized && <><input ref={fileInputRef} type="file" accept=".ics,.zip" className="hidden" onChange={(e) => importIcs(e.target.files?.[0])} /><Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={importing}><UploadSimple size={16} /> {importing ? "Importazione…" : "Importa .ics / ZIP"}</Button><Button variant="outline" onClick={relinkImported}>Collega ai clienti</Button></>}
          {migration.ready_to_finalize && !migration.finalized && <Button onClick={finalizeCalendarMigration}><CheckCircle size={16} /> Concludi migrazione</Button>}
        </div>
      </div>
    </div>}

    {loading && !events.length ? <div className="r51-empty">Caricamento pianificazione…</div> : view === "week"
      ? <WeekView days={days} byDay={byDay} onOpen={setDetail} onNew={newEvent} onDrop={dropOnDate} onDragStart={(e, event) => setDragging(event)} canCreate={canCreate} canEdit={canEdit} />
      : view === "month"
        ? <MonthView days={days} byDay={byDay} month={cursor} onOpen={setDetail} onNew={newEvent} canCreate={canCreate} />
        : <DayView day={days[0]} events={byDay[dateKey(days[0])] || []} onOpen={setDetail} onNew={newEvent} canCreate={canCreate} canEdit={canEdit} onDragStart={(e, event) => setDragging(event)} onDrop={dropOnDate} />}

    <Dialog open={!!detail} onOpenChange={(open) => !open && setDetail(null)}>
      <DialogContent className="max-w-xl">
        {detail && <>
          <DialogHeader><DialogTitle className="text-xl">{detail.title}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="rounded-xl bg-slate-50 border p-3"><div className="text-[10px] uppercase font-bold text-slate-400">Quando</div><div className="font-bold mt-1">{detail.all_day ? "Tutto il giorno" : `${new Date(detail.start).toLocaleDateString("it-IT")} · ${timeKey(detail.start)}${detail.end ? `–${timeKey(detail.end)}` : ""}`}</div></div>
              <div className="rounded-xl bg-slate-50 border p-3"><div className="text-[10px] uppercase font-bold text-slate-400">Assegnato</div><div className="font-bold mt-1 flex items-center gap-2"><span className="r51-resource-dot" style={{ background: eventColor(detail) }} />{detail.resource_name || "Non assegnato"}</div></div>
            </div>
            <div className="flex flex-wrap gap-2"><span className="px-2.5 py-1 rounded-full bg-slate-100 text-xs font-bold">{normalizeCategory(detail.category)}</span>{detail.status && <span className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-800 text-xs font-bold">{displayStatus(detail.status)}</span>}{detail.priority && <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 text-xs font-bold">{detail.priority}</span>}</div>
            {detail.cliente_id && <div><div className="text-xs font-bold text-slate-400 uppercase">Cliente</div><div className="mt-1 font-semibold">{clientName(detail.cliente_id) || "Cliente collegato"}</div></div>}
            {detail.location && <div><div className="text-xs font-bold text-slate-400 uppercase">Luogo</div><div className="mt-1 flex items-start gap-2"><MapPin size={16} className="mt-0.5 text-slate-400" />{detail.location}</div></div>}
            {detail.description && <div><div className="text-xs font-bold text-slate-400 uppercase">Note</div><div className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{detail.description}</div></div>}
            {normalizeCategory(detail.category) === "Installazione" && <InstallationWeather date={dateKey(detail.start)} site={selectedSite} address={detail.location || ""} compact />}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            {detail.source_type && detail.source_type !== "manual" && <Button variant="outline" onClick={() => openSource(detail)}><ArrowSquareOut size={15} /> Apri attività</Button>}
            {canEdit && <Button onClick={() => { editEvent(detail); setDetail(null); }}><PencilSimple size={15} /> Modifica</Button>}
          </DialogFooter>
        </>}
      </DialogContent>
    </Dialog>

    <Dialog open={!!editor} onOpenChange={(open) => !open && setEditor(null)}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto">
        {editor && <>
          <DialogHeader><DialogTitle>{editor.key ? "Modifica attività" : "Aggiungi attività"}</DialogTitle></DialogHeader>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2"><Label>Titolo *</Label><Input className="mt-1" value={editor.title || ""} onChange={(e) => setEditor((p) => ({ ...p, title: e.target.value }))} /></div>
            <div><Label>Inizio *</Label><Input type="datetime-local" className="mt-1" value={editor.start || ""} onChange={(e) => setEditor((p) => ({ ...p, start: e.target.value }))} /></div>
            <div><Label>Fine</Label><Input type="datetime-local" className="mt-1" value={editor.end || ""} onChange={(e) => setEditor((p) => ({ ...p, end: e.target.value }))} /></div>
            <div><Label>Tipologia</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={normalizeCategory(editor.category)} onChange={(e) => setEditor((p) => ({ ...p, category: e.target.value }))}>{(configLists.calendar_categories || []).map((x) => <option key={x}>{x}</option>)}</select></div>
            <div><Label>Persona / calendario</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={(editor.resource_ids || [])[0] || ""} onChange={(e) => setEditor((p) => ({ ...p, resource_ids: e.target.value ? [e.target.value] : [] }))}><option value="">Non assegnato</option>{resources.map((r) => <option key={r.id} value={r.id}>{r.name}{r.role ? ` · ${r.role}` : ""}</option>)}</select></div>
            <div><Label>Stato</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={editor.status || ""} onChange={(e) => setEditor((p) => ({ ...p, status: e.target.value }))}>{(configLists.calendar_statuses || []).map((x) => <option key={x}>{x}</option>)}</select></div>
            <div><Label>Priorità</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={editor.priority || "Normale"} onChange={(e) => setEditor((p) => ({ ...p, priority: e.target.value }))}>{(configLists.calendar_priorities || []).map((x) => <option key={x}>{x}</option>)}</select></div>
            <div><Label>Cliente</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={editor.cliente_id || ""} onChange={(e) => setEditor((p) => ({ ...p, cliente_id: e.target.value, sede_id: "", commessa_id: "" }))}><option value="">Nessun cliente</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.ragione_sociale || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente"}</option>)}</select></div>
            <div><Label>Sede</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={editor.sede_id || ""} onChange={(e) => setEditor((p) => ({ ...p, sede_id: e.target.value }))}><option value="">Nessuna sede</option>{editorSites.map((s) => <option key={s.id} value={s.id}>{s.nome || [s.indirizzo, s.comune].filter(Boolean).join(" · ") || "Sede"}</option>)}</select></div>
            <div><Label>Commessa</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={editor.commessa_id || ""} onChange={(e) => setEditor((p) => ({ ...p, commessa_id: e.target.value }))}><option value="">Nessuna commessa</option>{editorJobs.map((job) => <option key={job.id} value={job.id}>{job.number || job.cliente || "Commessa"}</option>)}</select></div>
            <div><Label>Luogo / indirizzo</Label><Input className="mt-1" value={editor.location || ""} onChange={(e) => setEditor((p) => ({ ...p, location: e.target.value }))} /></div>
            <div className="sm:col-span-2"><Label>Note / attività da svolgere</Label><Textarea className="mt-1" rows={4} value={editor.description || ""} onChange={(e) => setEditor((p) => ({ ...p, description: e.target.value }))} /></div>
            {editor.source_type === "manual" || !editor.key ? <><div><Label>Promemoria (minuti)</Label><Input type="number" min="0" className="mt-1" value={editor.reminder_minutes ?? 30} onChange={(e) => setEditor((p) => ({ ...p, reminder_minutes: Number(e.target.value || 0) }))} /></div><div><Label>Ricorrenza RRULE</Label><Input className="mt-1" value={editor.rrule || ""} placeholder="Es. FREQ=WEEKLY;COUNT=6" onChange={(e) => setEditor((p) => ({ ...p, rrule: e.target.value }))} /></div></> : null}
          </div>
          <DialogFooter className="gap-2 sm:justify-between">
            <div>{editor.key?.startsWith("manual:") && canEdit && <Button variant="destructive" onClick={deleteEvent}><Trash size={15} /> Elimina</Button>}</div>
            <div className="flex gap-2"><Button variant="outline" onClick={() => setEditor(null)}>Annulla</Button><Button onClick={saveEvent}>Salva</Button></div>
          </DialogFooter>
        </>}
      </DialogContent>
    </Dialog>

    <Dialog open={resourceDlg} onOpenChange={setResourceDlg}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Persone e ruoli del calendario</DialogTitle></DialogHeader>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3">
          <div><div className="text-sm font-black text-slate-900">Ruoli disponibili</div><div className="text-xs text-slate-500 mt-0.5">I ruoli si creano qui una volta sola. Poi possono essere soltanto assegnati alle persone da un Admin o da chi ha ricevuto il permesso dedicato.</div></div>
          <div className="flex flex-wrap gap-2">{personRoles.map((role) => <span key={role} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700">{role}<button type="button" className="text-slate-400 hover:text-red-600" onClick={() => removeRole(role)} aria-label={`Elimina ruolo ${role}`}><Trash size={13}/></button></span>)}</div>
          <div className="flex gap-2"><Input value={newRole} onChange={(e) => setNewRole(e.target.value)} placeholder="Nuovo ruolo, es. Tecnico interno" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRole(); } }} /><Button type="button" onClick={addRole}><Plus size={15}/> Aggiungi ruolo</Button></div>
        </div>
        <div className="space-y-3">
          {resources.map((resource) => <div key={resource.id} className="grid sm:grid-cols-[46px_minmax(0,1fr)_180px_42px] gap-2 items-center rounded-xl border border-slate-200 p-2.5">
            <input type="color" className="h-9 w-10 rounded border-0 p-0 bg-transparent" value={resource.color || "#64748b"} onChange={(e) => updateResource(resource, { color: e.target.value })} aria-label="Colore" />
            <Input value={resource.name || ""} onChange={(e) => setResources((prev) => prev.map((x) => x.id === resource.id ? { ...x, name: e.target.value } : x))} onBlur={() => updateResource(resource, { name: resources.find((x) => x.id === resource.id)?.name || resource.name })} />
            <select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-800" value={resource.role || personRoles[0] || "Tecnico"} onChange={(e) => updateResource(resource, { role: e.target.value })} aria-label={`Ruolo di ${resource.name}`}>{personRoles.map((role) => <option key={role} value={role}>{role}</option>)}</select>
            <button type="button" className="h-9 w-9 rounded-lg border border-slate-200 inline-flex items-center justify-center text-slate-500 hover:text-red-600" onClick={() => removeResource(resource)} aria-label="Nascondi"><Trash size={15} /></button>
          </div>)}
          <div className="grid sm:grid-cols-[46px_minmax(0,1fr)_180px_auto] gap-2 items-center pt-3 border-t border-slate-100">
            <input type="color" className="h-9 w-10 rounded border-0 p-0 bg-transparent" value={newResource.color} onChange={(e) => setNewResource((p) => ({ ...p, color: e.target.value }))} aria-label="Colore nuovo calendario" />
            <Input value={newResource.name} onChange={(e) => setNewResource((p) => ({ ...p, name: e.target.value }))} placeholder="Nome persona / calendario" />
            <select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-800" value={newResource.role || personRoles[0] || "Tecnico"} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))}>{personRoles.map((role) => <option key={role} value={role}>{role}</option>)}</select>
            <Button onClick={addResource}><Plus size={15} /> Aggiungi</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>;
}
