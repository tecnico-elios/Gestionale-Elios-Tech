import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/apiBase";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  House, Package, ArrowsClockwise, Warning, Gear, SignOut, UsersThree,
  CaretDown, CaretRight, Lock, Robot, ClipboardText, FileText, ShoppingCart,
  Wrench, Headset, List, X, CalendarBlank, SlidersHorizontal, ChartBar,
  Lightning, Database, ArrowsLeftRight,
} from "@phosphor-icons/react";
import { useInventoryCtx } from "../lib/InventoryContext";
import { useAuth } from "../lib/AuthContext";
import ChangeMyPasswordDialog from "./ChangeMyPasswordDialog";
import EliosLogo from "./EliosLogo";
import { fmtTime } from "../lib/tz";

const SECTION_META = [
  { key: "amministrazione", label: "Amministrazione", icon: FileText },
  { key: "tecnico", label: "Tecnico", icon: Wrench },
  { key: "gestione", label: "Gestione", icon: Package },
  { key: "sistema", label: "Sistema", icon: SlidersHorizontal },
];

const NATIVE_ITEMS = [
  { key: "dashboard", to: "/dashboard", label: "Dashboard", icon: House, testid: "nav-dashboard", module: "dashboard", section: "principale", order: 10 },
  { key: "calendar", to: "/calendario", label: "Calendario", icon: CalendarBlank, testid: "nav-calendar", module: "calendar", section: "principale", order: 20 },
  { key: "ordini_clienti", to: "/clienti-ordini", label: "Clienti e ordini", icon: ShoppingCart, testid: "nav-elios-tech-ordini", module: "ordini_clienti", section: "amministrazione", order: 10 },
  { key: "commesse", to: "/commesse", label: "Commesse", icon: Wrench, testid: "nav-commesse", module: "commesse", section: "amministrazione", order: 20 },
  { key: "fatturato", to: "/fatturato", label: "Fatturato", icon: ChartBar, testid: "nav-fatturato", module: "commesse", section: "amministrazione", order: 30 },
  { key: "wallbox", to: "/wallbox", label: "Wallbox", icon: Lightning, testid: "nav-wallbox", module: "commesse", section: "amministrazione", order: 40 },
  { key: "report", to: "/report", label: "Report attività", icon: FileText, testid: "nav-report", module: "commesse", section: "amministrazione", order: 50 },
  { key: "sopralluoghi", to: "/sopralluoghi", label: "Sopralluoghi", icon: ClipboardText, testid: "nav-sopralluoghi", module: "sopralluoghi", section: "tecnico", order: 10 },
  { key: "preventivi", to: "/preventivi", label: "Preventivi", icon: FileText, testid: "nav-preventivi", module: "preventivi", section: "tecnico", order: 20 },
  { key: "installazioni", to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni", section: "tecnico", order: 30 },
  { key: "report_liberi", to: "/report-liberi", label: "Report installazione", icon: FileText, testid: "nav-report-liberi", module: "installazioni", section: "tecnico", order: 40 },
  { key: "interventi_tecnici", to: "/interventi-tecnici", label: "Interventi tecnici", icon: Wrench, testid: "nav-interventi-tecnici", module: "installazioni", section: "tecnico", order: 50 },
  { key: "assistenza", to: "/assistenza", label: "Assistenza", icon: Headset, testid: "nav-assistenza", module: "assistenza", section: "tecnico", order: 60 },
  { key: "inventario", to: "/inventario", label: "Magazzino Elios Tech", icon: Package, testid: "nav-inventario", module: "inventario", section: "gestione", order: 10 },
  { key: "magazzino_verona", to: "/magazzino-verona", label: "Magazzino Verona", icon: Package, testid: "nav-magazzino-verona", module: "inventario", section: "gestione", order: 20 },
  { key: "trasferimenti", to: "/trasferimenti", label: "Trasferimenti", icon: ArrowsLeftRight, testid: "nav-trasferimenti", module: "movimenti", section: "gestione", order: 30 },
  { key: "arrivi", to: "/arrivi", label: "Arrivi", icon: ArrowsClockwise, testid: "nav-arrivi", module: "arrivi", section: "gestione", order: 40 },
  { key: "spedizioni", to: "/spedizioni", label: "Spedizioni", icon: Package, testid: "nav-spedizioni", module: "spedizioni", section: "gestione", order: 50 },
  { key: "movimenti", to: "/movimenti", label: "Movimenti", icon: ArrowsClockwise, testid: "nav-movimenti", module: "movimenti", section: "gestione", order: 60 },
  { key: "anomalie", to: "/anomalie", label: "Anomalie", icon: Warning, testid: "nav-anomalie", module: "anomalie", section: "gestione", order: 70 },
  { key: "ai", to: "/assistente-ai", label: "Assistente", icon: Robot, testid: "nav-ai", module: "ai", section: "sistema", order: 10 },
];

const PAGE_META = {
  "/dashboard": { section: "principale", eyebrow: "Operativo", icon: House, description: "Attività, scadenze e dati principali." },
  "/calendario": { section: "principale", eyebrow: "Operativo", icon: CalendarBlank, description: "Settimana operativa: interventi, sopralluoghi e assistenze." },
  "/clienti-ordini": { section: "amministrazione", eyebrow: "Amministrazione", icon: ShoppingCart, description: "Clienti e ordini, dal più recente." },
  "/commesse": { section: "amministrazione", eyebrow: "Amministrazione", icon: Wrench, description: "Commesse attive, materiali e avanzamento." },
  "/fatturato": { section: "amministrazione", eyebrow: "Amministrazione", icon: ChartBar, description: "Valore delle commesse per periodo." },
  "/wallbox": { section: "amministrazione", eyebrow: "Amministrazione", icon: Lightning, description: "Wallbox gestite e installate." },
  "/report": { section: "amministrazione", eyebrow: "Amministrazione", icon: FileText, description: "Attività giornaliere, ore lavorate e riepiloghi operativi." },
  "/report-liberi": { section: "tecnico", eyebrow: "Tecnico", icon: FileText, description: "Report pre e post installazione, anche senza collegamento obbligatorio." },
  "/sopralluoghi": { section: "tecnico", eyebrow: "Tecnico", icon: ClipboardText, description: "Sopralluoghi programmati e completati." },
  "/preventivi": { section: "tecnico", eyebrow: "Tecnico", icon: FileText, description: "Preventivi, revisioni e stato." },
  "/installazioni": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Installazioni ENRICO e RICCARDO, programmate e completate." },
  "/interventi-tecnici": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Interventi tecnici di RICCARDO, storici e futuri, separati dalle installazioni." },
  "/assistenza": { section: "tecnico", eyebrow: "Tecnico", icon: Headset, description: "Richieste e interventi di assistenza." },
  "/inventario": { section: "gestione", eyebrow: "Gestione", icon: Package, description: "Giacenze e seriali · sede Elios Tech." },
  "/magazzino-verona": { section: "gestione", eyebrow: "Gestione", icon: Package, description: "Giacenze e seriali · sede Verona." },
  "/trasferimenti": { section: "gestione", eyebrow: "Gestione", icon: ArrowsLeftRight, description: "Spostamenti tra Elios Tech e Verona." },
  "/arrivi": { section: "gestione", eyebrow: "Gestione", icon: ArrowsClockwise, description: "Materiale ricevuto e caricato a magazzino." },
  "/spedizioni": { section: "gestione", eyebrow: "Gestione", icon: Package, description: "Materiale in uscita verso clienti e commesse." },
  "/movimenti": { section: "gestione", eyebrow: "Gestione", icon: ArrowsClockwise, description: "Storico di carichi, scarichi e rettifiche." },
  "/anomalie": { section: "gestione", eyebrow: "Gestione", icon: Warning, description: "Segnalazioni da controllare." },
  "/assistente-ai": { section: "sistema", eyebrow: "Sistema", icon: Robot, description: "Consulta i dati del gestionale." },
  "/admin": { section: "sistema", eyebrow: "Sistema", icon: Gear, description: "Preferenze generali e comportamento del sistema." },
  "/admin/utenti": { section: "sistema", eyebrow: "Sistema", icon: UsersThree, description: "Utenti, ruoli e accessi." },
  "/admin/moduli": { section: "sistema", eyebrow: "Sistema", icon: SlidersHorizontal, description: "Pagine, campi e moduli personalizzati." },
  "/admin/migrazione-notion": { section: "sistema", eyebrow: "Sistema", icon: Database, description: "Importazione una tantum dei dati storici." },
};

function SidebarLink({ item, onNavigate }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      data-testid={item.testid}
      className={({ isActive }) => `et-sidebar-link ${isActive ? "is-active" : ""}`}
    >
      {({ isActive }) => (
        <>
          <span className="et-sidebar-icon"><Icon size={17} weight={isActive ? "fill" : "regular"} /></span>
          <span className="truncate">{item.label}</span>
          {isActive && <span className="et-sidebar-active-dot" />}
        </>
      )}
    </NavLink>
  );
}

function Section({ section, items, open, onToggle, onNavigate }) {
  const Icon = section.icon;
  return (
    <div className="space-y-1">
      <button type="button" onClick={onToggle} className="et-sidebar-section" data-testid={`menu-section-${section.key}`}>
        <span className="flex items-center gap-3"><Icon size={17} /><span>{section.label}</span></span>
        {open ? <CaretDown size={14} /> : <CaretRight size={14} />}
      </button>
      {open && <div className="space-y-1 pb-2">{items.map((item) => <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />)}</div>}
    </div>
  );
}

export default function AppLayout() {
  const { refreshedAt, refresh, loading } = useInventoryCtx();
  const { user, logout, isAdmin, hasPermission } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window === "undefined" ? true : window.innerWidth >= 1024));
  const [menuOpen, setMenuOpen] = useState(false);
  const [pwdOpen, setPwdOpen] = useState(false);
  const [customModules, setCustomModules] = useState([]);
  const [navigationConfig, setNavigationConfig] = useState([]);
  const [generalSettings, setGeneralSettings] = useState({ app_name: "Gestionale Elios Tech", company_name: "Elios Tech S.r.l." });
  const [sectionResetKey, setSectionResetKey] = useState(0);
  const [notionFinalized, setNotionFinalized] = useState(false);

  const loadGeneralSettings = async () => {
    try {
      const { data } = await axios.get(`${API}/settings`);
      const general = data.general || {};
      setGeneralSettings((p) => ({ ...p, ...general }));
      if (general.app_name) document.title = general.app_name;
      try { window.localStorage.setItem("elios_general_settings", JSON.stringify(general)); } catch {}
      if (general.primary_color && /^#[0-9a-fA-F]{6}$/.test(general.primary_color)) {
        document.documentElement.style.setProperty("--et-brand-primary", general.primary_color);
      }
    } catch {}
  };
  const loadCustomModules = async () => {
    try { const { data } = await axios.get(`${API}/custom/modules`); setCustomModules(data.items || []); }
    catch { setCustomModules([]); }
  };
  const loadNavigationConfig = async () => {
    try { const { data } = await axios.get(`${API}/custom/config/navigation`); setNavigationConfig(data.items || []); }
    catch { setNavigationConfig([]); }
  };

  useEffect(() => {
    loadCustomModules(); loadNavigationConfig(); loadGeneralSettings();
    const modulesFn = () => loadCustomModules();
    const navFn = () => loadNavigationConfig();
    const settingsFn = () => loadGeneralSettings();
    window.addEventListener("elios:custom-modules-changed", modulesFn);
    window.addEventListener("elios:navigation-changed", navFn);
    window.addEventListener("elios:settings-changed", settingsFn);
    return () => {
      window.removeEventListener("elios:custom-modules-changed", modulesFn);
      window.removeEventListener("elios:navigation-changed", navFn);
      window.removeEventListener("elios:settings-changed", settingsFn);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isAdmin) { setNotionFinalized(false); return undefined; }
    let active = true;
    const loadNotionState = async () => {
      try {
        const { data } = await axios.get(`${API}/admin/notion/config`);
        if (active) setNotionFinalized(!!data?.completed);
      } catch (_) {}
    };
    loadNotionState();
    const onFinalized = () => loadNotionState();
    window.addEventListener("elios:notion-finalized", onFinalized);
    return () => { active = false; window.removeEventListener("elios:notion-finalized", onFinalized); };
  }, [isAdmin]);

  const navSettings = useMemo(() => Object.fromEntries((navigationConfig || []).map((x) => [x.key, x])), [navigationConfig]);
  const configuredNativeItems = useMemo(() => NATIVE_ITEMS.map((item) => {
    const cfg = navSettings[item.key] || {};
    const rawSection = cfg.section || item.section;
    return {
      ...item,
      label: ((item.key === "report" || item.key === "report_liberi") && String(cfg.label || "").trim().toLowerCase() === "report") ? item.label : (cfg.label || item.label),
      section: rawSection === "commerciale" ? "amministrazione" : rawSection,
      active: cfg.active !== false,
      order: Number(cfg.sort_order ?? item.order ?? 100),
    };
  }), [navSettings]);
  const allowedNativeItems = configuredNativeItems.filter((item) => item.active && (!item.module || hasPermission(item.module, "view")));
  const principalItems = allowedNativeItems.filter((item) => item.section === "principale").sort((a, b) => a.order - b.order);

  const systemExtra = isAdmin ? [
    { to: "/admin", label: "Impostazioni", icon: Gear, testid: "nav-admin", order: 900 },
    { to: "/admin/utenti", label: "Utenti e accessi", icon: UsersThree, testid: "nav-admin-users", order: 910 },
    { to: "/admin/moduli", label: "Struttura gestionale", icon: SlidersHorizontal, testid: "nav-module-builder", order: 920 },
    ...(!notionFinalized ? [{ to: "/admin/migrazione-notion", label: "Importazione da Notion", icon: Database, testid: "nav-notion-migration", order: 930 }] : []),
  ] : [];

  const sectionItems = (sectionKey) => {
    const native = allowedNativeItems.filter((item) => item.section === sectionKey);
    const dynamic = customModules
      .filter((m) => (m.section === "commerciale" ? "amministrazione" : (m.section || "amministrazione")) === sectionKey)
      .filter((m) => !String(m.slug || "").startsWith("report-"))
      .map((m) => ({ to: `/moduli/${m.slug}`, label: m.name, icon: FileText, testid: `nav-custom-${m.slug}`, order: Number(m.sort_order || 100) }));
    return [...native, ...dynamic, ...(sectionKey === "sistema" ? systemExtra : [])].sort((a, b) => Number(a.order || 100) - Number(b.order || 100));
  };

  const initialSection = useMemo(() => {
    const native = NATIVE_ITEMS.find((i) => location.pathname.startsWith(i.to));
    return native?.section || (location.pathname.startsWith("/admin") ? "sistema" : "amministrazione");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [openSections, setOpenSections] = useState({
    amministrazione: initialSection === "amministrazione",
    tecnico: initialSection === "tecnico",
    gestione: initialSection === "gestione",
    sistema: initialSection === "sistema" || location.pathname.startsWith("/admin"),
  });

  useEffect(() => {
    const native = configuredNativeItems.find((i) => location.pathname.startsWith(i.to));
    const custom = customModules.find((m) => location.pathname.startsWith(`/moduli/${m.slug}`));
    let key = location.pathname.startsWith("/admin") ? "sistema" : (custom?.section || native?.section);
    if (key === "commerciale") key = "amministrazione";
    if (key && key !== "principale") setOpenSections((prev) => ({ ...prev, [key]: true }));
  }, [location.pathname, customModules, configuredNativeItems]);

  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [location.pathname]);

  const resetSectionAndNavigate = () => {
    setSectionResetKey((v) => v + 1);
    if (typeof window !== "undefined" && window.innerWidth < 1024) setSidebarOpen(false);
  };
  const refreshAll = async () => {
    try {
      await refresh();
      window.dispatchEvent(new Event("elios:refresh-dashboard"));
      toast.success("Dati aggiornati");
    } catch {
      toast.error("Aggiornamento fallito");
    }
  };
  const handleLogout = () => { setMenuOpen(false); logout(); navigate("/login", { replace: true }); };
  const roleLabel = { admin: "Admin", responsabile: "Responsabile", operator: "Operatore", tecnico: "Tecnico", commerciale: "Profilo storico" }[user?.role] || user?.role || "";
  const companyName = generalSettings.company_name || "Elios Tech S.r.l.";
  const appName = generalSettings.app_name || "Gestionale Elios Tech";
  const currentNative = configuredNativeItems.find((i) => location.pathname === i.to || location.pathname.startsWith(`${i.to}/`));
  const currentCustom = customModules.find((m) => location.pathname.startsWith(`/moduli/${m.slug}`));
  const currentTitle = location.pathname.startsWith("/admin/migrazione-notion") ? "Importazione da Notion" : location.pathname.startsWith("/admin/moduli") ? "Struttura gestionale" : location.pathname.startsWith("/admin/utenti") ? "Utenti e accessi" : location.pathname === "/admin" ? "Impostazioni" : currentCustom?.name || currentNative?.label || "Gestionale";
  const pageMeta = PAGE_META[location.pathname] || {
    section: currentCustom?.section === "commerciale" ? "amministrazione" : (currentCustom?.section || currentNative?.section || "amministrazione"),
    eyebrow: currentCustom ? "Modulo gestionale" : "Gestionale",
    icon: currentNative?.icon || FileText,
    description: currentCustom?.description || "Area operativa del Gestionale Elios Tech.",
  };
  const CurrentPageIcon = pageMeta.icon || currentNative?.icon || FileText;
  const currentSection = pageMeta.section || "amministrazione";
  const routeToken = location.pathname.startsWith("/moduli/")
    ? "custom"
    : (location.pathname.replace(/^\/+/, "").replace(/[^a-z0-9]+/gi, "-") || "dashboard");

  return (
    <div className="et-app-shell" data-testid="app-layout">
      <header className={`et-topbar r55-topbar r55-section-${currentSection}`}>
        <div className="h-full px-3 sm:px-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <button type="button" onClick={() => setSidebarOpen((v) => !v)} className="et-icon-btn-dark" aria-label={sidebarOpen ? "Chiudi menu" : "Apri menu"}>
              {sidebarOpen ? <X size={20} /> : <List size={22} />}
            </button>
            <button type="button" onClick={() => navigate("/dashboard")} className="et-brand-button">
              <span className="et-brand-logo"><EliosLogo size={31} /></span>
              <span className="hidden sm:block text-left min-w-0">
                <span className="block text-[10px] tracking-[0.17em] uppercase text-amber-300/90 font-bold truncate max-w-[220px]">{companyName}</span>
                <span className="block text-sm font-extrabold text-white truncate max-w-[245px]">{appName}</span>
              </span>
            </button>
            <div className="r55-topbar-page" data-r55-page-header>
              <div className="r55-topbar-page-icon"><CurrentPageIcon size={20} weight="duotone" /></div>
              <div className="r55-topbar-page-copy">
                <div className="r55-topbar-page-meta"><span className="r55-local-dot" />{pageMeta.eyebrow}</div>
                <div className="r55-topbar-page-row">
                  <span className="r55-topbar-page-title">{currentTitle}</span>
                  <span className="r55-topbar-page-description">{pageMeta.description}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button type="button" onClick={refreshAll} disabled={loading} className="et-topbar-action">
              <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} />
              <span className="hidden md:inline">Aggiorna</span>
            </button>
            {user && <div className="relative">
              <button type="button" onClick={() => setMenuOpen((v) => !v)} className="et-user-pill">
                <span className={`w-2 h-2 rounded-full ${user.role === "admin" ? "bg-amber-400" : "bg-emerald-400"}`} />
                <span className="hidden sm:inline text-sm font-semibold max-w-[180px] truncate">{user.full_name || user.username}</span>
                <CaretDown size={13} />
              </button>
              {menuOpen && <div className="et-user-menu">
                <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/80">
                  <div className="text-sm font-bold text-slate-900 truncate">{user.full_name || user.username}</div>
                  <div className="text-xs text-slate-500 truncate">@{user.username} · {roleLabel}</div>
                </div>
                <button type="button" onClick={() => { setMenuOpen(false); setPwdOpen(true); }} className="et-user-menu-item"><Lock size={15} /> Cambia password</button>
                <button type="button" onClick={handleLogout} className="et-user-menu-item text-red-600 border-t border-slate-100"><SignOut size={15} /> Esci</button>
              </div>}
            </div>}
          </div>
        </div>
      </header>

      <div className="flex min-h-screen pt-[68px]">
        {sidebarOpen && <div className="fixed inset-x-0 bottom-0 top-[68px] bg-slate-950/45 backdrop-blur-[1px] z-20 lg:hidden" onClick={() => setSidebarOpen(false)} aria-hidden="true" />}
        <aside className={`et-sidebar ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
          <div className="px-3 pt-4 pb-3 space-y-2">
            <div className="px-3 pb-1 text-[9px] uppercase tracking-[.22em] font-bold text-slate-500">Operativo</div>
            {principalItems.map((item) => <SidebarLink key={item.to} item={item} onNavigate={resetSectionAndNavigate} />)}
            <div className="h-px bg-white/8 my-3" />
            {SECTION_META.map((section) => {
              const items = sectionItems(section.key);
              if (!items.length) return null;
              return <Section key={section.key} section={section} items={items} open={!!openSections[section.key]} onToggle={() => setOpenSections((p) => ({ ...p, [section.key]: !p[section.key] }))} onNavigate={resetSectionAndNavigate} />;
            })}
          </div>
          <div className="et-sidebar-footer">
            <div className="flex items-center gap-2 text-[10px] font-semibold text-emerald-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Dati locali</div>
            {refreshedAt && <div className="mt-1 text-[10px] text-slate-500">Aggiornato alle <span className="text-slate-300">{fmtTime(refreshedAt)}</span></div>}
          </div>
        </aside>

        <main className={`et-main-content r52-main-shell r52-section-${currentSection} ${sidebarOpen ? "lg:ml-64" : "lg:ml-0"}`}>
          <div className={`et-page-host r52-page-host r52-route-${routeToken}`} data-r52-route={routeToken}>
            <Outlet key={`${location.pathname}:${sectionResetKey}`} />
          </div>
        </main>
      </div>
      <ChangeMyPasswordDialog open={pwdOpen} onClose={() => setPwdOpen(false)} />
    </div>
  );
}