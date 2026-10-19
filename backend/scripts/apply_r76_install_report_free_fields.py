from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "installation_report_routes.py"
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str):
    global text
    if old not in text:
        raise RuntimeError(f"R76 backend: {label} non trovato")
    text = text.replace(old, new, 1)


save_old = '''        prefill = await _prefill(inst)
        data = {**body.data}
        # I dati anagrafici certi sono sempre derivati dal gestionale.
        for k in ("data", "cliente", "indirizzo", "tecnico", "seriali"):
            data[k] = prefill.get(k)
'''
save_new = '''        # Il collegamento all'installazione serve solo per proporre i valori iniziali.
        # Dopo la compilazione il report conserva esattamente i valori inseriti dall'utente.
        data = {**body.data}
'''
replace_once(save_old, save_new, "forzatura dati in salvataggio")

generate_old = '''        prefill = await _prefill(inst)
        data = {**(inst.get("report_installazione_data") or {}), **body.data}
        for k in ("data", "cliente", "indirizzo", "tecnico", "seriali"):
            data[k] = prefill.get(k)
'''
generate_new = '''        # I dati salvati/modificati nel report prevalgono sempre sui dati dell'installazione.
        data = {**(inst.get("report_installazione_data") or {}), **body.data}
'''
replace_once(generate_old, generate_new, "forzatura dati in generazione")

text = text.replace(
    'installation_id, desired_consumption, cliente=str(prefill.get("cliente") or ""),',
    'installation_id, desired_consumption, cliente=str(data.get("cliente") or ""),',
    1,
)
text = text.replace(
    '"cliente": str(prefill.get("cliente") or ""), "status": "open",',
    '"cliente": str(data.get("cliente") or ""), "status": "open",',
    1,
)

if 'cliente=str(prefill.get("cliente") or "")' in text:
    raise RuntimeError("R76 backend: riferimento cliente prefill residuo nel consumo")
if '"cliente": str(prefill.get("cliente") or ""), "status": "open"' in text:
    raise RuntimeError("R76 backend: riferimento cliente prefill residuo nei materiali")

path.write_text(text, encoding="utf-8")
print("[R76 backend] report installazione libero: dati inseriti dall'utente non vengono piu sovrascritti.")
