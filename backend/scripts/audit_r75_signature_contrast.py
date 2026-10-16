from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

checks = {
    "firma nera": 'px[xx, yy] = (0, 0, 0, alpha)' in text,
    "boost firma trasparente": 'int(a * 1.45) + 25' in text,
    "box tecnico grande": '_signature(c, data.get("firma_tecnico"), 690, 1690, 460, 72)' in text,
    "crop stretto": 'img.width + 4, img.height + 4' in text,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R75 audit fallito: " + ", ".join(failed))
print("[R75 audit backend] OK: firma tecnico piu scura, grande e leggibile.")
