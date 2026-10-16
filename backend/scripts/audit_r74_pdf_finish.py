from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

checks = {
    "firma trasparente preservata": 'if a <= 8:' in text,
    "firma vuota ignorata": 'if visible < max(12' in text,
    "fondo foto stimato dai bordi": 'bg_lum = border_lums[len(border_lums) // 2]' in text,
    "note contenute": '_text_box(c, 110, 1298, data.get("accessori_note"), 1090, 138, 9.5, 6.4, 1.10)' in text,
    "lavori extra contenuti": '_text_box(c, 110, 1525, data.get("lavori_extra"), 660, 98, 9.5, 6.8, 1.10)' in text,
    "firma cliente sotto etichetta": '_signature(c, data.get("firma_cliente"), 180, 1698, 370, 62)' in text,
    "firma tecnico sotto etichetta": '_signature(c, data.get("firma_tecnico"), 735, 1698, 370, 62)' in text,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise RuntimeError("R74 audit fallito: " + ", ".join(missing))

compile(text, str(path), "exec")
print("[R74 audit backend] OK: note dentro il riquadro, firma vuota invisibile e firma immagine senza fondo.")
