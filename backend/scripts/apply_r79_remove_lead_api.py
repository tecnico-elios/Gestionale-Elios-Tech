from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
crm_path = ROOT / "routes" / "crm_routes.py"
crm = crm_path.read_text(encoding="utf-8")

# Nessuna risorsa Lead deve restare esposta dal CRM generico.
crm = crm.replace('    "lead": "crm_lead",\n', '')

# Rimuove anche l'endpoint legacy di conversione Lead -> Cliente.
start_marker = '    @router.post("/lead/{lead_id}/convert")\n'
end_marker = '    @router.get("/clienti/{client_id}/dossier")\n'
if start_marker in crm:
    start = crm.index(start_marker)
    try:
        end = crm.index(end_marker, start)
    except ValueError as exc:
        raise RuntimeError("R79: fine blocco convert Lead non trovata") from exc
    crm = crm[:start] + crm[end:]

crm_path.write_text(crm, encoding="utf-8")
print("[R79] risorsa ed endpoint Lead rimossi dal CRM.")
