from pathlib import Path

p = Path('backend/server.py')
text = p.read_text(encoding='utf-8')
old = 'params={"q": query, "limit": 6, "lang": "it"},'
new = 'params={"q": query, "limit": 6},'
if old not in text:
    raise SystemExit('Parametro Photon atteso non trovato')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

Path('VERSION').write_text('R15\n', encoding='utf-8')
