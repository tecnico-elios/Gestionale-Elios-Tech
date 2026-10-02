import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { Plus, Trash, FloppyDisk, ArrowUp, ArrowDown, ArchiveBox } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const ACTIONS = [
  ["view", "Vedi"], ["create", "Crea"], ["edit", "Modifica"], ["delete", "Elimina"], ["export", "Esporta"],
];
const newField = () => ({ key: `campo_${Date.now()}`, label: "Nuovo campo", type: "text", required: false, showInList: true, options: [] });
const empty = {
  name: "", section: "amministrazione", description: "", active: true, sort_order: 100,
  calendar_enabled: false, calendar_date_field: "", calendar_time_field: "", calendar_title_field: "",
  access_mode: "everyone", user_permissions: {}, fields: [newField()],
};

export default function ModuleBuilderPage() {
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ ...empty });
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [mods, usr] = await Promise.all([
      axios.get(`${API}/custom/modules/all`),
      axios.get(`${API}/admin/users`),
    ]);
    setItems(mods.data?.items || []);
    setUsers((usr.data?.items || []).filter((u) => u.active !== false));
  };
  useEffect(() => { load().catch(() => toast.error("Impossibile caricare il costruttore")); }, []);

  const edit = (m) => {
    setEditing(m.id);
    setForm({
      ...empty,
      ...m,
      user_permissions: { ...(m.user_permissions || {}) },
      fields: (m.fields || []).map((x) => ({ ...x })),
    });
  };
  const reset = () => { setEditing(null); setForm({ ...empty, fields: [newField()], user_permissions: {} }); };
  const patchField = (i, k, v) => setForm((p) => ({ ...p, fields: p.fields.map((f, j) => j === i ? { ...f, [k]: v } : f) }));
  const moveField = (i, delta) => setForm((p) => {
    const arr = [...(p.fields || [])]; const j = i + delta;
    if (j < 0 || j >= arr.length) return p;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    return { ...p, fields: arr };
  });

  const userKey = (u) => String(u.id || "");
  const hasUserAction = (uid, action) => (form.user_permissions?.[uid] || []).includes(action);
  const toggleUserAction = (uid, action) => setForm((p) => {
    const map = { ...(p.user_permissions || {}) };
    const set = new Set(map[uid] || []);
    if (set.has(action)) set.delete(action); else set.add(action);
    if (action !== "view" && set.has(action)) set.add("view");
    if (action === "view" && !set.has("view")) set.clear();
    map[uid] = [...set];
    return { ...p, user_permissions: map };
  });
  const toggleAllUser = (uid) => setForm((p) => {
    const map = { ...(p.user_permissions || {}) };
    const current = new Set(map[uid] || []);
    map[uid] = ACTIONS.every(([a]) => current.has(a)) ? [] : ACTIONS.map(([a]) => a);
    return { ...p, user_permissions: map };
  });

  const save = async () => {
    if (!String(form.name || "").trim()) return toast.error("Inserisci il nome");
    setBusy(true);
    try {
      const payload = { ...form, sort_order: Number(form.sort_order || 100) };
      editing ? await axios.put(`${API}/custom/modules/${editing}`, payload) : await axios.post(`${API}/custom/modules`, payload);
      toast.success("Modulo salvato");
      reset(); await load(); window.dispatchEvent(new Event("elios:custom-modules-changed"));
    } catch (e) { toast.error("Salvataggio non riuscito", { description: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const archive = async () => {
    if (!editing) return;
    setBusy(true);
    try { await axios.delete(`${API}/custom/modules/${editing}`); toast.success("Modulo archiviato"); reset(); await load(); window.dispatchEvent(new Event("elios:custom-modules-changed")); }
    catch (e) { toast.error("Operazione non riuscita", { description: e?.response?.data?.detail || e.message }); }
    finally { setBusy(false); }
  };

  const orderedItems = useMemo(() => [...items].sort((a, b) => String(a.section).localeCompare(String(b.section)) || Number(a.sort_order || 100) - Number(b.sort_order || 100) || String(a.name).localeCompare(String(b.name))), [items]);

  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5">
    <div className="mb-5"><h1 className="font-display text-3xl font-bold">Costruttore moduli</h1></div>
    <div className="grid lg:grid-cols-[360px_1fr] gap-5">
      <div className="bg-white border rounded-xl p-3 h-fit shadow-sm">
        <div className="flex justify-between items-center mb-3"><b>Moduli</b><Button size="sm" variant="outline" onClick={reset}><Plus/> Nuovo</Button></div>
        <div className="space-y-2">{orderedItems.map((m) => <button key={m.id} onClick={() => edit(m)} className={`w-full text-left border rounded-lg p-3 hover:bg-slate-50 ${editing === m.id ? "border-blue-400 bg-blue-50/50" : "border-slate-200"}`}>
          <div className="font-semibold">{m.name}</div><div className="text-xs text-slate-500 mt-1">{m.section} · {m.fields?.length || 0} campi · ordine {m.sort_order ?? 100}</div>
        </button>)}</div>
      </div>

      <div className="bg-white border rounded-xl p-4 sm:p-5 shadow-sm space-y-5">
        <div className="grid sm:grid-cols-2 gap-4">
          <div><Label>Nome voce *</Label><Input className="mt-1 h-12" value={form.name || ""} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></div>
          <div><Label>Sezione menu</Label><select className="mt-1 h-12 w-full border rounded-md px-3 bg-white" value={form.section || "amministrazione"} onChange={(e) => setForm((p) => ({ ...p, section: e.target.value }))}><option value="commerciale">Commerciale</option><option value="amministrazione">Amministrazione</option><option value="tecnico">Tecnico</option><option value="gestione">Gestione</option><option value="sistema">Sistema</option></select></div>
          <div className="sm:col-span-2"><Label>Descrizione</Label><Input className="mt-1 h-12" value={form.description || ""} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} /></div>
          <div><Label>Ordine nel menu</Label><Input type="number" className="mt-1 h-12" value={form.sort_order ?? 100} onChange={(e) => setForm((p) => ({ ...p, sort_order: e.target.value }))} /></div>
          <div className="flex items-end"><label className="h-12 flex items-center gap-2 font-medium"><input type="checkbox" checked={form.active !== false} onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))}/> Modulo attivo</label></div>
        </div>

        <div className="border rounded-lg p-4 bg-slate-50">
          <label className="flex items-center gap-2 font-semibold"><input type="checkbox" checked={!!form.calendar_enabled} onChange={(e) => setForm((p) => ({ ...p, calendar_enabled: e.target.checked }))}/> Mostra nel Calendario</label>
          {form.calendar_enabled && <div className="grid sm:grid-cols-3 gap-3 mt-3"><div><Label>Campo data</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={form.calendar_date_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_date_field: e.target.value }))}><option value="">Seleziona…</option>{(form.fields || []).filter((f) => f.type === "date").map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div><div><Label>Campo ora</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={form.calendar_time_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_time_field: e.target.value }))}><option value="">Facoltativo</option>{(form.fields || []).filter((f) => f.type === "time").map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div><div><Label>Titolo evento</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={form.calendar_title_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_title_field: e.target.value }))}><option value="">Primo campo</option>{(form.fields || []).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div></div>}
        </div>

        <div>
          <div className="flex items-center justify-between"><b>Campi</b><Button size="sm" variant="outline" onClick={() => setForm((p) => ({ ...p, fields: [...(p.fields || []), newField()] }))}><Plus/> Aggiungi campo</Button></div>
          <div className="space-y-3 mt-3">{(form.fields || []).map((f, i) => <div key={`${f.key}-${i}`} className="border rounded-lg p-3 grid md:grid-cols-[auto_1.3fr_1fr_1fr_auto] gap-2 items-end">
            <div className="flex md:flex-col gap-1"><Button type="button" variant="ghost" size="icon" onClick={() => moveField(i, -1)} disabled={i === 0}><ArrowUp/></Button><Button type="button" variant="ghost" size="icon" onClick={() => moveField(i, 1)} disabled={i === form.fields.length - 1}><ArrowDown/></Button></div>
            <div><Label>Nome campo</Label><Input className="mt-1" value={f.label || ""} onChange={(e) => { const label = e.target.value; patchField(i, "label", label); if (String(f.key || "").startsWith("campo_")) patchField(i, "key", label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || f.key); }}/></div>
            <div><Label>Tipo</Label><select className="mt-1 h-10 w-full border rounded-md px-2 bg-white" value={f.type || "text"} onChange={(e) => patchField(i, "type", e.target.value)}><option value="text">Testo</option><option value="textarea">Testo lungo</option><option value="number">Numero</option><option value="currency">Euro</option><option value="date">Data</option><option value="time">Ora</option><option value="checkbox">Sì/No</option><option value="select">Tendina</option></select></div>
            <div>{f.type === "select" ? <><Label>Opzioni (;)</Label><Input className="mt-1" value={(f.options || []).join(";")} onChange={(e) => patchField(i, "options", e.target.value.split(";").map((x) => x.trim()).filter(Boolean))}/></> : <div className="flex gap-3 h-10 items-center"><label className="text-xs"><input type="checkbox" checked={!!f.required} onChange={(e) => patchField(i, "required", e.target.checked)}/> Obbligatorio</label><label className="text-xs"><input type="checkbox" checked={f.showInList !== false} onChange={(e) => patchField(i, "showInList", e.target.checked)}/> In elenco</label></div>}</div>
            <Button variant="ghost" size="icon" className="text-red-600" onClick={() => setForm((p) => ({ ...p, fields: p.fields.filter((_, j) => j !== i) }))}><Trash/></Button>
          </div>)}</div>
        </div>

        <div className="border rounded-lg p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3"><b>Visibilità e permessi</b><select className="h-10 border rounded-md px-3 bg-white" value={form.access_mode || "everyone"} onChange={(e) => setForm((p) => ({ ...p, access_mode: e.target.value }))}><option value="everyone">Tutti gli utenti</option><option value="custom">Personalizzati per utente</option></select></div>
          {form.access_mode === "custom" && <div className="overflow-x-auto border rounded-lg"><table className="w-full min-w-[680px] text-sm"><thead className="bg-slate-50"><tr><th className="text-left p-3">Utente</th>{ACTIONS.map(([a,l]) => <th key={a} className="text-center p-3">{l}</th>)}</tr></thead><tbody>{users.map((u) => { const uid = userKey(u); return <tr key={uid} className="border-t"><td className="p-3 font-medium"><button type="button" onClick={() => toggleAllUser(uid)} className="text-left hover:text-blue-700">{u.full_name || `${u.first_name || ""} ${u.last_name || ""}`.trim() || u.username}<div className="text-xs text-slate-400 font-normal">{u.username}</div></button></td>{ACTIONS.map(([a]) => <td key={a} className="text-center p-2"><input type="checkbox" className="h-5 w-5" checked={hasUserAction(uid, a)} onChange={() => toggleUserAction(uid, a)}/></td>)}</tr>; })}</tbody></table></div>}
        </div>

        <div className="flex justify-between gap-2"><div>{editing && <Button variant="outline" className="text-red-700 border-red-200" onClick={archive} disabled={busy}><ArchiveBox/> Archivia modulo</Button>}</div><div className="flex gap-2"><Button variant="outline" onClick={reset} disabled={busy}>Annulla</Button><Button onClick={save} disabled={busy}><FloppyDisk/> {editing ? "Salva modifiche" : "Crea modulo"}</Button></div></div>
      </div>
    </div>
  </div>;
}
