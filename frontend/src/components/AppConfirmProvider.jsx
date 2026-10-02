import { useEffect, useRef, useState } from "react";
import { Warning, Trash, CheckCircle } from "@phosphor-icons/react";
import { registerAppConfirm } from "../lib/appConfirm";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";

export default function AppConfirmProvider({ children }) {
  const [state, setState] = useState(null);
  const resolverRef = useRef(null);

  useEffect(() => registerAppConfirm((options) => new Promise((resolve) => {
    resolverRef.current = resolve;
    setState({
      title: options.title || "Conferma operazione",
      message: options.message || "Confermi l'operazione?",
      confirmLabel: options.confirmLabel || "Conferma",
      cancelLabel: options.cancelLabel || "Annulla",
      danger: !!options.danger,
    });
  })), []);

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
        <DialogContent className="max-w-md w-[94vw]">
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
    </>
  );
}
