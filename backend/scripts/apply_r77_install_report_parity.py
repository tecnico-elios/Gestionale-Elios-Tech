from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str):
    global text
    if old not in text:
        raise RuntimeError(f"R77 backend: {label} non trovato")
    text = text.replace(old, new, 1)


# Payload: stessa scelta pagine disponibile nel report Tecnico standalone.
model_anchor = '    data: Dict[str, Any] = Field(default_factory=dict)\n'
if '    pdf_pages: str = "all"\n' not in text:
    replace_once(model_anchor, model_anchor + '    pdf_pages: str = "all"\n', 'campo pdf_pages')

if 'def _normalize_install_pdf_pages' not in text:
    helper_anchor = '\ndef _num(value: Any) -> float:\n'
    helper = '''\ndef _normalize_install_pdf_pages(value: Any) -> str:\n    return "2-3" if str(value or "").strip() == "2-3" else "all"\n\n'''
    replace_once(helper_anchor, helper + helper_anchor, 'helper normalizzazione pagine')

# GET: restituisce la scelta salvata insieme ai dati del report.
old_get = '        return {"data": {**prefill, **saved}, "customer_email": cliente.get("email") or "", "generated_document_id": inst.get("report_installazione_document_id")}\n'
new_get = '        return {"data": {**prefill, **saved}, "customer_email": cliente.get("email") or "", "generated_document_id": inst.get("report_installazione_document_id"), "pdf_pages": inst.get("report_installazione_pdf_pages") or "all"}\n'
if '"report_installazione_pdf_pages") or "all"' not in text:
    replace_once(old_get, new_get, 'GET pdf_pages')

# SAVE: R76 ha gia reso liberi i dati; salviamo anche la scelta pagine.
old_save = '        await db.crm_installazioni.update_one({"id": installation_id}, {"$set": {"report_installazione_data": data, "report_updated_at": datetime.now(timezone.utc), "report_updated_by": current.get("username")}})\n'
new_save = '        await db.crm_installazioni.update_one({"id": installation_id}, {"$set": {"report_installazione_data": data, "report_installazione_pdf_pages": _normalize_install_pdf_pages(body.pdf_pages), "report_updated_at": datetime.now(timezone.utc), "report_updated_by": current.get("username")}})\n'
if '"report_installazione_pdf_pages": _normalize_install_pdf_pages(body.pdf_pages)' not in text:
    replace_once(old_save, new_save, 'salvataggio pdf_pages')

# GENERATE: firme facoltative e pagine selezionabili, come nel report Tecnico.
generate_data = '        data = {**(inst.get("report_installazione_data") or {}), **body.data}\n'
if '        pdf_pages = _normalize_install_pdf_pages(body.pdf_pages)\n' not in text:
    replace_once(generate_data, generate_data + '        pdf_pages = _normalize_install_pdf_pages(body.pdf_pages)\n', 'pdf_pages generazione')

mandatory = '        if not data.get("firma_cliente") or not data.get("firma_tecnico"):\n            raise HTTPException(400, "Sono necessarie la firma del cliente e del tecnico")\n'
if mandatory in text:
    text = text.replace(mandatory, '', 1)

render_old = '        _render_pdf(data, out)\n'
render_new = '        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))\n'
if render_new not in text:
    replace_once(render_old, render_new, 'render pagine selezionate')

# Salva la scelta usata anche dopo la generazione.
final_update_anchor = '            "report_installazione_document_id": doc_id,\n            "report_generated_at": now,\n'
if '            "report_installazione_pdf_pages": pdf_pages,\n' not in text:
    replace_once(
        final_update_anchor,
        '            "report_installazione_document_id": doc_id,\n            "report_installazione_pdf_pages": pdf_pages,\n            "report_generated_at": now,\n',
        'persistenza pdf_pages generato'
    )

return_old = '        return {"ok": True, "document_id": doc_id, "filename": filename, "updated_existing": bool(existing_doc), "warehouse_changes": stock_changes, "unresolved_materials": unresolved_materials}\n'
return_new = '        return {"ok": True, "document_id": doc_id, "filename": filename, "updated_existing": bool(existing_doc), "warehouse_changes": stock_changes, "unresolved_materials": unresolved_materials, "pdf_pages": pdf_pages}\n'
if '"unresolved_materials": unresolved_materials, "pdf_pages": pdf_pages' not in text:
    replace_once(return_old, return_new, 'risposta pdf_pages')

# Ora il PDF puo essere generato prima della firma: le diciture devono essere neutrali.
text = text.replace('"note": "Report pre e post installazione firmato"', '"note": "Report pre e post installazione"')
text = text.replace('raise HTTPException(400, "Genera prima il report firmato")', 'raise HTTPException(400, "Genera prima il report")')

path.write_text(text, encoding="utf-8")

# Anche il report Tecnico standalone e generabile senza firme da R72: la nota documento non deve dichiararlo firmato.
free_path = ROOT / "routes" / "free_reports_routes.py"
free_text = free_path.read_text(encoding="utf-8")
free_text = free_text.replace(
    '"note": "Report pre e post installazione firmato, non collegato a installazione"',
    '"note": "Report pre e post installazione, non collegato a installazione"',
)
free_path.write_text(free_text, encoding="utf-8")

print("[R77 backend] report Installazioni allineato al report Tecnico: pagine selezionabili, firme facoltative e note coerenti.")
