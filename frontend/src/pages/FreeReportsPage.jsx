import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plus, FloppyDisk, Trash, PencilSimple, X } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";

const emptyReport = () => ({
  id: null,
  title: "",
  report_date: new Date().toISOString().slice(0, 10),
  technician: "",
  notes: "",
  fields: [{ label: "", value: "" }],
});

export default function FreeReportsPage() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(emptyReport());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/free-reports`);
      setItems(data.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Impossibile caricare i report");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((r) => [
      r.title, r.report_date, r.technician, r.notes,
      ...(r.fields || []).flatMap((f) => [f.label, f.value]),
    ].some((v) => String(v || "").toLowerCase().includes(q)));
  }, [items, search]);

  const setField = (idx, key, value) => {
    setForm((prev) => {
      const fields = [...(prev.fields || [])];
      fields[idx] = { ...fields[idx], [key]: value };
      return { ...prev, fields };
    });
  };

  const addField = () => setForm((p) => ({ ...p, fields: [...(p.fields || []), { label: "", value: "" }] }));
  const removeField = (idx) => setForm((p) => ({ ...p, fields: (p.fields || []).filter((_, i) => i !== idx) }));

  const save = async () => {
    if (!form.title.trim()) return toast.error("Inserisci un titolo per il report");
    const payload = {
      title: form.title.trim(),
      report_date: form.report_date || "",
      technician: form.technician || "",
      notes: form.notes || "",
      fields: (form.fields || []).filter((f) => f.label.trim()).map((f) => ({ label: f.label.trim(), value: f.value || "" })),
    };
    setSaving(true);
    try {
      if (form.id) await axios.put(`${API}/free-reports/${form.id}`, payload);
      else await axios.post(`${API}/free-reports`, payload);
      toast.success(form.id ? "Report aggiornato" : "Report salvato");
      setForm(emptyReport());
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Errore nel salvataggio del report");
    } finally {
      setSaving(false);
    }
  };

  const edit = (r) => setForm({
    id: r.id,
    title: r.title || "",
    report_date: r.report_date || "",
    technician: r.technician || "",
    notes: r.notes || "",
    fields: r.fields?.length ? r.fields.map((f) => ({ label: f.label || "", value: f.value || "" })) : [{ label: "", value: "" }],
  });

  const remove = async (r) => {
    if (!window.confirm(`Eliminare il report “${r.title}”?`)) return;
    try {
      await axios.delete(`${API}/free-reports/${r.id}`);
      if (form.id === r.id) setForm(emptyReport());
      toast.success("Report eliminato");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Impossibile eliminare il report");
    }
  };

  return (
    <div className="space-y-6" data-testid="free-reports-page">
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-6">
        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-200 flex flex-col md:flex-row md:items-center gap-3 justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Report liberi</h2>
              <p className="text-sm text-slate-500 mt-1">Report tecnici indipendenti, senza cliente, commessa o installazione obbligatori.</p>
            </div>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cerca nei report..."
              className="h-10 px-3 rounded-lg border border-slate-300 bg-white text-sm min-w-[220px]"
            />
          </div>
          <div className="divide-y divide-slate-100">
            {loading && <div className="p-6 text-sm text-slate-500">Caricamento...</div>}
            {!loading && filtered.length === 0 && <div className="p-6 text-sm text-slate-500">Nessun report presente.</div>}
            {filtered.map((r) => (
              <div key={r.id} className="p-5 hover:bg-slate-50/70">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 truncate">{r.title}</div>
                    <div className="text-xs text-slate-500 mt-1">{r.report_date || "Senza data"}{r.technician ? ` · ${r.technician}` : ""}</div>
                    {r.fields?.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                        {r.fields.slice(0, 6).map((f, i) => (
                          <div key={i} className="text-sm"><span className="font-medium text-slate-600">{f.label}:</span> <span className="text-slate-800">{f.value || "—"}</span></div>
                        ))}
                      </div>
                    )}
                    {r.notes && <div className="mt-3 text-sm text-slate-600 whitespace-pre-wrap line-clamp-3">{r.notes}</div>}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => edit(r)} className="p-2 rounded-lg hover:bg-slate-200" title="Modifica"><PencilSimple size={18} /></button>
                    <button onClick={() => remove(r)} className="p-2 rounded-lg hover:bg-red-50 text-red-600" title="Elimina"><Trash size={18} /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm p-5 h-fit xl:sticky xl:top-5">
          <div className="flex items-center justify-between gap-3 mb-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{form.id ? "Modifica report" : "Nuovo report"}</h2>
              <p className="text-xs text-slate-500 mt-1">Aggiungi tutti i campi che ti servono.</p>
            </div>
            {form.id && <button onClick={() => setForm(emptyReport())} className="p-2 rounded-lg hover:bg-slate-100" title="Chiudi modifica"><X size={18} /></button>}
          </div>

          <div className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">Titolo report
              <input value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-300" placeholder="Es. Verifica impianto / Attività interna" />
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block text-sm font-medium text-slate-700">Data
                <input type="date" value={form.report_date} onChange={(e) => setForm((p) => ({ ...p, report_date: e.target.value }))} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-300" />
              </label>
              <label className="block text-sm font-medium text-slate-700">Tecnico
                <input value={form.technician} onChange={(e) => setForm((p) => ({ ...p, technician: e.target.value }))} className="mt-1 w-full h-10 px-3 rounded-lg border border-slate-300" placeholder="Automatico se vuoto" />
              </label>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">Campi liberi</span>
                <button type="button" onClick={addField} className="inline-flex items-center gap-1 text-sm font-medium text-slate-700 hover:text-slate-900"><Plus size={16} /> Aggiungi campo</button>
              </div>
              <div className="space-y-2">
                {(form.fields || []).map((f, idx) => (
                  <div key={idx} className="grid grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)_36px] gap-2 items-start">
                    <input value={f.label} onChange={(e) => setField(idx, "label", e.target.value)} className="h-10 px-3 rounded-lg border border-slate-300 text-sm" placeholder="Nome campo" />
                    <textarea value={f.value} onChange={(e) => setField(idx, "value", e.target.value)} className="min-h-10 px-3 py-2 rounded-lg border border-slate-300 text-sm resize-y" placeholder="Valore / descrizione" rows={1} />
                    <button type="button" onClick={() => removeField(idx)} className="h-10 rounded-lg hover:bg-red-50 text-red-600 flex items-center justify-center" title="Rimuovi campo"><Trash size={17} /></button>
                  </div>
                ))}
              </div>
            </div>

            <label className="block text-sm font-medium text-slate-700">Note
              <textarea value={form.notes} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} className="mt-1 w-full min-h-28 px-3 py-2 rounded-lg border border-slate-300 resize-y" placeholder="Note libere, attività svolte, osservazioni..." />
            </label>

            <div className="flex gap-2 pt-2">
              <button onClick={save} disabled={saving} className="inline-flex items-center justify-center gap-2 h-11 px-4 rounded-lg bg-slate-900 text-white font-medium hover:bg-slate-800 disabled:opacity-60 flex-1">
                <FloppyDisk size={18} /> {saving ? "Salvataggio..." : form.id ? "Aggiorna report" : "Salva report"}
              </button>
              <button onClick={() => setForm(emptyReport())} className="inline-flex items-center justify-center gap-2 h-11 px-4 rounded-lg border border-slate-300 bg-white font-medium hover:bg-slate-50"><Plus size={18} /> Nuovo</button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
