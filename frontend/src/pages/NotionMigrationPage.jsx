import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowClockwise, CheckCircle, Database, Eye, FloppyDisk, Plugs, WarningCircle } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { appConfirm } from "../lib/appConfirm";

const EMPTY_FORM = {
  token: "",
  inventario_ds_id: "",
  ordini_ds_id: "",
  receipts_ds_id: "",
  tracker_ds_id: "",
  verona_inventario_ds_id: "",
  verona_receipts_ds_id: "",
  verona_tracker_ds_id: "",
};

const SOURCE_FIELDS = [
  ["inventario_ds_id", "Inventario Elios Tech"],
  ["ordini_ds_id", "Clienti / Ordini"],
  ["receipts_ds_id", "Entrate / Arrivi Elios Tech"],
  ["tracker_ds_id", "Uscite / Spedizioni Elios Tech"],
  ["verona_inventario_ds_id", "Inventario Verona"],
  ["verona_receipts_ds_id", "Entrate Verona"],
  ["verona_tracker_ds_id", "Uscite Verona"],
];

function messageFromError(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((x) => x?.msg || JSON.stringify(x)).join(" · ");
  return error?.message || "Errore imprevisto";
}

function Pill({ ok, children }) {
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold ${ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-800"}`}>{ok ? <CheckCircle size={14} weight="fill" /> : <WarningCircle size={14} weight="fill" />}{children}</span>;
}

function Stat({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</div><div className="text-2xl font-black text-slate-900 mt-1">{value ?? 0}</div></div>;
}

export default function NotionMigrationPage() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [advanced, setAdvanced] = useState(false);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(null);
  const [busy, setBusy] = useState("");
  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [finalizeText, setFinalizeText] = useState("");
  const [finalizePassword, setFinalizePassword] = useState("");
  const pollRef = useRef(null);

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/admin/notion/config`);
      setCfg(data);
      setForm((prev) => ({
        ...prev,
        token: "",
        ...Object.fromEntries(SOURCE_FIELDS.map(([key]) => [key, data?.[key] || ""])),
      }));
      if (data?.import_ready) {
        try {
          const status = await axios.get(`${API}/admin/notion/import-status`);
          setProgress(status.data || null);
        } catch (_) {}
      }
    } catch (e) {
      toast.error("Impossibile leggere la configurazione Notion", { description: messageFromError(e) });
    }
  };

  useEffect(() => {
    load();
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const saveConfig = async () => {
    setBusy("save");
    try {
      const payload = { ...form };
      const { data } = await axios.put(`${API}/admin/notion/config`, payload);
      setCfg(data);
      setForm((p) => ({ ...p, token: "" }));
      setPreview(null);
      toast.success("Configurazione Notion salvata");
    } catch (e) {
      toast.error("Salvataggio non riuscito", { description: messageFromError(e) });
    } finally { setBusy(""); }
  };

  const testConnection = async () => {
    setBusy("test");
    try {
      const { data } = await axios.post(`${API}/admin/notion/test`);
      toast.success(data.message || "Connessione Notion funzionante");
    } catch (e) {
      toast.error("Connessione Notion non valida", { description: messageFromError(e) });
    } finally { setBusy(""); }
  };

  const makePreview = async () => {
    setBusy("preview");
    setResult(null);
    try {
      const { data } = await axios.get(`${API}/admin/notion/import-preview`);
      setPreview(data);
      await load();
      const meaningful = (data.inventory_count || 0) + (data.orders_count || 0) + (data.all_sources_count || 0);
      if (meaningful > 0) toast.success("Anteprima completata: fonti Notion lette correttamente");
      else toast.warning("Connessione valida, ma non risultano dati importabili nelle fonti rilevate");
    } catch (e) {
      toast.error("Anteprima importazione fallita", { description: messageFromError(e) });
    } finally { setBusy(""); }
  };

  const readProgress = async () => {
    try {
      const { data } = await axios.get(`${API}/admin/notion/import-status`);
      setProgress(data || null);
      return data;
    } catch (_) { return null; }
  };

  const startPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(readProgress, 1200);
  };

  const stopPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const importAll = async () => {
    if (!preview) return toast.error("Esegui prima l'anteprima completa");
    if (!(preview.all_sources_count || preview.inventory_count || preview.orders_count)) return toast.error("Nessuna fonte valida rilevata: controlla token e mappature");
    const ok = await appConfirm({
      title: "Importazione completa da Notion",
      message: `Copiare nel gestionale tutti i dati rilevati? Fonti: ${preview.all_sources_count ?? 0}, prodotti Elios: ${preview.inventory_count ?? 0}, ordini: ${preview.orders_count ?? 0}. Notion resterà in sola lettura e l'operazione è rilanciabile senza duplicare i record già riconosciuti.`,
      confirmLabel: "Importa tutto",
    });
    if (!ok) return;
    setBusy("import");
    setResult(null);
    setProgress({ state: "running", phase: "Avvio", percent: 1, processed: 0, message: "Preparazione importazione" });
    startPolling();
    try {
      const { data } = await axios.post(`${API}/admin/notion/import-all`, {}, { timeout: 30 * 60 * 1000 });
      setResult(data);
      await readProgress();
      await load();
      window.dispatchEvent(new Event("elios:custom-modules-changed"));
      window.dispatchEvent(new Event("elios:navigation-changed"));
      window.dispatchEvent(new Event("elios:refresh-dashboard"));
      toast.success("Importazione completa terminata");
    } catch (e) {
      setProgress((p) => ({ ...(p || {}), state: "error", message: messageFromError(e) }));
      toast.error("Importazione completa fallita", { description: messageFromError(e) });
    } finally {
      stopPolling();
      setBusy("");
    }
  };

  const finalize = async () => {
    if (finalizeText.trim().toUpperCase() !== "CONFERMA MIGRAZIONE" || !finalizePassword) return;
    setBusy("finalize");
    try {
      const { data } = await axios.post(`${API}/admin/notion/finalize`, { confirmation_text: finalizeText.trim(), admin_password: finalizePassword });
      toast.success(data.message || "Migrazione confermata");
      setFinalizeOpen(false);
      setFinalizeText("");
      setFinalizePassword("");
      setPreview(null);
      setResult(null);
      await load();
    } catch (e) {
      toast.error("Conferma finale non riuscita", { description: messageFromError(e) });
    } finally { setBusy(""); }
  };

  const disconnect = async () => {
    const ok = await appConfirm({ title: "Disconnetti Notion", message: "Rimuovere la connessione Notion? I dati già copiati nel gestionale resteranno invariati.", confirmLabel: "Disconnetti", danger: true });
    if (!ok) return;
    setBusy("disconnect");
    try {
      await axios.delete(`${API}/admin/notion/config`);
      toast.success("Connessione Notion rimossa");
      setPreview(null);
      setResult(null);
      await load();
    } catch (e) {
      toast.error("Disconnessione non riuscita", { description: messageFromError(e) });
    } finally { setBusy(""); }
  };

  const summary = useMemo(() => {
    if (!result) return [];
    return [
      ["Prodotti nuovi", result.inventory?.created],
      ["Prodotti aggiornati", result.inventory?.updated],
      ["Clienti nuovi", result.crm?.clients_created],
      ["Clienti aggiornati", result.crm?.clients_updated],
      ["Sedi create", result.crm?.sites_created],
      ["Ordini nuovi", result.crm?.orders_created],
      ["Ordini aggiornati", result.crm?.orders_updated],
      ["Documenti copiati", result.crm?.documents_imported],
      ["Fonti archiviate", result.universal_archive?.sources],
      ["Record archivio", result.universal_archive?.records],
      ["Pagine autonome", result.universal_archive?.pages],
    ];
  }, [result]);

  const importErrors = result?.universal_archive?.errors || [];
  const canImport = !!cfg?.configured && !!preview && !!(preview.all_sources_count || preview.inventory_count || preview.orders_count);

  if (!cfg) return <div className="max-w-6xl mx-auto p-6 text-sm text-slate-500">Caricamento configurazione Notion…</div>;

  if (cfg.completed) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div><div className="text-xs font-semibold tracking-[.16em] uppercase text-emerald-700">Migrazione completata</div><h1 className="text-3xl font-black text-slate-900 mt-1">Importazione Notion</h1></div>
        <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-6">
          <div className="flex gap-3"><CheckCircle size={28} weight="fill" className="text-emerald-600 shrink-0" /><div><h2 className="font-black text-emerald-950 text-lg">Gestionale autonomo</h2><p className="text-sm text-emerald-900 mt-1">La migrazione è stata confermata e le credenziali Notion sono state rimosse. Da questo momento i dati operativi vengono gestiti nel database interno.</p></div></div>
        </section>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-5" data-testid="notion-migration-page">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-3">
        <div><div className="text-xs font-semibold tracking-[.16em] uppercase text-[#1A456B]">Dati e migrazione</div><h1 className="text-3xl font-black text-slate-900 mt-1">Importazione completa da Notion</h1><p className="text-sm text-slate-500 mt-1 max-w-3xl">Flusso guidato: collega, verifica, controlla l'anteprima, importa e solo alla fine scollega Notion.</p></div>
        <div className="flex gap-2"><Pill ok={cfg.configured}>{cfg.configured ? "Connessione configurata" : "Da configurare"}</Pill>{cfg.import_ready && <Pill ok>Import completato, da verificare</Pill>}</div>
      </div>

      <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold text-lg">1. Collegamento</h2><p className="text-sm text-slate-500">Il token serve soltanto alla migrazione e Notion viene usato in sola lettura.</p></div><Plugs size={24} className="text-slate-400" /></div>
        <div><Label>Token integrazione Notion</Label><Input type="password" className="mt-1 h-11" value={form.token} onChange={(e) => setForm((p) => ({ ...p, token: e.target.value }))} placeholder={cfg.token_configured ? `Configurato: ${cfg.token_masked}` : "secret_..."} /></div>
        <button type="button" className="text-sm font-semibold text-blue-700" onClick={() => setAdvanced((v) => !v)}>{advanced ? "Nascondi mappature avanzate" : "Mostra mappature avanzate"}</button>
        {advanced && <div className="grid md:grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">{SOURCE_FIELDS.map(([key, label]) => <div key={key}><Label>{label}</Label><Input className="mt-1 font-mono text-xs" value={form[key] || ""} onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))} placeholder="ID data source; vuoto = auto-rilevamento" /></div>)}</div>}
        <div className="flex flex-wrap gap-2"><Button onClick={saveConfig} disabled={!!busy}><FloppyDisk size={17} /> {busy === "save" ? "Salvataggio…" : "Salva collegamento"}</Button><Button variant="outline" onClick={testConnection} disabled={!!busy || !cfg.configured}>{busy === "test" ? "Verifica…" : "Test connessione"}</Button>{cfg.configured && <Button variant="outline" className="text-red-700" onClick={disconnect} disabled={!!busy}>Disconnetti</Button>}</div>
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold text-lg">2. Anteprima obbligatoria</h2><p className="text-sm text-slate-500">L'anteprima legge le fonti e mostra cosa verrà trasferito prima di scrivere nel gestionale.</p></div><Eye size={24} className="text-slate-400" /></div>
        <Button variant="outline" onClick={makePreview} disabled={!!busy || !cfg.configured}><ArrowClockwise size={17} className={busy === "preview" ? "animate-spin" : ""} /> {busy === "preview" ? "Lettura fonti…" : "Aggiorna anteprima"}</Button>
        {preview && <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3"><Stat label="Prodotti Elios" value={preview.inventory_count} /><Stat label="Ordini" value={preview.orders_count} /><Stat label="Entrate Elios" value={preview.receipts_count} /><Stat label="Uscite Elios" value={preview.exits_count} /><Stat label="Prodotti Verona" value={preview.verona_inventory_count} /><Stat label="Entrate Verona" value={preview.verona_receipts_count} /><Stat label="Uscite Verona" value={preview.verona_exits_count} /><Stat label="Fonti totali" value={preview.all_sources_count} /></div>
          {Array.isArray(preview.all_source_titles) && preview.all_source_titles.length > 0 && <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="font-semibold text-sm mb-2">Fonti rilevate</div><div className="flex flex-wrap gap-2">{preview.all_source_titles.map((title, i) => <span key={`${title}-${i}`} className="rounded-full bg-white border border-slate-200 px-2.5 py-1 text-xs text-slate-700">{title}</span>)}</div></div>}
        </>}
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold text-lg">3. Importazione</h2><p className="text-sm text-slate-500">Copia dati, relazioni, documenti e archivio nel database locale. Può essere rilanciata: i record riconosciuti vengono aggiornati o saltati, non duplicati.</p></div><Database size={24} className="text-slate-400" /></div>
        <Button onClick={importAll} disabled={!!busy || !canImport} className="h-11">{busy === "import" ? "Importazione in corso…" : "Importa tutto da Notion"}</Button>
        {!preview && <div className="text-xs text-amber-700">Prima dell'importazione è obbligatorio eseguire l'anteprima.</div>}
        {progress && progress.state !== "completed" && <div className={`rounded-xl border p-4 ${progress.state === "error" ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}><div className="flex items-center justify-between gap-3"><div><div className="font-bold text-sm">{progress.phase || "Migrazione"}</div><div className="text-xs text-slate-600 mt-1">{progress.message || "Elaborazione in corso"}</div></div><div className="font-black text-xl">{Math.max(0, Math.min(100, Number(progress.percent || 0)))}%</div></div><div className="mt-3 h-2.5 bg-white rounded-full overflow-hidden border"><div className="h-full bg-[#1A456B] transition-all" style={{ width: `${Math.max(2, Math.min(100, Number(progress.percent || 0)))}%` }} /></div><div className="text-xs text-slate-500 mt-2">Record/pagine elaborati: {progress.processed ?? 0}</div></div>}
        {result && <div className="space-y-3"><div className="grid grid-cols-2 md:grid-cols-4 gap-3">{summary.map(([label, value]) => <Stat key={label} label={label} value={value} />)}</div>{importErrors.length > 0 ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="font-bold text-amber-900">Elementi da verificare: {importErrors.length}</div><div className="text-xs text-amber-800 mt-2 space-y-1 max-h-44 overflow-y-auto">{importErrors.slice(0, 50).map((e, i) => <div key={i}>• {e?.source ? `${e.source}: ` : ""}{e?.error || JSON.stringify(e)}</div>)}</div></div> : <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"><b>Nessun errore segnalato dall'archivio universale.</b></div>}</div>}
      </section>

      {cfg.import_ready && <section className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-5"><div className="flex gap-3"><CheckCircle size={26} weight="fill" className="text-emerald-600 shrink-0" /><div className="flex-1"><h2 className="font-black text-emerald-950">4. Verifica finale e autonomia</h2><p className="text-sm text-emerald-900 mt-1">L'importazione è terminata. Controlla Clienti / Ordini, Commesse, Fatturato, Wallbox, Report, magazzini e documenti. Solo dopo questa verifica conferma la chiusura definitiva della migrazione.</p><Button className="mt-3" onClick={() => setFinalizeOpen(true)}>Conferma migrazione e scollega Notion</Button></div></div></section>}

      <Dialog open={finalizeOpen} onOpenChange={(v) => { setFinalizeOpen(v); if (!v) { setFinalizeText(""); setFinalizePassword(""); } }}><DialogContent className="max-w-lg"><DialogHeader><DialogTitle>Conferma chiusura migrazione</DialogTitle></DialogHeader><div className="space-y-4"><div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Questa azione rimuove le credenziali Notion dal gestionale. I dati già importati restano nel database interno e Notion non viene modificato.</div><div><Label>Digita CONFERMA MIGRAZIONE</Label><Input className="mt-1" value={finalizeText} onChange={(e) => setFinalizeText(e.target.value)} /></div><div><Label>Password amministratore</Label><Input type="password" className="mt-1" value={finalizePassword} onChange={(e) => setFinalizePassword(e.target.value)} autoComplete="current-password" /></div><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setFinalizeOpen(false)} disabled={busy === "finalize"}>Annulla</Button><Button onClick={finalize} disabled={busy === "finalize" || !finalizePassword || finalizeText.trim().toUpperCase() !== "CONFERMA MIGRAZIONE"}>{busy === "finalize" ? "Conferma in corso…" : "Conferma e scollega"}</Button></div></div></DialogContent></Dialog>
    </div>
  );
}
