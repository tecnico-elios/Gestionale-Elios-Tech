from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

start = text.find("def _prepare_signature(data_url):")
end = text.find("\n\ndef _check", start)
if start < 0 or end < 0:
    raise RuntimeError("R75: helper _prepare_signature non trovato")

new_prepare = r'''def _prepare_signature(data_url):
    """Rende la firma nitida, scura e trasparente, rimuovendo il fondo della foto."""
    if not data_url or "," not in str(data_url):
        return None
    raw = base64.b64decode(str(data_url).split(",", 1)[1])
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img.thumbnail((1800, 800), Image.Resampling.LANCZOS)
    if img.width < 2 or img.height < 2:
        return None

    original_alpha = img.getchannel("A")
    alpha_extrema = original_alpha.getextrema()
    has_transparency = alpha_extrema[0] < 250
    px = img.load()

    if has_transparency:
        visible = 0
        for yy in range(img.height):
            for xx in range(img.width):
                r, g, b, a = px[xx, yy]
                if a <= 8:
                    px[xx, yy] = (0, 0, 0, 0)
                    continue
                # Firma disegnata: conserva l'antialias ma rende il tratto nero e piu' leggibile.
                boosted = min(255, int(a * 1.45) + 25)
                if boosted >= 28:
                    visible += 1
                px[xx, yy] = (0, 0, 0, boosted)
        if visible < max(12, int(img.width * img.height * 0.00008)):
            return None
    else:
        # Foto/scansione: stima la luminosita' del fondo dai bordi.
        border_lums = []
        step_x = max(1, img.width // 80)
        step_y = max(1, img.height // 40)
        for xx in range(0, img.width, step_x):
            for yy in (0, min(2, img.height - 1), max(0, img.height - 3), img.height - 1):
                r, g, b, _ = px[xx, yy]
                border_lums.append((r * 299 + g * 587 + b * 114) / 1000.0)
        for yy in range(0, img.height, step_y):
            for xx in (0, min(2, img.width - 1), max(0, img.width - 3), img.width - 1):
                r, g, b, _ = px[xx, yy]
                border_lums.append((r * 299 + g * 587 + b * 114) / 1000.0)
        border_lums.sort()
        bg_lum = border_lums[len(border_lums) // 2] if border_lums else 245.0

        visible = 0
        for yy in range(img.height):
            for xx in range(img.width):
                r, g, b, _ = px[xx, yy]
                lum = (r * 299 + g * 587 + b * 114) / 1000.0
                delta = bg_lum - lum
                # Soglia piu' netta della R74: elimina il fondo e rende nero il tratto.
                if delta <= 11:
                    alpha = 0
                elif delta < 32:
                    alpha = int((delta - 11) / 21.0 * 210)
                elif delta < 60:
                    alpha = 210 + int((delta - 32) / 28.0 * 45)
                else:
                    alpha = 255
                alpha = max(0, min(255, alpha))
                if alpha >= 24:
                    visible += 1
                px[xx, yy] = (0, 0, 0, alpha)
        if visible < max(18, int(img.width * img.height * 0.00012)):
            return None

    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return None
    img = img.crop(bbox)
    if img.width < 2 or img.height < 2:
        return None

    # Margine minimo: la firma deve sfruttare quasi tutto il box disponibile.
    padded = Image.new("RGBA", (img.width + 4, img.height + 4), (255, 255, 255, 0))
    padded.paste(img, (2, 2), img)
    out = io.BytesIO()
    padded.save(out, format="PNG")
    out.seek(0)
    return out, padded.width, padded.height
'''
text = text[:start] + new_prepare + text[end:]

# R75: aumenta l'area della firma senza salire sopra il titolo.
# Cliente resta invariato; tecnico piu' largo e leggermente piu' alto, centrato sopra la riga.
old_tech = '_signature(c, data.get("firma_tecnico"), 735, 1698, 370, 62)'
new_tech = '_signature(c, data.get("firma_tecnico"), 690, 1690, 460, 72)'
if old_tech not in text:
    raise RuntimeError("R75: box firma tecnico R74 non trovato")
text = text.replace(old_tech, new_tech)

path.write_text(text, encoding="utf-8")
print("[R75 backend] firma tecnico scurita, ingrandita e riallineata.")
