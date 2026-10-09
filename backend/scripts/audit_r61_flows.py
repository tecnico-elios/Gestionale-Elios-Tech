from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]

for rel in [
    "calendar_installation_parser.py",
    "calendar_installation_sync.py",
    "routes/calendar_routes.py",
    "routes/admin_extra_routes.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

parser = (ROOT / "calendar_installation_parser.py").read_text(encoding="utf-8")
sync = (ROOT / "calendar_installation_sync.py").read_text(encoding="utf-8")
calendar = (ROOT / "routes" / "calendar_routes.py").read_text(encoding="utf-8")
admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")

for marker in ["plain_text", "parse_calendar_installation", "products", "comune", "provincia"]:
    if marker not in parser:
        raise RuntimeError(f"R61 audit: parser marker mancante: {marker}")
for marker in ["INSTALLATION_NORMALIZATION_VERSION", "descrizione_importata", "prodotti_da_installare", "needs_normalization"]:
    if marker not in sync:
        raise RuntimeError(f"R61 audit: sync marker mancante: {marker}")
for marker in ['@router.get("/roles")', '@router.post("/roles")', '@router.delete("/roles/{role_name}")', "validated_calendar_role"]:
    if marker not in calendar:
        raise RuntimeError(f"R61 audit: calendario marker mancante: {marker}")
for marker in ["BackgroundTasks", '@router.post("/notion/import-all/start"', "_run_notion_import_background", 'state="completed"']:
    if marker not in admin:
        raise RuntimeError(f"R61 audit: Notion background marker mancante: {marker}")

# Verifica reale del caso visto nello screenshot.
from calendar_installation_parser import parse_calendar_installation
sample = '<b><u>AVVISARE CLIENTE DI LIBERARE PARCHEGGIO!</u></b><br><b>Struttura: </b>Aura Boutique Hotel<br><b>Indirizzo: </b><a href="http://c.so/">C.so</a> Fogazzaro 238, Vicenza (VI)<br><b>Referente: </b>Laura Ricciolini<br><b>Cel: </b>342 8058087<br><b>Prodotti da installare: </b>2 pro 22 5 mt + meter + stand dual + 2 portacavo rpo<br><b>Note tecniche: </b>Installazione trifase in park esterno.'
parsed = parse_calendar_installation("Installazione Aura", sample, "")
assert "<b>" not in parsed["clean_description"] and "<br>" not in parsed["clean_description"]
assert parsed["structure"] == "Aura Boutique Hotel"
assert "Fogazzaro 238" in parsed["address"]
assert parsed["comune"] == "Vicenza" and parsed["provincia"] == "VI"
assert parsed["referente"] == "Laura Ricciolini"
assert parsed["telefono"] == "342 8058087"
assert len(parsed["products"]) >= 4 and parsed["products"][0]["quantita"] == 2

print("[R61 audit backend] OK: ruoli controllati, Notion background e normalizzazione installazioni verificati.")
