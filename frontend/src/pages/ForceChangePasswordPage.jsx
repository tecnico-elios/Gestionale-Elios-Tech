import { API } from "../lib/apiBase";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../lib/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Eye, EyeSlash, Lock, ShieldWarning, SignOut } from "@phosphor-icons/react";
import EliosLogo from "../components/EliosLogo";
import { validatePassword, PASSWORD_POLICY_HINT } from "../lib/passwordPolicy";

function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore imprevisto";
}

export default function ForceChangePasswordPage() {
  const { user, applyRefreshedToken, refreshMe, logout } = useAuth();
  const navigate = useNavigate();
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const passwordError = validatePassword(newPwd);
    if (passwordError) { toast.error("Password non valida", { description: passwordError }); return; }
    if (newPwd !== confirm) { toast.error("Le password non coincidono"); return; }
    if (newPwd === oldPwd) { toast.error("La nuova password deve essere diversa da quella temporanea"); return; }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/auth/change-my-password`, { old_password: oldPwd, new_password: newPwd });
      if (data?.token && typeof applyRefreshedToken === "function") applyRefreshedToken(data.token);
      await refreshMe();
      toast.success("Password aggiornata — benvenuto!");
      navigate("/", { replace: true });
    } catch (err) {
      toast.error("Cambio password fallito", { description: formatError(err) });
    } finally { setBusy(false); }
  };

  const handleLogout = () => { logout(); navigate("/login", { replace: true }); };

  return (
    <div className="r52-auth-page" data-testid="force-change-password-page">
      <aside className="r52-auth-brand-panel">
        <div className="r52-auth-brand-content">
          <div className="r52-auth-logo"><EliosLogo size={46} /></div>
          <div className="r52-auth-eyebrow">Primo accesso</div>
          <h1>Proteggiamo l’accesso prima di iniziare.</h1>
          <p>Imposta la tua password personale. Dopo il salvataggio entrerai direttamente nel Gestionale Elios Tech con i permessi assegnati al tuo profilo.</p>
        </div>
      </aside>
      <main className="r52-auth-form-panel">
        <div className="r52-auth-card">
          <div className="r52-auth-card-icon"><ShieldWarning size={24} weight="duotone" /></div>
          <div className="r52-auth-card-kicker">Configurazione sicurezza</div>
          <h2>Imposta la tua password</h2>
          <div className="r52-auth-notice">Ciao <strong>{user?.full_name || user?.username}</strong>, devi sostituire la password temporanea prima di usare il gestionale.</div>

          <form onSubmit={submit} className="r52-auth-form" data-testid="force-change-form">
            <div>
              <Label>Password temporanea</Label>
              <div className="relative mt-1">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input type={show ? "text" : "password"} value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} required autoFocus className="h-12 pl-9 pr-10" data-testid="fcp-old-password" />
                <button type="button" onClick={() => setShow((s) => !s)} className="r52-auth-eye" tabIndex={-1} aria-label={show ? "Nascondi password" : "Mostra password"}>{show ? <EyeSlash size={18} /> : <Eye size={18} />}</button>
              </div>
            </div>
            <div><Label>Nuova password <span className="text-slate-400 font-normal">({PASSWORD_POLICY_HINT})</span></Label><Input type={show ? "text" : "password"} value={newPwd} onChange={(e) => setNewPwd(e.target.value)} required minLength={8} className="h-12 mt-1" data-testid="fcp-new-password" /></div>
            <div><Label>Conferma nuova password</Label><Input type={show ? "text" : "password"} value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} className="h-12 mt-1" data-testid="fcp-confirm-password" /></div>
            <Button type="submit" disabled={busy || !oldPwd || !newPwd || !confirm} className="h-12 w-full et-btn-primary border-0" data-testid="fcp-submit">{busy ? "Salvo…" : "Imposta password e continua"}</Button>
            <button type="button" onClick={handleLogout} className="r52-auth-back" data-testid="fcp-logout"><SignOut size={15} /> Annulla e torna al login</button>
          </form>
        </div>
      </main>
    </div>
  );
}