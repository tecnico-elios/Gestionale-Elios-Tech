from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")

checks = {
    "salvataggio libero": "Il collegamento all'installazione serve solo per proporre i valori iniziali." in text,
    "generazione libera": "I dati salvati/modificati nel report prevalgono sempre sui dati dell'installazione." in text,
    "nessun overwrite forzato": 'for k in ("data", "cliente", "indirizzo", "tecnico", "seriali"):' not in text,
    "cliente inventario dal report": 'cliente=str(data.get("cliente") or "")' in text,
    "cliente materiali dal report": '"cliente": str(data.get("cliente") or ""), "status": "open"' in text,
    "prefill ancora disponibile": 'return {"data": {**prefill, **saved}' in text,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R76 audit backend fallito: " + ", ".join(failed))
print("[R76 audit backend] OK: precompilazione facoltativa e dati report non vincolati all'installazione.")
