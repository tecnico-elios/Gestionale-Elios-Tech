from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "admin_extra_routes.py"
text = path.read_text(encoding="utf-8")
original = text


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if new in text and old not in text:
        print(f"[R67 backend] {label}: già applicato")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"R67 backend: {label}: atteso 1 blocco, trovati {count}")
    text = text.replace(old, new, 1)
    print(f"[R67 backend] {label}: OK")


replace_once(
    "from notion_order_inventory_bridge import sync_order_wallbox_serials\n",
    "from notion_order_inventory_bridge import sync_order_wallbox_serials, normalize_codes, reconcile_order_wallbox_serials\n",
    "import bridge R67",
)

# _notion_value restituisce già una list per multi_select. Convertirla con str(...).split(',')
# inseriva parentesi e apici nei codici cliente/ordine.
replace_once(
    '''                codes_val = _notion_value(props, "Codice prodotto") or ""\n                codes = [x.strip() for x in str(codes_val).split(",") if x.strip()]\n''',
    '''                codes_val = _notion_value(props, "Codice prodotto") or []\n                codes = normalize_codes(codes_val)\n''',
    "parsing multi-select Codice prodotto Ordini correnti",
)

replace_once(
    '''                codes_raw = _notion_value(props, "Codice prodotto") or ""\n                codes = [x.strip() for x in str(codes_raw).split(",") if x.strip()]\n''',
    '''                codes_raw = _notion_value(props, "Codice prodotto") or []\n                codes = normalize_codes(codes_raw)\n''',
    "parsing multi-select Codice prodotto Ordini storici",
)

# L'Inventario è la fonte autorevole dell'anagrafica Elios: marchiamo esplicitamente
# warehouse e codice normalizzato, così il bridge non crea doppioni per alias/case.
replace_once(
    '''                    "name": it.get("name") or code,\n                    "code": code,\n                    "category": it.get("category"),\n''',
    '''                    "name": it.get("name") or code,\n                    "code": code,\n                    "code_lower": code.casefold(),\n                    "warehouse_id": "elios-tech",\n                    "import_source": "notion_inventory",\n                    "category": it.get("category"),\n''',
    "anagrafica Inventario autorevole",
)

# Un seriale deve essere globale: se una vecchia R66 lo aveva messo sotto un placeholder,
# l'Inventario corrente lo riporta sul prodotto corretto invece di crearne una seconda copia.
replace_once(
    '''                            {"product_id": local_id, "serial_lower": sn.lower()},\n                            {"$set": {\n''',
    '''                            {"serial_lower": sn.lower()},\n                            {"$set": {\n''',
    "upsert seriali Inventario su chiave globale",
)

# La riconciliazione va fatta soltanto DOPO aver importato Inventory Tracker, perché la
# relazione Item in uscita -> Inventario è la prova più affidabile del modello del seriale.
marker = '''        # 4) Fonti Notion aggiuntive del workspace Elios Tech (storico, Verona, interventi, report)\n'''
insert = '''        # 3b) R67 - riconciliazione autorevole Inventario -> Tracker -> Ordini.\n        # Se questa fase fallisce interrompiamo l'import: meglio nessuna migrazione che dati\n        # seriali/prodotto silenziosamente errati.\n        try:\n            order_bridge_stats = await reconcile_order_wallbox_serials(\n                db, actor=str(current_user.get("username") or "notion-import")\n            )\n            logger.info(\n                "R67 riconciliazione Notion: tracker=%s linked=%s unresolved=%s mismatch=%s duplicates=%s placeholders_removed=%s",\n                order_bridge_stats.get("tracker_serials_used", 0),\n                order_bridge_stats.get("serials_linked", 0),\n                len(order_bridge_stats.get("unresolved_serials") or []),\n                len(order_bridge_stats.get("quantity_serial_mismatches") or []),\n                len(order_bridge_stats.get("duplicate_order_serials") or []),\n                order_bridge_stats.get("placeholder_products_removed", 0),\n            )\n        except Exception as exc:\n            logger.exception("R67 riconciliazione Notion fallita")\n            raise HTTPException(500, f"Riconciliazione Notion fallita: {exc}")\n\n''' + marker
replace_once(marker, insert, "riconciliazione dopo Inventory Tracker")

if text != original:
    path.write_text(text, encoding="utf-8")
    print("[R67 backend] aggiornato admin_extra_routes.py")
else:
    print("[R67 backend] nessuna modifica necessaria")
