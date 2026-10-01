import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "../lib/AuthContext";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { MagnifyingGlass, Package, Plus, PencilSimple, Archive, Barcode } from "@phosphor-icons/react";
import { appConfirm } from "../lib/appConfirm";


const EMPTY = {
  name: "", code: "", category: "", brand: "", unit: "pz", tipo_gestione: "a_quantita",
  low_stock_threshold: 0, location: "", supplier: "", notes: "", unit_price: "", power: "", cable: "", active: true,
};

function errText(e) {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : e?.message || "Errore";
}

export function ProductDialog({ open, onClose, product, onSaved, warehouseId, warehouseName }) {
  const [form, setForm] = useState(product ? { ...EMPTY, ...product } : { ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [serials, setSerials] = useState([]);
  const [serialsLoading, setSerialsLoading] = useState(false);
  const edit = !!product?.id;
  useEffect(() => {
    setForm(product ? { ...EMPTY, ...product } : { ...EMPTY });
    setSerials([]);
    if (open && product?.id && product?.tipo_gestione === "a_seriale") {
      setSerialsLoading(true);
      axios.get(`${API}/products/${product.id}/serials`, { params: { warehouse_id: warehouseId } })
        .then(({ data }) => setSerials(data.items || []))
        .catch((e) => toast.error("Seriali non disponibili", { description: errText(e) }))
        .finally(() => setSerialsLoading(false));
    }
  }, [open, product, warehouseId]);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const save = async (e) => {
    e.preventDefault(); setSaving(true);
    try {
      const catalogPayload = { ...form, warehouse_id: warehouseId, low_stock_threshold: 0, location: "" };
      const response = edit
        ? await axios.put(`${API}/products/${product.id}`, catalogPayload)
        : await axios.post(`${API}/products`, catalogPayload);
      const productId = product?.id || response.data?.id;
      await axios.put(`${API}/products/${productId}/warehouse-settings`, {
        warehouse_id: warehouseId,
        location: form.location || "",
        low_stock_threshold: Number(form.low_stock_threshold || 0),
      });
      toast.success(edit ? "Prodotto aggiornato" : "Prodotto creato", { description: `Impostazioni salvate per ${warehouseName}.` });
      onSaved?.(); onClose();
    } catch (e) { toast.error("Salvataggio non riuscito", { description: errText(e) }); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{edit ? "Modifica prodotto" : "Nuovo prodotto"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2"><Label>Nome prodotto *</Label><Input className="mt-1 h-12" required value={form.name} onChange={(e) => set("name", e.target.value)} /></div>
            <div><Label>Codice prodotto</Label><Input className="mt-1 h-12" value={form.code} onChange={(e) => set("code", e.target.value)} /></div>
            <div><Label>Marca</Label><Input className="mt-1 h-12" value={form.brand} onChange={(e) => set("brand", e.target.value)} /></div>
            <div><Label>Categoria</Label><Input className="mt-1 h-12" value={form.category} onChange={(e) => set("category", e.target.value)} /></div>
            <div><Label>Unità di misura *</Label><select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3" value={form.unit} onChange={(e) => set("unit", e.target.value)}><option value="pz">Pezzi (pz)</option><option value="m">Metri (m)</option></select></div>
            <div className="sm:col-span-2">
              <Label>Tipo di gestione *</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
                <button type="button" onClick={() => { set("tipo_gestione", "a_seriale"); set("unit", "pz"); }} className={`min-h-14 rounded-md border px-4 text-left ${form.tipo_gestione === "a_seriale" ? "bg-amber-50 border-amber-400" : "bg-white border-slate-300"}`}>
                  <div className="font-semibold">A seriale</div><div className="text-xs text-slate-500">Ogni pezzo viene gestito tramite numero seriale univoco.</div>
                </button>
                <button type="button" onClick={() => set("tipo_gestione", "a_quantita")} className={`min-h-14 rounded-md border px-4 text-left ${form.tipo_gestione === "a_quantita" ? "bg-slate-100 border-slate-500" : "bg-white border-slate-300"}`}>
                  <div className="font-semibold">A quantità</div><div className="text-xs text-slate-500">La giacenza viene gestita come quantità numerica.</div>
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-2">Dopo i primi movimenti il tipo di gestione non può più essere cambiato.</p>
            </div>
            <div><Label>Soglia minima · {warehouseName}</Label><Input type="number" min="0" step="0.01" className="mt-1 h-12" value={form.low_stock_threshold} onChange={(e) => set("low_stock_threshold", Number(e.target.value || 0))} /></div>
            <div><Label>Posizione · {warehouseName}</Label><Input className="mt-1 h-12" value={form.location} onChange={(e) => set("location", e.target.value)} placeholder="Es. Scaffale A3" /></div>
            <div><Label>Prezzo unitario</Label><Input type="number" min="0" step="0.01" className="mt-1 h-12" value={form.unit_price ?? ""} onChange={(e) => set("unit_price", e.target.value === "" ? "" : Number(e.target.value))} /></div>
            <div><Label>Potenza</Label><Input className="mt-1 h-12" value={form.power || ""} onChange={(e) => set("power", e.target.value)} placeholder="Es. 22 kW" /></div>
            <div><Label>Cavo</Label><Input className="mt-1 h-12" value={form.cable || ""} onChange={(e) => set("cable", e.target.value)} placeholder="Es. 5 MT" /></div>
            <div className="sm:col-span-2"><Label>Fornitore principale</Label><Input className="mt-1 h-12" value={form.supplier} onChange={(e) => set("supplier", e.target.value)} /></div>
            <div className="sm:col-span-2"><Label>Note</Label><Textarea className="mt-1" rows={4} value={form.notes} onChange={(e) => set("notes", e.target.value)} /></div>
            {edit && form.tipo_gestione === "a_seriale" && <div className="sm:col-span-2 rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3"><div><Label>Seriali disponibili · {warehouseName}</Label><p className="text-xs text-slate-500 mt-1">Seriali realmente presenti nel magazzino.</p></div><Badge variant="outline">{serials.length} seriali</Badge></div>
              {serialsLoading ? <div className="text-sm text-slate-500 mt-3">Caricamento seriali…</div> : serials.length ? <div className="mt-3 max-h-44 overflow-y-auto grid sm:grid-cols-2 gap-2">{serials.map((sn) => <div key={sn} className="font-mono text-sm bg-white border rounded px-3 py-2 flex items-center gap-2"><Barcode size={16} className="text-slate-400" />{sn}</div>)}</div> : <div className="text-sm text-slate-500 mt-3">Nessun seriale disponibile.</div>}
            </div>}
          </div>
          <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={saving}>{saving ? "Salvataggio…" : "Salva prodotto"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function InventarioPage({ warehouseId = "elios-tech", warehouseName = "Magazzino Elios Tech" }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const refresh = async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await axios.get(`${API}/inventory`, { params: { warehouse_id: warehouseId } });
      setItems(data.items || []);
    } catch (e) { setError(errText(e)); } finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, [warehouseId]); // eslint-disable-line react-hooks/exhaustive-deps
  const { hasPermission } = useAuth();
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState({ open: false, product: null });
  const canCreate = hasPermission("inventario", "create");
  const canEdit = hasPermission("inventario", "edit");
  const canDelete = hasPermission("inventario", "delete");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => [it.name, it.code, it.category, it.brand, it.location, it.supplier].some((v) => String(v || "").toLowerCase().includes(q)));
  }, [items, query]);

  const archive = async (it) => {
    if (!(await appConfirm({ title: "Disattiva prodotto", message: `Disattivare il prodotto “${it.name}”?`, confirmLabel: "Disattiva", danger: true }))) return;
    try { await axios.delete(`${API}/products/${it.id}`); toast.success("Prodotto disattivato"); await refresh(); }
    catch (e) { toast.error("Operazione non riuscita", { description: errText(e) }); }
  };

  const qtyBadge = (it) => {
    const qty = Number(it.quantity) || 0;
    const threshold = Number(it.low_stock_threshold) || 0;
    if (qty <= 0) return <Badge className="bg-red-50 text-red-700 border-red-200">Esaurito</Badge>;
    if (threshold > 0 && qty <= threshold) return <Badge className="bg-amber-50 text-amber-800 border-amber-200">Sotto scorta</Badge>;
    return <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">Disponibile</Badge>;
  };

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-4" data-testid="inventario-page">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <div className="et-eyebrow">Gestione · Database locale</div>
          <h1 className="et-page-heading text-3xl sm:text-4xl mt-1">{warehouseName}</h1>
          <p className="text-slate-500 mt-1 text-sm">{items.length} prodotti. Le giacenze di questo deposito sono separate dagli altri magazzini.</p>
        </div>
        {canCreate && <Button className="h-12" onClick={() => setDialog({ open: true, product: null })}><Plus size={18} /> Nuovo prodotto</Button>}
      </div>

      <div className="relative max-w-lg">
        <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cerca prodotto, codice, marca, categoria o posizione…" className="pl-10 h-12" autoComplete="off" />
      </div>

      {error && <div className="border border-red-200 bg-red-50 text-red-700 p-4 rounded-md text-sm">{error}</div>}
      {loading && !items.length ? <div className="text-slate-500 py-12 text-center">Caricamento magazzino…</div> : (
        <>
          <div className="md:hidden space-y-2">
            {filtered.map((it) => (
              <div key={it.id} className="bg-white border border-slate-200 rounded-md p-4 space-y-3">
                <div className="flex items-start gap-3"><Package size={20} className="text-slate-400 mt-1" /><div className="min-w-0 flex-1"><div className="font-semibold text-slate-900">{it.name}</div><div className="text-xs text-slate-500">{it.code || "Senza codice"} · {it.category || "Senza categoria"}</div></div>{qtyBadge(it)}</div>
                <div className="grid grid-cols-2 gap-2 text-sm"><div><span className="text-slate-500">Giacenza</span><div className="font-semibold">{Number(it.quantity) || 0} {it.unit || "pz"}</div></div><div><span className="text-slate-500">Gestione</span><div className="font-semibold">{it.tipo_gestione === "a_seriale" ? "A seriale" : "A quantità"}</div></div><div><span className="text-slate-500">Posizione</span><div>{it.location || "—"}</div></div><div><span className="text-slate-500">Marca</span><div>{it.brand || "—"}</div></div></div>
                {(canEdit || canDelete) && <div className="flex gap-2 pt-1">{canEdit && <Button variant="outline" className="h-11 flex-1" onClick={() => setDialog({ open: true, product: it })}><PencilSimple size={16} /> Modifica</Button>}{canDelete && <Button variant="outline" className="h-11 text-red-600 border-red-200" onClick={() => archive(it)}><Archive size={16} /> Disattiva</Button>}</div>}
              </div>
            ))}
          </div>

          <div className="hidden md:block et-card-elevated overflow-hidden">
            <div className="overflow-x-auto"><table className="et-table"><thead><tr><th>Prodotto</th><th>Codice</th><th>Categoria</th><th>Posizione</th><th className="text-right">Quantità</th><th className="text-center">Gestione</th><th>Stato</th><th className="text-right">Azioni</th></tr></thead><tbody>
              {filtered.length === 0 ? <tr><td colSpan="8" className="text-center py-10 text-slate-400">Nessun prodotto trovato.</td></tr> : filtered.map((it) => <tr key={it.id} className="hover:bg-slate-50"><td className="px-4 py-3 font-medium"><div className="flex items-center gap-2"><Package size={14} className="text-slate-400" /><div><div>{it.name}</div>{it.brand && <div className="text-xs text-slate-400">{it.brand}</div>}</div></div></td><td className="px-4 py-3 font-mono-tight text-xs text-slate-500">{it.code || "—"}</td><td className="px-4 py-3 text-slate-500">{it.category || "—"}</td><td className="px-4 py-3 text-slate-500">{it.location || "—"}</td><td className="px-4 py-3 text-right font-semibold">{Number(it.quantity) || 0} <span className="text-slate-400 text-xs font-normal">{it.unit || "pz"}</span></td><td className="px-4 py-3 text-center"><Badge variant="outline" className={it.tipo_gestione === "a_seriale" ? "border-amber-300 text-amber-800 bg-amber-50" : "border-slate-300 text-slate-600"}>{it.tipo_gestione === "a_seriale" ? "A seriale" : "A quantità"}</Badge></td><td className="px-4 py-3">{qtyBadge(it)}</td><td className="px-4 py-3"><div className="flex justify-end gap-1">{it.tipo_gestione === "a_seriale" && <Button variant="outline" size="sm" onClick={() => setDialog({ open: true, product: it })}>Seriali ({Number(it.quantity) || 0})</Button>}{canEdit && <Button variant="ghost" size="icon" onClick={() => setDialog({ open: true, product: it })}><PencilSimple /></Button>}{canDelete && <Button variant="ghost" size="icon" className="text-red-600" onClick={() => archive(it)}><Archive /></Button>}</div></td></tr>)}
            </tbody></table></div>
          </div>
        </>
      )}

      <ProductDialog open={dialog.open} product={dialog.product} warehouseId={warehouseId} warehouseName={warehouseName} onClose={() => setDialog({ open: false, product: null })} onSaved={refresh} />
    </div>
  );
}
