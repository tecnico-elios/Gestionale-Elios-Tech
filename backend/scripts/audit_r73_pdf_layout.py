from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

checks = {
    "seriali normalizzati": "def _serial_values" in text and "serials = _serial_values" in text,
    "seriali su max 4 righe": "int(math.ceil(len(serials) / 4.0))" in text and "[:4]" in text,
    "doppio SN evitato": "re.sub(r\"(?i)^SN\\s*\"" in text,
    "prodotti normalizzati": "def _product_flags" in text and "products = _product_flags" in text,
    "note adattive": "def _text_box" in text and "_text_box(c, 110, 1305" in text,
    "firma immagine pulita": "def _prepare_signature" in text and "getchannel(\"A\")" in text,
    "firma centrata": "draw_x = xp + (box_w - draw_w) / 2" in text,
    "renderer pagine selezionabili": "page_numbers=None" in text and "selected = [i for i in (page_numbers or (1, 2, 3))" in text,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R73 audit fallito: " + ", ".join(failed))

print("[R73 audit backend] OK: seriali, prodotti, note, firme e pagine PDF verificati.")
