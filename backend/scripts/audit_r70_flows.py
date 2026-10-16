from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
server = (ROOT / "server.py").read_text(encoding="utf-8")
route = (ROOT / "routes" / "free_reports_routes.py").read_text(encoding="utf-8")

checks = {
    "router registrato": "free_reports_routes.build_router" in server,
    "indici report": "free_technical_reports.create_index" in server,
    "api lista": '@router.get("")' in route,
    "api creazione": '@router.post("")' in route,
    "api modifica": '@router.put("/{report_id}")' in route,
    "api eliminazione": '@router.delete("/{report_id}")' in route,
    "nessun cliente obbligatorio": "linked_client_id\": None" in route,
    "campi liberi": "fields: List[FreeField]" in route,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R70 audit backend failed: " + ", ".join(failed))
print("[R70 audit backend] OK: Report liberi indipendenti con campi dinamici e CRUD completo.")
