import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import { toast } from "sonner";
import { Plus, Trash, FloppyDisk, CopySimple, ArrowUp, ArrowDown, Eye, EyeSlash } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { appConfirm } from "../lib/appConfirm";

const SECTION_OPTIONS = [
  ["amministrazione", "Amministrazione"],
  ["tecnico", "Tecnico"],
  ["gestione", "Gestione"],
  ["sistema", "Sistema"],
];

const NATIVE_SECTION_OPTIONS = [
  ["principale", "Principale"],
  ...SECTION_OPTIONS,
];

const LIST_DEFINITIONS = [
  ["calendar_categories", "Tipi evento calendario"],
  ["calendar_statuses", "Stati calendario"],
  ["calendar_priorities", "Priorità calendario"],
  ["client_statuses", "Stati cliente"],
  ["payment_methods", "Metodi pagamento"],
  ["order_finance_statuses", "Stati finanziaria ordini"],
  ["order_admin_statuses", "Stati amministrativi ordini"],
  ["order_logistic_statuses", "Stati logistici ordini"],
  ["order_installation_statuses", "Stati installazione ordini"],
  ["order_line_types", "Tipi riga ordine"],
  ["quote_statuses", "Stati preventivo"],
  ["job_statuses", "Stati commessa"],
  ["installation_statuses", "Stati installazione"],
  ["assistance_statuses", "Stati assistenza"],
];

const normalizeSection = (value) => value === "commerciale" ? "amministrazione" : (value || "amministrazione");
const newField = () => ({ key: `campo_${Date.now()}`, label: "Nuovo campo", type: "text", required: false, showInList: true, searchable: true, options: [] });
const empty = {
  name: "",
  section: "amministrazione",
  description: "",
  active: true,
  sort_order: 100,
  calendar_enabled: false,
  calendar_date_field: "",
  calendar_time_field: "",
  calendar_title_field: "",
  primary_field: "",
  list_density: "comfortable",
  allow_create: true,
  allow_edit: true,
  allow_delete: true,
  show_counter: true,
  visible_roles: [],
  visible_usernames: [],
  fields: [newField()],
};
const clone = (v) => JSON.parse(JSON.stringify(v));

function cleanFieldKey(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

export default function ModuleBuilderPage() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(clone(empty));
  const [editing, setEditing] = useState(null);
  const [query, setQuery] = useState("");
  const [lists, setLists] = useState({});
  const [listsOpen, setListsOpen] = useState(false);
  const [savingLists, setSavingLists] = useState(false);
  const [nativePages, setNativePages] = useState([]);
  const [nativeOpen, setNativeOpen] = useState(false);
  const [savingNative, setSavingNative] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [{ data: m }, { data: l }, { data: n }] = await Promise.all([
        axios.get(`${API}/custom/modules/all`),
        axios.get(`${API}/custom/config/lists`),
        axios.get(`${API}/custom/config/navigation`),
      ]);
      setItems((m.items || []).map((x) => ({ ...x, section: normalizeSection(x.section) })));
      setLists(l.values || {});
      setNativePages((n.items || []).map((x) => ({ ...x, section: x.section === "commerciale" ? "amministrazione" : x.section })));
    } catch (e) {
      toast.error("Impossibile caricare la configurazione", { description: e?.response?.data?.detail || e?.message });
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const saveLists = async () => {
    setSavingLists(true);
    try {
      const payload = { ...lists };
      payload.calendar_categories = (payload.calendar_categories || []).filter((x) => String(x).toLowerCase() !== "commerciale");
      const { data } = await axios.put(`${API}/custom/config/lists`, { values: payload });
      setLists(data.values || payload);
      toast.success("Liste e stati salvati");
      window.dispatchEvent(new Event("elios:config-lists-changed"));
    } catch (e) {
      toast.error("Salvataggio liste non riuscito", { description: e?.response?.data?.detail || e?.message });
    } finally {
      setSavingLists(false);
    }
  };

  const saveNative = async () => {
    setSavingNative(true);
    try {
      const payload = nativePages.map((x) => ({ ...x, section: x.section === "commerciale" ? "amministrazione" : x.section }));
      const { data } = await axios.put(`${API}/custom/config/navigation`, { items: payload });
      setNativePages(data.items || payload);
      toast.success("Menu e pagine salvati");
      window.dispatchEvent(new Event("elios:navigation-changed"));
    } catch (e) {
      toast.error("Salvataggio menu non riuscito", { description: e?.response?.data?.detail || e?.message });
    } finally {
      setSavingNative(false);
    }
  };

  const edit = (m) => {
    setEditing(m.id);
    setForm({
      ...clone(empty),
      ...clone(m),
      section: normalizeSection(m.section),
      fields: (m.fields || []).map((x) => ({ ...x })),
    });
  };

  const reset = () => {
    setEditing(null);
    setForm(clone(empty));
  };

  const patchField = (i, k, v) => setForm((p) => ({ ...p, fields: p.fields.map((f, j) => j === i ? { ...f, [k]: v } : f) }));
  const moveField = (i, dir) => setForm((p) => {
    const next = [...(p.fields || [])];
    const j = i + dir;
    if (j < 0 || j >= next.length) return p;
    [next[i], next[j]] = [next[j], next[i]];
    return { ...p, fields: next };
  });

  const validate = () => {
    if (!form.name.trim()) return "Inserisci il nome del modulo";
    if (!(form.fields || []).length) return "Inserisci almeno un campo";
    const keys = (form.fields || []).map((f) => String(f.key || "").trim()).filter(Boolean);
    if (keys.length !== form.fields.length) return "Ogni campo deve avere una chiave tecnica";
    if (new Set(keys).size !== keys.length) return "Le chiavi tecniche dei campi devono essere univoche";
    if (form.calendar_enabled && !form.calendar_date_field) return "Per mostrare il modulo nel calendario seleziona il campo data";
    return "";
  };

  const save = async () => {
    const error = validate();
    if (error) return toast.error(error);
    setBusy(true);
    try {
      const payload = { ...form, section: normalizeSection(form.section) };
      if (editing) await axios.put(`${API}/custom/modules/${editing}`, payload);
      else await axios.post(`${API}/custom/modules`, payload);
      toast.success(editing ? "Modulo aggiornato" : "Modulo creato");
      reset();
      await load();
      window.dispatchEvent(new Event("elios:custom-modules-changed"));
    } catch (e) {
      toast.error("Salvataggio non riuscito", { description: e?.response?.data?.detail || e?.message });
    } finally {
      setBusy(false);
    }
  };

  const archive = async () => {
    if (!editing) return;
    const ok = await appConfirm({ title: "Nascondi modulo", message: "Il modulo verrà tolto dal menu, ma i dati resteranno archiviati.", confirmLabel: "Nascondi", danger: true });
    if (!ok) return;
    await axios.delete(`${API}/custom/modules/${editing}`);
    toast.success("Modulo nascosto");
    reset();
    await load();
    window.dispatchEvent(new Event("elios:custom-modules-changed"));
  };

  const destroy = async () => {
    if (!editing) return;
    const ok = await appConfirm({ title: "Elimina definitivamente", message: "Questa operazione elimina il modulo e TUTTI i record contenuti. Non è annullabile.", confirmLabel: "Elimina definitivamente", danger: true });
    if (!ok) return;
    await axios.delete(`${API}/custom/modules/${editing}/permanent`);
    toast.success("Modulo e dati eliminati");
    reset();
    await load();
    window.dispatchEvent(new Event("elios:custom-modules-changed"));
  };

  const duplicate = async () => {
    if (!editing) return;
    try {
      const { data } = await axios.post(`${API}/custom/modules/${editing}/duplicate`);
      toast.success("Modulo duplicato");
      await load();
      if (data?.id) {
        setEditing(data.id);
        setForm({ ...clone(empty), ...clone(data), section: normalizeSection(data.section) });
      }
      window.dispatchEvent(new Event("elios:custom-modules-changed"));
    } catch (e) {
      toast.error("Duplicazione non riuscita", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return !q ? items : items.filter((m) => `${m.name} ${m.section} ${m.description || ""}`.toLowerCase().includes(q));
  }, [items, query]);

  return (
    <div className="max-w-[1500px] mx-auto px-3 sm:px-6 py-5 space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-3">
        <div>
          <div className="text-xs font-semibold tracking-[.16em] uppercase text-blue-600">Configuratore</div>
          <h1 className="font-display text-3xl font-bold">Costruttore gestionale</h1>
          <p className="text-slate-500 mt-1 max-w-3xl">Gestisci pagine, menu, liste operative, moduli e campi. Le modifiche salvate vengono applicate al menu e alle funzioni che leggono queste configurazioni.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setNativeOpen((v) => !v)}>{nativeOpen ? "Chiudi pagine" : "Pagine e menu"}</Button>
          <Button variant="outline" onClick={() => setListsOpen((v) => !v)}>{listsOpen ? "Chiudi liste" : "Liste e stati"}</Button>
          <Button onClick={reset}><Plus /> Nuovo modulo</Button>
        </div>
      </div>

      {nativeOpen && (
        <section className="bg-white border rounded-xl p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div><h2 className="font-bold text-lg">Pagine native e menu</h2><p className="text-sm text-slate-500">Rinomina, sposta, ordina o nascondi le pagine principali. La posizione selezionata è quella realmente usata nel menu.</p></div>
            <Button onClick={saveNative} disabled={savingNative}><FloppyDisk /> {savingNative ? "Salvataggio…" : "Salva menu"}</Button>
          </div>
          <div className="space-y-2">
            {nativePages.map((row, i) => (
              <div key={row.key} className="grid sm:grid-cols-[1.4fr_1fr_120px_110px] gap-2 items-center rounded-xl border border-slate-200 p-3">
                <div><div className="text-[10px] uppercase text-slate-400 font-bold">{row.key}</div><Input value={row.label || ""} onChange={(e) => setNativePages((p) => p.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} /></div>
                <div><Label>Sezione</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={row.section || "amministrazione"} onChange={(e) => setNativePages((p) => p.map((x, j) => j === i ? { ...x, section: e.target.value } : x))}>{NATIVE_SECTION_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><Label>Ordine</Label><Input type="number" value={row.sort_order ?? 100} onChange={(e) => setNativePages((p) => p.map((x, j) => j === i ? { ...x, sort_order: Number(e.target.value) } : x))} /></div>
                <label className="flex items-center gap-2 text-sm font-semibold sm:pt-5"><input type="checkbox" checked={row.active !== false} onChange={(e) => setNativePages((p) => p.map((x, j) => j === i ? { ...x, active: e.target.checked } : x))} /> Visibile</label>
              </div>
            ))}
          </div>
        </section>
      )}

      {listsOpen && (
        <section className="bg-white border rounded-xl p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div><h2 className="font-bold text-lg">Liste e stati del gestionale</h2><p className="text-sm text-slate-500">Modifica le voci operative senza intervenire sul codice. Separa le voci con punto e virgola.</p></div>
            <Button onClick={saveLists} disabled={savingLists}><FloppyDisk /> {savingLists ? "Salvataggio…" : "Salva liste"}</Button>
          </div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {LIST_DEFINITIONS.map(([k, l]) => (
              <div key={k}><Label>{l}</Label><Textarea className="mt-1 min-h-24" value={(lists[k] || []).join("; ")} onChange={(e) => setLists((p) => ({ ...p, [k]: e.target.value.split(";").map((x) => x.trim()).filter(Boolean) }))} /></div>
            ))}
          </div>
        </section>
      )}

      <div className="grid lg:grid-cols-[360px_minmax(0,1fr)] gap-5">
        <aside className="bg-white border rounded-xl p-3 h-fit lg:sticky lg:top-20">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cerca modulo…" className="h-11 mb-3" />
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {filtered.map((m) => (
              <button key={m.id} onClick={() => edit(m)} className={`w-full text-left border rounded-xl p-3 transition ${editing === m.id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}>
                <div className="flex items-center justify-between gap-2"><div className="font-semibold truncate">{m.name}</div>{m.active === false ? <EyeSlash size={16} className="text-slate-400" /> : <Eye size={16} className="text-emerald-600" />}</div>
                <div className="text-xs text-slate-500 mt-1">{normalizeSection(m.section)} · {m.fields?.length || 0} campi · ordine {m.sort_order ?? 100}</div>
              </button>
            ))}
            {!filtered.length && <div className="text-sm text-slate-400 p-4 text-center">Nessun modulo.</div>}
          </div>
        </aside>

        <main className="bg-white border rounded-xl p-4 sm:p-5 space-y-5">
          <section>
            <div className="grid sm:grid-cols-2 gap-4">
              <div><Label>Nome voce *</Label><Input className="mt-1 h-12" value={form.name || ""} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} placeholder="Es. Report tecnici" /></div>
              <div><Label>Sezione menu</Label><select className="mt-1 h-12 w-full border rounded-md px-3" value={normalizeSection(form.section)} onChange={(e) => setForm((p) => ({ ...p, section: e.target.value }))}>{SECTION_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div className="sm:col-span-2"><Label>Descrizione</Label><Textarea className="mt-1" rows={2} value={form.description || ""} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} /></div>
              <div><Label>Ordine nel menu</Label><Input type="number" className="mt-1 h-12" value={form.sort_order ?? 100} onChange={(e) => setForm((p) => ({ ...p, sort_order: Number(e.target.value) }))} /></div>
              <div><Label>Densità elenco</Label><select className="mt-1 h-12 w-full border rounded-md px-3" value={form.list_density || "comfortable"} onChange={(e) => setForm((p) => ({ ...p, list_density: e.target.value }))}><option value="compact">Compatta</option><option value="comfortable">Normale</option><option value="spacious">Ampia</option></select></div>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 mt-4">
              {[["active", "Modulo attivo"], ["allow_create", "Permetti creazione"], ["allow_edit", "Permetti modifica"], ["allow_delete", "Permetti eliminazione"]].map(([k, l]) => (
                <label key={k} className="flex items-center gap-2 rounded-lg border p-3 text-sm font-semibold"><input type="checkbox" checked={form[k] !== false} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.checked }))} />{l}</label>
              ))}
            </div>

            <div className="grid sm:grid-cols-2 gap-3 mt-4">
              <div><Label>Ruoli che possono vedere il modulo</Label><Input className="mt-1" value={(form.visible_roles || []).join(", ")} onChange={(e) => setForm((p) => ({ ...p, visible_roles: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) }))} placeholder="Vuoto = tutti · es. tecnico, responsabile" /></div>
              <div><Label>Utenti specifici</Label><Input className="mt-1" value={(form.visible_usernames || []).join(", ")} onChange={(e) => setForm((p) => ({ ...p, visible_usernames: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) }))} placeholder="Vuoto = nessun limite · username separati da virgola" /></div>
            </div>
          </section>

          <section className="border rounded-xl p-4 bg-slate-50">
            <label className="flex items-center gap-2 font-semibold"><input type="checkbox" checked={!!form.calendar_enabled} onChange={(e) => setForm((p) => ({ ...p, calendar_enabled: e.target.checked }))} /> Mostra i record anche nel Calendario</label>
            {form.calendar_enabled && (
              <div className="grid sm:grid-cols-3 gap-3 mt-3">
                <div><Label>Campo data *</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={form.calendar_date_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_date_field: e.target.value }))}><option value="">Seleziona…</option>{(form.fields || []).filter((f) => f.type === "date").map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div>
                <div><Label>Campo ora</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={form.calendar_time_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_time_field: e.target.value }))}><option value="">Facoltativo</option>{(form.fields || []).filter((f) => f.type === "time").map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div>
                <div><Label>Titolo evento</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={form.calendar_title_field || ""} onChange={(e) => setForm((p) => ({ ...p, calendar_title_field: e.target.value }))}><option value="">Primo campo</option>{(form.fields || []).map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select></div>
              </div>
            )}
          </section>

          <section>
            <div className="flex items-center justify-between gap-3">
              <div><b>Campi del modulo</b><div className="text-xs text-slate-500">L'ordine qui è l'ordine usato nelle schede e negli elenchi.</div></div>
              <Button size="sm" variant="outline" onClick={() => setForm((p) => ({ ...p, fields: [...(p.fields || []), newField()] }))}><Plus /> Aggiungi campo</Button>
            </div>
            <div className="space-y-3 mt-3">
              {(form.fields || []).map((f, i) => (
                <div key={`${f.key}-${i}`} className="border rounded-xl p-3 grid xl:grid-cols-[42px_1.2fr_1fr_1.2fr_180px_44px] gap-2 items-end">
                  <div className="flex xl:flex-col gap-1"><Button type="button" variant="ghost" size="icon" disabled={i === 0} onClick={() => moveField(i, -1)}><ArrowUp /></Button><Button type="button" variant="ghost" size="icon" disabled={i === form.fields.length - 1} onClick={() => moveField(i, 1)}><ArrowDown /></Button></div>
                  <div><Label>Nome campo</Label><Input className="mt-1" value={f.label || ""} onChange={(e) => { const label = e.target.value; patchField(i, "label", label); if (String(f.key || "").startsWith("campo_")) patchField(i, "key", cleanFieldKey(label) || f.key); }} /></div>
                  <div><Label>Tipo</Label><select className="mt-1 h-10 w-full border rounded-md px-2" value={f.type || "text"} onChange={(e) => patchField(i, "type", e.target.value)}><option value="text">Testo</option><option value="textarea">Testo lungo</option><option value="number">Numero</option><option value="currency">Euro</option><option value="date">Data</option><option value="time">Ora</option><option value="checkbox">Sì/No</option><option value="select">Tendina</option><option value="email">Email</option><option value="phone">Telefono</option><option value="url">Link</option><option value="file">Documento/File</option></select></div>
                  <div>{f.type === "select" ? <><Label>Opzioni (separate da ;)</Label><Input className="mt-1" value={(f.options || []).join(";")} onChange={(e) => patchField(i, "options", e.target.value.split(";").map((x) => x.trim()).filter(Boolean))} /></> : <><Label>Chiave tecnica</Label><Input className="mt-1 font-mono text-xs" value={f.key || ""} onChange={(e) => patchField(i, "key", e.target.value.replace(/[^a-zA-Z0-9_]/g, "_"))} /></>}</div>
                  <div className="grid grid-cols-1 gap-1 text-xs"><label><input type="checkbox" checked={!!f.required} onChange={(e) => patchField(i, "required", e.target.checked)} /> Obbligatorio</label><label><input type="checkbox" checked={f.showInList !== false} onChange={(e) => patchField(i, "showInList", e.target.checked)} /> In elenco</label><label><input type="checkbox" checked={f.searchable !== false} onChange={(e) => patchField(i, "searchable", e.target.checked)} /> Ricercabile</label></div>
                  <Button variant="ghost" size="icon" className="text-red-600" onClick={() => setForm((p) => ({ ...p, fields: p.fields.filter((_, j) => j !== i) }))}><Trash /></Button>
                </div>
              ))}
            </div>
          </section>

          <div className="flex flex-col-reverse sm:flex-row justify-between gap-3 pt-2 border-t">
            <div className="flex flex-wrap gap-2">{editing && <><Button variant="outline" onClick={duplicate}><CopySimple /> Duplica</Button><Button variant="outline" className="text-amber-700 border-amber-200" onClick={archive}><EyeSlash /> Nascondi</Button><Button variant="outline" className="text-red-700 border-red-200" onClick={destroy}><Trash /> Elimina definitivamente</Button></>}</div>
            <div className="flex gap-2"><Button variant="outline" onClick={reset}>Annulla</Button><Button onClick={save} disabled={busy}><FloppyDisk /> {busy ? "Salvataggio…" : editing ? "Salva modifiche" : "Crea modulo"}</Button></div>
          </div>
        </main>
      </div>
    </div>
  );
}
