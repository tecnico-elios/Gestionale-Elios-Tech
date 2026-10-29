import { API } from "../lib/apiBase";
import { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Eye, EyeSlash, Lock, CheckCircle, ArrowLeft } from "@phosphor-icons/react";
import EliosLogo from "../components/EliosLogo";
import { validatePassword, PASSWORD_POLICY_HINT } from "../lib/passwordPolicy";

function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore";
}

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const [newPwd, setNewPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) navigate("/login", { replace: true });
  }, [token, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    if (newPwd !== confirm) { toast.error("Le password non coincidono"); return; }
    const passwordError = validatePassword(newPwd);
    if (passwordError) { toast.error("Password non valida", { description: passwordError }); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/auth/reset-password`, { token, new_password: newPwd });
      setDone(true);
      toast.success("Password aggiornata — puoi accedere");
      setTimeout(() => navigate("/login", { replace: true }), 1200);
    } catch (err) {
      toast.error("Errore", { description: formatError(err) });
    } finally { setBusy(false); }
  };

  return (
    <div className="r52-auth-page" data-testid="reset-password-page">
      <aside className="r52-auth-brand-panel">
        <div className="r52-auth-brand-content">
          <div className="r52-auth-logo"><EliosLogo size={46} /></div>
          <div className="r52-auth-eyebrow">Gestionale Elios Tech</div>
          <h1>Accesso sicuro al tuo spazio operativo.</h1>
          <p>Reimposta la password e torna al gestionale mantenendo invariati dati, ruoli e autorizzazioni.</p>
        </div>
      </aside>
      <main className="r52-auth-form-panel">
        <div className="r52-auth-card">
          <div className="r52-auth-card-icon"><Lock size={24} weight="duotone" /></div>
          <div className="r52-auth-card-kicker">Sicurezza account</div>
          <h2>Reimposta password</h2>
          <p className="r52-auth-card-copy">Inserisci la nuova password. Il link è valido una sola volta e per 1 ora.</p>
          <p className="text-xs text-slate-500 mt-1">{PASSWORD_POLICY_HINT}</p>

          {done ? (
            <div className="r52-auth-success"><CheckCircle size={20} weight="fill" /><div><b>Password aggiornata</b><span>Reindirizzamento al login…</span></div></div>
          ) : (
            <form onSubmit={submit} className="r52-auth-form">
              <div>
                <Label>Nuova password</Label>
                <div className="relative mt-1">
                  <Input type={show ? "text" : "password"} value={newPwd} onChange={(e) => setNewPwd(e.target.value)} required minLength={8} className="h-12 pr-10" autoFocus data-testid="reset-new-password" />
                  <button type="button" onClick={() => setShow((s) => !s)} className="r52-auth-eye" tabIndex={-1} aria-label={show ? "Nascondi password" : "Mostra password"}>{show ? <EyeSlash size={17} /> : <Eye size={17} />}</button>
                </div>
              </div>
              <div>
                <Label>Ripeti password</Label>
                <Input type={show ? "text" : "password"} value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} className="h-12 mt-1" data-testid="reset-confirm-password" />
              </div>
              <Button type="submit" disabled={busy} className="h-12 w-full et-btn-primary border-0" data-testid="reset-submit-btn">{busy ? "Aggiorno…" : "Aggiorna password"}</Button>
              <Link to="/login" className="r52-auth-back"><ArrowLeft size={15} /> Torna al login</Link>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}