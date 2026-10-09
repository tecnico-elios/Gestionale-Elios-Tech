import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Warning, ArrowsClockwise, MagnifyingGlass, Trash, ShieldWarning, CheckCircle } from "@phosphor-icons/react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../lib/AuthContext";
import { fmtDateTime, useTz } from "../lib/tz";
import { appConfirm } from "../lib/appConfirm";

const KIND_LABEL = {
  submit_blocked_serials: "Seriale non valido",
  shipment_shortage: "Giacenza insufficiente",
  arrivo_blocked_serials: "Seriale già presente/uscito",
  tipo_gestione_missing: "Tipo Gestione mancante",
};

export default function AnomaliePage() {
  const { isAdmin } = useAuth();
  useTz();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.get(`${API}/anomalie`, { params: { limit: 200 } });
      setItems(data.items || []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Errore lettura anomalie");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const deleteOne = async (a) => {
    if (!isAdmin) return;
    if (!(await appConfirm({ title: "Elimina anomalia", message: `Eliminare l’anomalia “${a.kind}”?`, confirmLabel: "Elimina", danger: true }))) return;
    try {
      await axios.delete(`${API}/admin/anomalie/${a.id}`);
      setItems((prev) => prev.filter((x) => x.id !== a.id));
      toast.success("Anomalia eliminata");
    } catch (e) {
      toast.error("Errore", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const clearAll = async () => {
    if (!isAdmin) return;
    if (!(await appConfirm({ title: "Elimina anomalie", message: `Eliminare tutte le ${items.length} anomalie?`, confirmLabel: "Elimina tutte", danger: true }))) return;
    try {
      const { data } = await axios.delete(`${API}/admin/anomalie`);
      toast.success(`${data.deleted} anomalie eliminate`);
      setItems([]);
    } catch (e) {
      toast.error("Errore", { description: e?.response?.data?.detail || e?.message });
    }
  };

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return items;
    return items.filter((it) =>
      (it.kind || "").toLowerCase().includes(query) ||
      (it.description || "").toLowerCase().includes(query) ||
      (it.operator || "").toLowerCase().includes(query) ||
      (it.product || "").toLowerCase().includes(query) ||
      (it.serial_or_code || "").toLowerCase().includes(query)
    );
  }, [items, q]);

  return (
    <div className="r52-anomalies-workspace" data-testid="anomalie-page">
      <div className="r52-commandbar">
        <div>
          <div className="r52-commandbar-title">Registro anomalie</div>
          <div className="r52-commandbar-subtitle">Eventi bloccanti, seriali non validi e situazioni da verificare.</div>
        </div>
        <div className="r52-commandbar-actions">
          <div className={`r52-anomaly-summary ${items.length ? "has-items" : "is-clear"}`}>
            {items.length ? <ShieldWarning size={16} weight="fill" /> : <CheckCircle size={16} weight="fill" />}
            <span>{items.length ? `${items.length} anomal${items.length === 1 ? "ia" : "ie"}` : "Nessuna anomalia"}</span>
          </div>
          <Button variant="outline" onClick={load} disabled={loading} className="r52-outline-button" data-testid="anomalie-refresh">
            <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} /> Aggiorna
          </Button>
          {isAdmin && items.length > 0 && (
            <Button variant="outline" onClick={clearAll} className="border-red-300 text-red-600 hover:bg-red-50" data-testid="anomalie-clear-all">
              <Trash size={16} /> Elimina tutte
            </Button>
          )}
        </div>
      </div>

      <section className="r52-panel r52-panel-flush">
        <div className="r52-anomalies-filterbar">
          <div className="relative flex-1 min-w-[220px] max-w-xl">
            <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cerca tipo, operatore, prodotto o seriale…" className="pl-10 h-11" data-testid="anomalie-search" />
          </div>
          <span className="r52-count-pill">{filtered.length}</span>
        </div>

        {error && <div className="r52-alert r52-alert-danger m-4">{error}</div>}

        {loading && !items.length ? (
          <div className="r52-empty-state">Caricamento anomalie…</div>
        ) : filtered.length === 0 ? (
          <div className="r52-empty-state"><CheckCircle size={32} weight="fill" className="text-emerald-500" /><strong>Nessuna anomalia registrata</strong><span>Il registro non contiene eventi corrispondenti alla ricerca.</span></div>
        ) : (
          <div className="overflow-x-auto">
            <table data-testid="anomalie-table">
              <thead><tr><th>Data/Ora</th><th>Tipo</th><th>Operatore</th><th>Prodotto / seriale</th><th>Descrizione</th>{isAdmin && <th className="w-12">Azioni</th>}</tr></thead>
              <tbody>
                {filtered.map((a, idx) => (
                  <tr key={a.id || idx} data-testid={`anom-row-${idx}`}>
                    <td className="font-mono-tight text-xs whitespace-nowrap">{fmtDateTime(a.created_at)}</td>
                    <td><Badge variant="outline" className="border-amber-300 text-amber-800 bg-amber-50"><Warning size={12} className="mr-1" />{KIND_LABEL[a.kind] || a.kind}</Badge></td>
                    <td>{a.operator || "—"}</td>
                    <td className="font-mono-tight text-xs">{a.product || "—"}{a.serial_or_code ? ` · ${a.serial_or_code}` : ""}</td>
                    <td className="max-w-md text-slate-600">{a.description}</td>
                    {isAdmin && <td><Button variant="ghost" size="icon" onClick={() => deleteOne(a)} className="h-8 w-8 text-red-600 hover:bg-red-50" data-testid={`anom-delete-${idx}`} aria-label="Elimina anomalia"><Trash size={14} /></Button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}