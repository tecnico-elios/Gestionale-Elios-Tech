import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  House,
  Package,
  ArrowsClockwise,
  Warning,
  Gear,
  SignOut,
  UsersThree,
  CaretDown,
  CaretRight,
  Lock,
  Robot,
  ClipboardText,
  FileText,
  ShoppingCart,
  Wrench,
  Headset,
  List,
  X,
  CalendarBlank,
  SlidersHorizontal,
  ChartBar,
  Lightning,
  Database,
} from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { useInventoryCtx } from "../lib/InventoryContext";
import { useAuth } from "../lib/AuthContext";
import ChangeMyPasswordDialog from "./ChangeMyPasswordDialog";
import EliosLogo from "./EliosLogo";
import { fmtTime } from "../lib/tz";

const normalizeSection = (value) => {
  const section = String(value || "").toLowerCase();
  if (section === "commerciale") return "amministrazione";
  if (["amministrazione", "tecnico", "gestione", "sistema"].includes(section)) return section;
  return "amministrazione";
};

const SECTIONS = [
  {
    key: "amministrazione",
    label: "Amministrazione",
    icon: FileText,
    items: [
      { to: "/clienti-ordini", label: "Clienti / Ordini", icon: ShoppingCart, testid: "nav-elios-tech-ordini", module: "ordini_clienti" },
      { to: "/commesse", label: "Commesse", icon: Wrench, testid: "nav-commesse", module: "commesse" },
      { to: "/fatturato", label: "Fatturato", icon: ChartBar, testid: "nav-fatturato", module: "commesse", configKey: "fatturato" },
      { to: "/wallbox", label: "Wallbox", icon: Lightning, testid: "nav-wallbox", module: "commesse", configKey: "wallbox" },
      { to: "/report", label: "Report", icon: FileText, testid: "nav-report", module: "commesse", configKey: "report" },
    ],
  },
  {
    key: "tecnico",
    label: "Tecnico",
    icon: Wrench,
    items: [
      { to: "/sopralluoghi", label: "Sopralluoghi", icon: ClipboardText, testid: "nav-sopralluoghi", module: "sopralluoghi" },
      { to: "/preventivi", label: "Preventivi", icon: FileText, testid: "nav-preventivi", module: "preventivi" },
      { to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni" },
      { to: "/assistenza", label: "Assistenza", icon: Headset, testid: "nav-assistenza", module: "assistenza" },
    ],
  },
  {
    key: "gestione",
    label: "Gestione",
    icon: Package,
    items: [
      { to: "/inventario", label: "Magazzino Elios Tech", icon: Package, testid: "nav-inventario", module: "inventario" },
      { to: "/magazzino-verona", label: "Magazzino Verona", icon: Package, testid: "nav-magazzino-verona", module: "inventario", configKey: "magazzino_verona" },
      { to: "/trasferimenti", label: "Trasferimenti", icon: ArrowsClockwise, testid: "nav-trasferimenti", module: "movimenti" },
      { to: "/arrivi", label: "Arrivi", icon: ArrowsClockwise, testid: "nav-arrivi", module: "arrivi" },
      { to: "/movimenti", label: "Movimenti", icon: ArrowsClockwise, testid: "nav-movimenti", module: "movimenti" },
      { to: "/anomalie", label: "Anomalie", icon: Warning, testid: "nav-anomalie", module: "anomalie" },
    ],
  },
  {
    key: "sistema",
    label: "Sistema",
    icon: SlidersHorizontal,
    items: [{ to: "/assistente-ai", label: "Assistente AI", icon: Robot, testid: "nav-ai", module: "ai" }],
  },
];

function SidebarLink({ item, onNavigate }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      data-testid={item.testid}
      className={({ isActive }) =>
        `relative flex items-center gap-3 h-11 pl-7 pr-3 rounded-md text-sm font-semibold transition-colors ${
          isActive ? "bg-white/10 text-white" : "text-slate-300 hover:text-white hover:bg-white/5"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-amber-400" />}
          <Icon size={17} weight={isActive ? "fill" : "regular"} />
          <span>{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

function Section({ section, open, onToggle, onNavigate, extraItems = [] }) {
  const Icon = section.icon;
  const items = [...section.items, ...extraItems];
  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={onToggle}
        className="w-full h-11 px-3 rounded-md flex items-center justify-between text-slate-200 hover:bg-white/5 hover:text-white"
        data-testid={`menu-section-${section.key}`}
      >
        <span className="flex items-center gap-3 text-sm font-bold">
          <Icon size={18} />
          {section.label}
        </span>
        {open ? <CaretDown size={15} /> : <CaretRight size={15} />}
      </button>
      {open && (
        <div className="space-y-1 pb-1">
          {items.map((item) => (
            <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />
          ))}
        </div>
      )}
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
  const [appSettings, setAppSettings] = useState({
    general: {
      app_name: "Gestionale Elios Tech",
      company_name: "Elios Tech S.r.l.",
      primary_color: "#1A456B",
    },
  });
  const [sectionResetKey, setSectionResetKey] = useState(0);

  const initialOpen = useMemo(() => {
    const found = SECTIONS.find((s) => s.items.some((i) => location.pathname.startsWith(i.to)));
    return found?.key || (location.pathname.startsWith("/admin") ? "sistema" : "amministrazione");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const [openSections, setOpenSections] = useState({
    amministrazione: initialOpen === "amministrazione",
    tecnico: initialOpen === "tecnico",
    gestione: initialOpen === "gestione",
    sistema: initialOpen === "sistema" || location.pathname.startsWith("/admin"),
  });

  useEffect(() => {
    const found = SECTIONS.find((s) => s.items.some((i) => location.pathname.startsWith(i.to)));
    const custom = customModules.find((m) => location.pathname.startsWith(`/moduli/${m.slug}`));
    const key = location.pathname.startsWith("/admin") ? "sistema" : normalizeSection(custom?.section || found?.key);
    if (key) setOpenSections((prev) => ({ ...prev, [key]: true }));
  }, [location.pathname, customModules]);

  const toggleSection = (key) => setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const closeOnMobile = () => {
    if (typeof window !== "undefined" && window.innerWidth < 1024) setSidebarOpen(false);
  };

  const resetSectionAndNavigate = () => {
    setSectionResetKey((v) => v + 1);
    closeOnMobile();
  };

  const refreshAll = async () => {
    try {
      await refresh();
      if (typeof window !== "undefined") window.dispatchEvent(new Event("elios:refresh-dashboard"));
      toast.success("Dati aggiornati");
    } catch {
      toast.error("Aggiornamento fallito");
    }
  };

  const loadCustomModules = async () => {
    try {
      const { data } = await axios.get(`${API}/custom/modules`);
      setCustomModules((data.items || []).map((m) => ({ ...m, section: normalizeSection(m.section) })));
    } catch {
      setCustomModules([]);
    }
  };

  const loadNavigationConfig = async () => {
    try {
      const { data } = await axios.get(`${API}/custom/config/navigation`);
      setNavigationConfig(
        (data.items || []).map((x) => ({
          ...x,
          section: x.section === "principale" ? "principale" : normalizeSection(x.section),
        })),
      );
    } catch {
      setNavigationConfig([]);
    }
  };

  const loadSettings = async () => {
    if (!isAdmin) return;
    try {
      const { data } = await axios.get(`${API}/admin/settings`);
      setAppSettings(data || {});
    } catch {
      // Il layout resta utilizzabile con i valori di fallback.
    }
  };

  useEffect(() => {
    loadCustomModules();
    loadNavigationConfig();
    loadSettings();

    const modulesFn = () => loadCustomModules();
    const navFn = () => loadNavigationConfig();
    const settingsFn = () => loadSettings();

    window.addEventListener("elios:custom-modules-changed", modulesFn);
    window.addEventListener("elios:navigation-changed", navFn);
    window.addEventListener("elios:settings-changed", settingsFn);

    return () => {
      window.removeEventListener("elios:custom-modules-changed", modulesFn);
      window.removeEventListener("elios:navigation-changed", navFn);
      window.removeEventListener("elios:settings-changed", settingsFn);
    };
  }, [isAdmin]); // eslint-disable-line react-hooks/exhaustive-deps

  const general = appSettings?.general || {};
  const appName = general.app_name || "Gestionale Elios Tech";
  const companyName = general.company_name || "Elios Tech S.r.l.";
  const primaryColor = /^#[0-9a-fA-F]{6}$/.test(String(general.primary_color || "")) ? general.primary_color : "#1A456B";

  useEffect(() => {
    if (typeof document !== "undefined") document.title = appName;
  }, [appName]);

  const navSettings = useMemo(
    () => Object.fromEntries((navigationConfig || []).filter((x) => x.key !== "lead").map((x) => [x.key, x])),
    [navigationConfig],
  );

  const configuredItem = (item) => {
    const key = item.configKey || item.module;
    const cfg = navSettings[key] || {};
    return {
      ...item,
      label: cfg.label || item.label,
      navSection: cfg.section ? (cfg.section === "principale" ? "principale" : normalizeSection(cfg.section)) : null,
      navActive: cfg.active !== false,
      navOrder: Number(cfg.sort_order ?? 100),
    };
  };

  const roleLabel = {
    admin: "Admin",
    responsabile: "Responsabile",
    operator: "Operatore",
    commerciale: "Utente storico",
    tecnico: "Tecnico",
  }[user?.role] || user?.role || "";

  const systemExtra = isAdmin
    ? [
        { to: "/admin", label: "Impostazioni", icon: Gear, testid: "nav-admin", module: "impostazioni", navOrder: 800 },
        { to: "/admin/utenti", label: "Utenti e permessi", icon: UsersThree, testid: "nav-admin-users", module: "utenti", navOrder: 810 },
        { to: "/admin/moduli", label: "Configura gestionale", icon: SlidersHorizontal, testid: "nav-module-builder", module: "impostazioni", navOrder: 820 },
        { to: "/admin/notion", label: "Importazione Notion", icon: Database, testid: "nav-notion-migration", module: "impostazioni", navOrder: 830 },
      ]
    : [];

  return (
    <div className="min-h-screen bg-slate-50" data-testid="app-layout">
      <header
        className="fixed top-0 left-0 right-0 z-50 h-16 border-b border-white/10 text-white shadow-sm"
        style={{ backgroundColor: primaryColor }}
      >
        <div className="h-full px-3 sm:px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              className="h-10 w-10 inline-flex items-center justify-center rounded-md border border-white/10 bg-white/5 hover:bg-white/10"
              aria-label={sidebarOpen ? "Chiudi menu" : "Apri menu"}
              data-testid="sidebar-toggle"
            >
              {sidebarOpen ? <X size={20} /> : <List size={22} />}
            </button>
            <button
              type="button"
              onClick={() => {
                setSectionResetKey((v) => v + 1);
                navigate("/dashboard");
              }}
              className="flex items-center gap-3 min-w-0 rounded-md px-1 py-1 hover:bg-white/5"
              data-testid="brand-home-btn"
            >
              <EliosLogo size={30} />
              <div className="hidden sm:block text-left min-w-0">
                <div className="text-[10px] tracking-[0.18em] uppercase text-amber-300/90 font-semibold truncate">{companyName}</div>
                <div className="text-sm font-bold text-white/95 truncate">{appName}</div>
              </div>
            </button>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={refreshAll}
              disabled={loading}
              className="h-10 px-3 rounded-md bg-white/5 border border-white/10 text-slate-100 hover:border-amber-300/50 hover:text-white flex items-center gap-2 disabled:opacity-60"
              data-testid="topbar-refresh-btn"
              title="Aggiorna i dati"
            >
              <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} />
              <span className="hidden md:inline text-sm">Aggiorna</span>
            </button>

            {user && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen((v) => !v)}
                  className="h-10 px-3 rounded-md bg-white/5 border border-white/10 hover:border-amber-300/50 flex items-center gap-2"
                  data-testid="current-user-badge"
                >
                  <span className={`w-2 h-2 rounded-full ${user.role === "admin" ? "bg-amber-400" : "bg-emerald-400"}`} />
                  <span className="hidden sm:inline text-sm font-semibold">{user.full_name || user.username}</span>
                  <CaretDown size={13} className="text-slate-300" />
                </button>

                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-60 bg-white border border-slate-200 rounded-md shadow-xl z-50 overflow-hidden" data-testid="user-menu">
                    <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
                      <div className="text-sm font-semibold text-slate-800">{user.full_name || user.username}</div>
                      <div className="text-xs text-slate-500">@{user.username} · {roleLabel}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        setPwdOpen(true);
                      }}
                      className="w-full text-left px-3 py-2.5 text-sm text-slate-700 hover:bg-amber-50 flex items-center gap-2"
                    >
                      <Lock size={15} /> Cambia password
                    </button>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="w-full text-left px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 border-t border-slate-100"
                    >
                      <SignOut size={15} /> Esci
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="flex min-h-screen pt-16">
        {sidebarOpen && (
          <div
            className="fixed inset-x-0 bottom-0 top-16 bg-black/35 z-20 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <aside
          className={`fixed top-16 left-0 z-30 h-[calc(100vh-4rem)] w-64 border-r border-white/10 overflow-y-auto overscroll-contain transition-transform duration-200 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
          style={{ backgroundColor: primaryColor }}
          data-testid="main-sidebar"
        >
          <div className="p-3 space-y-2">
            {hasPermission("dashboard", "view") && navSettings.dashboard?.active !== false && (
              <SidebarLink
                item={{
                  to: "/dashboard",
                  label: navSettings.dashboard?.label || "Dashboard",
                  icon: House,
                  testid: "nav-dashboard",
                  module: "dashboard",
                }}
                onNavigate={resetSectionAndNavigate}
              />
            )}
            {hasPermission("calendar", "view") && navSettings.calendar?.active !== false && (
              <SidebarLink
                item={{
                  to: "/calendario",
                  label: navSettings.calendar?.label || "Calendario",
                  icon: CalendarBlank,
                  testid: "nav-calendar",
                  module: "calendar",
                }}
                onNavigate={resetSectionAndNavigate}
              />
            )}

            <div className="h-px bg-white/10 my-2" />

            {SECTIONS.map((section) => {
              const allowed = SECTIONS.flatMap((s) => s.items)
                .map(configuredItem)
                .filter((item) => {
                  const original = SECTIONS.find((s) => s.items.some((x) => x.to === item.to))?.key;
                  return normalizeSection(item.navSection || original) === section.key;
                })
                .filter((item) => item.navActive && (!item.module || hasPermission(item.module, "view")))
                .sort((a, b) => a.navOrder - b.navOrder);

              const dynamicExtras = customModules
                .filter((m) => normalizeSection(m.section) === section.key && !String(m.slug || "").startsWith("report-"))
                .map((m) => ({
                  to: `/moduli/${m.slug}`,
                  label: m.name,
                  icon: FileText,
                  testid: `nav-custom-${m.slug}`,
                  navOrder: Number(m.sort_order || 100),
                }));

              const extras = [...(section.key === "sistema" ? systemExtra : []), ...dynamicExtras]
                .filter((item) => isAdmin || !item.module || hasPermission(item.module, "view"))
                .sort((a, b) => (a.navOrder || 900) - (b.navOrder || 900));

              if (!allowed.length && !extras.length) return null;

              return (
                <Section
                  key={section.key}
                  section={{ ...section, items: allowed }}
                  open={!!openSections[section.key]}
                  onToggle={() => toggleSection(section.key)}
                  onNavigate={resetSectionAndNavigate}
                  extraItems={extras}
                />
              );
            })}
          </div>

          {refreshedAt && (
            <div
              className="sticky bottom-0 px-4 py-3 text-[10px] text-slate-300 border-t border-white/10"
              style={{ backgroundColor: primaryColor }}
            >
              Ultimo aggiornamento: <span className="text-amber-300/90">{fmtTime(refreshedAt)}</span>
            </div>
          )}
        </aside>

        <main className={`flex-1 min-w-0 min-h-[calc(100vh-4rem)] transition-[margin] duration-200 ${sidebarOpen ? "lg:ml-64" : "lg:ml-0"}`}>
          <Outlet key={`${location.pathname}:${sectionResetKey}`} />
        </main>
      </div>

      <ChangeMyPasswordDialog open={pwdOpen} onClose={() => setPwdOpen(false)} />
    </div>
  );
}
