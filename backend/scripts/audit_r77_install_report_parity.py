from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")
free_text = (ROOT / "routes" / "free_reports_routes.py").read_text(encoding="utf-8")

checks = {
    "r76 dati liberi": "Il collegamento all'installazione serve solo per proporre i valori iniziali." in text,
    "nessun overwrite anagrafica": 'for k in ("data", "cliente", "indirizzo", "tecnico", "seriali"):' not in text,
    "campo pdf_pages": 'pdf_pages: str = "all"' in text,
    "helper pdf_pages": "def _normalize_install_pdf_pages" in text,
    "get pdf_pages": '"report_installazione_pdf_pages") or "all"' in text,
    "save pdf_pages": '"report_installazione_pdf_pages": _normalize_install_pdf_pages(body.pdf_pages)' in text,
    "generate pdf_pages": 'pdf_pages = _normalize_install_pdf_pages(body.pdf_pages)' in text,
    "render selettivo": '_render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))' in text,
    "firme facoltative": 'Sono necessarie la firma del cliente e del tecnico' not in text,
    "persistenza pagine": '"report_installazione_pdf_pages": pdf_pages' in text,
    "nota installazione neutra": 'Report pre e post installazione firmato' not in text,
    "nota standalone neutra": 'Report pre e post installazione firmato, non collegato a installazione' not in free_text,
    "cliente inventario da report": 'cliente=str(data.get("cliente") or "")' in text,
    "cliente anomalie da report": '"cliente": str(data.get("cliente") or ""), "status": "open"' in text,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R77 audit backend fallito: " + ", ".join(failed))
print("[R77 audit backend] OK: report Installazioni e Report Tecnico coerenti senza perdere le correzioni R76.")
