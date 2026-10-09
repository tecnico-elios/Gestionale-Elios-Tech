from __future__ import annotations

from html import unescape
from typing import Any, Dict, List
import re

INSTALLATION_NORMALIZATION_VERSION = 2

_LABEL_ALIASES = {
    "struttura": "structure",
    "cliente": "structure",
    "indirizzo": "address",
    "indirizzo installazione": "address",
    "referente": "referente",
    "cel": "telefono",
    "cell": "telefono",
    "cellulare": "telefono",
    "telefono": "telefono",
    "prodotti da installare": "products_text",
    "prodotto da installare": "products_text",
    "consegna merce": "delivery",
    "note tecniche da file excel": "technical_notes",
    "note tecniche": "technical_notes",
    "agente di vendita": "agent",
    "agente": "agent",
}
_LABEL_PATTERN = re.compile(
    r"(?im)^\s*(struttura|cliente|indirizzo installazione|indirizzo|referente|cel|cell|cellulare|telefono|prodotti da installare|prodotto da installare|consegna merce|note tecniche da file excel|note tecniche|agente di vendita|agente)\s*:\s*"
)


def plain_text(value: Any) -> str:
    """Converte HTML/rich text importato in testo leggibile, mantenendo gli a-capo."""
    text = unescape(str(value or ""))
    text = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?is)</\s*(p|div|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?is)<\s*li\b[^>]*>", "• ", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = text.replace("\xa0", " ").replace("\r", "\n")
    lines: List[str] = []
    for raw in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw).strip(" -\t")
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _products(value: str) -> List[Dict[str, Any]]:
    if not value:
        return []
    chunks = [x.strip(" ,;.-") for x in re.split(r"\s*\+\s*|\s*;\s*", value) if x.strip(" ,;.-")]
    out: List[Dict[str, Any]] = []
    for chunk in chunks:
        match = re.match(r"^([0-9]+(?:[.,][0-9]+)?)\s+(.+)$", chunk)
        if match:
            raw_qty = match.group(1).replace(",", ".")
            qty_num = float(raw_qty)
            qty: Any = int(qty_num) if qty_num.is_integer() else qty_num
            name = match.group(2).strip(" ,;.-")
        else:
            qty, name = 1, chunk
        if name:
            out.append({"nome": name, "quantita": qty})
    return out


def _address_parts(address: str) -> Dict[str, str]:
    out = {"comune": "", "provincia": "", "cap": ""}
    if not address:
        return out
    prov = re.search(r"\(([A-Za-z]{2})\)\s*$", address)
    if prov:
        out["provincia"] = prov.group(1).upper()
    cap = re.search(r"\b(\d{5})\b", address)
    if cap:
        out["cap"] = cap.group(1)
    tail = re.sub(r"\s*\([A-Za-z]{2}\)\s*$", "", address).strip()
    pieces = [p.strip() for p in tail.split(",") if p.strip()]
    if len(pieces) >= 2:
        candidate = pieces[-1]
        candidate = re.sub(r"\b\d{5}\b", "", candidate).strip()
        if candidate:
            out["comune"] = candidate
    return out


def parse_calendar_installation(title: Any, description: Any, location: Any) -> Dict[str, Any]:
    clean_title = plain_text(title)
    clean_description = plain_text(description)
    clean_location = plain_text(location)

    fields: Dict[str, str] = {}
    matches = list(_LABEL_PATTERN.finditer(clean_description))
    intro = clean_description[: matches[0].start()].strip() if matches else clean_description
    for index, match in enumerate(matches):
        label = re.sub(r"\s+", " ", match.group(1).casefold()).strip()
        key = _LABEL_ALIASES.get(label)
        if not key:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(clean_description)
        value = clean_description[match.end():end].strip(" \n:;-")
        if value and not fields.get(key):
            fields[key] = value

    address = fields.get("address") or clean_location
    parts = _address_parts(address)
    technical_notes = fields.get("technical_notes", "")
    delivery = fields.get("delivery", "")

    instruction_parts: List[str] = []
    if intro:
        instruction_parts.append(intro)
    if technical_notes and technical_notes.casefold() not in {x.casefold() for x in instruction_parts}:
        instruction_parts.append(technical_notes)
    if delivery and delivery not in {"-", "—"}:
        instruction_parts.append(f"Consegna merce: {delivery}")
    instructions = "\n\n".join(x for x in instruction_parts if x).strip() or clean_description

    return {
        "title": clean_title,
        "clean_description": clean_description,
        "structure": fields.get("structure", ""),
        "address": address,
        "comune": parts["comune"],
        "provincia": parts["provincia"],
        "cap": parts["cap"],
        "referente": fields.get("referente", ""),
        "telefono": fields.get("telefono", ""),
        "agent": fields.get("agent", ""),
        "products_text": fields.get("products_text", ""),
        "products": _products(fields.get("products_text", "")),
        "technical_notes": technical_notes,
        "delivery": delivery,
        "instructions": instructions,
    }
