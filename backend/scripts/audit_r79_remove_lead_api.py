from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
crm = (ROOT / "routes" / "crm_routes.py").read_text(encoding="utf-8")
doc = (ROOT / "routes" / "documents_routes.py").read_text(encoding="utf-8")

checks = {
    "nessuna risorsa CRM Lead": '"lead": "crm_lead"' not in crm,
    "nessun endpoint conversione Lead": '/lead/{lead_id}/convert' not in crm,
    "nessuna risorsa documentale Lead": '"lead": ("crm_lead", "lead")' not in doc,
    "clienti ancora disponibili": '"clienti": "crm_clienti"' in crm,
    "dossier cliente preservato": '/clienti/{client_id}/dossier' in crm,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R79 audit fallito: " + ", ".join(failed))
print("[R79 audit] OK: Lead non esposto da CRM o Documenti; flussi Clienti preservati.")
