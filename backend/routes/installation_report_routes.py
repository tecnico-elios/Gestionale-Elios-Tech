from __future__ import annotations

import base64
import io
import math
import re
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PIL import Image

import auth as auth_mod
import email_service
import inventory_local
import persistent_files

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "report_installazione"
UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT") or (Path(__file__).resolve().parent.parent / "uploads" / "installazioni"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

PAGE_W_PX = 1324.0
PAGE_H_PX = 1872.0
A4_W, A4_H = A4


class ReportBody(BaseModel):
    model_config = {"extra": "allow"}
    data: Dict[str, Any] = Field(default_factory=dict)
    pdf_pages: str = "all"


class SendBody(BaseModel):
    recipient: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None


def _px(x: float, y: float):
    return (x / PAGE_W_PX * A4_W, A4_H - (y / PAGE_H_PX * A4_H))


def _clean_words(value: str) -> str:
    value = " ".join(str(value or "").strip().split())
    if not value:
        return ""
    keep_upper = {"PC", "PR", "MI", "LO", "RE", "MO", "BG", "BS", "CR", "PV", "MN"}
    words = []
    for token in value.split(" "):
        raw = token.strip()
        plain = raw.strip(",.;()")
        if plain.upper() in keep_upper or plain.isdigit() or any(ch.isdigit() for ch in plain):
            words.append(raw.upper())
        elif raw:
            # Mantiene apostrofi e trattini ma rende leggibili indirizzi salvati tutti minuscoli.
            words.append("-".join(part[:1].upper()+part[1:].lower() if part else part for part in raw.split("-")))
    return " ".join(words)


def _format_address(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    chunks = [c.strip() for c in value.split(",") if c.strip()]
    if not chunks:
        return _clean_words(value)
    return ", ".join(_clean_words(c) for c in chunks)


def _fit_text(c, x, y, value, size=10.8, max_width_px=520, min_size=8.8):
    """Scrive su una sola riga riducendo leggermente il font solo se serve."""
    value = str(value or "").strip()
    if not value:
        return
    xp, yp = _px(x, y)
    max_width = max_width_px / PAGE_W_PX * A4_W
    font_size = float(size)
    while font_size > min_size and c.stringWidth(value, "Helvetica", font_size) > max_width:
        font_size -= 0.2
    c.setFont("Helvetica", font_size)
    c.drawString(xp, yp, value)


def _text(c, x, y, value, size=9.2, max_chars=70):
    value = str(value or "").strip()
    if not value:
        return
    c.setFont("Helvetica", size)
    xp, yp = _px(x, y)
    # basic wrapping; preserves the original form underneath.
    words = value.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if len(candidate) > max_chars and line:
            lines.append(line); line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for idx, ln in enumerate(lines[:4]):
        c.drawString(xp, yp - idx * (size + 2), ln)


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


def _check(c, x, y, checked, box_size=20):
    """Disegna una X realmente dentro la casella del modello.

    x/y sono le coordinate (pixel del template 1324x1872) dell'angolo
    superiore sinistro della casella. Usiamo due linee invece del carattere
    tipografico X, così il segno resta centrato e non dipende dal font.
    """
    if not checked:
        return
    pad = 4.0
    x1, y1 = _px(x + pad, y + pad)
    x2, y2 = _px(x + box_size - pad, y + box_size - pad)
    x3, y3 = _px(x + box_size - pad, y + pad)
    x4, y4 = _px(x + pad, y + box_size - pad)
    c.saveState()
    c.setLineWidth(1.05)
    c.line(x1, y1, x2, y2)
    c.line(x3, y3, x4, y4)
    c.restoreState()


def _date_fields(c, value, day_x, month_x, year_x, y, size=9.2):
    """Compila separatamente gg / mm / aaaa sulle tre righe del modello."""
    raw = str(value or "").strip()
    if not raw:
        return
    parts = []
    if "/" in raw:
        parts = raw.split("/")
    elif "-" in raw:
        iso = raw.split("-")
        if len(iso) == 3:
            parts = [iso[2], iso[1], iso[0]]
    if len(parts) != 3:
        _text(c, day_x, y, raw, size, 12)
        return
    _text(c, day_x, y, parts[0], size, 2)
    _text(c, month_x, y, parts[1], size, 2)
    _text(c, year_x, y, parts[2], size, 4)


def _signature(c, data_url, x, y, w, h):
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


def _render_pdf(data: Dict[str, Any], out_path: Path, page_numbers=None):
    c = canvas.Canvas(str(out_path), pagesize=A4)
    selected = [i for i in (page_numbers or (1, 2, 3)) if i in (1, 2, 3)]
    if not selected:
        selected = [1, 2, 3]
    pages = [(i, ASSET_DIR / f"page-{i}.png") for i in selected]
    for idx, bg in pages:
        c.drawImage(str(bg), 0, 0, width=A4_W, height=A4_H)
        if idx == 1:
            _fit_text(c, 310, 340, data.get("societa_installatrice"), 12.2, 420, 10.8)
            _fit_text(c, 310, 370, data.get("tecnico"), 12.2, 420, 10.8)
            _fit_text(c, 310, 398, _format_address(data.get("indirizzo")), 12.0, 490, 10.5)
            _fit_text(c, 455, 558, data.get("cliente"), 12.2, 500, 10.8)
            _fit_text(c, 310, 588, _format_address(data.get("indirizzo")), 12.0, 650, 10.5)
            _fit_text(c, 185, 618, data.get("telefono"), 11.8, 210, 10.5)
            _fit_text(c, 515, 618, data.get("email"), 11.8, 300, 10.2)
            for key, y in [("quadro_idoneo",741),("quadro_non_conforme",770),("surriscaldamento",800),("protezioni_assenti",829),("sezione_cavi_non_idonea",858),("messa_terra_non_conforme",887)]:
                _check(c, 76, y, data.get(key), 16)
            _text(c, 155, 925, data.get("altro_verifica"), 7.6, 58)
            _text(c, 75, 1018, data.get("criticita"), 7.4, 105)
            _check(c, 76, 1107, data.get("nessuna_criticita"), 16)
            scelta = data.get("scelta_cliente")
            _check(c, 60, 1528, scelta == "autorizza", 16)
            _check(c, 60, 1559, scelta == "adeguamento", 16)
            _check(c, 60, 1589, scelta == "rinvia", 16)
            _signature(c, data.get("firma_cliente"), 180, 1698, 370, 62)
            _signature(c, data.get("firma_tecnico"), 690, 1690, 460, 72)
            _date_fields(c, data.get("data"), 322, 386, 455, 1794, 11.8)
        elif idx == 2:
            _fit_text(c, 135, 515, data.get("tecnico"), 12.6, 255, 11.0)
            _fit_text(c, 135, 625, data.get("cliente"), 12.6, 255, 11.0)
            _fit_text(c, 135, 735, _format_address(data.get("indirizzo")), 12.0, 430, 10.4)
            products = _product_flags(data.get("prodotti") or [])
            for label, y in [("Pro",810),("Pro Socket",845),("Max",880),("Copper",914)]:
                _check(c, 134, y, label in products, 20)
            serials = _serial_values(data.get("seriali"))
            if serials:
                per_row = max(1, min(3, int(math.ceil(len(serials) / 4.0))))
                rows = [serials[i:i + per_row] for i in range(0, len(serials), per_row)][:4]
                shown = sum(len(r) for r in rows)
                for i, row in enumerate(rows):
                    label = " / ".join(row)
                    if i == 3 and shown < len(serials):
                        label += f" / +{len(serials) - shown}"
                    _fit_text(c, 185, 1050 + i*51, label, 11.7, 390, 7.8)
            tipo = data.get("tipo_installazione")
            _check(c, 136, 1445, tipo == "Su Muro", 20)
            _check(c, 136, 1480, tipo == "Su Stand", 20)
            _fit_text(c, 140, 1668, data.get("orario_inizio"), 12.2, 180, 11.0)
            _fit_text(c, 140, 1818, data.get("orario_fine"), 12.2, 180, 11.0)
            cavo = str(data.get("cavo_fg16") or "")
            for label, y in [("4mmq",378),("6mmq",413),("10mmq",448),("16mmq",482)]:
                _check(c, 785, y, cavo == label, 20)
            if cavo:
                _fit_text(c, 910, {"4mmq":392,"6mmq":427,"10mmq":462,"16mmq":497}.get(cavo,392), (f"{data.get('cavo_fg16_mt')} m" if data.get('cavo_fg16_mt') not in (None, '') else ''), 11.8, 155, 10.4)
            _check(c, 951, 541, bool(data.get("cavo_rs485_qta")), 21); _fit_text(c, 860, 602, (f"{data.get('cavo_rs485_qta')} m" if data.get('cavo_rs485_qta') not in (None, '') else ''), 11.8, 115, 10.4)
            _check(c, 1154, 540, bool(data.get("raccorderia_qta")), 21); _fit_text(c, 1075, 602, data.get("raccorderia_qta"), 11.8, 115, 10.4)
            for key, y, qx, qy in [
                ("quadretto_qta",656,860,708),("tubazione_qta",759,860,812),("guaina_qta",871,860,922),
                ("clips_qta",967,860,1020),("stand_mono_qta",1071,860,1122),("stand_dual_qta",1167,860,1219),
                ("cable_dock_qta",1256,860,1310)]:
                checked = bool(data.get(key))
                _check(c, 783 if y not in (871,967) else 779, y, checked, 21)
                value = data.get(key)
                if key == "tubazione_qta" and checked and data.get("tubazione_misura"):
                    value = f"Ø{str(data.get('tubazione_misura')).replace(' mm','')} · {value} m"
                elif key == "guaina_qta" and checked and data.get("guaina_misura"):
                    value = f"Ø{str(data.get('guaina_misura')).replace(' mm','')} · {value} m"
                _fit_text(c, qx, qy, value, 11.8, 145, 10.0)
            _check(c, 784, 1355, bool(data.get("meter")), 20)
            _check(c, 784, 1389, bool(data.get("meter_clamps")), 20)
            _check(c, 784, 1501, bool(data.get("scavo_mt")), 20); _fit_text(c, 860, 1562, data.get("scavo_mt"), 11.8, 145, 10.4)
            _check(c, 784, 1605, bool(data.get("plinto_qta")), 20); _fit_text(c, 860, 1660, data.get("plinto_qta"), 11.8, 145, 10.4)
            _check(c, 784, 1709, bool(data.get("fori_qta")), 20); _fit_text(c, 860, 1762, data.get("fori_qta"), 11.8, 145, 10.4)
        else:
            _text_box(c, 110, 1298, data.get("accessori_note"), 1090, 138, 9.5, 6.4, 1.10)
            _text_box(c, 110, 1525, data.get("lavori_extra"), 660, 98, 9.5, 6.8, 1.10)
            _fit_text(c, 1055, 1588, data.get("costo_lavori_extra"), 10.0, 130)
            _signature(c, data.get("firma_cliente"), 180, 1698, 370, 62)
            _signature(c, data.get("firma_tecnico"), 690, 1690, 460, 72)
            _date_fields(c, data.get("data"), 322, 386, 455, 1794, 11.8)
        c.showPage()
    c.save()


def _normalize_install_pdf_pages(value: Any) -> str:
    return "2-3" if str(value or "").strip() == "2-3" else "all"


def _num(value: Any) -> float:
    try:
        text = str(value or "").strip().replace(",", ".")
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def _norm(value: Any) -> str:
    import re
    text = str(value or "").lower().replace("ø", " ")
    text = text.replace("mm²", "mmq").replace("mm2", "mmq")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _variant_key(value: Any) -> str:
    return _norm(value).replace(" ", "-")


async def _auto_verona_consumption(db, data: Dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Traduce il report tecnico in consumi del Magazzino Verona senza chiedere nulla al tecnico.

    Prima usa eventuali mappature amministrative salvate in `report_material_mappings`.
    In assenza di mappatura prova una corrispondenza prudente su nome/codice/categoria.
    Se non c'è una corrispondenza univoca, il report viene comunque generato e il materiale
    viene registrato come `da_associare`, senza scaricare un prodotto sbagliato.
    """
    items = await inventory_local.list_inventory(warehouse_id=inventory_local.WAREHOUSE_VERONA)
    active = [x for x in items if x.get("active") is not False and x.get("tipo_gestione") == "a_quantita"]

    specs = []
    fg = str(data.get("cavo_fg16") or "").strip()
    if _num(data.get("cavo_fg16_mt")) > 0:
        specs.append(("cavo_fg16", fg, _num(data.get("cavo_fg16_mt")), "m", ["fg16", fg]))
    if _num(data.get("cavo_rs485_qta")) > 0:
        specs.append(("cavo_rs485", "", _num(data.get("cavo_rs485_qta")), "m", ["rs485"]))
    if _num(data.get("raccorderia_qta")) > 0:
        specs.append(("raccorderia", "", _num(data.get("raccorderia_qta")), "pz", ["raccord"]))
    if _num(data.get("quadretto_qta")) > 0:
        specs.append(("quadretto", "", _num(data.get("quadretto_qta")), "pz", ["quadretto", "differenziale", "magnetotermico"]))
    if _num(data.get("tubazione_qta")) > 0:
        specs.append(("tubazione", data.get("tubazione_misura") or "", _num(data.get("tubazione_qta")), "m", ["tubazione", "tubo", data.get("tubazione_misura") or ""]))
    if _num(data.get("guaina_qta")) > 0:
        specs.append(("guaina", data.get("guaina_misura") or "", _num(data.get("guaina_qta")), "m", ["guaina", data.get("guaina_misura") or ""]))
    if _num(data.get("clips_qta")) > 0:
        specs.append(("clips", "", _num(data.get("clips_qta")), "pz", ["clip", "viti"]))
    if _num(data.get("stand_mono_qta")) > 0:
        specs.append(("stand_mono", "", _num(data.get("stand_mono_qta")), "pz", ["stand", "mono"]))
    if _num(data.get("stand_dual_qta")) > 0:
        specs.append(("stand_dual", "", _num(data.get("stand_dual_qta")), "pz", ["stand", "dual"]))
    if _num(data.get("cable_dock_qta")) > 0:
        specs.append(("cable_dock", "", _num(data.get("cable_dock_qta")), "pz", ["cable", "dock"]))
    if _num(data.get("plinto_qta")) > 0:
        specs.append(("plinto", "", _num(data.get("plinto_qta")), "pz", ["plinto", "staffa"]))
    if data.get("meter"):
        specs.append(("meter", "", 1.0, "pz", ["meter"]))
    if data.get("meter_clamps"):
        specs.append(("meter_clamps", "", 1.0, "pz", ["meter", "clamp"]))

    resolved: list[dict] = []
    unresolved: list[dict] = []
    for key, variant, qty, unit, tokens in specs:
        variant_key = _variant_key(variant)
        mapping = await db.report_material_mappings.find_one({
            "warehouse_id": inventory_local.WAREHOUSE_VERONA,
            "material_key": key,
            "variant": variant_key,
        })
        if not mapping and variant_key:
            mapping = await db.report_material_mappings.find_one({
                "warehouse_id": inventory_local.WAREHOUSE_VERONA,
                "material_key": key,
                "variant": "",
            })
        if mapping:
            pid = str(mapping.get("product_id") or "")
            item = next((x for x in active if str(x.get("id")) == pid), None)
            if item:
                resolved.append({"product_id": pid, "quantity": qty, "material_key": key, "variant": variant_key})
                continue

        norm_tokens = [_norm(t) for t in tokens if _norm(t)]
        candidates = []
        for item in active:
            item_unit = str(item.get("unit") or "pz").lower()
            if unit == "m" and item_unit not in ("m", "mt", "metro", "metri"):
                continue
            if unit == "pz" and item_unit in ("m", "mt", "metro", "metri"):
                continue
            hay = _norm(" ".join(str(item.get(k) or "") for k in ("name", "code", "category", "brand")))
            score = 0.0
            for tok in norm_tokens:
                if tok and tok in hay:
                    score += 2.0 if len(tok) > 2 else 1.0
            # Meter non deve finire su Meter Clamps e viceversa.
            if key == "meter" and "clamp" in hay:
                score -= 4
            if key == "meter_clamps" and "clamp" not in hay:
                score -= 4
            if variant_key and _norm(variant) in hay:
                score += 2.5
            if score > 0:
                candidates.append((score, item))
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = None
        if candidates:
            best_score = candidates[0][0]
            second = candidates[1][0] if len(candidates) > 1 else -1
            # Accetta solo match sufficient e non ambiguo.
            if best_score >= 2.0 and best_score > second + 0.5:
                chosen = candidates[0][1]
        if chosen:
            pid = str(chosen.get("id"))
            resolved.append({"product_id": pid, "quantity": qty, "material_key": key, "variant": variant_key})
            # Memorizza il match riuscito: i report successivi non devono rifare l'associazione
            # né dipendere da eventuali rinomine del prodotto.
            await db.report_material_mappings.update_one(
                {"warehouse_id": inventory_local.WAREHOUSE_VERONA, "material_key": key, "variant": variant_key},
                {"$set": {"product_id": pid, "source": "auto", "updated_at": datetime.now(timezone.utc)},
                 "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
        else:
            unresolved.append({
                "material_key": key, "variant": variant_key, "quantity": qty, "unit": unit,
                "description": " ".join(str(t) for t in tokens if str(t).strip()),
            })
    return resolved, unresolved


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/installation-reports", tags=["installation-reports"])
    dep = deps.require_password_current

    async def _get_installation(installation_id: str, current):
        inst = await db.crm_installazioni.find_one({"id": installation_id})
        if not inst:
            raise HTTPException(404, "Installazione non trovata")
        if not (current.get("role") == auth_mod.ROLE_ADMIN or auth_mod.is_master_user(current) or auth_mod.has_permission(current, "installazioni", "view_all")):
            uid = str(current.get("_id") or current.get("id") or "")
            assigned = str(inst.get("tecnico_user_id") or "")
            aliases = {str(current.get(k) or "").strip().lower() for k in ("username","full_name","email")}
            tech = str(inst.get("tecnico") or "").strip().lower()
            if not ((uid and uid == assigned) or (tech and tech in aliases)):
                raise HTTPException(403, "Questa installazione non è assegnata al tuo utente")
        return inst

    async def _prefill(inst):
        cliente = await db.crm_clienti.find_one({"id": str(inst.get("cliente_id") or "")}) or {}
        sede = await db.crm_sedi.find_one({"id": str(inst.get("sede_id") or "")}) or {}
        comm = await db.commesse.find_one({"id": str(inst.get("commessa_id") or "")}) or {}
        client_name = cliente.get("ragione_sociale") or " ".join(x for x in [cliente.get("nome"), cliente.get("cognome")] if x) or inst.get("cliente_nome") or ""
        addr = " ".join(x for x in [sede.get("indirizzo"), sede.get("civico")] if x).strip()
        loc = " ".join(x for x in [sede.get("cap"), sede.get("comune"), sede.get("provincia")] if x).strip()
        serials = []
        for row in comm.get("righe") or []:
            serials.extend(row.get("seriali_prelevati") or [])
            serials.extend(row.get("seriali_spediti") or [])
        serials = list(dict.fromkeys(str(x) for x in serials if x))
        date_val = inst.get("data") or datetime.now().date().isoformat()
        try:
            display_date = datetime.fromisoformat(str(date_val)).strftime("%d/%m/%Y")
        except Exception:
            display_date = str(date_val)
        return {
            "data": display_date,
            "cliente": _clean_words(client_name),
            "indirizzo": _format_address(", ".join(x for x in [addr, loc] if x)),
            "tecnico": _clean_words(inst.get("tecnico") or ""),
            "seriali": serials[:6],
        }

    @router.get("/template")
    async def download_template(current=Depends(dep)):
        path = ASSET_DIR / "modello_originale.pdf"
        if not path.exists():
            raise HTTPException(404, "Modello report non disponibile")
        return FileResponse(path, media_type="application/pdf", filename="DOCUMENTO PRE E POST INSTALLAZIONE.pdf")

    @router.get("/{installation_id}")
    async def get_report(installation_id: str, current=Depends(dep)):
        inst = await _get_installation(installation_id, current)
        prefill = await _prefill(inst)
        saved = inst.get("report_installazione_data") or {}
        cliente = await db.crm_clienti.find_one({"id": str(inst.get("cliente_id") or "")}) or {}
        return {"data": {**prefill, **saved}, "customer_email": cliente.get("email") or "", "generated_document_id": inst.get("report_installazione_document_id"), "pdf_pages": inst.get("report_installazione_pdf_pages") or "all"}

    @router.put("/{installation_id}")
    async def save_report(installation_id: str, body: ReportBody, current=Depends(dep)):
        inst = await _get_installation(installation_id, current)
        if not auth_mod.has_permission(current, "installazioni", "edit"):
            raise HTTPException(403, "Non hai il permesso di compilare il report")
        # Il collegamento all'installazione serve solo per proporre i valori iniziali.
        # Dopo la compilazione il report conserva esattamente i valori inseriti dall'utente.
        data = {**body.data}
        await db.crm_installazioni.update_one({"id": installation_id}, {"$set": {"report_installazione_data": data, "report_installazione_pdf_pages": _normalize_install_pdf_pages(body.pdf_pages), "report_updated_at": datetime.now(timezone.utc), "report_updated_by": current.get("username")}})
        return {"ok": True, "data": data}

    @router.post("/{installation_id}/generate")
    async def generate_report(installation_id: str, body: ReportBody, current=Depends(dep)):
        inst = await _get_installation(installation_id, current)
        if not auth_mod.has_permission(current, "installazioni", "edit"):
            raise HTTPException(403, "Non hai il permesso di generare il report")
        # I dati salvati/modificati nel report prevalgono sempre sui dati dell'installazione.
        data = {**(inst.get("report_installazione_data") or {}), **body.data}
        pdf_pages = _normalize_install_pdf_pages(body.pdf_pages)
        # Il tecnico compila solo il report. Le associazioni con il Magazzino Verona
        # vengono risolte automaticamente dal gestionale, senza tendine di magazzino.
        desired_consumption, unresolved_materials = await _auto_verona_consumption(db, data)
        try:
            stock_changes = await inventory_local.reconcile_report_consumption(
                installation_id, desired_consumption, cliente=str(data.get("cliente") or ""),
                operator=str(current.get("username") or ""),
                report_date=datetime.now(timezone.utc).date().isoformat(),
            )
        except RuntimeError as exc:
            # Una giacenza insufficiente è un problema amministrativo, ma non deve impedire
            # al tecnico di chiudere e firmare il report legale. La segnaliamo all'ufficio.
            unresolved_materials.append({"material_key": "stock", "variant": "", "quantity": 0, "unit": "", "description": str(exc)})
            stock_changes = []

        await db.report_material_unresolved.delete_many({"installation_id": installation_id})
        if unresolved_materials:
            now_unresolved = datetime.now(timezone.utc)
            await db.report_material_unresolved.insert_many([
                {**row, "id": str(uuid.uuid4()), "installation_id": installation_id,
                 "cliente": str(data.get("cliente") or ""), "status": "open",
                 "created_at": now_unresolved, "updated_at": now_unresolved}
                for row in unresolved_materials
            ])
        folder = UPLOAD_ROOT / installation_id
        folder.mkdir(parents=True, exist_ok=True)
        # Un solo report per intervento: le modifiche sovrascrivono lo stesso PDF
        # invece di creare Report_1, Report_2, Report_3 uguali.
        filename = "Report_pre_post_installazione.pdf"
        out = folder / filename
        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))
        gridfs_id = await persistent_files.replace_bytes(
            db, inst.get("report_installazione_gridfs_id"), out.read_bytes(), filename, "application/pdf",
            metadata={"resource": "installazioni", "record_id": installation_id, "category": "Report installazione"},
        )
        now = datetime.now(timezone.utc)
        existing_id = inst.get("report_installazione_document_id")
        existing_doc = await db.documents.find_one({"id": existing_id}) if existing_id else None
        if existing_doc:
            doc_id = existing_id
            old_path = Path(existing_doc.get("stored_path") or "")
            if old_path and old_path != out and old_path.exists():
                try:
                    old_path.unlink()
                except OSError:
                    pass
            await db.documents.update_one({"id": doc_id}, {"$set": {
                "filename": filename, "stored_path": str(out), "content_type": "application/pdf",
                "size": out.stat().st_size, "gridfs_id": gridfs_id, "storage": "gridfs", "category": "Report installazione",
                "note": "Report pre e post installazione",
                "updated_at": now, "updated_by": current.get("username"),
            }})
        else:
            doc_id = str(uuid.uuid4())
            await db.documents.insert_one({
                "id": doc_id, "resource": "installazioni", "record_id": installation_id,
                "filename": filename, "stored_path": str(out), "content_type": "application/pdf",
                "size": out.stat().st_size, "gridfs_id": gridfs_id, "storage": "gridfs", "category": "Report installazione",
                "note": "Report pre e post installazione",
                "created_at": now, "created_by": current.get("username"),
            })

        # Pulisce eventuali copie storiche create dalle versioni precedenti del gestionale.
        duplicates = await db.documents.find({
            "resource": "installazioni", "record_id": installation_id,
            "category": "Report installazione", "id": {"$ne": doc_id},
        }).to_list(length=100)
        for dup in duplicates:
            old = Path(dup.get("stored_path") or "")
            if old.exists() and old != out:
                try:
                    old.unlink()
                except OSError:
                    pass
            await persistent_files.delete_bytes(db, dup.get("gridfs_id"))
            await db.documents.delete_one({"id": dup.get("id")})

        await db.crm_installazioni.update_one({"id": installation_id}, {"$set": {
            "report_installazione_data": data,
            "report_installazione_document_id": doc_id,
            "report_installazione_gridfs_id": gridfs_id,
            "report_installazione_pdf_pages": pdf_pages,
            "report_generated_at": now,
            "report_generated_by": current.get("username"),
        }})
        return {"ok": True, "document_id": doc_id, "filename": filename, "updated_existing": bool(existing_doc), "warehouse_changes": stock_changes, "unresolved_materials": unresolved_materials, "pdf_pages": pdf_pages}

    @router.get("/{installation_id}/pdf")
    async def download_latest(installation_id: str, current=Depends(dep)):
        inst = await _get_installation(installation_id, current)
        doc_id = inst.get("report_installazione_document_id")
        if not doc_id:
            raise HTTPException(404, "Report non ancora generato")
        doc = await db.documents.find_one({"id": doc_id})
        if not doc:
            raise HTTPException(404, "File report non disponibile")
        report_path = Path(doc.get("stored_path") or "")
        if not report_path.exists() and doc.get("gridfs_id"):
            try:
                report_path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), report_path)
            except FileNotFoundError:
                pass
        if not report_path.exists():
            raise HTTPException(404, "File report non disponibile")
        return FileResponse(doc["stored_path"], media_type="application/pdf", filename=doc.get("filename") or "report_installazione.pdf")

    @router.post("/{installation_id}/send")
    async def send_report(installation_id: str, body: SendBody, current=Depends(dep)):
        inst = await _get_installation(installation_id, current)
        if current.get("role") == auth_mod.ROLE_TECNICO:
            raise HTTPException(403, "L'invio al cliente è disponibile all'ufficio, non al tecnico")
        doc_id = inst.get("report_installazione_document_id")
        if not doc_id:
            raise HTTPException(400, "Genera prima il report")
        doc = await db.documents.find_one({"id": doc_id})
        if not doc:
            raise HTTPException(404, "File report non disponibile")
        report_path = Path(doc.get("stored_path") or "")
        if not report_path.exists() and doc.get("gridfs_id"):
            try:
                report_path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), report_path)
            except FileNotFoundError:
                pass
        if not report_path.exists():
            raise HTTPException(404, "File report non disponibile")
        cliente = await db.crm_clienti.find_one({"id": str(inst.get("cliente_id") or "")}) or {}
        recipient = (body.recipient or cliente.get("email") or "").strip()
        if not recipient:
            raise HTTPException(400, "Il cliente non ha un indirizzo email")
        subject = body.subject or "Report installazione - Elios Tech"
        message = body.message or "In allegato trovi copia del report pre e post installazione."
        try:
            await email_service.send_email_with_attachment(db, recipient, subject, f"<p>{message}</p>", Path(doc["stored_path"]), doc.get("filename") or "report_installazione.pdf", "application/pdf")
        except Exception as exc:
            raise HTTPException(500, str(exc))
        await db.crm_installazioni.update_one({"id": installation_id}, {"$push": {"report_email_log": {
            "recipient": recipient, "sent_at": datetime.now(timezone.utc), "sent_by": current.get("username"), "document_id": doc_id,
        }}})
        return {"ok": True, "recipient": recipient}

    return router
