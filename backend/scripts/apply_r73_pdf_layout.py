from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

# Dipendenze helper: regex, math e Pillow per pulizia firma da immagine.
if "import math\n" not in text:
    text = text.replace("import io\n", "import io\nimport math\nimport re\n", 1)
if "from PIL import Image\n" not in text:
    text = text.replace("from reportlab.pdfgen import canvas\n", "from reportlab.pdfgen import canvas\nfrom PIL import Image\n", 1)

# Box di testo adattivo: usa larghezza reale e riduce il font finche' tutto il testo entra.
if "def _text_box(" not in text:
    anchor = "\ndef _check(c, x, y, checked, box_size=20):\n"
    helper = r'''
def _text_box(c, x, y, value, width_px, height_px, size=10.0, min_size=7.2, leading_factor=1.18):
    value = str(value or "").strip()
    if not value:
        return
    width_pt = width_px / PAGE_W_PX * A4_W
    height_pt = height_px / PAGE_H_PX * A4_H
    xp, yp = _px(x, y)

    def wrap(font_size):
        words = value.split()
        lines, line = [], ""
        for word in words:
            candidate = (line + " " + word).strip()
            if line and c.stringWidth(candidate, "Helvetica", font_size) > width_pt:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines

    font_size = float(size)
    lines = wrap(font_size)
    while font_size > min_size:
        leading = font_size * leading_factor
        if len(lines) * leading <= height_pt:
            break
        font_size = round(font_size - 0.2, 2)
        lines = wrap(font_size)
    leading = font_size * leading_factor
    max_lines = max(1, int(height_pt // leading))
    c.setFont("Helvetica", font_size)
    for idx, line in enumerate(lines[:max_lines]):
        if idx == max_lines - 1 and len(lines) > max_lines:
            while line and c.stringWidth(line + "…", "Helvetica", font_size) > width_pt:
                line = line[:-1]
            line = line.rstrip() + "…"
        c.drawString(xp, yp - idx * leading, line)


def _serial_values(value):
    """Estrae seriali puliti anche da stringhe tipo 'SN 123-SN 456-789'."""
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result = []
    seen = set()
    for raw in raw_values:
        s = str(raw or "").strip()
        if not s:
            continue
        # Il campo contiene esclusivamente seriali: estrai token alfanumerici plausibili,
        # ignorando il prefisso SN e i separatori usati dagli operatori.
        tokens = re.findall(r"(?i)(?:\bSN\s*)?([A-Z0-9]{5,})", s)
        if not tokens:
            tokens = [p for p in re.split(r"[\s,;|/\\-]+", s) if len(p) >= 5]
        for token in tokens:
            serial = re.sub(r"(?i)^SN\s*", "", str(token)).strip(" -_/;,.")
            if serial and serial.upper() not in seen:
                seen.add(serial.upper())
                result.append(serial)
    return result


def _product_flags(value):
    values = value if isinstance(value, (list, tuple, set)) else [value]
    normalized = []
    for item in values:
        s = str(item or "").lower().replace("_", " ").replace("-", " ")
        normalized.append(" ".join(s.split()))
    flags = set()
    for s in normalized:
        if not s:
            continue
        if "pro socket" in s:
            flags.add("Pro Socket")
        elif "pro" in s:
            flags.add("Pro")
        if "max" in s:
            flags.add("Max")
        if "copper" in s:
            flags.add("Copper")
    return flags


def _prepare_signature(data_url):
    """Ritaglia bordi/sfondo chiaro delle firme caricate e restituisce PNG trasparente."""
    if not data_url or "," not in str(data_url):
        return None
    raw = base64.b64decode(str(data_url).split(",", 1)[1])
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    # Limita immagini enormi caricate da telefono/fotocamera.
    img.thumbnail((1800, 800), Image.Resampling.LANCZOS)
    px = img.load()
    for yy in range(img.height):
        for xx in range(img.width):
            r, g, b, a = px[xx, yy]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if lum >= 178:
                na = 0
            elif lum >= 145:
                na = int((178 - lum) / 33 * 220)
            else:
                na = min(255, max(a, 235))
            px[xx, yy] = (r, g, b, na)
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return None
    img = img.crop(bbox)
    # piccolo margine trasparente per non tagliare i tratti estremi
    padded = Image.new("RGBA", (img.width + 16, img.height + 12), (255, 255, 255, 0))
    padded.paste(img, (8, 6), img)
    out = io.BytesIO()
    padded.save(out, format="PNG")
    out.seek(0)
    return out, padded.width, padded.height
'''
    if anchor not in text:
        raise RuntimeError("R73: anchor _check non trovato")
    text = text.replace(anchor, helper + anchor, 1)

# Sostituisce il renderer firma con crop, trasparenza e centratura nel box.
start = text.find("def _signature(c, data_url, x, y, w, h):")
end = text.find("\n\ndef _render_pdf", start)
if start < 0 or end < 0:
    raise RuntimeError("R73: funzione _signature non trovata")
new_signature = r'''def _signature(c, data_url, x, y, w, h):
    try:
        prepared = _prepare_signature(data_url)
        if not prepared:
            return
        stream, iw, ih = prepared
        xp, top = _px(x, y)
        box_w = w / PAGE_W_PX * A4_W
        box_h = h / PAGE_H_PX * A4_H
        ratio = min(box_w / max(iw, 1), box_h / max(ih, 1))
        draw_w = iw * ratio
        draw_h = ih * ratio
        draw_x = xp + (box_w - draw_w) / 2
        draw_y = top - box_h + (box_h - draw_h) / 2
        c.drawImage(ImageReader(stream), draw_x, draw_y, width=draw_w, height=draw_h, mask="auto")
    except Exception:
        return
'''
text = text[:start] + new_signature + text[end:]

# Prodotti: accetta sia 'Pro' sia descrizioni complete tipo 'Wallbox Pulsar Pro'.
old_products = '''            products = set(data.get("prodotti") or [])
            for label, y in [("Pro",810),("Pro Socket",845),("Max",880),("Copper",914)]:
                _check(c, 134, y, label in products, 20)'''
new_products = '''            products = _product_flags(data.get("prodotti") or [])
            for label, y in [("Pro",810),("Pro Socket",845),("Max",880),("Copper",914)]:
                _check(c, 134, y, label in products, 20)'''
if old_products in text:
    text = text.replace(old_products, new_products, 1)
elif "products = _product_flags" not in text:
    raise RuntimeError("R73: blocco prodotti non trovato")

# Seriali: massimo 4 righe del modello, distribuendo 2/3 seriali per riga se necessario.
old_serials = '''            serials = list(data.get("seriali") or [])[:6]
            for i, serial in enumerate(serials):
                _fit_text(c, 185, 1050 + i*51, serial, 12.0, 270, 10.5)'''
new_serials = '''            serials = _serial_values(data.get("seriali"))
            if serials:
                per_row = max(1, min(3, int(math.ceil(len(serials) / 4.0))))
                rows = [serials[i:i + per_row] for i in range(0, len(serials), per_row)][:4]
                shown = sum(len(r) for r in rows)
                for i, row in enumerate(rows):
                    label = " / ".join(row)
                    if i == 3 and shown < len(serials):
                        label += f" / +{len(serials) - shown}"
                    _fit_text(c, 185, 1050 + i*51, label, 11.7, 390, 7.8)'''
if old_serials in text:
    text = text.replace(old_serials, new_serials, 1)
elif "serials = _serial_values" not in text:
    raise RuntimeError("R73: blocco seriali non trovato")

# Note e lavori extra: usa tutto lo spazio disponibile invece di troncare a 4 righe.
old_notes = '''            _text(c, 110, 1305, data.get("accessori_note"), 10.0, 92)
            _text(c, 110, 1532, data.get("lavori_extra"), 10.0, 78)'''
new_notes = '''            _text_box(c, 110, 1305, data.get("accessori_note"), 1090, 165, 10.0, 7.4)
            _text_box(c, 110, 1532, data.get("lavori_extra"), 660, 120, 10.0, 7.6)'''
if old_notes in text:
    text = text.replace(old_notes, new_notes, 1)
elif "_text_box(c, 110, 1305" not in text:
    raise RuntimeError("R73: blocco note non trovato")

# Firma tecnico/cliente piu' ampia e centrata sulla linea, su pagine 1 e 3.
text = text.replace('_signature(c, data.get("firma_cliente"), 180, 1690, 370, 80)', '_signature(c, data.get("firma_cliente"), 160, 1665, 420, 105)')
text = text.replace('_signature(c, data.get("firma_tecnico"), 735, 1690, 370, 80)', '_signature(c, data.get("firma_tecnico"), 710, 1665, 420, 105)')

path.write_text(text, encoding="utf-8")
print("[R73 backend] seriali, prodotti, note e firme PDF corretti.")
