from pathlib import Path

path = Path(__file__).resolve().parents[1] / "routes" / "custom_modules_routes.py"
text = path.read_text(encoding="utf-8")
original = text

if '    "preventivi",\n' not in text.split('RETIRED_IMPORT_TITLES = {', 1)[1].split('}', 1)[0]:
    marker = '    "people",\n}'
    if marker not in text:
        raise RuntimeError("R57: RETIRED_IMPORT_TITLES non trovato")
    text = text.replace(marker, '    "people",\n    "preventivi",\n}', 1)

slug_block = text.split('RETIRED_IMPORT_SLUGS = {', 1)[1].split('}', 1)[0]
if '    "import-preventivi",\n' not in slug_block:
    marker = '    "import-people",\n}'
    if marker not in text:
        raise RuntimeError("R57: RETIRED_IMPORT_SLUGS non trovato")
    text = text.replace(marker, '    "import-people",\n    "import-preventivi",\n    "preventivi",\n}', 1)

if text != original:
    path.write_text(text, encoding="utf-8")
    print("[R57 backend] modulo amministrativo Preventivi marcato per eliminazione completa.")
else:
    print("[R57 backend] Preventivi amministrativo gia ritirato.")
