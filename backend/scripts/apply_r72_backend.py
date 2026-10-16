from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
free_path = ROOT / "routes" / "free_reports_routes.py"
install_path = ROOT / "routes" / "installation_report_routes.py"
free = free_path.read_text(encoding="utf-8")
install = install_path.read_text(encoding="utf-8")

# Il renderer ufficiale resta compatibile con Installazioni, ma può renderizzare solo le pagine richieste.
old_render = '''def _render_pdf(data: Dict[str, Any], out_path: Path):
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pages = [ASSET_DIR / f"page-{i}.png" for i in (1, 2, 3)]
    for idx, bg in enumerate(pages, start=1):'''
new_render = '''def _render_pdf(data: Dict[str, Any], out_path: Path, page_numbers=None):
    c = canvas.Canvas(str(out_path), pagesize=A4)
    selected = [i for i in (page_numbers or (1, 2, 3)) if i in (1, 2, 3)]
    if not selected:
        selected = [1, 2, 3]
    pages = [(i, ASSET_DIR / f"page-{i}.png") for i in selected]
    for idx, bg in pages:'''
if 'def _render_pdf(data: Dict[str, Any], out_path: Path, page_numbers=None):' not in install:
    if old_render not in install:
        raise RuntimeError("R72 backend: renderer PDF anchor non trovato")
    install = install.replace(old_render, new_render, 1)

# Payload report standalone: salva anche la scelta delle pagine.
model_anchor = '    data: Dict[str, Any] = Field(default_factory=dict)\n'
if '    pdf_pages: str = "all"' not in free:
    if model_anchor not in free:
        raise RuntimeError("R72 backend: model anchor non trovato")
    free = free.replace(model_anchor, model_anchor + '    pdf_pages: str = "all"\n', 1)

if 'def _normalize_pdf_pages' not in free:
    anchor = '\ndef build_router(db, deps) -> APIRouter:\n'
    helper = '''\ndef _normalize_pdf_pages(value: Any) -> str:\n    return "2-3" if str(value or "").strip() == "2-3" else "all"\n\n'''
    if anchor not in free:
        raise RuntimeError("R72 backend: build_router anchor non trovato")
    free = free.replace(anchor, helper + anchor, 1)

# GET singolo: restituisce la scelta salvata.
get_anchor = '            "generated_document_id": doc.get("generated_document_id"),\n            "title": doc.get("title") or _display_title(doc.get("data") or {}),\n'
if '            "pdf_pages": doc.get("pdf_pages") or "all",\n' not in free:
    if get_anchor not in free:
        raise RuntimeError("R72 backend: get report anchor non trovato")
    free = free.replace(get_anchor, '            "generated_document_id": doc.get("generated_document_id"),\n            "pdf_pages": doc.get("pdf_pages") or "all",\n            "title": doc.get("title") or _display_title(doc.get("data") or {}),\n', 1)

# CREATE.
create_anchor = '            "title": _display_title(data),\n            "data": data,\n            "created_by": str(current.get("username") or ""),\n'
if '            "pdf_pages": _normalize_pdf_pages(body.pdf_pages),\n' not in free:
    if create_anchor not in free:
        raise RuntimeError("R72 backend: create anchor non trovato")
    free = free.replace(create_anchor, '            "title": _display_title(data),\n            "data": data,\n            "pdf_pages": _normalize_pdf_pages(body.pdf_pages),\n            "created_by": str(current.get("username") or ""),\n', 1)

# UPDATE bozza.
update_anchor = '                "data": data,\n                "title": _display_title(data),\n                "updated_at": datetime.now(timezone.utc),\n'
if '                "pdf_pages": _normalize_pdf_pages(body.pdf_pages),\n' not in free:
    if update_anchor not in free:
        raise RuntimeError("R72 backend: update anchor non trovato")
    free = free.replace(update_anchor, '                "data": data,\n                "title": _display_title(data),\n                "pdf_pages": _normalize_pdf_pages(body.pdf_pages),\n                "updated_at": datetime.now(timezone.utc),\n', 1)

# Generazione: le firme sono opzionali. Se manca la firma cliente il PDF resta firmabile esternamente.
mandatory = '''        if not data.get("firma_cliente") or not data.get("firma_tecnico"):\n            raise HTTPException(400, "Sono necessarie la firma del cliente e del tecnico")\n\n'''
if mandatory in free:
    free = free.replace(mandatory, '', 1)

data_anchor = '        data = {**(existing.get("data") or {}), **(body.data or {})}\n'
if '        pdf_pages = _normalize_pdf_pages(body.pdf_pages)\n' not in free:
    if data_anchor not in free:
        raise RuntimeError("R72 backend: generate data anchor non trovato")
    free = free.replace(data_anchor, data_anchor + '        pdf_pages = _normalize_pdf_pages(body.pdf_pages)\n', 1)

render_call = '        _render_pdf(data, out)\n'
render_selected = '        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))\n'
if render_selected not in free:
    if render_call not in free:
        raise RuntimeError("R72 backend: render call non trovato")
    free = free.replace(render_call, render_selected, 1)

# Salva la scelta effettivamente usata nel documento.
gen_update_anchor = '            "generated_document_id": doc_id,\n            "pdf_path": str(out),\n            "updated_at": now,\n'
if '            "pdf_pages": pdf_pages,\n' not in free:
    if gen_update_anchor not in free:
        raise RuntimeError("R72 backend: generate update anchor non trovato")
    free = free.replace(gen_update_anchor, '            "generated_document_id": doc_id,\n            "pdf_path": str(out),\n            "pdf_pages": pdf_pages,\n            "updated_at": now,\n', 1)

return_anchor = '        return {"ok": True, "id": report_id, "document_id": doc_id, "updated_existing": updated_existing}\n'
if '"pdf_pages": pdf_pages' not in return_anchor and return_anchor in free:
    free = free.replace(return_anchor, '        return {"ok": True, "id": report_id, "document_id": doc_id, "updated_existing": updated_existing, "pdf_pages": pdf_pages}\n', 1)

free_path.write_text(free, encoding="utf-8")
install_path.write_text(install, encoding="utf-8")
print("[R72 backend] PDF standalone generabile senza firme e con scelta pagine all / 2-3.")
