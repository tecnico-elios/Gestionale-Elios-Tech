from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
free = (ROOT / "routes" / "free_reports_routes.py").read_text(encoding="utf-8")
install = (ROOT / "routes" / "installation_report_routes.py").read_text(encoding="utf-8")

checks = {
    "payload pagine": 'pdf_pages: str = "all"' in free,
    "normalizzazione pagine": 'def _normalize_pdf_pages' in free,
    "scelta 2-3": 'page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3)' in free,
    "firma cliente facoltativa": 'Sono necessarie la firma del cliente e del tecnico' not in free,
    "scelta salvata": '"pdf_pages": pdf_pages' in free,
    "renderer selettivo": 'def _render_pdf(data: Dict[str, Any], out_path: Path, page_numbers=None):' in install,
    "renderer pagine": 'pages = [(i, ASSET_DIR / f"page-{i}.png") for i in selected]' in install,
    "installazioni compatibili": '_render_pdf(data, out)' in install,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R72 audit backend failed: " + ", ".join(failed))
print("[R72 audit backend] OK: PDF senza firma cliente e selezione tutte le pagine / solo 2-3 verificati.")
