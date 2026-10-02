import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import {
  Pulse,
  ArrowsClockwise,
  Bell,
  Brain,
  CheckCircle,
  Database,
  DownloadSimple,
  Gear,
  Package,
  UsersThree,
  ListMagnifyingGlass,
  ArrowsLeftRight,
  ClipboardText,
  WarningCircle,
  Wrench,
} from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import {
  AuditLogTab,
  SystemLogsTab,
  SettingsTab,
  SettingsArriviTab,
  SettingsSpedizioniTab,
  SessionsTab,
  ManutenzioneTab,
  ExportMovimentiTab,
  DataResetTab,
  SettingsScannerTab,
} from "./AdminExtraTabs";



import { appConfirm } from "../lib/appConfirm";
const CATEGORIES = [
  { key: "general", label: "Generali", icon: Gear },
  { key: "users", label: "Utenti e sicurezza", icon: UsersThree },
  { key: "warehouse", label: "Magazzino e scanner", icon: Package },
  { key: "operations", label: "Flusso operativo", icon: Wrench },
  { key: "notifications", label: "Notifiche", icon: Bell },
  { key: "ai", label: "Assistente AI", icon: Brain },
  { key: "data", label: "Dati e backup", icon: Database },
  { key: "system", label: "Sistema, log e audit", icon: Pulse },
];

function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore";
}

function StatusPill({ ok, label }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
      {ok ? <CheckCircle size={14} weight="fill" /> : <WarningCircle size={14} weight="fill" />}
      {label}
    </span>
  );
}

function SectionCard({ title, description, children, right }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-bold text-slate-900">{title}</h2>
          
        </div>
        {right}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ToggleRow({ label, hint, checked, onChange, disabled }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-slate-100 last:border-0">
      <div>
        <div className="text-sm font-semibold text-slate-800">{label}</div>
        
      </div>
      <Switch checked={!!checked} onCheckedChange={(v) => onChange?.(v)} disabled={disabled} className="et-settings-switch" />
    </div>
  );
}

function GeneralPane() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const load = async () => {
    try { setS((await axios.get(`${API}/admin/settings`)).data); }
    catch (e) { toast.error("Impossibile caricare le impostazioni", { description: formatError(e) }); }
  };
  useEffect(() => { load(); }, []);
  if (!s) return <div className="text-sm text-slate-500">Caricamento…</div>;
  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        general: s.general,
        dashboard: s.dashboard,
        sicurezza: s.sicurezza,
      };
      setS((await axios.put(`${API}/admin/settings`, payload)).data);
      window.dispatchEvent(new Event("elios:settings-changed"));
      toast.success("Impostazioni generali salvate");
    } catch (e) { toast.error("Salvataggio fallito", { description: formatError(e) }); }
    finally { setSaving(false); }
  };
  const setGeneral = (p) => setS((x) => ({ ...x, general: { ...(x.general || {}), ...p } }));
  const setDashboard = (p) => setS((x) => ({ ...x, dashboard: { ...(x.dashboard || {}), ...p } }));
  return (
    <div className="space-y-5">
      <SectionCard title="Identità gestionale" description="Nome e formati usati in tutta l'applicazione.">
        <div className="grid md:grid-cols-2 gap-4">
          <div><Label>Nome applicazione</Label><Input className="mt-1 h-11" value={s.general?.app_name || "Gestionale Elios Tech"} onChange={(e) => setGeneral({ app_name: e.target.value })} /></div>
          <div><Label>Azienda</Label><Input className="mt-1 h-11" value={s.general?.company_name || "Elios Tech S.r.l."} onChange={(e) => setGeneral({ company_name: e.target.value })} /></div>
          <div><Label>Fuso orario</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={s.general?.timezone || "Europe/Rome"} onChange={(e) => setGeneral({ timezone: e.target.value })}><option>Europe/Rome</option><option>UTC</option><option>Europe/London</option></select></div>
          <div><Label>Formato data</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={s.general?.date_format || "DD/MM/YYYY"} onChange={(e) => setGeneral({ date_format: e.target.value })}><option>DD/MM/YYYY</option><option>YYYY-MM-DD</option><option>MM/DD/YYYY</option></select></div>
        </div>
        <div className="mt-4">
          <ToggleRow label="Aggiornamento automatico Dashboard" hint="Permette l'aggiornamento periodico della Dashboard operativa." checked={!!s.general?.auto_refresh_enabled} onChange={(v) => setGeneral({ auto_refresh_enabled: v })} />
          {s.general?.auto_refresh_enabled && <div className="pt-3"><Label>Intervallo aggiornamento (secondi)</Label><Input type="number" min="15" max="3600" className="mt-1 h-11 max-w-[180px]" value={s.dashboard?.autorefresh_seconds || 60} onChange={(e) => setDashboard({ autorefresh_seconds: Number(e.target.value) })} /></div>}
        </div>
      </SectionCard>
      <div className="flex justify-end"><Button onClick={save} disabled={saving} className="h-11 et-btn-primary">{saving ? "Salvataggio…" : "Salva modifiche"}</Button></div>
    </div>
  );
}

function UsersSecurityPane() {
  return (
    <div className="space-y-5">
      <SectionCard title="Utenti e permessi" right={<Link to="/admin/utenti" className="inline-flex h-10 items-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white">Gestisci utenti</Link>}>
        <div className="text-sm text-slate-500">Account attivi e permessi</div>
      </SectionCard>
      <SectionCard title="Sicurezza accessi" description="Durata sessione, inattività, tentativi di accesso e blocco temporaneo."><SettingsTab filter={["sicurezza"]} /></SectionCard>
      <SectionCard title="Sessioni attive" description="Controlla i dispositivi collegati e revoca una sessione quando necessario."><SessionsTab /></SectionCard>
    </div>
  );
}

function AIPane() {
  const [settings, setSettings] = useState(null);
  const [config, setConfig] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const load = async () => {
    const [a, c] = await Promise.allSettled([axios.get(`${API}/ai/settings`), axios.get(`${API}/ai/provider-config`)]);
    if (a.status === "fulfilled") setSettings(a.value.data);
    else {
      setSettings({ enabled: false, mode: "consultation", confirm_before_modify: true, auto_execute: false, daily_limit: 20 });
      toast.error("Impossibile leggere le impostazioni AI", { description: formatError(a.reason) });
    }
    if (c.status === "fulfilled") setConfig(c.value.data);
    else {
      setConfig({ provider: "groq", model: "openai/gpt-oss-120b", configured: false, api_key_configured: false });
      toast.error("Impossibile leggere il provider AI", { description: formatError(c.reason) });
    }
  };
  useEffect(() => { load(); }, []);
  if (!settings || !config) return <div className="text-sm text-slate-500">Caricamento…</div>;
  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/ai/settings`, {
        enabled: !!settings.enabled,
        mode: settings.mode || "consultation",
        confirm_before_modify: !!settings.confirm_before_modify,
        auto_execute: !!settings.auto_execute,
        daily_limit: Number(settings.daily_limit ?? 20),
      });
      const payload = { provider: config.provider || "groq", model: config.model || "openai/gpt-oss-120b" };
      if (apiKey.trim()) payload.api_key = apiKey.trim();
      try {
        const c = await axios.put(`${API}/ai/provider-config`, payload);
        setConfig(c.data); setApiKey("");
      } catch (providerError) {
        toast.warning("Impostazioni AI salvate, ma il provider non è stato aggiornato", { description: formatError(providerError) });
      }
      toast.success(settings.enabled ? "Assistente AI attivato" : "Impostazioni AI salvate");
      await load();
    } catch (e) { toast.error("Salvataggio AI fallito", { description: formatError(e) }); }
    finally { setSaving(false); }
  };
  const test = async () => {
    setTesting(true);
    try { const { data } = await axios.post(`${API}/ai/provider-test`); toast.success(data.message || "Connessione AI funzionante"); await load(); }
    catch (e) { toast.error("Test AI fallito", { description: formatError(e) }); }
    finally { setTesting(false); }
  };
  const upd = (p) => setSettings((s) => ({ ...s, ...p }));
  return (
    <div className="space-y-5">
      <SectionCard title="Stato Assistente AI" description="Attiva o disattiva l'Assistente AI. Le modifiche diventano effettive quando premi “Salva Assistente AI”." right={<StatusPill ok={config.configured} label={config.configured ? "Provider configurato" : "Da configurare"} />}>
        <ToggleRow label="Attiva Assistente AI" hint="Quando disattivato nessuna richiesta viene inviata al provider." checked={!!settings.enabled} onChange={(v) => upd({ enabled: v })} />
        {settings.enabled && !config.configured && <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">L'Assistente AI può essere attivato, ma per usarlo devi configurare una API key valida nella sezione Provider AI.</div>}
        <div className="grid md:grid-cols-2 gap-4 pt-4">
          <div><Label>Modalità</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={settings.mode || "consultation"} onChange={(e) => upd({ mode: e.target.value, ...(e.target.value !== "full_operational" ? { auto_execute: false } : {}) })}><option value="consultation">Solo consultazione</option><option value="operational">Operativa con conferma</option><option value="full_operational">Operativa completa</option></select></div>
          <div><Label>Limite giornaliero per utente</Label><Input type="number" min="0" max="10000" className="mt-1 h-11" value={settings.daily_limit ?? 20} onChange={(e) => upd({ daily_limit: Number(e.target.value) })} /></div>
        </div>
        <div className="mt-3">
          <ToggleRow label="Conferma prima delle modifiche" hint="Consigliato: l'AI prepara l'operazione ma non la esegue finché l'utente non conferma." checked={!!settings.confirm_before_modify} onChange={(v) => upd({ confirm_before_modify: v })} />
          <ToggleRow label="Esecuzione automatica" hint="Disponibile solo in modalità Operativa completa. Da usare solo se strettamente necessario." checked={!!settings.auto_execute} disabled={settings.mode !== "full_operational"} onChange={(v) => upd({ auto_execute: v })} />
        </div>
      </SectionCard>
      <SectionCard title="Provider AI" description="La chiave resta sul backend e non viene mai restituita al browser." right={<Button variant="outline" onClick={test} disabled={testing || !config.configured} className="h-10">{testing ? "Test…" : "Test connessione"}</Button>}>
        <div className="grid md:grid-cols-2 gap-4">
          <div><Label>Provider</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={config.provider || "groq"} onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}><option value="groq">Groq</option></select></div>
          <div><Label>Modello</Label><Input className="mt-1 h-11" value={config.model || "openai/gpt-oss-120b"} onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))} /></div>
          <div className="md:col-span-2"><Label>API key</Label><Input type="password" className="mt-1 h-11" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={config.api_key_configured ? `Configurata: ${config.api_key_masked}` : "Inserisci API key"} /><p className="text-xs text-slate-500 mt-1">Lascia vuoto per mantenere la chiave già salvata.</p></div>
        </div>
      </SectionCard>
      <div className="flex justify-end"><Button onClick={save} disabled={saving} className="h-11 et-btn-primary">{saving ? "Salvataggio…" : "Salva Assistente AI"}</Button></div>
    </div>
  );
}

function WarehousePane() {
  const [tab, setTab] = useState("stock");
  const tabs = [
    ["stock", "Scorte", Package],
    ["search", "Ricerca", ListMagnifyingGlass],
    ["scanner", "Scanner", ClipboardText],
    ["moves", "Movimenti", ArrowsLeftRight],
  ];
  return (
    <div className="space-y-4">
      <div className="settings-page-intro">
        <h2 className="font-display text-xl font-bold text-slate-900">Magazzino e scanner</h2>
        
      </div>
      <div className="settings-subnav">
        {tabs.map(([key, label, Icon]) => (
          <button key={key} type="button" onClick={() => setTab(key)} className={`settings-subnav-btn ${tab === key ? "active" : ""}`}>
            <Icon size={16} /> <span>{label}</span>
          </button>
        ))}
      </div>
      {tab === "stock" && <SettingsTab filter={["magazzino"]} saveLabel="Salva regole scorte" />}
      {tab === "search" && <SettingsTab filter={["ricerca"]} saveLabel="Salva ricerca prodotti" />}
      {tab === "scanner" && <SettingsScannerTab />}
      {tab === "moves" && <SettingsTab filter={["movimenti"]} saveLabel="Salva movimenti" />}
    </div>
  );
}

function OperationsPane() {
  const [tab, setTab] = useState("arrivi");
  const tabs = [["arrivi","Arrivi"],["spedizioni","Spedizioni"],["workflow","Automazioni"]];
  return (
    <div className="space-y-4">
      <div className="settings-page-intro">
        <h2 className="font-display text-xl font-bold text-slate-900">Flusso operativo</h2>
        
      </div>
      <div className="settings-subnav">
        {tabs.map(([k,l]) => <button key={k} onClick={() => setTab(k)} className={`settings-subnav-btn ${tab===k?"active":""}`}>{l}</button>)}
      </div>
      {tab === "arrivi" && <SectionCard title="Arrivi" description="Controlli applicati quando il materiale entra a magazzino."><SettingsArriviTab /></SectionCard>}
      {tab === "spedizioni" && <SectionCard title="Spedizioni" description="Controlli applicati prima dell'uscita del materiale."><SettingsSpedizioniTab /></SectionCard>}
      {tab === "workflow" && <SectionCard title="Automazioni operative" description="Passaggi automatici già attivi nel flusso Elios Tech.">
        <div className="grid md:grid-cols-2 gap-3 text-sm">
          {["Ordine confermato → crea/aggiorna la Commessa", "Preventivo accettato → crea/aggiorna la Commessa", "Spedizione completa → rende disponibile la fase successiva", "Installazione completata → aggiorna lo storico cliente"].map((x) => <div key={x} className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3 text-emerald-800 flex gap-2"><CheckCircle size={18} weight="fill" className="shrink-0" />{x}</div>)}
        </div>
      </SectionCard>}
    </div>
  );
}

function NotificationsPane() {
  const [items, setItems] = useState([]);
  const [newEmail, setNewEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [emailCfg, setEmailCfg] = useState(null);
  const [smtpPassword, setSmtpPassword] = useState("");
  const [testRecipient, setTestRecipient] = useState("");
  const [testing, setTesting] = useState(false);
  const EVENTS = [
    ["arrivi", "Arrivi"], ["spedizioni", "Spedizioni"], ["sotto_scorta", "Sotto scorta"],
    ["esauriti", "Esauriti"], ["anomalie", "Anomalie"], ["errori_notion", "Errori di importazione"],
  ];
  const load = async () => {
    const [r, c] = await Promise.allSettled([axios.get(`${API}/admin/recipients`), axios.get(`${API}/admin/email/config`)]);
    let recipientItems = [];
    if (r.status === "fulfilled") {
      recipientItems = (r.value.data.items || []).map((it) => ({ ...it, events: { ...(it.events || {}) } }));
      setItems(recipientItems);
    } else {
      setItems([]);
      toast.error("Impossibile caricare i destinatari", { description: formatError(r.reason) });
    }
    if (c.status === "fulfilled") setEmailCfg(c.value.data);
    else {
      setEmailCfg({ enabled: false, host: "", port: 587, username: "", from_email: "", from_name: "Elios Tech", security: "starttls", configured: false, password_configured: false });
      toast.error("Impossibile caricare la configurazione email", { description: formatError(c.reason) });
    }
    setTestRecipient((prev) => prev || (recipientItems?.[0]?.email || (c.status === "fulfilled" ? c.value.data?.from_email : "") || ""));
  };
  useEffect(() => { load(); }, []);
  if (!emailCfg) return <div className="text-sm text-slate-500">Caricamento…</div>;

  const add = () => {
    const v = newEmail.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return toast.error("Email non valida");
    if (items.some((x) => x.email === v)) return toast.error("Email già presente");
    setItems((x) => [...x, { email: v, enabled: true, events: Object.fromEntries(EVENTS.map(([k]) => [k, true])) }]);
    setNewEmail("");
  };

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/recipients`, { items });
      const payload = {
        enabled: !!emailCfg.enabled,
        host: emailCfg.host || "",
        port: Number(emailCfg.port || 587),
        username: emailCfg.username || "",
        from_email: emailCfg.from_email || "",
        from_name: emailCfg.from_name || "Elios Tech",
        security: emailCfg.security || "starttls",
      };
      if (smtpPassword.trim()) payload.password = smtpPassword.trim();
      const { data } = await axios.put(`${API}/admin/email/config`, payload);
      setEmailCfg(data);
      setSmtpPassword("");
      toast.success("Notifiche ed email salvate");
    } catch (e) { toast.error("Salvataggio notifiche fallito", { description: formatError(e) }); }
    finally { setSaving(false); }
  };

  const testEmail = async () => {
    const target = testRecipient.trim();
    if (!target) return toast.error("Inserisci un destinatario per il test");
    setTesting(true);
    try {
      const { data } = await axios.post(`${API}/admin/email/test`, { recipient: target });
      toast.success(data.message || "Email di test inviata");
    } catch (e) { toast.error("Test email fallito", { description: formatError(e) }); }
    finally { setTesting(false); }
  };

  return (
    <div className="space-y-5">
      <SectionCard title="Invio email SMTP" description="Configura l'account email usato dal Gestionale Elios Tech." right={<StatusPill ok={emailCfg.configured} label={emailCfg.configured ? (emailCfg.enabled ? "Configurato e attivo" : "Configurato") : "Da configurare"} />}>
        {!emailCfg.configured && <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Puoi salvare i destinatari anche senza configurare l'SMTP. Le email verranno inviate soltanto dopo aver configurato e abilitato il server di posta.</div>}
        <ToggleRow label="Abilita invio email" hint="Se disattivato, il gestionale non invia email automatiche." checked={!!emailCfg.enabled} onChange={(v) => setEmailCfg((x) => ({ ...x, enabled: v }))} />
        <div className="grid md:grid-cols-2 gap-3 mt-4">
          <div><Label>Server SMTP</Label><Input className="mt-1 h-11" value={emailCfg.host || ""} onChange={(e) => setEmailCfg((x) => ({ ...x, host: e.target.value }))} placeholder="smtp.provider.it" /></div>
          <div><Label>Porta</Label><Input type="number" className="mt-1 h-11" value={emailCfg.port || 587} onChange={(e) => setEmailCfg((x) => ({ ...x, port: Number(e.target.value) }))} /></div>
          <div><Label>Username SMTP</Label><Input className="mt-1 h-11" value={emailCfg.username || ""} onChange={(e) => setEmailCfg((x) => ({ ...x, username: e.target.value }))} /></div>
          <div><Label>Password SMTP</Label><Input type="password" className="mt-1 h-11" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder={emailCfg.password_configured ? `Configurata: ${emailCfg.password_masked}` : "Password / app password"} /></div>
          <div><Label>Email mittente</Label><Input type="email" className="mt-1 h-11" value={emailCfg.from_email || ""} onChange={(e) => setEmailCfg((x) => ({ ...x, from_email: e.target.value }))} placeholder="tecnico@eliostech.org" /></div>
          <div><Label>Nome mittente</Label><Input className="mt-1 h-11" value={emailCfg.from_name || "Elios Tech"} onChange={(e) => setEmailCfg((x) => ({ ...x, from_name: e.target.value }))} /></div>
          <div><Label>Sicurezza</Label><select className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={emailCfg.security || "starttls"} onChange={(e) => setEmailCfg((x) => ({ ...x, security: e.target.value }))}><option value="starttls">STARTTLS</option><option value="ssl">SSL/TLS</option><option value="none">Nessuna</option></select></div>
          <div><Label>Email per test</Label><div className="flex gap-2 mt-1"><Input type="email" className="h-11" value={testRecipient} onChange={(e) => setTestRecipient(e.target.value)} /><Button variant="outline" onClick={testEmail} disabled={testing || !emailCfg.enabled || !emailCfg.configured} className="h-11 shrink-0">{testing ? "Invio…" : "Test"}</Button></div></div>
        </div>
      </SectionCard>

      <SectionCard title="Destinatari notifiche" description="Scegli chi riceve le notifiche e per quali eventi.">
        <div className="flex gap-2 mb-4"><Input type="email" className="h-11" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="nome@azienda.it" /><Button onClick={add} className="h-11">Aggiungi</Button></div>
        <div className="space-y-3">
          {items.map((it, idx) => <div key={it.email} className="border border-slate-200 rounded-md p-4">
            <div className="flex items-center justify-between gap-3"><div className="font-semibold text-slate-800 break-all">{it.email}</div><div className="flex gap-2"><button type="button" className={`text-xs font-semibold px-3 py-1.5 rounded-full ${it.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`} onClick={() => setItems((a) => a.map((x, i) => i === idx ? { ...x, enabled: !x.enabled } : x))}>{it.enabled ? "Attivo" : "Disattivato"}</button><button type="button" className="text-xs text-red-600" onClick={() => setItems((a) => a.filter((_, i) => i !== idx))}>Rimuovi</button></div></div>
            <div className="flex flex-wrap gap-2 mt-3">{EVENTS.map(([k, lab]) => <label key={k} className="inline-flex items-center gap-1.5 text-xs border border-slate-200 rounded px-2 py-1.5"><input type="checkbox" checked={it.events?.[k] !== false} onChange={() => setItems((a) => a.map((x, i) => i === idx ? { ...x, events: { ...(x.events || {}), [k]: x.events?.[k] === false } } : x))} />{lab}</label>)}</div>
          </div>)}
          {items.length === 0 && <div className="text-sm text-slate-500">Nessun destinatario configurato.</div>}
        </div>
      </SectionCard>
      <div className="flex justify-end"><Button onClick={save} disabled={saving} className="h-11 et-btn-primary">{saving ? "Salvataggio…" : "Salva notifiche ed email"}</Button></div>
    </div>
  );
}

function NotionMigrationPane() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({ token: "", inventario_ds_id: "", ordini_ds_id: "", receipts_ds_id: "", tracker_ds_id: "", verona_inventario_ds_id: "", verona_receipts_ds_id: "", verona_tracker_ds_id: "" });
  const [preview, setPreview] = useState(null);
  const [fullImportResult, setFullImportResult] = useState(null);
  const [busy, setBusy] = useState("");
  const ELIOS_INVENTORY_DS = "279a9b09-6783-806d-b0db-000b37db3122";

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/admin/notion/config`);
      setCfg(data);
      if (!data.finalized) setForm((x) => ({ ...x, token: "", inventario_ds_id: data.inventario_ds_id || ELIOS_INVENTORY_DS, ordini_ds_id: data.ordini_ds_id || "", receipts_ds_id: data.receipts_ds_id || "", tracker_ds_id: data.tracker_ds_id || "", verona_inventario_ds_id: data.verona_inventario_ds_id || "", verona_receipts_ds_id: data.verona_receipts_ds_id || "", verona_tracker_ds_id: data.verona_tracker_ds_id || "" }));
    } catch (e) { toast.error("Errore configurazione migrazione", { description: formatError(e) }); }
  };
  useEffect(() => { load(); }, []);
  if (!cfg) return <div className="text-sm text-slate-500">Caricamento…</div>;

  const save = async () => {
    setBusy("save");
    try { const { data } = await axios.put(`${API}/admin/notion/config`, form); setCfg(data); setForm((x) => ({ ...x, token: "" })); toast.success("Configurazione salvata"); }
    catch (e) { toast.error("Salvataggio fallito", { description: formatError(e) }); }
    finally { setBusy(""); }
  };
  const test = async () => { setBusy("test"); try { await axios.post(`${API}/admin/notion/test`); toast.success("Connessione verificata"); } catch (e) { toast.error("Test fallito", { description: formatError(e) }); } finally { setBusy(""); } };
  const doPreview = async () => { setBusy("preview"); try { const { data } = await axios.get(`${API}/admin/notion/import-preview`); setPreview(data); toast.success("Anteprima pronta"); } catch (e) { toast.error("Anteprima fallita", { description: formatError(e) }); } finally { setBusy(""); } };
  const importAllNotion = async () => {
    if (!preview) return toast.error("Fai prima l'anteprima");
    const ok = await appConfirm({
      title: "Migrazione completa",
      message: `Importare tutti i dati disponibili? Ordini rilevati: ${preview.orders_count ?? 0}. Verranno copiati clienti, sedi, ordini, prodotti, seriali, servizi, scadenze, credenziali, portali, storico movimenti, contratti e tutti gli allegati. L'operazione è rilanciabile senza duplicare i record già importati.`,
      confirmLabel: "Avvia migrazione",
    });
    if (!ok) return;
    setBusy("full-import"); setFullImportResult(null);
    try { const { data } = await axios.post(`${API}/admin/notion/import-all`, {}, { timeout: 10 * 60 * 1000 }); setFullImportResult(data); toast.success("Migrazione completata"); }
    catch (e) { toast.error("Migrazione fallita", { description: formatError(e) }); }
    finally { setBusy(""); }
  };
  const finalizeMigration = async () => {
    const ok = await appConfirm({
      title: "Completa e scollega",
      message: "Confermi che la migrazione è stata verificata? I dati locali restano invariati. Verranno eliminate credenziali, collegamenti e metadati di provenienza esterni. Dopo questa operazione la migrazione non sarà più rilanciabile senza riconfigurare manualmente una nuova sorgente.",
      confirmLabel: "Completa e scollega",
      danger: true,
    });
    if (!ok) return;
    setBusy("finalize");
    try { await axios.post(`${API}/admin/notion/finalize-migration`, { confirm: true }); setPreview(null); setFullImportResult(null); await load(); toast.success("Migrazione chiusa. Gestionale autonomo."); }
    catch (e) { toast.error("Chiusura migrazione fallita", { description: formatError(e) }); }
    finally { setBusy(""); }
  };
  const downloadBackup = async () => {
    setBusy("backup");
    try {
      const response = await axios.get(`${API}/admin/backup/download`, { responseType: "blob" });
      const disposition = response.headers?.["content-disposition"] || "";
      const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
      const filename = match ? decodeURIComponent(match[1].replace(/"/g, "")) : `Gestionale_Elios_Tech_backup_${new Date().toISOString().slice(0,10)}.zip`;
      const url = URL.createObjectURL(response.data); const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("Backup completo creato");
    } catch (e) { toast.error("Backup non riuscito", { description: formatError(e) }); }
    finally { setBusy(""); }
  };

  if (cfg.finalized) return <div className="space-y-5">
    <SectionCard title="Migrazione completata" right={<StatusPill ok label="Completata" />}>
      <div className="grid sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">Stato</div><div className="text-lg font-bold mt-1">Gestionale autonomo</div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">Database operativo</div><div className="text-lg font-bold mt-1">Locale</div></div>
        <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">Collegamenti esterni</div><div className="text-lg font-bold mt-1">Rimossi</div></div>
      </div>
    </SectionCard>
    <SectionCard title="Esportazione movimenti"><ExportMovimentiTab /></SectionCard>
    <SectionCard title="Backup completo"><Button onClick={downloadBackup} disabled={!!busy} className="h-11"><DownloadSimple size={18} /> {busy === "backup" ? "Creazione…" : "Scarica backup completo"}</Button></SectionCard>
    <SectionCard title="Pulizia dati"><DataResetTab /></SectionCard>
  </div>;

  return <div className="space-y-5">
    <SectionCard title="Migrazione dati" right={<StatusPill ok={cfg.configured} label={cfg.configured ? "Configurata" : "Da configurare"} />}>
      <div className="grid md:grid-cols-2 gap-3">
        <div className="md:col-span-2"><Label>Token di integrazione</Label><Input type="password" className="mt-1 h-11" value={form.token} onChange={(e) => setForm((x) => ({ ...x, token: e.target.value }))} placeholder={cfg.token_configured ? `Configurato: ${cfg.token_masked}` : "secret_..."} /></div>
        <div><Label>Inventario Elios Tech</Label><Input className="mt-1 h-11" value={form.inventario_ds_id} onChange={(e) => setForm((x) => ({ ...x, inventario_ds_id: e.target.value }))} placeholder={ELIOS_INVENTORY_DS} /></div>
        <div><Label>Entrate Elios Tech</Label><Input className="mt-1 h-11" value={form.receipts_ds_id} onChange={(e) => setForm((x) => ({ ...x, receipts_ds_id: e.target.value }))} /></div>
        <div><Label>Uscite Elios Tech</Label><Input className="mt-1 h-11" value={form.tracker_ds_id} onChange={(e) => setForm((x) => ({ ...x, tracker_ds_id: e.target.value }))} /></div>
        <div><Label>Ordini</Label><Input className="mt-1 h-11" value={form.ordini_ds_id} onChange={(e) => setForm((x) => ({ ...x, ordini_ds_id: e.target.value }))} /></div>
        <div><Label>Inventario Verona</Label><Input className="mt-1 h-11" value={form.verona_inventario_ds_id} onChange={(e) => setForm((x) => ({ ...x, verona_inventario_ds_id: e.target.value }))} /></div>
        <div><Label>Entrate Verona</Label><Input className="mt-1 h-11" value={form.verona_receipts_ds_id} onChange={(e) => setForm((x) => ({ ...x, verona_receipts_ds_id: e.target.value }))} /></div>
        <div><Label>Uscite Verona</Label><Input className="mt-1 h-11" value={form.verona_tracker_ds_id} onChange={(e) => setForm((x) => ({ ...x, verona_tracker_ds_id: e.target.value }))} /></div>
      </div>
      <div className="flex flex-wrap gap-2 mt-4"><Button onClick={save} disabled={!!busy}>Salva</Button><Button variant="outline" onClick={test} disabled={!!busy || !cfg.configured}>Test</Button><Button variant="outline" onClick={doPreview} disabled={!!busy || !cfg.configured}>{busy === "preview" ? "Lettura…" : "Anteprima"}</Button></div>
    </SectionCard>

    {preview && <SectionCard title="Anteprima migrazione">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[
        ["Prodotti Elios", preview.inventory_count ?? 0], ["Entrate Elios", preview.receipts_count ?? 0], ["Uscite Elios", preview.exits_count ?? 0], ["Ordini", preview.orders_count ?? 0],
        ["Prodotti Verona", preview.verona_inventory_count ?? 0], ["Entrate Verona", preview.verona_receipts_count ?? 0], ["Uscite Verona", preview.verona_exits_count ?? 0], ["Ordini storici", preview.historical_orders_count ?? 0],
        ["Interventi", preview.interventions_count ?? 0], ["Report attività", preview.staff_reports_count ?? 0], ["Report installazioni", preview.riccardo_reports_count ?? 0],
      ].map(([l,v]) => <div key={l} className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-xs text-slate-500">{l}</div><div className="text-2xl font-bold mt-1">{v}</div></div>)}</div>
      <div className="mt-4 flex flex-wrap gap-2"><Button onClick={importAllNotion} disabled={!!busy} className="h-11">{busy === "full-import" ? "Migrazione in corso…" : "Importa tutto"}</Button>{fullImportResult && <Button variant="outline" className="h-11 border-red-200 text-red-700" onClick={finalizeMigration} disabled={!!busy}>{busy === "finalize" ? "Chiusura…" : "Completa e scollega"}</Button>}</div>
      {fullImportResult && <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">{[
        ["Clienti nuovi", fullImportResult.crm?.clients_created], ["Clienti aggiornati", fullImportResult.crm?.clients_updated], ["Sedi", fullImportResult.crm?.sites_created], ["Ordini nuovi", fullImportResult.crm?.orders_created],
        ["Ordini aggiornati", fullImportResult.crm?.orders_updated], ["Documenti", fullImportResult.crm?.documents_imported], ["Già presenti", fullImportResult.crm?.documents_skipped], ["Errori file", fullImportResult.crm?.document_errors],
      ].map(([l,v]) => <div key={l} className="rounded-xl border border-emerald-200 bg-emerald-50 p-3"><div className="text-xs text-emerald-800">{l}</div><div className="text-xl font-bold text-emerald-950">{v ?? 0}</div></div>)}</div>}
    </SectionCard>}

    <SectionCard title="Esportazione movimenti"><ExportMovimentiTab /></SectionCard>
    <SectionCard title="Backup completo"><Button onClick={downloadBackup} disabled={!!busy} className="h-11"><DownloadSimple size={18} /> {busy === "backup" ? "Creazione…" : "Scarica backup completo"}</Button></SectionCard>
    <SectionCard title="Pulizia dati"><DataResetTab /></SectionCard>
  </div>;
}

function SystemPane() {
  const [tab, setTab] = useState("status");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/admin/system/status`);
      setStatus(data); setLoadError("");
    } catch (e) {
      const msg = formatError(e); setStatus(null); setLoadError(msg);
      toast.error("Diagnostica non disponibile", { description: msg });
    } finally { setLoading(false); }
  };
  useEffect(() => { if (tab === "status") load(); }, [tab]);
  const tabs = [["status","Stato sistema"],["audit","Audit attività"],["logs","Log sistema"],["maintenance","Manutenzione"]];
  const cards = status ? [
    { label: "Backend", ok: status.backend?.ok, text: status.backend?.ok ? "Operativo" : "Errore", detail: status.backend?.label },
    { label: "Database", ok: status.database?.ok, text: status.database?.ok ? "Connesso" : "Errore", detail: status.database?.label },
    { label: "Archivio documenti", ok: status.storage?.ok, text: status.storage?.ok ? "Disponibile" : "Errore", detail: status.storage?.path || status.storage?.label },
    { label: "AI", ok: status.ai?.configured, text: status.ai?.configured ? "Configurata" : "Da configurare", detail: [status.ai?.provider, status.ai?.model].filter(Boolean).join(" · ") },
    { label: "Email", ok: status.email?.configured, text: status.email?.configured ? (status.email?.enabled ? "Configurata e attiva" : "Configurata, invio disattivato") : "Da configurare", detail: "SMTP" },
  ] : [];
  return (
    <div className="space-y-4">
      <div className="settings-page-intro">
        <h2 className="font-display text-xl font-bold text-slate-900">Sistema, log e audit</h2>
        
      </div>
      <div className="settings-subnav">{tabs.map(([k,l]) => <button key={k} onClick={() => setTab(k)} className={`settings-subnav-btn ${tab===k?"active":""}`}>{l}</button>)}</div>
      {tab === "status" && <SectionCard title="Stato sistema" description="Controllo dei servizi usati dal Gestionale Elios Tech." right={<Button variant="outline" onClick={load} disabled={loading} className="h-10"><ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} /> Aggiorna</Button>}>
        {loading && !status ? <div className="text-sm text-slate-500">Controllo servizi in corso…</div> : loadError ? <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{loadError}</div> : <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">{cards.map((card) => <div key={card.label} className="rounded-lg border border-slate-200 p-4 min-w-0"><div className="text-sm font-semibold">{card.label}</div><div className="mt-2"><StatusPill ok={!!card.ok} label={card.text} /></div>{card.detail && <div className="mt-2 text-[11px] text-slate-500 break-words">{card.detail}</div>}</div>)}</div>}
      </SectionCard>}
      {tab === "audit" && <SectionCard title="Audit attività" description="Azioni amministrative, modifiche e operazioni rilevanti."><AuditLogTab /></SectionCard>}
      {tab === "logs" && <SectionCard title="Log sistema" description="Eventi applicativi e tecnici del gestionale."><SystemLogsTab /></SectionCard>}
      {tab === "maintenance" && <SectionCard title="Manutenzione" description="Strumenti amministrativi di manutenzione."><ManutenzioneTab /></SectionCard>}
    </div>
  );
}

export default function AdminPage() {
  const [category, setCategory] = useState("general");
  const current = useMemo(() => CATEGORIES.find((x) => x.key === category) || CATEGORIES[0], [category]);
  const CurrentIcon = current.icon;
  const Content = () => {
    if (category === "general") return <GeneralPane />;
    if (category === "users") return <UsersSecurityPane />;
    if (category === "ai") return <AIPane />;
    if (category === "warehouse") return <WarehousePane />;
    if (category === "operations") return <OperationsPane />;
    if (category === "notifications") return <NotificationsPane />;
    if (category === "data") return <NotionMigrationPane />;
    if (category === "system") return <SystemPane />;
    return <GeneralPane />;
  };
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8" data-testid="settings-page">
      <div className="mb-6">
        <h1 className="et-page-heading text-3xl sm:text-4xl">Impostazioni</h1>
      </div>
      <div className="grid lg:grid-cols-[270px_minmax(0,1fr)] gap-5 items-start">
        <aside className="bg-white border border-slate-200 rounded-xl p-2 lg:sticky lg:top-20 overflow-hidden">
          <div className="flex lg:block gap-2 overflow-x-auto lg:overflow-visible snap-x snap-mandatory pb-1 lg:pb-0">
            {CATEGORIES.map((item) => {
              const Icon = item.icon; const active = category === item.key;
              return <button key={item.key} type="button" onClick={() => setCategory(item.key)} className={`shrink-0 w-[190px] lg:w-full min-h-14 text-left flex items-start gap-3 rounded-xl px-3 py-3 lg:mb-1 snap-start border transition-colors ${active ? "bg-[#1A456B] text-white border-[#1A456B]" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50 hover:border-slate-300"}`}>
                <Icon size={19} className={active ? "text-white" : "text-slate-500"} />
                <span className="block text-sm font-bold">{item.label}</span>
              </button>;
            })}
          </div>
        </aside>
        <main className="min-w-0">
          <div className="mb-4 flex items-center gap-3"><div className="h-10 w-10 rounded-md bg-slate-950 text-amber-300 flex items-center justify-center"><CurrentIcon size={20} /></div><h2 className="text-xl font-bold text-slate-900">{current.label}</h2></div>
          <Content />
        </main>
      </div>
    </div>
  );
}
