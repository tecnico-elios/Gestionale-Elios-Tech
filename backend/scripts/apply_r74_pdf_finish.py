from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

# R74: sostituisce la preparazione firma R73.
# - non rende mai opachi i pixel originariamente trasparenti (fix rettangolo nero firma vuota)
# - per foto/scansioni stima il colore di fondo dai bordi e lo rende trasparente
# - ignora immagini che non contengono una quantita' minima di inchiostro
start = text.find("def _prepare_signature(data_url):")
end = text.find("\n\ndef _check", start)
if start < 0 or end < 0:
    raise RuntimeError("R74: helper _prepare_signature R73 non trovato")

new_prepare = r'''def _prepare_signature(data_url):
    """Prepara una firma senza fondi rettangolari e ignora firme realmente vuote."""
    if not data_url or "," not in str(data_url):
        return None
    raw = base64.b64decode(str(data_url).split(",", 1)[1])
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img.thumbnail((1800, 800), Image.Resampling.LANCZOS)
    if img.width < 2 or img.height < 2:
        return None

    # Se l'immagine possiede gia' trasparenza (es. SignaturePad), quella e' autorevole:
    # un pixel trasparente resta SEMPRE trasparente, anche se RGB=0,0,0.
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
                    px[xx, yy] = (r, g, b, 0)
                    continue
                # Firma disegnata: mantieni il tratto e la sua antialias originale.
                visible += 1
                px[xx, yy] = (r, g, b, a)
        # Un canvas vuoto o quasi vuoto non deve produrre alcun rettangolo nel PDF.
        if visible < max(12, int(img.width * img.height * 0.00008)):
            return None
    else:
        # Foto/scansione: stima il fondo usando una fascia lungo i bordi.
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
        # Fondo grigio/bianco: usa differenza dal fondo, non una soglia assoluta.
        visible = 0
        for yy in range(img.height):
            for xx in range(img.width):
                r, g, b, _ = px[xx, yy]
                lum = (r * 299 + g * 587 + b * 114) / 1000.0
                delta = bg_lum - lum
                if delta <= 14:
                    na = 0
                elif delta < 55:
                    na = int((delta - 14) / 41.0 * 235)
                else:
                    na = 255
                if na >= 28:
                    visible += 1
                px[xx, yy] = (r, g, b, max(0, min(255, na)))
        if visible < max(18, int(img.width * img.height * 0.00012)):
            return None

    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return None
    img = img.crop(bbox)
    if img.width < 2 or img.height < 2:
        return None

    # Margine trasparente minimo: evita il taglio dei tratti senza creare pannelli visibili.
    padded = Image.new("RGBA", (img.width + 10, img.height + 8), (255, 255, 255, 0))
    padded.paste(img, (5, 4), img)
    out = io.BytesIO()
    padded.save(out, format="PNG")
    out.seek(0)
    return out, padded.width, padded.height
'''
text = text[:start] + new_prepare + text[end:]

# Riquadro Accessori/Note: mantiene margine interno sopra/sotto e riduce il font fino a far
# entrare TUTTO il testo nel riquadro, senza invadere Lavori Extra.
old_note = '_text_box(c, 110, 1305, data.get("accessori_note"), 1090, 165, 10.0, 7.4)'
new_note = '_text_box(c, 110, 1298, data.get("accessori_note"), 1090, 138, 9.5, 6.4, 1.10)'
if old_note not in text:
    raise RuntimeError("R74: chiamata Accessori/Note R73 non trovata")
text = text.replace(old_note, new_note, 1)

# Anche Lavori Extra mantiene un margine reale dal bordo inferiore.
old_extra = '_text_box(c, 110, 1532, data.get("lavori_extra"), 660, 120, 10.0, 7.6)'
new_extra = '_text_box(c, 110, 1525, data.get("lavori_extra"), 660, 98, 9.5, 6.8, 1.10)'
if old_extra in text:
    text = text.replace(old_extra, new_extra, 1)

# Firma: R73 aveva allargato il box verso l'alto, coprendo la dicitura del modello.
# La firma viene ora posizionata soltanto nello spazio fra titolo e linea firma.
text = text.replace('_signature(c, data.get("firma_cliente"), 160, 1665, 420, 105)', '_signature(c, data.get("firma_cliente"), 180, 1698, 370, 62)')
text = text.replace('_signature(c, data.get("firma_tecnico"), 710, 1665, 420, 105)', '_signature(c, data.get("firma_tecnico"), 735, 1698, 370, 62)')

path.write_text(text, encoding="utf-8")
print("[R74 backend] note contenute nel box, firme vuote ignorate e sfondo firma foto rimosso.")
