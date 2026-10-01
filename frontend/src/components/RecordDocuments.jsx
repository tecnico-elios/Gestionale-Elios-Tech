import { API } from "../lib/apiBase";
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Camera, FileText, Trash, UploadSimple, Eye, X } from "@phosphor-icons/react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { useAuth } from "../lib/AuthContext";
import { appConfirm } from "../lib/appConfirm";



function errText(e) {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : e?.message || "Errore";
}
function fmtBytes(n) {
  const x = Number(n || 0);
  if (x < 1024) return `${x} B`;
  if (x < 1024 * 1024) return `${(x / 1024).toFixed(1)} KB`;
  return `${(x / 1024 / 1024).toFixed(1)} MB`;
}

export default function RecordDocuments({ open, onOpenChange, resource, recordId, title = "Documenti", module }) {
  const { hasPermission, isTecnico } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState("Documento");
  const techInstallDocs = isTecnico && resource === "installazioni";
  const [note, setNote] = useState("");
  const fileRef = useRef(null);
  const photoRef = useRef(null);
  const cameraRef = useRef(null);
  const canEdit = hasPermission(module, "edit");
  const canDelete = hasPermission(module, "delete");

  const load = async () => {
    if (!recordId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/files/${resource}/${recordId}`);
      setItems(data.items || []);
    } catch (e) {
      toast.error("Impossibile caricare i documenti", { description: errText(e) });
    } finally { setLoading(false); }
  };
  useEffect(() => {
    if (open && recordId) {
      if (techInstallDocs) setCategory("Report fotografico");
      load();
    }
  }, [open, recordId, techInstallDocs]); // eslint-disable-line react-hooks/exhaustive-deps

  const uploadFiles = async (files, forcedCategory = null) => {
    if (!files?.length || !recordId) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("category", forcedCategory || category || "Documento");
        fd.append("note", note || "");
        await axios.post(`${API}/files/${resource}/${recordId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      toast.success(files.length === 1 ? "File caricato" : `${files.length} file caricati`);
      setNote("");
      await load();
    } catch (e) {
      toast.error("Caricamento non riuscito", { description: errText(e) });
    } finally { setUploading(false); }
  };

  const openFile = async (doc) => {
    try {
      const { data } = await axios.get(`${API}/files/download/${doc.id}`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error("Impossibile aprire il file", { description: errText(e) }); }
  };

  const remove = async (doc) => {
    if (!(await appConfirm({ title: "Elimina documento", message: `Eliminare definitivamente “${doc.filename}”?`, confirmLabel: "Elimina", danger: true }))) return;
    try {
      await axios.delete(`${API}/files/document/${doc.id}`);
      toast.success("Documento eliminato");
      await load();
    } catch (e) { toast.error("Eliminazione non riuscita", { description: errText(e) }); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto p-0">
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-slate-200">
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="p-4 sm:p-5 space-y-4">
          {canEdit && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3 sm:p-4 space-y-3">
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <Label>Tipo documento</Label>
                  <select className="mt-1 h-12 w-full rounded-md border border-slate-300 bg-white px-3 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
                    {techInstallDocs ? (<>
                      <option>Report fotografico</option><option>Report installazione</option><option>Altro</option>
                    </>) : (<>
                      <option>Documento</option><option>Foto</option><option>Report fotografico</option><option>Report sopralluogo</option><option>Report installazione</option><option>Contratto</option><option>Fattura</option><option>Preventivo firmato</option><option>Verbale</option><option>Schema tecnico</option><option>Altro</option>
                    </>)}
                  </select>
                </div>
                <div>
                  <Label>Nota</Label>
                  <Input className="mt-1 h-12" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Descrizione facoltativa" />
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <input ref={fileRef} className="hidden" type="file" multiple onChange={(e) => { uploadFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
                <input ref={photoRef} className="hidden" type="file" accept="image/*" multiple onChange={(e) => { uploadFiles(Array.from(e.target.files || []), techInstallDocs ? category : "Foto"); e.target.value = ""; }} />
                <input ref={cameraRef} className="hidden" type="file" accept="image/*" capture="environment" onChange={(e) => { uploadFiles(Array.from(e.target.files || []), techInstallDocs ? category : "Foto"); e.target.value = ""; }} />
                <Button type="button" variant="outline" className="h-12" disabled={uploading} onClick={() => fileRef.current?.click()}><UploadSimple size={18} /> Allega file</Button>
                <Button type="button" variant="outline" className="h-12" disabled={uploading} onClick={() => photoRef.current?.click()}><UploadSimple size={18} /> Allega foto</Button>
                <Button type="button" className="h-12" disabled={uploading} onClick={() => cameraRef.current?.click()}><Camera size={18} /> Scatta foto</Button>
              </div>
            </div>
          )}

          {loading ? <div className="py-8 text-center text-slate-500">Caricamento documenti…</div> : items.length === 0 ? (
            <div className="py-10 text-center border border-dashed border-slate-300 rounded-md text-slate-500">Nessun documento caricato.</div>
          ) : (
            <div className="space-y-2">
              {items.map((doc) => (
                <div key={doc.id} className="border border-slate-200 rounded-md p-3 flex items-center gap-3 bg-white">
                  <div className="h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center shrink-0"><FileText size={20} /></div>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-sm truncate">{doc.filename}</div>
                    <div className="text-xs text-slate-500 flex flex-wrap gap-x-2"><span>{doc.category}</span><span>{fmtBytes(doc.size)}</span><span>Caricato da {doc.created_by || "—"}</span></div>
                    {doc.note && <div className="text-xs text-slate-600 mt-1">{doc.note}</div>}
                  </div>
                  <Button variant="outline" size="icon" className="h-10 w-10" onClick={() => openFile(doc)} title="Apri"><Eye size={17} /></Button>
                  {canDelete && <Button variant="outline" size="icon" className="h-10 w-10 text-red-600 border-red-200" onClick={() => remove(doc)} title="Elimina"><Trash size={17} /></Button>}
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end"><Button variant="outline" onClick={() => onOpenChange(false)}><X size={16} /> Chiudi</Button></div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
