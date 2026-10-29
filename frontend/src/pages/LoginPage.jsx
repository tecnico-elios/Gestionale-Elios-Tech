import { API } from "../lib/apiBase";
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../lib/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "../components/ui/dialog";
import { Eye, EyeSlash, User as UserIcon, Lock, ShieldCheck } from "@phosphor-icons/react";
import EliosLogo from "../components/EliosLogo";
import { validatePassword, PASSWORD_POLICY_HINT } from "../lib/passwordPolicy";



function formatError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" • ");
  return err?.message || "Errore imprevisto";
}

function BootstrapForm() {
  const { bootstrapFirstAdmin } = useAuth();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      toast.error("Le password non coincidono");
      return;
    }
    const passwordError = validatePassword(password);
    if (passwordError) {
      toast.error("Password non valida", { description: passwordError });
      return;
    }
    setBusy(true);
    try {
      await bootstrapFirstAdmin({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        username: username.trim().toLowerCase(),
        password,
      });
      toast.success("Admin creato — accesso effettuato");
      navigate("/", { replace: true });
    } catch (err) {
      toast.error("Bootstrap fallito", { description: formatError(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3" data-testid="bootstrap-form">
      <div className="text-center pb-2">
        <div className="inline-flex items-center gap-1 text-[10px] tracking-[0.25em] uppercase text-amber-200/90 font-semibold border border-amber-200/30 px-2 py-0.5 rounded-full">
          <ShieldCheck size={11} /> Primo avvio
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Input
          data-testid="bootstrap-first-name"
          placeholder="Nome"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          required
          className="h-12 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 focus-visible:ring-amber-300/50"
          autoFocus
        />
        <Input
          data-testid="bootstrap-last-name"
          placeholder="Cognome"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          required
          className="h-12 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 focus-visible:ring-amber-300/50"
        />
      </div>
      <Input
        data-testid="bootstrap-username"
        placeholder="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value.toLowerCase())}
        required
        className="h-12 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 font-mono-tight focus-visible:ring-amber-300/50"
      />
      <div className="grid grid-cols-2 gap-2">
        <div className="relative">
          <Input
            data-testid="bootstrap-password"
            type={show ? "text" : "password"}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="h-12 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 focus-visible:ring-amber-300/50 pr-10"
          />
          <button type="button" onClick={() => setShow((s) => !s)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-300 hover:text-white"
            tabIndex={-1}>{show ? <EyeSlash size={16} /> : <Eye size={16} />}</button>
        </div>
        <Input
          data-testid="bootstrap-password-confirm"
          type={show ? "text" : "password"}
          placeholder="Ripeti password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
          className="h-12 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 focus-visible:ring-amber-300/50"
        />
      </div>
      <div className="text-[11px] text-slate-200/80">{PASSWORD_POLICY_HINT}</div>
      <Button
        type="submit"
        disabled={busy}
        className="h-12 w-full bg-slate-800/80 hover:bg-slate-800 text-white border border-white/10 mt-2"
        data-testid="bootstrap-submit-btn"
      >
        {busy ? "Creazione…" : "Crea amministratore"}
      </Button>
    </form>
  );
}

function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [forgotOpen, setForgotOpen] = useState(false);

  const from = location.state?.from?.pathname || "/dashboard";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await login(username.trim().toLowerCase(), password, remember);
      toast.success("Accesso effettuato");
      if (result?.mustChangePassword) {
        navigate("/force-change-password", { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      toast.error("Accesso negato", { description: formatError(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <form onSubmit={submit} className="space-y-3" data-testid="login-form">
        {/* Logo card interno */}
        <div className="flex items-center justify-center pb-2">
          <EliosLogo size={30} className="max-w-[190px]" />
        </div>

        {/* Username */}
        <div>
          <Label className="sr-only" htmlFor="lg-user">Username</Label>
          <div className="relative">
            <UserIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300/70 pointer-events-none" />
            <Input
              id="lg-user"
              data-testid="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
              placeholder="Username"
              className="h-12 pl-10 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 font-mono-tight focus-visible:ring-amber-300/50 focus-visible:border-amber-300/40"
            />
          </div>
        </div>

        {/* Password + show/hide */}
        <div>
          <Label className="sr-only" htmlFor="lg-pwd">Password</Label>
          <div className="relative">
            <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300/70 pointer-events-none" />
            <Input
              id="lg-pwd"
              data-testid="login-password"
              type={show ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              placeholder="Password"
              className="h-12 pl-10 pr-10 bg-slate-900/40 border-slate-100/30 text-white placeholder:text-slate-300/60 focus-visible:ring-amber-300/50 focus-visible:border-amber-300/40"
            />
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-300 hover:text-white"
              tabIndex={-1}
              aria-label={show ? "Nascondi password" : "Mostra password"}
              data-testid="login-toggle-password"
            >
              {show ? <EyeSlash size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        {/* Remember me */}
        <label className="flex items-center gap-2 text-slate-100/90 select-none cursor-pointer text-sm pt-1">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300 text-amber-500 focus:ring-amber-300"
            data-testid="login-remember-me"
          />
          <span>Rimani collegato</span>
        </label>

        {/* Submit */}
        <Button
          type="submit"
          disabled={busy || !username || !password}
          className="h-12 w-full bg-slate-950/70 hover:bg-slate-900 text-white border border-white/15 rounded-md mt-2 text-base font-semibold tracking-wide shadow-lg shadow-black/40"
          data-testid="login-submit-btn"
        >
          {busy ? "Verifica…" : "Accedi"}
        </Button>

        {/* Forgot password (admin flow) */}
        <div className="text-center pt-1">
          <button
            type="button"
            onClick={() => setForgotOpen(true)}
            className="text-[12px] text-slate-200/80 hover:text-white underline underline-offset-2"
            data-testid="login-forgot-password"
          >
            Password dimenticata?
          </button>
        </div>
      </form>

      <ForgotPasswordDialog open={forgotOpen} onClose={() => setForgotOpen(false)} />
    </>
  );
}

function ForgotPasswordDialog({ open, onClose }) {
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const { data } = await axios.post(`${API}/auth/forgot-password`, {
        username: username.trim().toLowerCase(),
      });
      setMsg(data.message || "Richiesta inviata.");
    } catch (err) {
      setMsg("Richiesta inviata. Se lo username esiste, verrai contattato.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="max-w-sm" data-testid="forgot-password-dialog">
        <DialogHeader>
          <DialogTitle>Password dimenticata</DialogTitle>
          <DialogDescription>
            Solo gli Amministratori possono recuperare le proprie credenziali.
            Inserisci il tuo username: un altro Admin potrà reimpostarla dalla
            sezione Utenti.
          </DialogDescription>
        </DialogHeader>
        {msg ? (
          <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded p-3" data-testid="forgot-msg">
            {msg}
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase())}
              placeholder="Il tuo username"
              className="h-11 font-mono-tight"
              required
              autoFocus
              data-testid="forgot-username"
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>Chiudi</Button>
              <Button type="submit" disabled={busy || !username} className="et-btn-primary border-0" data-testid="forgot-submit">
                {busy ? "Invio…" : "Invia richiesta"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function LoginPage() {
  const { bootstrap, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!isLoading && isAuthenticated) {
    const from = location.state?.from?.pathname || "/dashboard";
    setTimeout(() => navigate(from, { replace: true }), 0);
  }

  const showBootstrap = bootstrap?.needs_bootstrap === true;

  return (
    <div className="min-h-screen bg-slate-50 grid lg:grid-cols-[1.15fr_0.85fr]" data-testid="login-page">
      <section className="hidden lg:flex relative overflow-hidden bg-[#1A456B] text-white p-12 xl:p-16 flex-col justify-between">
        <div className="absolute inset-0 pointer-events-none" aria-hidden>
          <div className="absolute inset-0 bg-gradient-to-br from-[#1A456B] via-[#1A456B] to-[#163B5C]" />
          <div className="absolute inset-0 opacity-[0.08]" style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.8) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.8) 1px, transparent 1px)", backgroundSize: "44px 44px" }} />
          <div className="absolute right-[12%] top-[18%] h-[360px] w-[210px] rounded-[28px] border border-amber-300/20 bg-white/[0.035] shadow-2xl shadow-black/30">
            <div className="absolute left-1/2 top-8 h-3 w-3 -translate-x-1/2 rounded-full bg-amber-300/60" />
            <div className="absolute left-1/2 top-20 h-28 w-28 -translate-x-1/2 rounded-full border border-white/10" />
            <div className="absolute left-1/2 top-[130px] h-12 w-12 -translate-x-1/2 rounded-full border-2 border-amber-300/30" />
            <div className="absolute bottom-10 left-1/2 h-16 w-[2px] -translate-x-1/2 bg-amber-300/20" />
          </div>
          <div className="absolute -top-28 -left-24 w-96 h-96 rounded-full border border-amber-300/10" />
          <div className="absolute bottom-[-120px] right-[-80px] w-[520px] h-[520px] rounded-full border border-amber-300/10" />
        </div>
        <div className="relative z-10 flex items-center gap-3">
          <EliosLogo size={42} />
          <div>
            <div className="text-[11px] tracking-[0.25em] uppercase text-amber-300 font-semibold">Elios Tech</div>
            <div className="text-lg font-bold">Gestionale aziendale</div>
          </div>
        </div>
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300">Piattaforma interna</div>
          <h1 className="font-display text-5xl xl:text-6xl font-black tracking-tight leading-[1.02] mt-5">Gestionale<br /><span className="text-amber-300">Elios Tech</span></h1>
          <p className="mt-5 max-w-lg text-slate-300 text-base leading-relaxed">Commerciale, amministrazione, tecnico, magazzino e assistenza in un unico sistema autonomo.</p>
        </div>
        <div className="relative z-10 text-xs text-slate-500">Accesso riservato al personale autorizzato Elios Tech.</div>
      </section>

      <section className="flex items-start sm:items-center justify-center px-4 sm:px-8 py-4 sm:py-10 bg-white min-w-0">
        <div className="w-full max-w-md min-w-0">
          {/* Testata mobile: il logo ufficiale è bianco, quindi deve stare su fondo Elios */}
          <div className="lg:hidden mb-5 rounded-2xl bg-[#1A456B] border border-[#163B5C] shadow-sm px-4 py-4 flex items-center justify-between gap-3 overflow-hidden">
            <EliosLogo size={30} className="max-w-[175px] shrink-0" />
            <div className="text-right shrink-0">
              <div className="text-[9px] tracking-[0.20em] uppercase text-amber-300 font-semibold">Gestionale</div>
              <div className="text-xs font-bold text-white/95">aziendale</div>
            </div>
          </div>

          <div className="mb-5 sm:mb-6">
            <h2 className="font-display text-[28px] leading-[1.08] sm:text-3xl font-black text-slate-950">{showBootstrap ? "Configura il primo accesso" : "Accedi al Gestionale Elios Tech"}</h2>
            <p className="text-sm text-slate-500 mt-2">{showBootstrap ? "Crea l'amministratore iniziale del sistema." : "Inserisci le tue credenziali aziendali."}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-[#1A456B] p-4 sm:p-6 shadow-lg shadow-slate-900/10" data-testid={showBootstrap ? "bootstrap-card" : "login-card"}>
            {showBootstrap ? <BootstrapForm /> : <LoginForm />}
          </div>
          <div className="mt-4 text-center text-[10px] sm:text-[11px] text-slate-400">Gestionale Elios Tech · Database locale · Accesso protetto</div>
        </div>
      </section>
    </div>
  );
}
