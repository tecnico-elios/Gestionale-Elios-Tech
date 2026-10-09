const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const file = path.join(ROOT, 'src/pages/CalendarPage.jsx');
let s = fs.readFileSync(file, 'utf8');

function replaceOnce(from, to, label) {
  if (s.includes(to)) return;
  if (!s.includes(from)) throw new Error(`[R58] ${label}: blocco non trovato`);
  s = s.replace(from, to);
}

replaceOnce(
  'const CATEGORY_COLORS = {',
  'const PERSON_ROLES = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"];\n\nconst CATEGORY_COLORS = {',
  'ruoli operativi'
);

replaceOnce(
  '  const [selectedCategories, setSelectedCategories] = useState([]);',
  '  const [selectedCategories, setSelectedCategories] = useState([]);\n  const [selectedRoles, setSelectedRoles] = useState([]);',
  'stato filtro ruoli'
);

replaceOnce(
  '  const [newResource, setNewResource] = useState({ name: "", color: "#2d6ea3" });',
  '  const [newResource, setNewResource] = useState({ name: "", color: "#2d6ea3", role: "Tecnico" });',
  'ruolo nuova persona'
);

replaceOnce(
  '      const { data } = await axios.get(`${API}/calendar/events`, { params: { start: localIso(range[0]), end: localIso(range[1]) } });\n      setEvents((data.items || []).map((event) => ({ ...event, category: normalizeCategory(event.category) })));\n      setResources(data.resources || []);',
  '      const { data } = await axios.get(`${API}/calendar/events`, { params: { start: localIso(range[0]), end: localIso(range[1]) } });\n      const loadedResources = data.resources || [];\n      setResources(loadedResources);\n      setEvents((data.items || []).map((event) => {\n        const assigned = loadedResources.find((r) => (event.resource_ids || []).includes(r.id));\n        return { ...event, category: normalizeCategory(event.category), resource_role: event.resource_role || assigned?.role || "" };\n      }));',
  'caricamento ruoli'
);

replaceOnce(
  '      if (selectedCategories.length && !selectedCategories.includes(normalizeCategory(event.category))) return false;\n      if (query && !`${event.title || ""} ${event.description || ""} ${event.location || ""} ${event.resource_name || ""}`.toLowerCase().includes(query)) return false;',
  '      if (selectedCategories.length && !selectedCategories.includes(normalizeCategory(event.category))) return false;\n      if (selectedRoles.length) {\n        const eventRoles = (event.resource_ids || []).map((id) => resources.find((r) => r.id === id)?.role).filter(Boolean);\n        if (!eventRoles.some((role) => selectedRoles.includes(role))) return false;\n      }\n      if (query && !`${event.title || ""} ${event.description || ""} ${event.location || ""} ${event.resource_name || ""} ${event.resource_role || ""}`.toLowerCase().includes(query)) return false;',
  'filtro eventi per ruolo'
);

replaceOnce(
  '  }, [events, selectedResources, selectedCategories, search]);',
  '  }, [events, resources, selectedResources, selectedCategories, selectedRoles, search]);',
  'dipendenze filtro ruoli'
);

replaceOnce(
  '  const toggleCategory = (category) => setSelectedCategories((prev) => prev.includes(category) ? prev.filter((x) => x !== category) : [...prev, category]);\n  const clearFilters = () => { setSelectedResources([]); setSelectedCategories([]); setSearch(""); };',
  '  const toggleCategory = (category) => setSelectedCategories((prev) => prev.includes(category) ? prev.filter((x) => x !== category) : [...prev, category]);\n  const toggleRole = (role) => setSelectedRoles((prev) => prev.includes(role) ? prev.filter((x) => x !== role) : [...prev, role]);\n  const clearFilters = () => { setSelectedResources([]); setSelectedCategories([]); setSelectedRoles([]); setSearch(""); };',
  'azioni filtro ruoli'
);

replaceOnce(
  '      setNewResource({ name: "", color: "#2d6ea3" });',
  '      setNewResource({ name: "", color: "#2d6ea3", role: "Tecnico" });',
  'reset ruolo nuova persona'
);

replaceOnce(
  '    try { await axios.put(`${API}/calendar/resources/${resource.id}`, { name: next.name, color: next.color, linked_user_id: next.linked_user_id, sort_order: next.sort_order }); }',
  '    try { await axios.put(`${API}/calendar/resources/${resource.id}`, { name: next.name, color: next.color, role: next.role, linked_user_id: next.linked_user_id, sort_order: next.sort_order }); }',
  'salvataggio ruolo persona'
);

replaceOnce(
  '<div className="grid lg:grid-cols-2 gap-4">\n        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Persone / calendari</div><div className="flex flex-wrap gap-2">{resources.map((resource) => { const active = selectedResources.includes(resource.id); return <button type="button" key={resource.id} onClick={() => toggleResource(resource.id)} className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}><span className="r51-resource-dot" style={{ background: resource.color || "#64748b" }} />{resource.name}</button>; })}</div></div>\n        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Tipologia</div><div className="flex flex-wrap gap-2">{(configLists.calendar_categories || []).map((category) => { const active = selectedCategories.includes(category); return <button type="button" key={category} onClick={() => toggleCategory(category)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}>{category}</button>; })}</div></div>\n      </div>',
  '<div className="grid xl:grid-cols-3 gap-4">\n        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Persone / calendari</div><div className="flex flex-wrap gap-2">{resources.map((resource) => { const active = selectedResources.includes(resource.id); return <button type="button" key={resource.id} onClick={() => toggleResource(resource.id)} className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}><span className="r51-resource-dot" style={{ background: resource.color || "#64748b" }} /><span>{resource.name}</span>{resource.role && <span className="text-[10px] text-slate-400">· {resource.role}</span>}</button>; })}</div></div>\n        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Ruolo operativo</div><div className="flex flex-wrap gap-2">{PERSON_ROLES.map((role) => { const active = selectedRoles.includes(role); return <button type="button" key={role} onClick={() => toggleRole(role)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}>{role}</button>; })}</div></div>\n        <div><div className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Tipologia</div><div className="flex flex-wrap gap-2">{(configLists.calendar_categories || []).map((category) => { const active = selectedCategories.includes(category); return <button type="button" key={category} onClick={() => toggleCategory(category)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${active ? "border-slate-500 bg-slate-100 text-slate-900" : "border-slate-200 bg-white text-slate-600"}`}>{category}</button>; })}</div></div>\n      </div>',
  'pannello filtro ruolo'
);

replaceOnce(
  '<div><Label>Persona / calendario</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={(editor.resource_ids || [])[0] || ""} onChange={(e) => setEditor((p) => ({ ...p, resource_ids: e.target.value ? [e.target.value] : [] }))}><option value="">Non assegnato</option>{resources.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>',
  '<div><Label>Persona / calendario</Label><select className="mt-1 h-10 w-full border bg-white px-3" value={(editor.resource_ids || [])[0] || ""} onChange={(e) => setEditor((p) => ({ ...p, resource_ids: e.target.value ? [e.target.value] : [] }))}><option value="">Non assegnato</option>{resources.map((r) => <option key={r.id} value={r.id}>{r.name}{r.role ? ` · ${r.role}` : ""}</option>)}</select></div>',
  'ruolo nella scelta persona'
);

replaceOnce(
  'className="grid grid-cols-[46px_minmax(0,1fr)_42px] gap-2 items-center rounded-xl border border-slate-200 p-2.5"',
  'className="grid sm:grid-cols-[46px_minmax(0,1fr)_180px_42px] gap-2 items-center rounded-xl border border-slate-200 p-2.5"',
  'griglia persona'
);

replaceOnce(
  '<Input value={resource.name || ""} onChange={(e) => setResources((prev) => prev.map((x) => x.id === resource.id ? { ...x, name: e.target.value } : x))} onBlur={() => updateResource(resource, { name: resources.find((x) => x.id === resource.id)?.name || resource.name })} />',
  '<Input value={resource.name || ""} onChange={(e) => setResources((prev) => prev.map((x) => x.id === resource.id ? { ...x, name: e.target.value } : x))} onBlur={() => updateResource(resource, { name: resources.find((x) => x.id === resource.id)?.name || resource.name })} />\n            <select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm" value={resource.role || "Tecnico"} onChange={(e) => updateResource(resource, { role: e.target.value })} aria-label={`Ruolo di ${resource.name}`}>{PERSON_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
  'select ruolo persona'
);

replaceOnce(
  'className="grid sm:grid-cols-[46px_minmax(0,1fr)_auto] gap-2 items-center pt-3 border-t border-slate-100"',
  'className="grid sm:grid-cols-[46px_minmax(0,1fr)_180px_auto] gap-2 items-center pt-3 border-t border-slate-100"',
  'griglia nuova persona'
);

replaceOnce(
  '<Input value={newResource.name} onChange={(e) => setNewResource((p) => ({ ...p, name: e.target.value }))} placeholder="Nome persona / calendario" />',
  '<Input value={newResource.name} onChange={(e) => setNewResource((p) => ({ ...p, name: e.target.value }))} placeholder="Nome persona / calendario" />\n            <select className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm" value={newResource.role} onChange={(e) => setNewResource((p) => ({ ...p, role: e.target.value }))}>{PERSON_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}</select>',
  'select ruolo nuova persona'
);

fs.writeFileSync(file, s, 'utf8');
console.log('[R58] ruoli operativi persone calendario applicati.');
