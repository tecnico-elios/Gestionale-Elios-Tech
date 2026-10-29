import { formatDateIT } from "../lib/dateFmt";
import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plus, MagnifyingGlass, PencilSimple, Trash, FileText, Archive, ArrowCounterClockwise } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { useAuth } from "../lib/AuthContext";
import RecordDocuments from "../components/RecordDocuments";
import InstallationWeather from "../components/InstallationWeather";
import { appConfirm } from "../lib/appConfirm";




const MODULE_BY_RESOURCE = {
  lead: "lead", clienti: "clienti", contatti: "contatti", sedi: "sedi",
  sopralluoghi: "sopralluoghi", preventivi: "preventivi", "ordini-clienti": "ordini_clienti",
  installazioni: "installazioni", assistenza: "assistenza",
};
function optionLabel(item, cfg = {}) {
  if (!item) return "—";
  if (typeof cfg.lookupLabel === "function") return cfg.lookupLabel(item);
  if (Array.isArray(cfg.lookupLabelKeys)) {
    const joined = cfg.lookupLabelKeys.map((k) => item?.[k]).filter(Boolean).join(" · ");
    if (joined) return joined;
  }
  return item.ragione_sociale || item.nome || item.numero || item.number || item.id || "—";
}

function errorText(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return err?.message || "Errore imprevisto";
}

function lookupKey(cfg = {}) {
  return cfg.lookupKey || cfg.lookupResource || cfg.lookupEndpoint || null;
}

function lookupUrl(cfg = {}) {
  if (cfg.lookupEndpoint) return `${API}/${cfg.lookupEndpoint}`;
  if (cfg.lookupResource) return `${API}/crm/${cfg.lookupResource}`;
  return null;
}

export default function RegistryPage({ resource, title, subtitle, fields, columns, rowActions = null, newLabel = "Nuovo" }) {
  const { hasPermission, isAdmin } = useAuth();
  const module = MODULE_BY_RESOURCE[resource] || resource;
  const canCreate = hasPermission(module, "create");
  const canEdit = hasPermission(module, "edit");
  const canDelete = hasPermission(module, "delete") && (resource !== "clienti" || isAdmin);
  const [items, setItems] = useState([]);
  const [lookups, setLookups] = useState({});
  const [lookupSearch, setLookupSearch] = useState({});
  const [lookupOpen, setLookupOpen] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [siteCreate, setSiteCreate] = useState({ open: false, fieldKey: "", clienteId: "" });
  const [siteDraft, setSiteDraft] = useState({ nome: "Sede installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" });
  const [siteSaving, setSiteSaving] = useState(false);
  const [clientCreate, setClientCreate] = useState({ open: false, fieldKey: "" });
  const [clientDraft, setClientDraft] = useState({ tipo: "Azienda", ragione_sociale: "", telefono: "", email: "", indirizzo: "", cap: "", comune: "", provincia: "" });
  const [clientSaving, setClientSaving] = useState(false);
  const [documentsTarget, setDocumentsTarget] = useState(null);
  const [clientView, setClientView] = useState("active");

  const empty = useMemo(
    () => Object.fromEntries(fields.map((f) => [f.key, f.default ?? (f.type === "checkbox" ? false : "")])),
    [fields]
  );

  const lookupConfigs = useMemo(() => {
    const map = new Map();
    [...fields, ...columns].forEach((cfg) => {
      const key = lookupKey(cfg);
      const url = lookupUrl(cfg);
      if (key && url && !map.has(key)) map.set(key, { key, url });
    });
    return [...map.values()];
  }, [fields, columns]);

  const load = async () => {
    setLoading(true);
    try {
      const [main, ...related] = await Promise.all([
        axios.get(`${API}/crm/${resource}`, { params: resource === "clienti" ? { include_archived: true } : {} }),
        ...lookupConfigs.map((x) => axios.get(x.url)),
      ]);
      setItems(main.data.items || []);
      const nextLookups = {};
      lookupConfigs.forEach((cfg, i) => {
        nextLookups[cfg.key] = related[i]?.data?.items || [];
      });
      setLookups(nextLookups);
    } catch (e) {
      toast.error("Errore caricamento", { description: errorText(e) });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource]);

  const resolveLookup = (cfg, value) => {
    const keyName = lookupKey(cfg);
    if (!keyName || !value) return value || "—";
    const list = lookups[keyName] || [];
    const key = cfg.lookupValueKey || "id";
    const found = list.find((x) => String(x?.[key]) === String(value));
    return found ? optionLabel(found, cfg) : "Record non trovato";
  };

  const displayCell = (column, row) => {
    if (lookupKey(column)) return resolveLookup(column, row[column.key]);
    if (fields.some((field) => field.key === column.key && field.type === "date")) return formatDateIT(row[column.key]) || "—";
    return (row[column.key] ?? "—") || "—";
  };

  const shown = useMemo(() => {
    const needle = search.trim().toLowerCase();
    let base = items;
    if (resource === "clienti") {
      if (clientView === "active") base = base.filter((x) => !x.archived);
      if (clientView === "archived") base = base.filter((x) => !!x.archived);
    }
    if (!needle) return base;
    return base.filter((x) => {
      const raw = Object.values(x || {}).join(" ");
      const resolved = columns
        .map((c) => (lookupKey(c) ? resolveLookup(c, x[c.key]) : x[c.key]))
        .join(" ");
      return `${raw} ${resolved}`.toLowerCase().includes(needle);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, search, columns, lookups, clientView, resource]);

  const startNew = () => {
    setEditing(null);
    setForm({ ...empty });
    setLookupSearch({});
    setLookupOpen({});
    setOpen(true);
  };

  const startEdit = (x) => {
    setEditing(x.id);
    setForm({ ...empty, ...x });
    setLookupSearch({});
    setLookupOpen({});
    setOpen(true);
  };

  const changeField = (field, value) => {
    setForm((prev) => {
      const next = { ...prev, [field.key]: value };
      for (const dep of field.clearOnChange || []) next[dep] = "";

      if (lookupKey(field) && field.fillFromLookup && value) {
        const list = lookups[lookupKey(field)] || [];
        const valueKey = field.lookupValueKey || "id";
        const found = list.find((x) => String(x?.[valueKey]) === String(value));
        if (found) {
          Object.entries(field.fillFromLookup).forEach(([targetField, sourceField]) => {
            next[targetField] = found?.[sourceField] ?? "";
          });
        }
      }
      return next;
    });
  };

  const selectedLookupItem = (field) => {
    const value = form[field.key];
    if (!value) return null;
    const key = field.lookupValueKey || "id";
    return (lookups[lookupKey(field)] || []).find((x) => String(x?.[key]) === String(value)) || null;
  };

  const lookupTextValue = (field) => {
    if (Object.prototype.hasOwnProperty.call(lookupSearch, field.key)) return lookupSearch[field.key] || "";
    const selected = selectedLookupItem(field);
    if (selected) return optionLabel(selected, field);
    if (field.allowFreeText && field.freeTextTarget) return form[field.freeTextTarget] || "";
    return "";
  };

  const typeLookup = (field, text) => {
    setLookupSearch((p) => ({ ...p, [field.key]: text }));
    setLookupOpen((p) => ({ ...p, [field.key]: true }));
    setForm((prev) => {
      const next = { ...prev, [field.key]: "" };
      for (const dep of field.clearOnChange || []) next[dep] = "";
      if (field.allowFreeText && field.freeTextTarget) next[field.freeTextTarget] = text;
      return next;
    });
  };

  const chooseLookup = (field, item) => {
    const key = field.lookupValueKey || "id";
    const value = item?.[key] || "";
    changeField(field, value);
    setLookupSearch((p) => ({ ...p, [field.key]: optionLabel(item, field) }));
    setLookupOpen((p) => ({ ...p, [field.key]: false }));
    if (field.allowFreeText && field.freeTextTarget) {
      setForm((prev) => ({ ...prev, [field.freeTextTarget]: "" }));
    }
  };

  const lookupOptions = (field) => {
    let list = lookups[lookupKey(field)] || [];
    if (field.lookupFilterBy && field.dependsOn) {
      const parentValue = form[field.dependsOn];
      list = parentValue
        ? list.filter((x) => String(x?.[field.lookupFilterBy]) === String(parentValue))
        : [];
    }
    if (typeof field.lookupFilter === "function") {
      list = list.filter((x) => field.lookupFilter(x, form));
    }
    const needle = String(lookupSearch[field.key] || "").trim().toLowerCase();
    if (needle) {
      list = list.filter((x) => `${optionLabel(x, field)} ${Object.values(x || {}).join(" ")}`.toLowerCase().includes(needle));
    }
    return list;
  };

  const openClientCreate = (field) => {
    const typed = String(lookupTextValue(field) || "").trim();
    setClientDraft({ tipo: "Azienda", ragione_sociale: typed, telefono: "", email: "", indirizzo: "", cap: "", comune: "", provincia: "" });
    setClientCreate({ open: true, fieldKey: field.key });
  };

  const saveInlineClient = async () => {
    const field = fields.find((x) => x.key === clientCreate.fieldKey);
    if (!field) return;
    const name = String(clientDraft.ragione_sociale || "").trim();
    if (!name) {
      toast.error("Ragione sociale / nome cliente obbligatorio");
      return;
    }
    const norm = (v) => String(v || "").trim().toLocaleLowerCase("it-IT");
    const email = norm(clientDraft.email);
    const phone = norm(clientDraft.telefono).replace(/\s+/g, "");
    const existing = (lookups.clienti || []).find((c) => {
      const sameName = norm(optionLabel(c, field)) === norm(name);
      const sameEmail = email && norm(c.email) === email;
      const samePhone = phone && norm(c.telefono).replace(/\s+/g, "") === phone;
      return sameName || sameEmail || samePhone;
    });
    if (existing) {
      chooseLookup(field, existing);
      setClientCreate({ open: false, fieldKey: "" });
      toast.info("Cliente già presente: ho selezionato l'anagrafica esistente");
      return;
    }
    setClientSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(clientDraft).map(([k, v]) => [k, typeof v === "string" ? v.trim() : v])
      );
      const { data } = await axios.post(`${API}/crm/clienti`, payload);
      setLookups((prev) => ({ ...prev, clienti: [...(prev.clienti || []), data] }));
      changeField(field, data.id);
      setLookupSearch((prev) => ({ ...prev, [field.key]: optionLabel(data, field) }));
      if (field.allowFreeText && field.freeTextTarget) {
        setForm((prev) => ({ ...prev, [field.freeTextTarget]: "" }));
      }
      setClientCreate({ open: false, fieldKey: "" });
      toast.success("Cliente creato e selezionato");
    } catch (e) {
      toast.error("Creazione cliente non riuscita", { description: errorText(e) });
    } finally {
      setClientSaving(false);
    }
  };

  const openSiteCreate = (field) => {
    const clienteId = form[field.dependsOn || "cliente_id"] || form.cliente_id;
    if (!clienteId) {
      toast.error("Seleziona prima il cliente");
      return;
    }
    setSiteDraft({ nome: "Sede installazione", indirizzo: "", civico: "", cap: "", comune: "", provincia: "", telefono: "" });
    setSiteCreate({ open: true, fieldKey: field.key, clienteId });
  };

  const saveInlineSite = async () => {
    if (!siteDraft.nome.trim() || !siteDraft.indirizzo.trim() || !siteDraft.comune.trim()) {
      toast.error("Nome sede, indirizzo e comune sono obbligatori");
      return;
    }
    setSiteSaving(true);
    try {
      const payload = {
        cliente_id: siteCreate.clienteId,
        tipo: "Installazione",
        ...siteDraft,
      };
      const { data } = await axios.post(`${API}/crm/sedi`, payload);
      setLookups((prev) => ({ ...prev, sedi: [...(prev.sedi || []), data] }));
      setForm((prev) => ({ ...prev, [siteCreate.fieldKey]: data.id }));
      setSiteCreate({ open: false, fieldKey: "", clienteId: "" });
      toast.success("Sede creata e selezionata");
    } catch (e) {
      toast.error("Creazione sede non riuscita", { description: errorText(e) });
    } finally {
      setSiteSaving(false);
    }
  };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) await axios.put(`${API}/crm/${resource}/${editing}`, form);
      else await axios.post(`${API}/crm/${resource}`, form);
      toast.success(editing ? "Modifica salvata" : "Record creato");
      setOpen(false);
      await load();
    } catch (err) {
      toast.error("Salvataggio non riuscito", { description: errorText(err) });
    }
  };

  const remove = async (id) => {
    if (resource === "clienti") {
      try {
        const { data } = await axios.get(`${API}/crm/clienti/${id}/delete-impact`);
        if (!data.can_delete) {
          const detail = Object.entries(data.linked || {}).map(([k,v]) => `${k}: ${v}`).join(" · ");
          toast.error("Cliente con storico operativo", { description: `Non può essere eliminato definitivamente. Archivialo per mantenerne lo storico. ${detail}` });
          return;
        }
      } catch (e) {
        toast.error("Controllo cliente non riuscito", { description: errorText(e) });
        return;
      }
    }
    if (!(await appConfirm({ title: "Elimina cliente", message: "Confermi l’eliminazione definitiva? Questa operazione non è annullabile.", confirmLabel: "Elimina", danger: true }))) return;
    try {
      await axios.delete(`${API}/crm/${resource}/${id}`);
      toast.success("Eliminato definitivamente");
      await load();
    } catch (e) {
      toast.error("Eliminazione non riuscita", { description: errorText(e) });
    }
  };

  const archiveClient = async (x) => {
    if (!(await appConfirm({ title: "Archivia cliente", message: `Archiviare ${x.ragione_sociale || x.nome || "questo cliente"}?`, confirmLabel: "Archivia" }))) return;
    try {
      await axios.post(`${API}/crm/clienti/${x.id}/archive`);
      toast.success("Cliente archiviato");
      await load();
    } catch (e) { toast.error("Archiviazione non riuscita", { description: errorText(e) }); }
  };

  const restoreClient = async (x) => {
    try {
      await axios.post(`${API}/crm/clienti/${x.id}/restore`);
      toast.success("Cliente riattivato");
      await load();
    } catch (e) { toast.error("Ripristino non riuscito", { description: errorText(e) }); }
  };

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5" data-testid={`${resource}-page`}>
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-5">
        <div>
          <div className="text-xs font-semibold tracking-[.16em] uppercase text-blue-600">Gestionale Elios Tech</div>
          <h1 className="font-display text-3xl font-bold text-slate-900 mt-1">{title}</h1>
          <p className="text-slate-500 mt-1">{subtitle}</p>
        </div>
        {canCreate && (
          <Button className="h-12" onClick={startNew} data-testid={`${resource}-new-btn`}>
            <Plus size={18} /> {newLabel}
          </Button>
        )}
      </div>

      {resource === "clienti" && (
        <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1 gap-1">
          {[['active','Attivi'],['archived','Archiviati'],['all','Tutti']].map(([k,l]) => (
            <button key={k} type="button" onClick={() => setClientView(k)} className={`h-9 px-3 rounded-md text-sm font-semibold ${clientView === k ? "bg-[#1A456B] text-white" : "text-slate-600 hover:bg-slate-50"}`}>{l}</button>
          ))}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-md">
        <div className="p-3 border-b border-slate-200 flex items-center gap-2">
          <MagnifyingGlass size={18} className="text-slate-400" />
          <Input
            className="h-12 max-w-md"
            placeholder={`Cerca in ${title.toLowerCase()}...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid={`${resource}-search`}
          />
          <span className="ml-auto text-sm text-slate-500">{shown.length} record</span>
        </div>

        <div className="md:hidden divide-y divide-slate-100">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Caricamento…</div>
          ) : shown.length === 0 ? (
            <div className="p-10 text-center text-slate-500">Nessun record presente.</div>
          ) : shown.map((x) => (
            <div key={x.id} className="p-4 space-y-3">
              <div className="space-y-2">
                {columns.map((c) => (
                  <div key={c.key} className="grid grid-cols-[110px_1fr] gap-2 text-sm">
                    <span className="text-slate-500 font-medium">{c.label}</span>
                    <span className="text-slate-900 break-words">{displayCell(c, x)}</span>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                {rowActions && rowActions(x, { reload: load })}
                <Button variant="outline" className="h-11 flex-1 min-w-[130px]" onClick={() => setDocumentsTarget(x)}><FileText size={17} /> Documenti</Button>
                {resource === "clienti" && !x.archived && canEdit && <Button variant="outline" size="icon" className="h-11 w-11 text-amber-700 border-amber-200" onClick={() => archiveClient(x)} aria-label="Archivia" title="Archivia cliente"><Archive /></Button>}
                {resource === "clienti" && x.archived && canEdit && <Button variant="outline" size="icon" className="h-11 w-11 text-emerald-700 border-emerald-200" onClick={() => restoreClient(x)} aria-label="Riattiva" title="Riattiva cliente"><ArrowCounterClockwise /></Button>}
                {canEdit && !x.archived && <Button variant="outline" size="icon" className="h-11 w-11" onClick={() => startEdit(x)} aria-label="Modifica"><PencilSimple /></Button>}
                {canDelete && <Button variant="outline" size="icon" className="h-11 w-11 text-red-600 border-red-200" onClick={() => remove(x.id)} aria-label="Elimina"><Trash /></Button>}
              </div>
            </div>
          ))}
        </div>

        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                {columns.map((c) => <th key={c.key} className="text-left px-4 py-3 font-semibold">{c.label}</th>)}
                <th className="px-4 py-3 text-right">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={columns.length + 1} className="p-8 text-center text-slate-500">Caricamento…</td></tr>
              ) : shown.length === 0 ? (
                <tr><td colSpan={columns.length + 1} className="p-10 text-center text-slate-500">Nessun record presente.</td></tr>
              ) : shown.map((x) => (
                <tr key={x.id} className="border-t border-slate-100 hover:bg-slate-50/60">
                  {columns.map((c) => <td key={c.key} className="px-4 py-3">{displayCell(c, x)}</td>)}
                  <td className="px-4 py-2">
                    <div className="flex justify-end gap-1">
                      {rowActions && rowActions(x, { reload: load })}
                      <Button variant="ghost" size="icon" onClick={() => setDocumentsTarget(x)} aria-label="Documenti" title="Documenti e foto"><FileText /></Button>
                      {resource === "clienti" && !x.archived && canEdit && <Button variant="ghost" size="icon" onClick={() => archiveClient(x)} className="text-amber-700" aria-label="Archivia" title="Archivia cliente"><Archive /></Button>}
                      {resource === "clienti" && x.archived && canEdit && <Button variant="ghost" size="icon" onClick={() => restoreClient(x)} className="text-emerald-700" aria-label="Riattiva" title="Riattiva cliente"><ArrowCounterClockwise /></Button>}
                      {canEdit && !x.archived && <Button variant="ghost" size="icon" onClick={() => startEdit(x)} aria-label="Modifica"><PencilSimple /></Button>}
                      {canDelete && <Button variant="ghost" size="icon" onClick={() => remove(x.id)} className="text-red-600" aria-label="Elimina"><Trash /></Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? `Modifica ${title}` : `Nuovo ${title}`}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save}>
            <div className="grid sm:grid-cols-2 gap-4 py-3">
              {fields.map((f) => {
                const disabledByDependency = !!f.dependsOn && !form[f.dependsOn];
                const disabled = disabledByDependency || !!f.disabled;
                return (
                  <div key={f.key} className={f.full ? "sm:col-span-2" : ""}>
                    <Label>{f.label}{f.required ? " *" : ""}</Label>
                    {f.type === "checkbox" ? (
                      <label className="mt-2 min-h-12 flex items-center gap-3 rounded-md border border-slate-200 px-3 bg-white cursor-pointer">
                        <input
                          type="checkbox"
                          className="h-5 w-5"
                          checked={Boolean(form[f.key])}
                          onChange={(e) => changeField(f, e.target.checked)}
                          disabled={disabled}
                        />
                        <span className="text-sm text-slate-700">{form[f.key] ? "Sì" : "No"}</span>
                      </label>
                    ) : f.type === "textarea" ? (
                      <Textarea
                        className="mt-1"
                        rows={4}
                        value={form[f.key] || ""}
                        onChange={(e) => changeField(f, e.target.value)}
                        required={f.required}
                        disabled={disabled}
                      />
                    ) : lookupKey(f) ? (
                      <div className="relative">
                        <div className="relative mt-1">
                          <Input
                            className="h-12 pr-10"
                            placeholder={disabledByDependency ? "Seleziona prima il campo precedente" : `Scrivi o scegli ${f.label.toLowerCase()}...`}
                            value={lookupTextValue(f)}
                            onChange={(e) => typeLookup(f, e.target.value)}
                            onFocus={() => !disabled && setLookupOpen((p) => ({ ...p, [f.key]: true }))}
                            onBlur={() => setTimeout(() => setLookupOpen((p) => ({ ...p, [f.key]: false })), 160)}
                            required={f.required && !f.allowFreeText}
                            disabled={disabled}
                            autoComplete="off"
                          />
                          <button type="button" tabIndex={-1} disabled={disabled}
                            onMouseDown={(e)=>e.preventDefault()}
                            onClick={() => setLookupOpen((p) => ({ ...p, [f.key]: !p[f.key] }))}
                            className="absolute right-1 top-1 h-10 w-9 rounded-md text-slate-500 hover:bg-slate-100 disabled:opacity-40">⌄</button>
                        </div>
                        {lookupOpen[f.key] && !disabled && (
                          <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-xl max-h-60 overflow-auto">
                            {lookupOptions(f).length ? lookupOptions(f).map((o) => {
                              const key = f.lookupValueKey || "id";
                              return <button type="button" key={o[key]} onMouseDown={(e)=>e.preventDefault()} onClick={()=>chooseLookup(f,o)} className="block w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b border-slate-50 last:border-0">
                                <div className="font-semibold text-sm text-slate-900">{optionLabel(o,f)}</div>
                              </button>;
                            }) : <div className="px-3 py-3 text-sm text-slate-500">{f.allowFreeText && lookupTextValue(f) ? `Nessun cliente esistente per “${lookupTextValue(f)}”.` : "Nessun risultato"}</div>}
                            {f.inlineCreateClient && lookupTextValue(f).trim() && !form[f.key] && (
                              <button type="button" onMouseDown={(e)=>e.preventDefault()} onClick={() => openClientCreate(f)} className="block w-full text-left px-3 py-3 font-semibold text-blue-700 hover:bg-blue-50 border-t border-slate-100">
                                + Aggiungi nuovo cliente
                              </button>
                            )}
                          </div>
                        )}
                        {f.allowFreeText && !form[f.key] && lookupTextValue(f) && <div className="text-xs text-amber-700 mt-1">Puoi lasciarlo come prospect oppure usare “Aggiungi nuovo cliente” per creare subito l’anagrafica e la sede.</div>}
                        {f.inlineCreateSite && !disabledByDependency && (
                          <div className="mt-2 flex items-center gap-2 flex-wrap">
                            {lookupOptions(f).length === 0 && (
                              <span className="text-xs text-amber-700">Nessuna sede presente per questo cliente.</span>
                            )}
                            <Button type="button" variant="outline" size="sm" onClick={() => openSiteCreate(f)}>
                              + Crea sede di installazione
                            </Button>
                          </div>
                        )}
                      </div>
                    ) : f.options ? (
                      <select
                        className="mt-1 flex h-12 w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-500"
                        value={form[f.key] || ""}
                        onChange={(e) => changeField(f, e.target.value)}
                        required={f.required}
                        disabled={disabled}
                      >
                        <option value="">Seleziona...</option>
                        {form[f.key] && !f.options.some((o) => String(o) === String(form[f.key])) && (
                          <option value={form[f.key]}>{form[f.key]} (storico)</option>
                        )}
                        {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <Input
                        className="mt-1 h-12"
                        type={f.type || "text"}
                        value={form[f.key] || ""}
                        onChange={(e) => changeField(f, e.target.value)}
                        required={f.required}
                        disabled={disabled}
                      />
                    )}
                    {f.help && <p className="text-xs text-slate-500 mt-1">{f.help}</p>}
                  </div>
                );
              })}
            </div>
            {resource === "installazioni" && (() => {
              const selectedSite = (lookups.sedi || []).find((x) => String(x.id) === String(form.sede_id));
              return <div className="mb-4"><InstallationWeather date={form.data} site={selectedSite}/></div>;
            })()}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annulla</Button>
              <Button type="submit">Salva</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <RecordDocuments
        open={!!documentsTarget}
        onOpenChange={(v) => !v && setDocumentsTarget(null)}
        resource={resource}
        recordId={documentsTarget?.id}
        module={module}
        title={`Documenti · ${title}`}
      />

      <Dialog open={clientCreate.open} onOpenChange={(v) => setClientCreate((prev) => ({ ...prev, open: v }))}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Nuovo cliente</DialogTitle></DialogHeader>
          <div className="grid sm:grid-cols-2 gap-4 py-2">
            <div>
              <Label>Tipo</Label>
              <select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={clientDraft.tipo} onChange={(e) => setClientDraft((x) => ({ ...x, tipo: e.target.value }))}>
                <option value="Azienda">Azienda</option><option value="Privato">Privato</option>
              </select>
            </div>
            <div>
              <Label>Ragione sociale / Nome cliente *</Label>
              <Input className="mt-1 h-12" value={clientDraft.ragione_sociale} onChange={(e) => setClientDraft((x) => ({ ...x, ragione_sociale: e.target.value }))} />
            </div>
            <div><Label>Telefono</Label><Input className="mt-1 h-12" value={clientDraft.telefono} onChange={(e) => setClientDraft((x) => ({ ...x, telefono: e.target.value }))} /></div>
            <div><Label>Email</Label><Input type="email" className="mt-1 h-12" value={clientDraft.email} onChange={(e) => setClientDraft((x) => ({ ...x, email: e.target.value }))} /></div>
            <div className="sm:col-span-2"><Label>Indirizzo</Label><Input className="mt-1 h-12" value={clientDraft.indirizzo} onChange={(e) => setClientDraft((x) => ({ ...x, indirizzo: e.target.value }))} /></div>
            <div><Label>CAP</Label><Input className="mt-1 h-12" value={clientDraft.cap} onChange={(e) => setClientDraft((x) => ({ ...x, cap: e.target.value }))} /></div>
            <div><Label>Comune</Label><Input className="mt-1 h-12" value={clientDraft.comune} onChange={(e) => setClientDraft((x) => ({ ...x, comune: e.target.value }))} /></div>
            <div><Label>Provincia</Label><Input className="mt-1 h-12" value={clientDraft.provincia} onChange={(e) => setClientDraft((x) => ({ ...x, provincia: e.target.value }))} /></div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setClientCreate({ open: false, fieldKey: "" })}>Annulla</Button>
            <Button type="button" onClick={saveInlineClient} disabled={clientSaving}>{clientSaving ? "Salvataggio…" : "Crea e seleziona"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={siteCreate.open} onOpenChange={(v) => setSiteCreate((prev) => ({ ...prev, open: v }))}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Nuova sede di installazione</DialogTitle>
          </DialogHeader>
          <div className="grid sm:grid-cols-2 gap-4 py-2">
            <div className="sm:col-span-2">
              <Label>Nome sede *</Label>
              <Input className="mt-1 h-12" value={siteDraft.nome} onChange={(e) => setSiteDraft((x) => ({ ...x, nome: e.target.value }))} />
            </div>
            <div>
              <Label>Indirizzo *</Label>
              <Input className="mt-1 h-12" value={siteDraft.indirizzo} onChange={(e) => setSiteDraft((x) => ({ ...x, indirizzo: e.target.value }))} />
            </div>
            <div>
              <Label>Civico</Label>
              <Input className="mt-1 h-12" value={siteDraft.civico} onChange={(e) => setSiteDraft((x) => ({ ...x, civico: e.target.value }))} />
            </div>
            <div>
              <Label>CAP</Label>
              <Input className="mt-1 h-12" value={siteDraft.cap} onChange={(e) => setSiteDraft((x) => ({ ...x, cap: e.target.value }))} />
            </div>
            <div>
              <Label>Comune *</Label>
              <Input className="mt-1 h-12" value={siteDraft.comune} onChange={(e) => setSiteDraft((x) => ({ ...x, comune: e.target.value }))} />
            </div>
            <div>
              <Label>Provincia</Label>
              <Input className="mt-1 h-12" value={siteDraft.provincia} onChange={(e) => setSiteDraft((x) => ({ ...x, provincia: e.target.value }))} />
            </div>
            <div>
              <Label>Telefono sede</Label>
              <Input className="mt-1 h-12" value={siteDraft.telefono} onChange={(e) => setSiteDraft((x) => ({ ...x, telefono: e.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSiteCreate((prev) => ({ ...prev, open: false }))}>Annulla</Button>
            <Button type="button" onClick={saveInlineSite} disabled={siteSaving}>{siteSaving ? "Salvataggio…" : "Crea e seleziona"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
