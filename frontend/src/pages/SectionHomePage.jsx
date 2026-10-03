import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import axios from "axios";
import { API } from "../lib/apiBase";
import { useAuth } from "../lib/AuthContext";
import { Briefcase, FileText, Wrench, Package, Robot, UserPlus, ShoppingCart, ClipboardText, Headset, ArrowsClockwise, Warning, SlidersHorizontal } from "@phosphor-icons/react";

const sections = {
  commerciale: { label: "Commerciale", icon: Briefcase, items: [{ to: "/lead", label: "Lead", module: "lead", icon: UserPlus }] },
  amministrazione: { label: "Amministrazione", icon: FileText, items: [{ to: "/elios-tech-ordini", label: "Elios Tech Ordini", module: "ordini_clienti", icon: ShoppingCart }, { to: "/commesse", label: "Commesse", module: "commesse", icon: Wrench }] },
  tecnico: { label: "Tecnico", icon: Wrench, items: [{ to: "/sopralluoghi", label: "Sopralluoghi", module: "sopralluoghi", icon: ClipboardText }, { to: "/preventivi", label: "Preventivi", module: "preventivi", icon: FileText }, { to: "/installazioni", label: "Installazioni", module: "installazioni", icon: Wrench }, { to: "/assistenza", label: "Assistenza", module: "assistenza", icon: Headset }] },
  gestione: { label: "Gestione", icon: Package, items: [{ to: "/inventario", label: "Magazzino Elios Tech", module: "inventario", icon: Package }, { to: "/magazzino-verona", label: "Magazzino Verona", module: "inventario", icon: Package }, { to: "/trasferimenti", label: "Trasferimenti", module: "movimenti", icon: ArrowsClockwise }, { to: "/arrivi", label: "Arrivi", module: "arrivi", icon: ArrowsClockwise }, { to: "/spedizioni", label: "Spedizioni", module: "spedizioni", icon: Package }, { to: "/movimenti", label: "Movimenti", module: "movimenti", icon: ArrowsClockwise }, { to: "/anomalie", label: "Anomalie", module: "anomalie", icon: Warning }] },
  sistema: { label: "Sistema", icon: SlidersHorizontal, items: [{ to: "/assistente-ai", label: "Assistente AI", module: "ai", icon: Robot }] },
};

export default function SectionHomePage() {
  const { section } = useParams();
  const { hasPermission, isAdmin } = useAuth();
  const [custom, setCustom] = useState([]);
  const cfg = sections[section] || sections.commerciale;
  useEffect(() => { axios.get(`${API}/custom/modules`).then(({data}) => setCustom((data.items || []).filter((m) => m.section === section))).catch(() => setCustom([])); }, [section]);
  const items = useMemo(() => {
    const standard = cfg.items.filter((x) => hasPermission(x.module, "view") || isAdmin);
    return [...standard, ...custom.map((m) => ({ to: `/moduli/${m.slug}`, label: m.name, icon: FileText, custom: true }))];
  }, [cfg, custom, hasPermission, isAdmin]);
  const Icon = cfg.icon;
  return <div className="max-w-7xl mx-auto px-3 sm:px-6 py-6">
    <div className="flex items-center gap-3 mb-5"><div className="h-11 w-11 rounded-xl border border-slate-200 bg-white flex items-center justify-center"><Icon size={22}/></div><h1 className="font-display text-3xl font-bold">{cfg.label}</h1></div>
    <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">{items.map((item) => { const I=item.icon; return <Link key={item.to} to={item.to} className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-blue-300 hover:shadow-md transition"><div className="flex items-center justify-between gap-3"><div className="h-10 w-10 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center"><I size={20}/></div>{item.custom && <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Modulo</span>}</div><div className="font-bold text-lg mt-4 text-slate-950 group-hover:text-blue-700">{item.label}</div></Link>; })}</div>
  </div>;
}
