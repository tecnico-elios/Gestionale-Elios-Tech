import { API } from "../lib/apiBase";
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "../lib/AuthContext";
import { Navigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { UserPlus, Key, PencilSimple, Prohibit, ArrowClockwise, Trash } from "@phosphor-icons/react";
import { fmtDateTime, useTz } from "../lib/tz";

const MASTER_EMAIL = "tecnico@eliostech.org";
const isMasterUser = (u) => String(u?.email || "").trim().toLowerCase() === MASTER_EMAIL;
const ROLES = [
  ["operator", "Operatore"],
  ["responsabile", "Responsabile"],
  ["tecnico", "Tecnico"],
  ["admin", "Admin"],
];

const PERMISSION_MODULES = [
  ["dashboard", "Dashboard"], ["calendar", "Calendario"],
  ["ordini_clienti", "Clienti e ordini"], ["commesse", "Commesse"],
  ["sopralluoghi", "Sopralluoghi"], ["preventivi", "Preventivi"],
  ["installazioni", "Installazioni"], ["assistenza", "Assistenza"],
  ["inventario", "Magazzini"], ["arrivi", "Arrivi"], ["spedizioni", "Spedizioni"],
  ["movimenti", "Movimenti"], ["anomalie", "Anomalie"], ["ai", "Assistente"],
];
const PERMISSION_ACTIONS = [["view", "Vedi"], ["create", "Crea"], ["edit", "Modifica"], ["delete", "Elimina"], ["export", "Esporta"]];

function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore";
}

function CreateUserDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState({ first_name: "", last_name: "", username: "", email: "", password: "", role: "operator" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setForm({ first_name: "", last_name: "", username: "", email: "", password: "", role: "operator" }); }, [open]);
  const patch = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/admin/users`, {
        first_name: form.first_name.trim(), last_name: form.last_name.trim(),
        username: form.username.trim().toLowerCase(), email: form.email.trim().toLowerCase() || undefined,
        password: form.password, role: form.role,
      });
      toast.success(`Utente ${data.username} creato`);
      onCreated?.(); onClose();
    } catch (e2) { toast.error("Creazione fallita", { description: formatError(e2) }); }
    finally { setBusy(false); }
  };
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-lg"><DialogHeader><DialogTitle>Nuovo utente</DialogTitle></DialogHeader><form onSubmit={submit} className="space-y-4" autoComplete="off">
    <div className="grid grid-cols-2 gap-3"><div><Label>Nome</Label><Input className="mt-1" required value={form.first_name} onChange={(e) => patch("first_name", e.target.value)} autoComplete="off" /></div><div><Label>Cognome</Label><Input className="mt-1" required value={form.last_name} onChange={(e) => patch("last_name", e.target.value)} autoComplete="off" /></div></div>
    <div><Label>Username</Label><Input className="mt-1" required value={form.username} onChange={(e) => patch("username", e.target.value.toLowerCase())} placeholder="minuscole, numeri, . _ -" autoComplete="off" /></div>
    <div><Label>Email</Label><Input className="mt-1" type="email" value={form.email} onChange={(e) => patch("email", e.target.value)} autoComplete="off" /></div>
    <div><Label>Password iniziale</Label><Input className="mt-1" type="password" minLength={6} required value={form.password} onChange={(e) => patch("password", e.target.value)} autoComplete="new-password" /><p className="text-xs text-slate-500 mt-1">Al primo accesso l'utente dovrà impostarne una nuova.</p></div>
    <div><Label>Ruolo</Label><div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">{ROLES.map(([value, label]) => <button key={value} type="button" onClick={() => patch("role", value)} className={`h-10 rounded-md border text-sm font-semibold ${form.role === value ? "bg-slate-900 text-white border-slate-900" : "bg-white border-slate-300"}`}>{label}</button>)}</div></div>
    <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Annulla</Button><Button type="submit" disabled={busy}>{busy ? "Creazione…" : "Crea utente"}</Button></DialogFooter>
  </form></DialogContent></Dialog>;
}

function EditEmailDialog({ user, onClose, onDone }) {
  const [email, setEmail] = useState(user?.email || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setEmail(user?.email || ""); }, [user]);
  if (!user) return null;
  const save = async () => {
    setBusy(true);
    try { await axios.patch(`${API}/admin/users/${user.id}`, { email }); toast.success("Email aggiornata"); onDone?.(); onClose(); }
    catch (e) { toast.error("Aggiornamento fallito", { description: formatError(e) }); }
    finally { setBusy(false); }
  };
  return <Dialog open onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Email — {user.username}</DialogTitle></DialogHeader><div><Label>Email</Label><Input className="mt-1" type="email" value={email} onChange={(e) => setEmail(e.target.value.toLowerCase())} /></div><DialogFooter><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={save} disabled={busy}>{busy ? "Salvataggio…" : "Salva"}</Button></DialogFooter></DialogContent></Dialog>;
}

function ResetPwdDialog({ user, onClose, onDone }) {
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) setPwd(""); }, [user]);
  if (!user) return null;
  const save = async () => {
    setBusy(true);
    try { await axios.post(`${API}/admin/users/${user.id}/reset-password`, { new_password: pwd }); toast.success("Password reimpostata e sessioni revocate"); onDone?.(); onClose(); }
    catch (e) { toast.error("Reset fallito", { description: formatError(e) }); }
    finally { setBusy(false); }
  };
  return <Dialog open onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-sm"><DialogHeader><DialogTitle>Reset password — {user.username}</DialogTitle></DialogHeader><div><Label>Nuova password</Label><Input className="mt-1" type="password" minLength={6} value={pwd} onChange={(e) => setPwd(e.target.value)} /></div><DialogFooter><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={save} disabled={busy || pwd.length < 6}>{busy ? "Reset…" : "Reset password"}</Button></DialogFooter></DialogContent></Dialog>;
}

function PermissionsDialog({ user, onClose, onDone }) {
  const [perms, setPerms] = useState([]);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!user) return;
    const src = user.permissions_customized ? user.permissions : user.effective_permissions;
    const allowedPrefixes = new Set(PERMISSION_MODULES.map(([m]) => m));
    setPerms((Array.isArray(src) ? src : []).filter((p) => p === "installazioni:view_all" || p === "calendar:manage_people_roles" || (p.includes(":") && allowedPrefixes.has(p.split(":")[0]))));
  }, [user]);
  if (!user) return null;
  const keyOf = (m, a) => `${m}:${a}`;
  const has = (m, a) => perms.includes(keyOf(m, a));
  const toggle = (m, a) => setPerms((prev) => {
    const key = keyOf(m, a);
    let next = prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key];
    if (a !== "view" && !prev.includes(key) && !next.includes(keyOf(m, "view"))) next.push(keyOf(m, "view"));
    if (a === "view" && prev.includes(key)) next = next.filter((x) => !x.startsWith(`${m}:`));
    return next;
  });
  const toggleModule = (m) => setPerms((prev) => {
    const allOn = PERMISSION_ACTIONS.every(([a]) => prev.includes(keyOf(m, a)));
    const without = prev.filter((x) => !x.startsWith(`${m}:`));
    return allOn ? without : [...without, ...PERMISSION_ACTIONS.map(([a]) => keyOf(m, a))];
  });
  const save = async () => {
    setSaving(true);
    try { await axios.patch(`${API}/admin/users/${user.id}`, { permissions: perms }); toast.success("Permessi aggiornati"); onDone?.(); onClose(); }
    catch (e) { toast.error("Salvataggio fallito", { description: formatError(e) }); }
    finally { setSaving(false); }
  };
  return <Dialog open onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto"><DialogHeader><DialogTitle>Permessi — {user.full_name || user.username}</DialogTitle></DialogHeader><div className="overflow-x-auto border rounded-lg"><table className="w-full min-w-[720px] text-sm"><thead className="bg-slate-50"><tr><th className="text-left p-3">Modulo</th>{PERMISSION_ACTIONS.map(([a, l]) => <th key={a} className="p-3 text-center">{l}</th>)}</tr></thead><tbody>{PERMISSION_MODULES.map(([m, label]) => <tr key={m} className="border-t"><td className="p-3 font-semibold"><button type="button" onClick={() => toggleModule(m)} className="hover:text-blue-700">{label}</button></td>{PERMISSION_ACTIONS.map(([a]) => <td key={a} className="p-2 text-center"><input type="checkbox" className="h-5 w-5" checked={has(m, a)} onChange={() => toggle(m, a)} /></td>)}</tr>)}</tbody></table></div><label className="flex gap-3 items-start border rounded-lg p-3 bg-blue-50/60 border-blue-100"><input type="checkbox" className="h-5 w-5 mt-0.5" checked={perms.includes("calendar:manage_people_roles")} onChange={() => setPerms((p) => p.includes("calendar:manage_people_roles") ? p.filter((x) => x !== "calendar:manage_people_roles") : [...p, "calendar:manage_people_roles", ...(p.includes("calendar:view") ? [] : ["calendar:view"])])} /><span><b className="text-sm">Calendario · gestisci persone e ruoli</b><span className="block text-xs text-slate-500">Consente di creare/modificare persone e ruoli operativi senza rendere l’utente Admin.</span></span></label><label className="flex gap-3 items-start border rounded-lg p-3 bg-slate-50"><input type="checkbox" className="h-5 w-5 mt-0.5" checked={perms.includes("installazioni:view_all")} onChange={() => setPerms((p) => p.includes("installazioni:view_all") ? p.filter((x) => x !== "installazioni:view_all") : [...p, "installazioni:view_all", ...(p.includes("installazioni:view") ? [] : ["installazioni:view"])])} /><span><b className="text-sm">Installazioni · visualizza tutte</b><span className="block text-xs text-slate-500">Se disattivato, il tecnico vede solo le installazioni assegnate.</span></span></label><DialogFooter><Button variant="outline" onClick={onClose}>Annulla</Button><Button onClick={save} disabled={saving}>{saving ? "Salvataggio…" : "Salva permessi"}</Button></DialogFooter></DialogContent></Dialog>;
}

function DeleteUserDialog({ user, onClose, onDone }) {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) setConfirm(""); }, [user]);
  if (!user) return null;
  const remove = async () => {
    setBusy(true);
    try { await axios.delete(`${API}/admin/users/${user.id}`); toast.success("Utente eliminato definitivamente"); onDone?.(); onClose(); }
    catch (e) { toast.error("Eliminazione fallita", { description: formatError(e) }); }
    finally { setBusy(false); }
  };
  return <Dialog open onOpenChange={(v) => !v && onClose()}><DialogContent className="max-w-md"><DialogHeader><DialogTitle>Elimina definitivamente {user.username}</DialogTitle></DialogHeader><div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">L'account e le credenziali verranno cancellati; lo storico operativo e l'audit restano conservati.</div><div><Label>Digita ELIMINA</Label><Input className="mt-1" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></div><DialogFooter><Button variant="outline" onClick={onClose}>Annulla</Button><Button className="bg-red-600 hover:bg-red-700 text-white" onClick={remove} disabled={busy || confirm.trim().toUpperCase() !== "ELIMINA"}><Trash size={16} /> Elimina definitivamente</Button></DialogFooter></DialogContent></Dialog>;
}

function UserActions({ u, me, onReload, onEmail, onReset, onPerm, onDelete }) {
  const master = isMasterUser(u);
  const isMe = me?.id === u.id;
  const lock = master || isMe;
  const changeRole = async (role) => {
    if (role === u.role) return;
    try { await axios.patch(`${API}/admin/users/${u.id}`, { role }); toast.success("Ruolo aggiornato"); onReload(); }
    catch (e) { toast.error("Aggiornamento ruolo fallito", { description: formatError(e) }); }
  };
  const toggleActive = async () => {
    try { await axios.patch(`${API}/admin/users/${u.id}`, { active: !u.active }); toast.success(u.active ? "Utente disattivato" : "Utente riattivato"); onReload(); }
    catch (e) { toast.error("Aggiornamento fallito", { description: formatError(e) }); }
  };
  return <>
    <select value={u.role} onChange={(e) => changeRole(e.target.value)} disabled={lock} className="h-9 rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold min-w-[140px] disabled:opacity-50">
      {u.role === "commerciale" && <option value="commerciale" disabled>Commerciale (legacy)</option>}
      {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
    <div className="flex gap-1 justify-end">
      <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => onEmail(u)} title="Email"><PencilSimple size={14} /></Button>
      <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => onPerm(u)} disabled={master || u.role === "admin"} title="Permessi"><PencilSimple size={14} /></Button>
      <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => onReset(u)} disabled={master} title="Reset password"><Key size={14} /></Button>
      <Button size="icon" variant="outline" className={`h-8 w-8 ${u.active ? "text-red-600" : "text-emerald-700"}`} onClick={toggleActive} disabled={lock} title={u.active ? "Disattiva" : "Riattiva"}><Prohibit size={14} /></Button>
      <Button size="icon" variant="outline" className="h-8 w-8 text-red-700" onClick={() => onDelete(u)} disabled={lock} title="Elimina"><Trash size={14} /></Button>
    </div>
  </>;
}

export default function AdminUsersPage() {
  const { user: me, isAdmin, isLoading } = useAuth();
  useTz();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [emailTarget, setEmailTarget] = useState(null);
  const [permTarget, setPermTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/admin/users`); setUsers(data.items || []); }
    catch (e) { toast.error("Errore caricamento utenti", { description: formatError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (isAdmin) load(); }, [isAdmin]); // eslint-disable-line react-hooks/exhaustive-deps
  if (isLoading) return <div className="p-6 text-slate-500">Caricamento…</div>;
  if (!isAdmin) return <Navigate to="/" replace />;

  return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5" data-testid="admin-users-page">
    <div className="flex items-end justify-between gap-3 flex-wrap"><div><div className="text-xs uppercase tracking-[.16em] text-[#1A456B] font-semibold">Sistema</div><h1 className="text-3xl font-black text-slate-900">Utenti e accessi</h1><p className="text-sm text-slate-500 mt-1">Ruoli disponibili: Admin, Responsabile, Operatore e Tecnico.</p></div><div className="flex gap-2"><Button variant="outline" onClick={load} disabled={loading}><ArrowClockwise className={loading ? "animate-spin" : ""} /> Aggiorna</Button><Button onClick={() => setCreateOpen(true)}><UserPlus /> Nuovo utente</Button></div></div>

    <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50"><tr><th className="text-left p-3">Utente</th><th className="text-left p-3">Ruolo</th><th className="text-left p-3">Stato</th><th className="text-left p-3">Ultimo accesso</th><th className="text-right p-3">Azioni</th></tr></thead><tbody>{users.map((u) => <tr key={u.id} className="border-t border-slate-100"><td className="p-3"><div className="font-semibold text-slate-900">{u.full_name || u.username}</div><div className="text-xs text-slate-500">@{u.username}{u.email ? ` · ${u.email}` : ""}</div>{isMasterUser(u) && <div className="text-[10px] font-bold text-amber-700 mt-1">ACCOUNT MASTER</div>}</td><td className="p-3"><UserActions u={u} me={me} onReload={load} onEmail={setEmailTarget} onReset={setResetTarget} onPerm={setPermTarget} onDelete={setDeleteTarget} /></td><td className="p-3">{u.active ? <Badge className="bg-emerald-100 text-emerald-800">Attivo</Badge> : <Badge variant="outline" className="text-red-700 border-red-200 bg-red-50">Disattivato</Badge>}</td><td className="p-3 text-xs text-slate-500">{fmtDateTime(u.last_login)}</td><td className="p-3 text-right text-xs text-slate-400">{u.permissions_customized ? "Permessi personalizzati" : "Permessi ruolo"}</td></tr>)}{!loading && users.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-400">Nessun utente.</td></tr>}</tbody></table></div>

    <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={load} />
    <EditEmailDialog user={emailTarget} onClose={() => setEmailTarget(null)} onDone={load} />
    <ResetPwdDialog user={resetTarget} onClose={() => setResetTarget(null)} onDone={load} />
    <PermissionsDialog user={permTarget} onClose={() => setPermTarget(null)} onDone={load} />
    <DeleteUserDialog user={deleteTarget} onClose={() => setDeleteTarget(null)} onDone={load} />
  </div>;
}
