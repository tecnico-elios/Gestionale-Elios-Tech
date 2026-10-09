import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Warning, Trash, CheckCircle } from "@phosphor-icons/react";
import { API } from "../lib/apiBase";
import { registerAppConfirm } from "../lib/appConfirm";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";

export default function AppConfirmProvider({ children }) {
  const [state, setState] = useState(null);
  const [confirmImportantOps, setConfirmImportantOps] = useState(true);
  const resolverRef = useRef(null);
  const settingRef = useRef(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/settings`);
        const enabled = data?.general?.confirm_important_ops !== false;
        if (alive) setConfirmImportantOps(enabled);
        settingRef.current = enabled;
      } catch {
        settingRef.current = true;
      }
    };
    load();
    const onSettings = () => load();
    window.addEventListener("elios:settings-changed", onSettings);
    return () => {
      alive = false;
      window.removeEventListener("elios:settings-changed", onSettings);
    };
  }, []);

  useEffect(() => registerAppConfirm((options = {}) => {
    // Le operazioni distruttive restano SEMPRE protette. Per le altre l'admin può
    // disattivare la conferma generale da Impostazioni.
    if (!options.danger && !settingRef.current) return Promise.resolve(true);
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setState({
        title: options.title || "Conferma operazione",
        message: options.message || "Confermi l'operazione?",
        confirmLabel: options.confirmLabel || "Conferma",
        cancelLabel: options.cancelLabel || "Annulla",
        danger: !!options.danger,
      });
    });
  }), []);

  const finish = (value) => {
    const resolve = resolverRef.current;
    resolverRef.current = null;
    setState(null);
    resolve?.(value);
  };

  return (
    <>
      {children}
      <Dialog open={!!state} onOpenChange={(open) => { if (!open && state) finish(false); }}>
        <DialogContent className="max-w-md w-[94vw] et-modal-surface">
          <DialogHeader>
            <DialogTitle className={`flex items-center gap-2 ${state?.danger ? "text-red-700" : "text-slate-900"}`}>
              {state?.danger ? <Trash size={20} weight="bold" /> : <Warning size={20} weight="bold" className="text-amber-500" />}
              {state?.title}
            </DialogTitle>
            <DialogDescription className="text-sm leading-6 text-slate-600 whitespace-pre-line">
              {state?.message}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => finish(false)}>{state?.cancelLabel}</Button>
            <Button
              onClick={() => finish(true)}
              className={state?.danger ? "bg-red-600 hover:bg-red-700 text-white" : "et-btn-primary border-0"}
            >
              {!state?.danger && <CheckCircle size={16} className="mr-1" />}
              {state?.confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <span className="sr-only" data-confirm-important-ops={String(confirmImportantOps)} />
    </>
  );
}
