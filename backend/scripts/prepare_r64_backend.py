from pathlib import Path

path = Path(__file__).with_name("apply_r64_backend.py")
text = path.read_text(encoding="utf-8")
old = '"""Migrazione una tantum completa Notion -> gestionale locale.'
new = '"""Importa nel gestionale locale tutto ciò che è ricostruibile dalle fonti Notion configurate.'
if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("[R64 prepare] target import completo Notion allineato al sorgente reale.")
else:
    print("[R64 prepare] target import completo Notion già allineato.")
