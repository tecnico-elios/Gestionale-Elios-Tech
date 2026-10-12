from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
calendar = (ROOT / "routes" / "calendar_routes.py").read_text(encoding="utf-8")

checks = {
    "lead exclusion remains active": 'skipped_leads' in calendar and 'R56_CALENDAR_FILTERS' in calendar,
    "holidays are not excluded": 'Festività in Italia"), _norm("Holidays in Italy")): continue' not in calendar,
    "Google originals preferred": "shadow_keys" in calendar and "manual_ids" in calendar,
    "technical interventions calendar": 'synth("Intervento tecnico", "crm_interventi_tecnici"' in calendar,
    "derived duplicates removed": 'calendar_event_id' in calendar and 'not in manual_ids' in calendar,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R65 audit failed: " + ", ".join(failed))
print("[R65 audit backend] OK: importa tutto tranne Lead, conserva originali Google e rimuove duplicati derivati.")