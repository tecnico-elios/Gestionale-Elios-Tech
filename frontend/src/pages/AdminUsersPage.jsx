import { API } from "../lib/apiBase";
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "../lib/AuthContext";
import { Link, Navigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "../components/ui/dialog";
import { UserPlus, Key, ArrowLeft, PencilSimple, Prohibit, ArrowClockwise, Trash } from "@phosphor-icons/react";
import { fmtDateTime, useTz } from "../lib/tz";


const MASTER_EMAIL = "tecnico@eliostech.org";
const isMasterUser = (u) => String(u?.email || "").trim().toLowerCase() === MASTER_EMAIL;

function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore";
}

function CreateUserDialog({ open, onClose, onCreated }) {
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("operator");
  const [busy, setBusy] = useState(false);

  // F14 (BLOCCO 3) — Reset totale del form ad ogni apertura. Il form NON deve mai
  // ereditare dati dall'utente attualmente loggato (né stato React né autofill browser).
  useEffect(() => {
    if (open) {
      setFirst(""); setLast(""); setUsername(""); setEmail(""); setPassword(""); setRole("operator");
    }
  }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/admin/users`, {
        first_name: first.trim(),
        last_name: last.trim(),
        username: username.trim().toLowerCase(),
        email: email.trim().toLowerCase() || undefined,
        password,
        role,
      });
      toast.success(`Utente ${data.username} creato`);
      onCreated?.(data);
      onClose();
    } catch (e) {
      toast.error("Creazione fallita", { description: formatError(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="create-user-dialog">
        <DialogHeader>
          <DialogTitle>Nuovo utente</DialogTitle>
          
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3" autoComplete="off" data-testid="create-user-form">
          {/* F14 (BLOCCO 3) — Trappole anti-autofill: fields nascosti che intercettano
              username/password che il browser tenterebbe di auto-inserire con le credenziali
              dell'utente attualmente loggato. NON toccano lo stato del form. */}
          <input type="text" name="username" autoComplete="username" tabIndex={-1} aria-hidden="true" style={{ position: "absolute", left: "-9999px", opacity: 0, height: 0, width: 0 }} />
          <input type="password" name="password" autoComplete="current-password" tabIndex={-1} aria-hidden="true" style={{ position: "absolute", left: "-9999px", opacity: 0, height: 0, width: 0 }} />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label>Nome</Label>
              <Input value={first} onChange={(e) => setFirst(e.target.value)} required className="h-11 mt-1" data-testid="new-user-first-name" autoComplete="off" />
            </div>
            <div>
              <Label>Cognome</Label>
              <Input value={last} onChange={(e) => setLast(e.target.value)} required className="h-11 mt-1" data-testid="new-user-last-name" autoComplete="off" />
            </div>
          </div>
          <div>
            <Label>Username</Label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase())}
              required
              className="h-11 mt-1 font-mono-tight"
              data-testid="new-user-username"
              placeholder="minuscole, numeri, . _ -"
              autoComplete="off"
              name="new-user-username-noautofill"
            />
          </div>
          <div>
            <Label>Email (per recupero password)</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value.toLowerCase())}
              className="h-11 mt-1"
              data-testid="new-user-email"
              placeholder="opzionale"
              autoComplete="off"
              name="new-user-email-noautofill"
            />
          </div>
          <div>
            <Label>Password (min 6 caratteri)</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="h-11 mt-1"
              data-testid="new-user-password"
              autoComplete="new-password"
              name="new-user-password-noautofill"
            />
          </div>
          <div>
            <Label>Ruolo</Label>
            <div className="flex gap-2 mt-1 flex-wrap">
              <button
                type="button"
                onClick={() => setRole("operator")}
                className={`h-11 px-4 rounded-md border font-semibold text-sm ${
                  role === "operator" ? "bg-slate-900 text-white border-slate-900" : "bg-white border-slate-300"
                }`}
                data-testid="new-user-role-operator"
              >
                Operatore
              </button>
              <button
                type="button"
                onClick={() => setRole("responsabile")}
                className={`h-11 px-4 rounded-md border font-semibold text-sm ${
                  role === "responsabile" ? "bg-sky-700 text-white border-sky-700" : "bg-white border-slate-300"
                }`}
                data-testid="new-user-role-responsabile"
              >
                Responsabile
              </button>
              <button
                type="button"
                onClick={() => setRole("commerciale")}
                className={`h-11 px-4 rounded-md border font-semibold text-sm ${
                  role === "commerciale" ? "bg-violet-700 text-white border-violet-700" : "bg-white border-slate-300"
                }`}
                data-testid="new-user-role-commerciale"
              >
                Commerciale
              </button>
              <button
                type="button"
                onClick={() => setRole("tecnico")}
                className={`h-11 px-4 rounded-md border font-semibold text-sm ${
                  role === "tecnico" ? "bg-emerald-700 text-white border-emerald-700" : "bg-white border-slate-300"
                }`}
                data-testid="new-user-role-tecnico"
              >
                Tecnico
              </button>
              <button
                type="button"
                onClick={() => setRole("admin")}
                className={`h-11 px-4 rounded-md border font-semibold text-sm ${
                  role === "admin" ? "bg-amber-600 text-white border-amber-600" : "bg-white border-slate-300"
                }`}
                data-testid="new-user-role-admin"
              >
                Admin
              </button>
            </div>
          </div>
          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={busy} className="et-btn-primary border-0" data-testid="create-user-submit">
              {busy ? "Creo…" : "Crea utente"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditEmailDialog({ user, onClose, onDone }) {
  const [email, setEmail] = useState(user?.email || "");
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await axios.patch(`${API}/admin/users/${user.id}`, { email });
      toast.success(`Email aggiornata per ${user.username}`);
      onDone?.();
      onClose();
    } catch (e) {
      toast.error("Errore", { description: formatError(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm" data-testid="edit-email-dialog">
        <DialogHeader>
          <DialogTitle>Email — {user.username}</DialogTitle>
          
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value.toLowerCase())}
            className="h-11"
            placeholder=""
            data-testid="edit-email-input"
            autoFocus
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={busy} className="et-btn-primary border-0" data-testid="edit-email-submit">
              {busy ? "Salvo…" : "Salva email"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}


function ResetPwdDialog({ user, onClose, onDone }) {
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await axios.post(`${API}/admin/users/${user.id}/reset-password`, { new_password: pwd });
      toast.success(`Password di ${user.username} reimpostata`, {
        description: "Tutte le sessioni precedenti sono state invalidate.",
      });
      onDone?.();
      onClose();
    } catch (e) {
      toast.error("Reset fallito", { description: formatError(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm" data-testid="reset-password-dialog">
        <DialogHeader>
          <DialogTitle>Reset password — {user.username}</DialogTitle>
          
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label>Nuova password (min 6)</Label>
            <Input
              type="password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              required
              minLength={6}
              className="h-11 mt-1"
              data-testid="reset-password-input"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annulla</Button>
            <Button type="submit" disabled={busy} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="reset-password-submit">
              {busy ? "Reset…" : "Reset password"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Matrice permessi per tutti i ruoli non Admin.
const PERMISSION_MODULES = [
  ["dashboard", "Dashboard"], ["calendar", "Calendario"], ["lead", "Lead"],
  ["ordini_clienti", "Elios Tech Ordini"], ["commesse", "Commesse"],
  ["sopralluoghi", "Sopralluoghi"], ["preventivi", "Preventivi"], ["installazioni", "Installazioni"],
  ["assistenza", "Assistenza"], ["inventario", "Magazzini"], ["arrivi", "Arrivi"],
  ["spedizioni", "Spedizioni"], ["movimenti", "Movimenti"], ["anomalie", "Anomalie"], ["ai", "Assistente AI"],
];
const PERMISSION_ACTIONS = [
  ["view", "Vedi"], ["create", "Crea"], ["edit", "Modifica"], ["delete", "Elimina"], ["export", "Esporta"],
];

function PermissionsDialog({ user, onClose, onDone }) {
  const [perms, setPerms] = useState([]);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (user) {
      const src = user.permissions_customized ? user.permissions : user.effective_permissions;
      setPerms(Array.isArray(src) ? src.filter((p) => p.includes(":")) : []);
    }
  }, [user]);
  if (!user) return null;
  const keyOf = (m, a) => `${m}:${a}`;
  const has = (m, a) => perms.includes(keyOf(m, a));
  const toggle = (m, a) => setPerms((p) => {
    const k = keyOf(m, a);
    let next = p.includes(k) ? p.filter((x) => x !== k) : [...p, k];
    if (a !== "view" && !p.includes(k) && !next.includes(keyOf(m, "view"))) next.push(keyOf(m, "view"));
    if (a === "view" && p.includes(k)) next = next.filter((x) => !x.startsWith(`${m}:`));
    return next;
  });
  const toggleModule = (m) => {
    const allOn = PERMISSION_ACTIONS.every(([a]) => has(m, a));
    setPerms((p) => {
      const without = p.filter((x) => !x.startsWith(`${m}:`));
      return allOn ? without : [...without, ...PERMISSION_ACTIONS.map(([a]) => keyOf(m, a))];
    });
  };
  const save = async () => {
    setSaving(true);
    try {
      await axios.patch(`${API}/admin/users/${user.id}`, { permissions: perms });
      toast.success("Permessi aggiornati");
      onDone?.(); onClose();
    } catch (e) { toast.error("Salvataggio fallito", { description: formatError(e) }); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open={!!user} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="permissions-dialog">
        <DialogHeader>
          <DialogTitle>Permessi — {user.full_name || user.username}</DialogTitle>
          
        </DialogHeader>
        <div className="overflow-x-auto border border-slate-200 rounded-md">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left p-3">Modulo</th>
                {PERMISSION_ACTIONS.map(([a, l]) => <th key={a} className="text-center p-3">{l}</th>)}
              </tr>
            </thead>
            <tbody>
              {PERMISSION_MODULES.map(([m, label]) => (
                <tr key={m} className="border-t border-slate-100">
                  <td className="p-3 font-semibold">
                    <button type="button" onClick={() => toggleModule(m)} className="text-left hover:text-blue-700">{label}</button>
                  </td>
                  {PERMISSION_ACTIONS.map(([a]) => (
                    <td key={a} className="p-2 text-center">
                      <input type="checkbox" className="h-5 w-5 accent-slate-900" checked={has(m, a)} onChange={() => toggle(m, a)} aria-label={`${label} ${a}`} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 flex items-start gap-3">
          <input type="checkbox" className="h-5 w-5 mt-0.5 accent-slate-900" checked={perms.includes("installazioni:view_all")} onChange={() => setPerms((p) => p.includes("installazioni:view_all") ? p.filter((x) => x !== "installazioni:view_all") : [...p, "installazioni:view_all", ...(p.includes("installazioni:view") ? [] : ["installazioni:view"])])} />
          <div><div className="font-semibold text-sm text-slate-900">Installazioni · visualizza tutte</div><div className="text-xs text-slate-500 mt-0.5">Se disattivato, l'utente vede solo le installazioni assegnate al proprio account.</div></div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>Annulla</Button>
          <Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="perm-save">
            {saving ? "Salvataggio…" : "Salva permessi"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteUserDialog({ user, onClose, onDone }) {
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user) setConfirmText(""); }, [user]);
  if (!user) return null;
  const canConfirm = confirmText.trim().toUpperCase() === "ELIMINA" && !busy;
  const submit = async () => {
    setBusy(true);
    try {
      await axios.delete(`${API}/admin/users/${user.id}`);
      toast.success(`Utente ${user.username} eliminato definitivamente`);
      onDone?.();
      onClose();
    } catch (e) {
      toast.error("Eliminazione fallita", { description: formatError(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={!!user} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="delete-user-dialog">
        <DialogHeader>
          <DialogTitle className="text-red-700 flex items-center gap-2">
            <Trash size={20} weight="bold" /> Elimina definitivamente utente
          </DialogTitle>
          <DialogDescription className="text-slate-700">
            Attenzione: stai per eliminare definitivamente <b>{user.full_name || user.username}</b> (@{user.username}) e i suoi dati di accesso. L'operazione <b>non può essere annullata</b>.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="rounded-md border border-red-200 bg-red-50 text-red-800 text-xs p-3 space-y-1">
            <div>• account, credenziali e password/hash saranno rimossi</div>
            <div>• le sessioni attive verranno revocate immediatamente</div>
            <div>• lo storico Arrivi/Spedizioni/Movimenti/Audit resta intatto (username anonimizzato in "[utente eliminato]")</div>
          </div>
          <div>
            <Label htmlFor="delete-confirm" className="text-sm font-semibold">
              Per confermare, digita <span className="font-mono-tight text-red-700">ELIMINA</span>
            </Label>
            <Input
              id="delete-confirm"
              autoFocus
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && canConfirm) submit(); }}
              placeholder="ELIMINA"
              className="h-11 mt-1 font-mono-tight tracking-wider"
              data-testid="delete-user-confirm-input"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="delete-user-cancel">
            Annulla
          </Button>
          <Button
            onClick={submit}
            disabled={!canConfirm}
            className="bg-red-600 hover:bg-red-700 text-white"
            data-testid="delete-user-confirm"
          >
            <Trash size={16} className="mr-1" /> Elimina definitivamente
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminUsersPage() {
  const { user: me, isAdmin, isLoading } = useAuth();
  const iAmMaster = isMasterUser(me);
  useTz();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [emailTarget, setEmailTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [permTarget, setPermTarget] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/admin/users`);
      setUsers(data.items || []);
    } catch (e) {
      toast.error("Errore caricamento utenti", { description: formatError(e) });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin]);

  if (isLoading) return <div className="p-6 text-slate-500">Caricamento…</div>;
  if (!isAdmin) return <Navigate to="/" replace />;

  const toggleActive = async (u) => {
    try {
      await axios.patch(`${API}/admin/users/${u.id}`, { active: !u.active });
      toast.success(`Utente ${u.username} ${!u.active ? "riattivato" : "disattivato"}`);
      load();
    } catch (e) {
      toast.error("Aggiornamento fallito", { description: formatError(e) });
    }
  };

  const changeRole = async (u, newRole) => {
    if (u.role === newRole) return;
    try {
      await axios.patch(`${API}/admin/users/${u.id}`, { role: newRole });
      toast.success(`Ruolo aggiornato: ${u.username} → ${newRole}`);
      load();
    } catch (e) {
      toast.error("Aggiornamento fallito", { description: formatError(e) });
    }
  };

  const fmtDate = (v) => fmtDateTime(v);

  return (
    <div className="min-h-screen bg-slate-50 admin-users-page" data-testid="admin-users-page">


      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
          <h1 className="font-display text-2xl font-black text-slate-900">Utenti e permessi</h1>
          <Button onClick={() => setCreateOpen(true)} className="et-btn-primary border-0 h-10" data-testid="create-user-btn"><UserPlus size={16} className="mr-1" /> Nuovo utente</Button>
        </div>
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider">
            {users.length} utenti
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="reload-users-btn">
            <ArrowClockwise size={14} className={loading ? "animate-spin" : ""} />
          </Button>
        </div>

        <div className="et-card-elevated overflow-x-auto hidden sm:block">
          <table className="et-table w-full min-w-[980px]">
            <thead>
              <tr>
                <th>Utente</th>
                <th>Ruolo</th>
                <th>Stato</th>
                <th>Ultimo accesso</th>
                <th className="text-right">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = me?.id === u.id;
                const isMaster = isMasterUser(u);
                const lockChange = isMe || isMaster;
                return (
                  <tr key={u.id} data-testid={`user-row-${u.username}`}>
                    <td className="px-3 py-3 align-top">
                      <div className="font-semibold text-slate-900 text-sm truncate">{u.full_name || u.username}</div>
                      <div className="text-xs font-mono-tight text-slate-500 truncate">@{u.username}</div>
                      <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-1 min-w-0">
                        {u.email ? (
                          <span className="font-mono-tight truncate">{u.email}</span>
                        ) : (
                          <span className="text-slate-400 italic">nessuna email</span>
                        )}
                        <button
                          type="button"
                          onClick={() => setEmailTarget(u)}
                          className="text-[10px] uppercase tracking-wider text-slate-500 hover:text-slate-900 underline underline-offset-2 shrink-0"
                          data-testid={`edit-email-${u.username}`}
                        >
                          modifica
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <select
                        value={u.role}
                        onChange={(e) => changeRole(u, e.target.value)}
                        disabled={lockChange}
                        className="h-9 w-full min-w-[140px] rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700 disabled:opacity-50"
                        aria-label={`Ruolo ${u.username}`}
                      >
                        <option value="operator">Operatore</option>
                        <option value="responsabile">Responsabile</option>
                        <option value="commerciale">Commerciale</option>
                        <option value="tecnico">Tecnico</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-3 py-3 align-top">
                      {u.active ? (
                        <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 hover:bg-emerald-100 text-[10px]">
                          Attivo
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-red-200 text-red-700 bg-red-50 text-[10px]">
                          Disatt.
                        </Badge>
                      )}
                      {isMe && (
                        <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-0.5">tu</div>
                      )}
                      {isMaster && iAmMaster && (
                        <div className="text-[10px] uppercase tracking-wider text-amber-600 font-bold mt-0.5" title="Account master protetto">🔒 master</div>
                      )}
                    </td>
                    <td className="px-3 py-3 align-top text-[11px] text-slate-500 font-mono-tight truncate">
                      {fmtDate(u.last_login)}
                    </td>
                    <td className="px-3 py-3 align-top">
                      <div className="flex items-center gap-1 justify-end">
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => setPermTarget(u)}
                          disabled={isMaster || u.role === "admin"}
                          className="h-8 w-8"
                          data-testid={`perm-${u.username}`}
                          title={u.role === "admin" ? "L'Admin ha tutti i permessi" : "Permessi configurabili"}
                          aria-label="Permessi"
                        >
                          <PencilSimple size={14} weight="bold" />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => setResetTarget(u)}
                          className="h-8 w-8"
                          data-testid={`reset-${u.username}`}
                          disabled={isMaster}
                          title={isMaster ? "Account master protetto" : "Reset password"}
                          aria-label="Reset password"
                        >
                          <Key size={14} weight="bold" />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => toggleActive(u)}
                          disabled={isMe || isMaster}
                          className={`h-8 w-8 ${u.active ? "border-red-300 text-red-600 hover:bg-red-50" : "border-emerald-300 text-emerald-700 hover:bg-emerald-50"}`}
                          data-testid={`toggle-active-${u.username}`}
                          title={isMaster ? "Account master protetto" : (u.active ? "Disattiva utente" : "Riattiva utente")}
                          aria-label={u.active ? "Disattiva" : "Riattiva"}
                        >
                          <Prohibit size={14} weight="bold" />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          onClick={() => setDeleteTarget(u)}
                          disabled={isMe || isMaster}
                          className="h-8 w-8 border-red-400 text-red-700 hover:bg-red-50"
                          data-testid={`delete-${u.username}`}
                          title={isMaster ? "Account master protetto" : "Elimina definitivamente"}
                          aria-label="Elimina utente"
                        >
                          <Trash size={14} weight="bold" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                    Nessun utente.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Card view mobile — visibile solo <640px, dati identici ma verticali */}
        <div className="sm:hidden space-y-3" data-testid="users-cards-mobile">
          {users.map((u) => {
            const isMe = me?.id === u.id;
            const isMaster = isMasterUser(u);
            const lockChange = isMe || isMaster;
            return (
              <div
                key={u.id}
                className="et-card-elevated p-3 space-y-2"
                data-testid={`user-card-${u.username}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-slate-900 text-sm">
                      {u.full_name || u.username}
                    </div>
                    <div className="text-xs font-mono-tight text-slate-500">@{u.username}</div>
                    <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-1 flex-wrap">
                      {u.email ? (
                        <span className="font-mono-tight break-all">{u.email}</span>
                      ) : (
                        <span className="text-slate-400 italic">nessuna email</span>
                      )}
                      <button
                        type="button"
                        onClick={() => setEmailTarget(u)}
                        className="text-[10px] uppercase tracking-wider text-slate-500 hover:text-slate-900 underline underline-offset-2"
                      >
                        modifica
                      </button>
                    </div>
                  </div>
                  {u.active ? (
                    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 hover:bg-emerald-100 shrink-0">
                      Attivo
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="border-red-200 text-red-700 bg-red-50 shrink-0">
                      Disattivato
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-1 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-1">Ruolo</span>
                  <button
                    type="button"
                    onClick={() => changeRole(u, "operator")}
                    disabled={lockChange}
                    className={`px-2 h-8 rounded-md text-xs font-semibold border ${
                      u.role === "operator"
                        ? "bg-slate-900 text-white border-slate-900"
                        : "bg-white border-slate-300 text-slate-600"
                    } disabled:opacity-40`}
                  >
                    Operatore
                  </button>
                  <button
                    type="button"
                    onClick={() => changeRole(u, "responsabile")}
                    disabled={lockChange}
                    className={`px-2 h-8 rounded-md text-xs font-semibold border ${
                      u.role === "responsabile"
                        ? "bg-sky-700 text-white border-sky-700"
                        : "bg-white border-slate-300 text-slate-600"
                    } disabled:opacity-40`}
                  >
                    Responsabile
                  </button>
                  <button type="button" onClick={() => changeRole(u, "commerciale")} disabled={lockChange}
                    className={`px-2 h-8 rounded-md text-xs font-semibold border ${u.role === "commerciale" ? "bg-violet-700 text-white border-violet-700" : "bg-white border-slate-300 text-slate-600"} disabled:opacity-40`}>
                    Commerciale
                  </button>
                  <button type="button" onClick={() => changeRole(u, "tecnico")} disabled={lockChange}
                    className={`px-2 h-8 rounded-md text-xs font-semibold border ${u.role === "tecnico" ? "bg-emerald-700 text-white border-emerald-700" : "bg-white border-slate-300 text-slate-600"} disabled:opacity-40`}>
                    Tecnico
                  </button>
                  <button
                    type="button"
                    onClick={() => changeRole(u, "admin")}
                    disabled={lockChange}
                    className={`px-2 h-8 rounded-md text-xs font-semibold border ${
                      u.role === "admin"
                        ? "bg-amber-600 text-white border-amber-600"
                        : "bg-white border-slate-300 text-slate-600"
                    } disabled:opacity-40`}
                  >
                    Admin
                  </button>
                  {isMe && (
                    <span className="ml-1 text-[10px] uppercase tracking-wider text-slate-400">tu</span>
                  )}
                  {isMaster && iAmMaster && (
                    <span className="ml-1 text-[10px] uppercase tracking-wider text-amber-600 font-bold">🔒 master</span>
                  )}
                </div>

                <div className="text-[11px] text-slate-500 font-mono-tight">
                  Ultimo accesso: {fmtDate(u.last_login)}
                </div>

                <div className="flex flex-wrap gap-2 pt-1 border-t border-slate-100">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setPermTarget(u)}
                    disabled={isMaster || u.role === "admin"}
                    className="h-9 flex-1 min-w-[calc(50%-0.25rem)]"
                    data-testid={`m-perm-${u.username}`}
                    title={u.role === "admin" ? "L'Admin ha tutti i permessi" : "Permessi configurabili"}
                  >
                    <PencilSimple size={14} className="mr-1" /> Permessi
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setResetTarget(u)}
                    className="h-9 flex-1 min-w-[calc(50%-0.25rem)]"
                    data-testid={`m-reset-${u.username}`}
                    disabled={isMaster}
                  >
                    <Key size={14} className="mr-1" /> Reset PW
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleActive(u)}
                    disabled={isMe || isMaster}
                    className={`h-9 flex-1 min-w-[calc(50%-0.25rem)] ${u.active ? "border-red-300 text-red-600 hover:bg-red-50" : "border-emerald-300 text-emerald-700 hover:bg-emerald-50"}`}
                    data-testid={`m-toggle-${u.username}`}
                  >
                    <Prohibit size={14} className="mr-1" /> {u.active ? "Disattiva" : "Riattiva"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDeleteTarget(u)}
                    disabled={isMe || isMaster}
                    className="h-9 flex-1 min-w-[calc(50%-0.25rem)] border-red-400 text-red-700 hover:bg-red-50"
                    data-testid={`m-delete-${u.username}`}
                  >
                    <Trash size={14} className="mr-1" /> Elimina
                  </Button>
                </div>
              </div>
            );
          })}
          {users.length === 0 && !loading && (
            <div className="et-card p-4 text-center text-slate-400 text-sm">Nessun utente.</div>
          )}
        </div>
      </main>

      <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={load} />
      <ResetPwdDialog user={resetTarget} onClose={() => setResetTarget(null)} onDone={load} />
      <EditEmailDialog user={emailTarget} onClose={() => setEmailTarget(null)} onDone={load} />
      <DeleteUserDialog user={deleteTarget} onClose={() => setDeleteTarget(null)} onDone={load} />
      <PermissionsDialog user={permTarget} onClose={() => setPermTarget(null)} onDone={load} />
    </div>
  );
}
