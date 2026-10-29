from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new, label):
    text = read(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: atteso 1 match per {label}, trovati {count}")
    write(rel, text.replace(old, new, 1))


# -----------------------------------------------------------------------------
# 1) Backend: completa il mapping permessi delle route CRM statiche/speciali.
# -----------------------------------------------------------------------------
replace_once(
    "backend/auth.py",
    '''            "ordini-clienti": "ordini_clienti",
            "installazioni": "installazioni",
            "assistenza": "assistenza",
''',
    '''            "ordini-clienti": "ordini_clienti",
            "clienti-summary": "ordini_clienti",
            "ordini-insights": "commesse",
            "installazioni": "installazioni",
            "interventi-tecnici": "installazioni",
            "assistenza": "assistenza",
''',
    "mapping route CRM speciali",
)

# Regressione permanente: il system audit deve fallire se queste route tornano
# prive di mapping permessi.
replace_once(
    "backend/system_audit.py",
    '''sys.path.insert(0, str(BACKEND))

try:
    import server  # noqa: E402
''',
    '''sys.path.insert(0, str(BACKEND))

# Le route CRM statiche, che non coincidono con una chiave RESOURCES, devono
# essere mappate esplicitamente al modulo autorizzativo corretto.
try:
    import auth as audit_auth  # noqa: E402
    from types import SimpleNamespace

    permission_cases = [
        ("GET", "/api/crm/clienti-summary", ("ordini_clienti", "view")),
        ("GET", "/api/crm/ordini-insights", ("commesse", "view")),
        ("GET", "/api/crm/interventi-tecnici", ("installazioni", "view")),
        ("POST", "/api/crm/interventi-tecnici", ("installazioni", "create")),
    ]
    for method, path, expected in permission_cases:
        req = SimpleNamespace(method=method, url=SimpleNamespace(path=path))
        actual = audit_auth._request_module_action(req)
        if actual != expected:
            issue(f"Mapping permesso errato per {method} {path}: {actual!r}, atteso {expected!r}")
        else:
            ok(f"Mapping permesso {method} {path} -> {expected[0]}/{expected[1]}")
except Exception as exc:
    issue(f"Verifica mapping permessi fallita: {type(exc).__name__}: {exc}")

try:
    import server  # noqa: E402
''',
    "regressione mapping permessi",
)


# -----------------------------------------------------------------------------
# 2) Dashboard: non interroga né mostra moduli che l'utente non può vedere.
# -----------------------------------------------------------------------------
dashboard = "frontend/src/pages/DashboardPage.jsx"
replace_once(
    dashboard,
    'import { formatDateIT } from "../lib/dateFmt";\n',
    'import { formatDateIT } from "../lib/dateFmt";\nimport { useAuth } from "../lib/AuthContext";\n',
    "import useAuth dashboard",
)
replace_once(
    dashboard,
    '''export default function DashboardPage() {
  const [data, setData] = useState({ clienti: [], sedi: [], sopralluoghi: [], preventivi: [], ordini: [], installazioni: [], assistenza: [], anomalie: [], sottoScorta: [], esauriti: [] });
''',
    '''export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState({ clienti: [], sedi: [], sopralluoghi: [], preventivi: [], ordini: [], installazioni: [], assistenza: [], anomalie: [], sottoScorta: [], esauriti: [] });
''',
    "utente dashboard",
)
replace_once(
    dashboard,
    '''  const [refreshedAt, setRefreshedAt] = useState(null);
  const [refreshSeconds, setRefreshSeconds] = useState(0);

  const safeGet = useCallback(async (url, fallback) => {
''',
    '''  const [refreshedAt, setRefreshedAt] = useState(null);
  const [refreshSeconds, setRefreshSeconds] = useState(0);

  const canView = useCallback((module) => {
    if (!user) return false;
    if (user.role === "admin") return true;
    const perms = Array.isArray(user.effective_permissions)
      ? user.effective_permissions
      : (Array.isArray(user.permissions) ? user.permissions : []);
    return perms.includes(module) || perms.includes(`${module}:view`);
  }, [user]);

  const safeGet = useCallback(async (url, fallback) => {
''',
    "helper permessi dashboard",
)
replace_once(
    dashboard,
    '''      const [clienti, sedi, sopralluoghi, preventivi, ordini, installazioni, assistenza, anomalie, kpi] = await Promise.all([
        safeGet(`${API}/crm/clienti`, { items: [] }),
        safeGet(`${API}/crm/sedi`, { items: [] }),
        safeGet(`${API}/crm/sopralluoghi`, { items: [] }),
        safeGet(`${API}/crm/preventivi`, { items: [] }),
        safeGet(`${API}/crm/ordini-clienti`, { items: [] }),
        safeGet(`${API}/crm/installazioni`, { items: [] }),
        safeGet(`${API}/crm/assistenza`, { items: [] }),
        safeGet(`${API}/anomalie?limit=200`, { items: [] }),
        safeGet(`${API}/dashboard/kpi`, {}),
      ]);
''',
    '''      const emptyItems = Promise.resolve({ items: [] });
      const emptyObject = Promise.resolve({});
      const [clienti, sedi, sopralluoghi, preventivi, ordini, installazioni, assistenza, anomalie, kpi] = await Promise.all([
        canView("ordini_clienti") ? safeGet(`${API}/crm/clienti`, { items: [] }) : emptyItems,
        canView("ordini_clienti") ? safeGet(`${API}/crm/sedi`, { items: [] }) : emptyItems,
        canView("sopralluoghi") ? safeGet(`${API}/crm/sopralluoghi`, { items: [] }) : emptyItems,
        canView("preventivi") ? safeGet(`${API}/crm/preventivi`, { items: [] }) : emptyItems,
        canView("ordini_clienti") ? safeGet(`${API}/crm/ordini-clienti`, { items: [] }) : emptyItems,
        canView("installazioni") ? safeGet(`${API}/crm/installazioni`, { items: [] }) : emptyItems,
        canView("assistenza") ? safeGet(`${API}/crm/assistenza`, { items: [] }) : emptyItems,
        canView("anomalie") ? safeGet(`${API}/anomalie?limit=200`, { items: [] }) : emptyItems,
        canView("inventario") ? safeGet(`${API}/dashboard/kpi`, {}) : emptyObject,
      ]);
''',
    "fetch dashboard per permessi",
)
replace_once(
    dashboard,
    '''  }, [safeGet]);
''',
    '''  }, [safeGet, canView]);
''',
    "dipendenze load dashboard",
)

replace_once(
    dashboard,
    '''  const clientName = useCallback((id) => { const c = clientiById[String(id)] || {}; return c.ragione_sociale || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente"; }, [clientiById]);
  const siteName = useCallback((id) => { const s = sediById[String(id)] || {}; return s.nome || [s.indirizzo, s.comune].filter(Boolean).join(" · ") || "Sede"; }, [sediById]);
''',
    '''  const clientName = useCallback((id) => { const c = clientiById[String(id)] || {}; return c.ragione_sociale || [c.nome, c.cognome].filter(Boolean).join(" ") || "Cliente"; }, [clientiById]);
  const siteName = useCallback((id) => { const s = sediById[String(id)] || {}; return s.nome || [s.indirizzo, s.comune].filter(Boolean).join(" · ") || "Sede"; }, [sediById]);
  const recordClientName = useCallback((x) => x?.cliente_nome || x?.nominativo || clientName(x?.cliente_id), [clientName]);
  const recordSiteName = useCallback((x) => x?.sede_nome || x?.sede || siteName(x?.sede_id), [siteName]);
''',
    "nomi record dashboard",
)

# Le installazioni sono già arricchite dal backend con cliente_nome/sede_nome;
# usiamo quei campi quando Clienti e ordini non è accessibile.
replace_once(
    dashboard,
    '''subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`''',
    '''subtitle: `${recordClientName(x)} · ${recordSiteName(x)}`''',
    "installazione sospesa nomi arricchiti",
)
replace_once(
    dashboard,
    '''subtitle: `${clientName(x.cliente_id)} · ${siteName(x.sede_id)}`, detail: x.data ? `Data: ${formatDateIT(x.data)}`''',
    '''subtitle: `${recordClientName(x)} · ${recordSiteName(x)}`, detail: x.data ? `Data: ${formatDateIT(x.data)}`''',
    "installazione da gestire nomi arricchiti",
)

replace_once(
    dashboard,
    '''  }, [data.assistenza, data.installazioni, data.sopralluoghi, data.preventivi, data.anomalie, clientName, siteName]);

  const quickFlow = [
    [ShoppingCart, "Clienti e ordini", "/clienti-ordini"],
    [Wrench, "Commesse", "/commesse"],
    [ClipboardText, "Sopralluoghi", "/sopralluoghi"],
    [FileText, "Preventivi", "/preventivi"],
    [CalendarBlank, "Calendario", "/calendario"],
    [Wrench, "Installazioni", "/installazioni"],
    [Headset, "Assistenza", "/assistenza"],
  ];
''',
    '''  }, [data.assistenza, data.installazioni, data.sopralluoghi, data.preventivi, data.anomalie, clientName, siteName, recordClientName, recordSiteName]);

  const quickFlow = [
    [ShoppingCart, "Clienti e ordini", "/clienti-ordini", "ordini_clienti"],
    [Wrench, "Commesse", "/commesse", "commesse"],
    [ClipboardText, "Sopralluoghi", "/sopralluoghi", "sopralluoghi"],
    [FileText, "Preventivi", "/preventivi", "preventivi"],
    [CalendarBlank, "Calendario", "/calendario", "calendar"],
    [Wrench, "Installazioni", "/installazioni", "installazioni"],
    [Headset, "Assistenza", "/assistenza", "assistenza"],
  ].filter(([, , , module]) => canView(module));
''',
    "quick flow per permessi",
)

replace_once(
    dashboard,
    '''          <StatCard icon={CalendarBlank} title="Programmate" value={programmate.length} meta={`${programmateOggi} oggi`} to="/installazioni" tone="blue" />
          <StatCard icon={Wrench} title="Da installare" value={daInstallare.length} meta="da programmare / confermate" to="/installazioni" tone="navy" />
          <StatCard icon={Headset} title="Assistenze" value={assistenzeAperte.length} meta="aperte o in lavorazione" to="/assistenza" tone="teal" />
          <StatCard icon={ClipboardText} title="Sopralluoghi" value={sopralluoghiAperti.length} meta="da gestire" to="/sopralluoghi" tone="violet" />
          <StatCard icon={ShoppingCart} title="Ordini aperti" value={ordiniAperti.length} meta={`${preventiviAperti.length} preventivi aperti`} to="/clienti-ordini" tone="amber" />
          <StatCard icon={Package} title="Magazzino critico" value={magazzinoCritico} meta={`${data.esauriti.length} esauriti`} to="/inventario" tone="red" />
''',
    '''          {canView("installazioni") && <StatCard icon={CalendarBlank} title="Programmate" value={programmate.length} meta={`${programmateOggi} oggi`} to="/installazioni" tone="blue" />}
          {canView("installazioni") && <StatCard icon={Wrench} title="Da installare" value={daInstallare.length} meta="da programmare / confermate" to="/installazioni" tone="navy" />}
          {canView("assistenza") && <StatCard icon={Headset} title="Assistenze" value={assistenzeAperte.length} meta="aperte o in lavorazione" to="/assistenza" tone="teal" />}
          {canView("sopralluoghi") && <StatCard icon={ClipboardText} title="Sopralluoghi" value={sopralluoghiAperti.length} meta="da gestire" to="/sopralluoghi" tone="violet" />}
          {canView("ordini_clienti") && <StatCard icon={ShoppingCart} title="Ordini aperti" value={ordiniAperti.length} meta={canView("preventivi") ? `${preventiviAperti.length} preventivi aperti` : "ordini da gestire"} to="/clienti-ordini" tone="amber" />}
          {canView("inventario") && <StatCard icon={Package} title="Magazzino critico" value={magazzinoCritico} meta={`${data.esauriti.length} esauriti`} to="/inventario" tone="red" />}
''',
    "stat card per permessi",
)
replace_once(
    dashboard,
    '''            {quickFlow.map(([Icon, label, to], i) => (
''',
    '''            {quickFlow.map(([Icon, label, to], i) => (
''',
    "quickflow mantiene rendering compatibile",
)


# -----------------------------------------------------------------------------
# 3) Report installazione: usa il popup di conferma uniforme dell'app.
# -----------------------------------------------------------------------------
free_reports = "frontend/src/pages/FreeReportsPage.jsx"
replace_once(
    free_reports,
    'import StandaloneInstallationReportDialog from "../components/StandaloneInstallationReportDialog";\n',
    'import StandaloneInstallationReportDialog from "../components/StandaloneInstallationReportDialog";\nimport { appConfirm } from "../lib/appConfirm";\n',
    "import appConfirm report liberi",
)
replace_once(
    free_reports,
    '''  const remove=async(r)=>{if(!window.confirm(`Eliminare il report “${r.title||"Report pre e post installazione"}”?`))return;try{await axios.delete(`${API}/free-reports/${r.id}`);toast.success("Report eliminato");await load()}catch(e){toast.error(e?.response?.data?.detail||"Impossibile eliminare il report")}};
''',
    '''  const remove=async(r)=>{if(!(await appConfirm({title:"Elimina report installazione",message:`Eliminare definitivamente il report “${r.title||"Report pre e post installazione"}”?`,confirmLabel:"Elimina",danger:true})))return;try{await axios.delete(`${API}/free-reports/${r.id}`);toast.success("Report eliminato");await load()}catch(e){toast.error(e?.response?.data?.detail||"Impossibile eliminare il report")}};
''',
    "conferma uniforme report liberi",
)

write("VERSION", "R7\n")

# Guardrail finali.
auth = read("backend/auth.py")
dash = read(dashboard)
free = read(free_reports)
audit = read("backend/system_audit.py")
for needle in ('"clienti-summary": "ordini_clienti"', '"ordini-insights": "commesse"', '"interventi-tecnici": "installazioni"'):
    assert needle in auth, needle
assert '/api/crm/ordini-insights' in audit and '/api/crm/interventi-tecnici' in audit
assert 'const { user } = useAuth();' in dash
assert 'canView("inventario") ? safeGet' in dash
assert '.filter(([, , , module]) => canView(module))' in dash
assert 'window.confirm' not in free
assert 'appConfirm' in free
print("R7 hardening applicato correttamente")
