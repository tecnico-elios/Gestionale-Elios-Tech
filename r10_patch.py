from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: attesa 1 occorrenza, trovate {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# VERSION
Path("VERSION").write_text("R10\n", encoding="utf-8")

# Backend: nuova sezione operativo nelle impostazioni Admin.
replace_once(
    "backend/routes/admin_extra_routes.py",
    '''class RetroattivitaSettings(BaseModel):
    """F14 §9 — Impostazioni retroattività."""
    model_config = ConfigDict(extra="ignore")
    email_enabled: Optional[bool] = None              # invio email automatico dopo save success


# Lista IANA supportata''',
    '''class RetroattivitaSettings(BaseModel):
    """F14 §9 — Impostazioni retroattività."""
    model_config = ConfigDict(extra="ignore")
    email_enabled: Optional[bool] = None              # invio email automatico dopo save success


class OperativoSettings(BaseModel):
    """R10 — Opzioni operative modificabili dall'Admin senza cambiare codice."""
    model_config = ConfigDict(extra="ignore")
    sopralluoghi_stati: Optional[List[str]] = None
    assistenza_tipi: Optional[List[str]] = None
    assistenza_priorita: Optional[List[str]] = None
    assistenza_stati: Optional[List[str]] = None


# Lista IANA supportata''',
)

replace_once(
    "backend/routes/admin_extra_routes.py",
    '''    # F14 Retroattività
    retroattivita: Optional[RetroattivitaSettings] = None
    # F8 general (timezone)
    general: Optional[GeneralSettings] = None''',
    '''    # F14 Retroattività
    retroattivita: Optional[RetroattivitaSettings] = None
    # R10 opzioni operative configurabili
    operativo: Optional[OperativoSettings] = None
    # F8 general (timezone)
    general: Optional[GeneralSettings] = None''',
)

replace_once(
    "backend/routes/admin_extra_routes.py",
    '''    "retroattivita": {
        "email_enabled": False,   # F14 §9 — default OFF (no email)
    },
    "general": {''',
    '''    "retroattivita": {
        "email_enabled": False,   # F14 §9 — default OFF (no email)
    },
    "operativo": {
        "sopralluoghi_stati": ["Da programmare", "Programmato", "Eseguito", "Annullato"],
        "assistenza_tipi": ["Remota", "In loco"],
        "assistenza_priorita": ["Bassa", "Normale", "Alta", "Urgente"],
        "assistenza_stati": [
            "Aperta", "Da programmare", "Programmata", "In lavorazione",
            "In attesa cliente / fornitore", "Tecnico in intervento", "Risolta", "Completata", "Chiusa",
        ],
    },
    "general": {''',
)

replace_once(
    "backend/routes/admin_extra_routes.py",
    '''    for section in ("scanner", "dashboard", "magazzino", "ricerca", "movimenti", "sicurezza", "arrivi", "spedizioni", "retroattivita", "general"):
        result[section] = _merge_section(DEFAULT_SETTINGS[section], doc.get(section))''',
    '''    for section in ("scanner", "dashboard", "magazzino", "ricerca", "movimenti", "sicurezza", "arrivi", "spedizioni", "retroattivita", "operativo", "general"):
        result[section] = _merge_section(DEFAULT_SETTINGS[section], doc.get(section))''',
)

replace_once(
    "backend/routes/admin_extra_routes.py",
    '''            ("arrivi", body.arrivi),
            ("spedizioni", body.spedizioni),
            ("general", body.general),''',
    '''            ("arrivi", body.arrivi),
            ("spedizioni", body.spedizioni),
            ("operativo", body.operativo),
            ("general", body.general),''',
)

replace_once(
    "backend/routes/admin_extra_routes.py",
    '''            if not section_dict:
                continue
            # F8: valida timezone IANA''',
    '''            if not section_dict:
                continue
            if section_name == "operativo":
                normalized = {}
                for key, values in section_dict.items():
                    cleaned = []
                    for value in values or []:
                        item = str(value or "").strip()
                        if item and item not in cleaned:
                            cleaned.append(item)
                    if not cleaned:
                        raise HTTPException(400, f"{key}: inserisci almeno una voce")
                    if len(cleaned) > 30:
                        raise HTTPException(400, f"{key}: massimo 30 voci")
                    if any(len(item) > 80 for item in cleaned):
                        raise HTTPException(400, f"{key}: ogni voce può avere massimo 80 caratteri")
                    normalized[key] = cleaned
                section_dict = normalized
            # F8: valida timezone IANA''',
)

# Endpoint autenticato e non sensibile: rende disponibili le opzioni operative anche ai non-admin.
replace_once(
    "backend/server.py",
    '''@api_router.get("/")
async def root():
    return {"status": "ok", "service": "Gestionale Elios Tech", "database": "locale"}


@api_router.get("/inventory", dependencies=[Depends(dep_current_user)])''',
    '''@api_router.get("/")
async def root():
    return {"status": "ok", "service": "Gestionale Elios Tech", "database": "locale"}


@api_router.get("/operational-options", dependencies=[Depends(dep_current_user)])
async def operational_options():
    settings = await admin_extra_routes.get_app_settings(db)
    return settings.get("operativo") or admin_extra_routes.DEFAULT_SETTINGS["operativo"]


@api_router.get("/inventory", dependencies=[Depends(dep_current_user)])''',
)

# Frontend: hook condiviso per le opzioni operative.
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''import RegistryPage from "./RegistryPage";
import InstallazioniCalendarPage from "./InstallazioniCalendarPage";''',
    '''import { useEffect, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import RegistryPage from "./RegistryPage";
import InstallazioniCalendarPage from "./InstallazioniCalendarPage";''',
)

replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''const COMMESSA_LOOKUP = { lookupEndpoint: "crm/lookups/commesse", lookupKey: "commesse", lookupLabel: commessaLabel };

export const ClientiPage''',
    '''const COMMESSA_LOOKUP = { lookupEndpoint: "crm/lookups/commesse", lookupKey: "commesse", lookupLabel: commessaLabel };

const DEFAULT_OPERATIONAL_OPTIONS = {
  sopralluoghi_stati: ["Da programmare", "Programmato", "Eseguito", "Annullato"],
  assistenza_tipi: ["Remota", "In loco"],
  assistenza_priorita: ["Bassa", "Normale", "Alta", "Urgente"],
  assistenza_stati: ["Aperta", "Da programmare", "Programmata", "In lavorazione", "In attesa cliente / fornitore", "Tecnico in intervento", "Risolta", "Completata", "Chiusa"],
};

function useOperationalOptions() {
  const [options, setOptions] = useState(DEFAULT_OPERATIONAL_OPTIONS);
  useEffect(() => {
    let active = true;
    axios.get(`${API}/operational-options`).then(({ data }) => {
      if (!active || !data) return;
      setOptions({ ...DEFAULT_OPERATIONAL_OPTIONS, ...data });
    }).catch(() => {
      // Fallback locale: le pagine restano operative anche durante un errore di rete temporaneo.
    });
    return () => { active = false; };
  }, []);
  return options;
}

export const ClientiPage''',
)

replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''export const SopralluoghiPage = () => (
  <RegistryPage''',
    '''export const SopralluoghiPage = () => {
  const operational = useOperationalOptions();
  return (
  <RegistryPage''',
)
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''      F("stato", "Stato", { options: ["Da programmare", "Programmato", "Eseguito", "Annullato"], default: "Da programmare" }),''',
    '''      F("stato", "Stato", { options: operational.sopralluoghi_stati, default: operational.sopralluoghi_stati?.[0] || "Da programmare" }),''',
)
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''  />
);

export const PreventiviPage''',
    '''  />
  );
};

export const PreventiviPage''',
)

replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''export const AssistenzaPage = () => (
  <RegistryPage''',
    '''export const AssistenzaPage = () => {
  const operational = useOperationalOptions();
  return (
  <RegistryPage''',
)
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''      F("tipo", "Tipo assistenza", { options: ["Remota", "In loco"], default: "Remota" }),
      F("priorita", "Priorità", { options: ["Bassa", "Normale", "Alta", "Urgente"], default: "Normale" }),''',
    '''      F("tipo", "Tipo assistenza", { options: operational.assistenza_tipi, default: operational.assistenza_tipi?.[0] || "Remota" }),
      F("priorita", "Priorità", { options: operational.assistenza_priorita, default: operational.assistenza_priorita?.includes("Normale") ? "Normale" : (operational.assistenza_priorita?.[0] || "Normale") }),''',
)
replace_once(
    "frontend/src/pages/BusinessPages.jsx",
    '''      F("stato", "Stato", { options: ["Aperta", "Da programmare", "Programmata", "In lavorazione", "In attesa cliente / fornitore", "Tecnico in intervento", "Risolta", "Completata", "Chiusa"], default: "Aperta" }),''',
    '''      F("stato", "Stato", { options: operational.assistenza_stati, default: operational.assistenza_stati?.[0] || "Aperta" }),''',
)

p = Path("frontend/src/pages/BusinessPages.jsx")
text = p.read_text(encoding="utf-8")
old_suffix = '''  />
);\n'''
if not text.endswith(old_suffix):
    raise SystemExit("BusinessPages.jsx: finale Assistenza inatteso")
p.write_text(text[:-len(old_suffix)] + '''  />
  );
};\n''', encoding="utf-8")

# Registry: preserva valori storici non più presenti nella configurazione Admin.
replace_once(
    "frontend/src/pages/RegistryPage.jsx",
    '''                        <option value="">Seleziona...</option>
                        {f.options.map((o) => <option key={o} value={o}>{o}</option>)}''',
    '''                        <option value="">Seleziona...</option>
                        {form[f.key] && !f.options.some((o) => String(o) === String(form[f.key])) && (
                          <option value={form[f.key]}>{form[f.key]} (storico)</option>
                        )}
                        {f.options.map((o) => <option key={o} value={o}>{o}</option>)}''',
)

# Admin: nuova scheda Stati e priorità nel flusso operativo.
replace_once(
    "frontend/src/pages/AdminPage.jsx",
    '''function OperationsPane() {
  const [tab, setTab] = useState("arrivi");''',
    '''function OperationalOptionsPane() {
  const [options, setOptions] = useState(null);
  const [saving, setSaving] = useState(false);
  const fields = [
    ["sopralluoghi_stati", "Stati sopralluoghi", "Una voce per riga. Il primo valore diventa lo stato predefinito dei nuovi sopralluoghi."],
    ["assistenza_tipi", "Tipi assistenza", "Esempio: Remota, In loco."],
    ["assistenza_priorita", "Priorità assistenza", "Le priorità disponibili nei ticket di assistenza."],
    ["assistenza_stati", "Stati assistenza", "Il primo valore diventa lo stato predefinito dei nuovi ticket."],
  ];
  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/admin/settings`);
      setOptions(data.operativo || {});
    } catch (e) {
      toast.error("Impossibile caricare stati e priorità", { description: formatError(e) });
    }
  };
  useEffect(() => { load(); }, []);
  const update = (key, value) => setOptions((prev) => ({ ...(prev || {}), [key]: value.split("\\n") }));
  const save = async () => {
    const cleaned = {};
    for (const [key, label] of fields) {
      const seen = new Set();
      cleaned[key] = (options?.[key] || []).map((x) => String(x || "").trim()).filter((x) => x && !seen.has(x) && seen.add(x));
      if (!cleaned[key].length) return toast.error(`${label}: inserisci almeno una voce`);
    }
    setSaving(true);
    try {
      const { data } = await axios.put(`${API}/admin/settings`, { operativo: cleaned });
      setOptions(data.operativo || cleaned);
      window.dispatchEvent(new Event("elios:settings-changed"));
      toast.success("Stati e priorità salvati");
    } catch (e) {
      toast.error("Salvataggio stati e priorità fallito", { description: formatError(e) });
    } finally { setSaving(false); }
  };
  if (!options) return <div className="text-sm text-slate-500">Caricamento…</div>;
  return <SectionCard title="Stati e priorità operative" description="Configura le voci usate nei moduli operativi attivi.">
    <div className="mb-4 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
      Inserisci una voce per riga. I record già esistenti mantengono il proprio valore anche se una voce viene rimossa in seguito.
    </div>
    <div className="grid lg:grid-cols-2 gap-4">
      {fields.map(([key, label, hint]) => <div key={key}>
        <Label>{label}</Label>
        <textarea
          rows={key === "assistenza_stati" ? 9 : 5}
          className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 focus:outline-none focus:ring-2 focus:ring-slate-300"
          value={(options[key] || []).join("\\n")}
          onChange={(e) => update(key, e.target.value)}
        />
        <p className="mt-1 text-xs text-slate-500">{hint}</p>
      </div>)}
    </div>
    <div className="mt-4 flex justify-end"><Button onClick={save} disabled={saving} className="h-11 et-btn-primary">{saving ? "Salvataggio…" : "Salva stati e priorità"}</Button></div>
  </SectionCard>;
}

function OperationsPane() {
  const [tab, setTab] = useState("arrivi");''',
)

replace_once(
    "frontend/src/pages/AdminPage.jsx",
    '''  const tabs = [["arrivi","Arrivi"],["spedizioni","Spedizioni"],["workflow","Automazioni"]];''',
    '''  const tabs = [["arrivi","Arrivi"],["spedizioni","Spedizioni"],["options","Stati e priorità"],["workflow","Automazioni"]];''',
)

replace_once(
    "frontend/src/pages/AdminPage.jsx",
    '''      {tab === "spedizioni" && <SectionCard title="Spedizioni" description="Controlli applicati prima dell'uscita del materiale."><SettingsSpedizioniTab /></SectionCard>}
      {tab === "workflow" && <SectionCard''',
    '''      {tab === "spedizioni" && <SectionCard title="Spedizioni" description="Controlli applicati prima dell'uscita del materiale."><SettingsSpedizioniTab /></SectionCard>}
      {tab === "options" && <OperationalOptionsPane />}
      {tab === "workflow" && <SectionCard''',
)

# Smoke test R10: salvataggio Admin + lettura endpoint operativo autenticato.
replace_once(
    "backend/integration_smoke.py",
    '''    me = expect("GET", "/api/auth/me", token=token).json()
    assert me.get("username") == "auditadmin" and me.get("role") == "admin", me

    # Feature flag pubblico e aree principali autenticate.''',
    '''    me = expect("GET", "/api/auth/me", token=token).json()
    assert me.get("username") == "auditadmin" and me.get("role") == "admin", me

    # R10: opzioni operative configurabili da Admin e leggibili da ogni utente autenticato.
    admin_settings = expect("GET", "/api/admin/settings", token=token).json()
    operativo = admin_settings.get("operativo") or {}
    assert operativo.get("sopralluoghi_stati") and operativo.get("assistenza_stati"), operativo
    probe = {k: list(v) for k, v in operativo.items()}
    probe["sopralluoghi_stati"] = list(probe["sopralluoghi_stati"]) + ["Verifica R10"]
    saved_settings = expect("PUT", "/api/admin/settings", token=token, json={"operativo": probe}).json()
    assert "Verifica R10" in saved_settings.get("operativo", {}).get("sopralluoghi_stati", []), saved_settings
    public_options = expect("GET", "/api/operational-options", token=token).json()
    assert "Verifica R10" in public_options.get("sopralluoghi_stati", []), public_options

    # Feature flag pubblico e aree principali autenticate.''',
)

print("R10 patch applicata con successo")
