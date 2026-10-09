import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/apiBase";
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
  { key: "ordini_clienti", to: "/clienti-ordini", label: "Clienti / Ordini", icon: ShoppingCart, testid: "nav-elios-tech-ordini", module: "ordini_clienti", section: "amministrazione", order: 10 },
  { key: "commesse", to: "/commesse", label: "Commesse", icon: Wrench, testid: "nav-commesse", module: "commesse", section: "amministrazione", order: 20 },
  { key: "fatturato", to: "/fatturato", label: "Fatturato", icon: ChartBar, testid: "nav-fatturato", module: "commesse", section: "amministrazione", order: 30 },
  { key: "wallbox", to: "/wallbox", label: "Wallbox", icon: Lightning, testid: "nav-wallbox", module: "commesse", section: "amministrazione", order: 40 },
  { key: "report", to: "/report", label: "Report", icon: FileText, testid: "nav-report", module: "commesse", section: "amministrazione", order: 50 },
  { key: "sopralluoghi", to: "/sopralluoghi", label: "Sopralluoghi", icon: ClipboardText, testid: "nav-sopralluoghi", module: "sopralluoghi", section: "tecnico", order: 10 },
  { key: "preventivi", to: "/preventivi", label: "Preventivi", icon: FileText, testid: "nav-preventivi", module: "preventivi", section: "tecnico", order: 20 },
  { key: "installazioni", to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni", section: "tecnico", order: 30 },
  { key: "assistenza", to: "/assistenza", label: "Assistenza", icon: Headset, testid: "nav-assistenza", module: "assistenza", section: "tecnico", order: 40 },
  { key: "inventario", to: "/inventario", label: "Magazzino Elios Tech", icon: Package, testid: "nav-inventario", module: "inventario", section: "gestione", order: 10 },
  { key: "magazzino_verona", to: "/magazzino-verona", label: "Magazzino Verona", icon: Package, testid: "nav-magazzino-verona", module: "inventario", section: "gestione", order: 20 },
  { key: "trasferimenti", to: "/trasferimenti", label: "Trasferimenti", icon: ArrowsClockwise, testid: "nav-trasferimenti", module: "movimenti", section: "gestione", order: 30 },
  { key: "arrivi", to: "/arrivi", label: "Arrivi", icon: ArrowsClockwise, testid: "nav-arrivi", module: "arrivi", section: "gestione", order: 40 },
  { key: "movimenti", to: "/movimenti", label: "Movimenti", icon: ArrowsClockwise, testid: "nav-movimenti", module: "movimenti", section: "gestione", order: 50 },
  { key: "anomalie", to: "/anomalie", label: "Anomalie", icon: Warning, testid: "nav-anomalie", module: "anomalie", section: "gestione", order: 60 },
  { key: "ai", to: "/assistente-ai", label: "Assistente AI", icon: Robot, testid: "nav-ai", module: "ai", section: "sistema", order: 10 },
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

function Section({ section, items, open, onToggle, onNavigate }) {
  const Icon = section.icon;
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
          {items.map((item) => <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />)}
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
  const [sectionResetKey, setSectionResetKey] = useState(0);

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
      setCustomModules(data.items || []);
    } catch {
      setCustomModules([]);
    }
  };

  const loadNavigationConfig = async () => {
    try {
      const { data } = await axios.get(`${API}/custom/config/navigation`);
      setNavigationConfig(data.items || []);
    } catch {
      setNavigationConfig([]);
    }
  };

  useEffect(() => {
    loadCustomModules();
    loadNavigationConfig();
    const modulesFn = () => loadCustomModules();
    const navFn = () => loadNavigationConfig();
    window.addEventListener("elios:custom-modules-changed", modulesFn);
    window.addEventListener("elios:navigation-changed", navFn);
    return () => {
      window.removeEventListener("elios:custom-modules-changed", modulesFn);
      window.removeEventListener("elios:navigation-changed", navFn);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const navSettings = useMemo(
    () => Object.fromEntries((navigationConfig || []).map((x) => [x.key, x])),
    [navigationConfig],
  );

  const configuredNativeItems = useMemo(() => NATIVE_ITEMS.map((item) => {
    const cfg = navSettings[item.key] || {};
    const rawSection = cfg.section || item.section;
    const section = rawSection === "commerciale" ? "amministrazione" : rawSection;
    return {
      ...item,
      label: cfg.label || item.label,
      section,
      active: cfg.active !== false,
      order: Number(cfg.sort_order ?? item.order ?? 100),
    };
  }), [navSettings]);

  const allowedNativeItems = useMemo(
    () => configuredNativeItems.filter((item) => item.active && (!item.module || hasPermission(item.module, "view"))),
    [configuredNativeItems, hasPermission],
  );

  const principalItems = useMemo(
    () => allowedNativeItems.filter((item) => item.section === "principale").sort((a, b) => a.order - b.order),
    [allowedNativeItems],
  );

  const systemExtra = isAdmin ? [
    { to: "/admin", label: "Impostazioni", icon: Gear, testid: "nav-admin", module: "impostazioni", order: 900 },
    { to: "/admin/utenti", label: "Utenti e permessi", icon: UsersThree, testid: "nav-admin-users", module: "utenti", order: 910 },
    { to: "/admin/moduli", label: "Costruttore gestionale", icon: SlidersHorizontal, testid: "nav-module-builder", module: "impostazioni", order: 920 },
  ] : [];

  const sectionItems = (sectionKey) => {
    const native = allowedNativeItems.filter((item) => item.section === sectionKey);
    const dynamic = customModules
      .filter((m) => (m.section === "commerciale" ? "amministrazione" : (m.section || "amministrazione")) === sectionKey)
      .filter((m) => !String(m.slug || "").startsWith("report-"))
      .map((m) => ({
        to: `/moduli/${m.slug}`,
        label: m.name,
        icon: FileText,
        testid: `nav-custom-${m.slug}`,
        order: Number(m.sort_order || 100),
      }));
    const extras = sectionKey === "sistema" ? systemExtra : [];
    return [...native, ...dynamic, ...extras].sort((a, b) => Number(a.order || 100) - Number(b.order || 100));
  };

  useEffect(() => {
    const native = configuredNativeItems.find((i) => location.pathname.startsWith(i.to));
    const custom = customModules.find((m) => location.pathname.startsWith(`/moduli/${m.slug}`));
    let key = location.pathname.startsWith("/admin") ? "sistema" : (custom?.section || native?.section);
    if (key === "commerciale") key = "amministrazione";
    if (key && key !== "principale") setOpenSections((prev) => ({ ...prev, [key]: true }));
  }, [location.pathname, customModules, configuredNativeItems]);

  const roleLabel = {
    admin: "Admin",
    responsabile: "Responsabile",
    operator: "Operatore",
    tecnico: "Tecnico",
  }[user?.role] || user?.role || "";

  return (
    <div className="min-h-screen bg-slate-50" data-testid="app-layout">
      <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#1A456B] border-b border-white/10 text-white shadow-sm">
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
              onClick={() => { setSectionResetKey((v) => v + 1); navigate("/dashboard"); }}
              className="flex items-center gap-3 min-w-0 rounded-md px-1 py-1 hover:bg-white/5"
              data-testid="brand-home-btn"
            >
              <EliosLogo size={30} />
              <div className="hidden sm:block text-left min-w-0">
                <div className="text-[10px] tracking-[0.22em] uppercase text-amber-300/90 font-semibold">ELIOS TECH</div>
                <div className="text-sm font-bold text-white/95 truncate">Gestionale aziendale</div>
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
                    <button type="button" onClick={() => { setMenuOpen(false); setPwdOpen(true); }} className="w-full text-left px-3 py-2.5 text-sm text-slate-700 hover:bg-amber-50 flex items-center gap-2">
                      <Lock size={15} /> Cambia password
                    </button>
                    <button type="button" onClick={handleLogout} className="w-full text-left px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 border-t border-slate-100">
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
        {sidebarOpen && <div className="fixed inset-x-0 bottom-0 top-16 bg-black/35 z-20 lg:hidden" onClick={() => setSidebarOpen(false)} aria-hidden="true" />}

        <aside
          className={`fixed top-16 left-0 z-30 h-[calc(100vh-4rem)] w-64 bg-[#1A456B] border-r border-white/10 overflow-y-auto overscroll-contain transition-transform duration-200 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
          data-testid="main-sidebar"
        >
          <div className="p-3 space-y-2">
            {principalItems.map((item) => <SidebarLink key={item.to} item={item} onNavigate={resetSectionAndNavigate} />)}

            <div className="h-px bg-white/10 my-2" />

            {SECTION_META.map((section) => {
              const items = sectionItems(section.key);
              if (!items.length) return null;
              return (
                <Section
                  key={section.key}
                  section={section}
                  items={items}
                  open={!!openSections[section.key]}
                  onToggle={() => toggleSection(section.key)}
                  onNavigate={resetSectionAndNavigate}
                />
              );
            })}
          </div>

          {refreshedAt && (
            <div className="sticky bottom-0 px-4 py-3 text-[10px] text-slate-400 bg-[#1A456B] border-t border-white/10">
              Ultimo aggiornamento: <span className="text-amber-300/80">{fmtTime(refreshedAt)}</span>
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
