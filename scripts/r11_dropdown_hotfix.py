from pathlib import Path

registry = Path('frontend/src/pages/RegistryPage.jsx')
text = registry.read_text(encoding='utf-8')
old = '''  const lookupOptions = (field) => {\n    let list = lookups[lookupKey(field)] || [];\n'''
new = '''  const lookupOptions = (field) => {\n    const needle = String(lookupSearch[field.key] || "").trim().toLowerCase();\n    if (field.suggestOnlyAfterTyping && !needle) return [];\n    let list = lookups[lookupKey(field)] || [];\n'''
if old not in text:
    raise SystemExit('lookupOptions anchor not found')
text = text.replace(old, new, 1)
old2 = '''    const needle = String(lookupSearch[field.key] || "").trim().toLowerCase();\n    if (needle) {\n'''
if old2 in text:
    text = text.replace(old2, '''    if (needle) {\n''', 1)
old3 = '''                            onFocus={() => !disabled && setLookupOpen((p) => ({ ...p, [f.key]: true }))}\n'''
new3 = '''                            onFocus={() => !disabled && !f.suggestOnlyAfterTyping && setLookupOpen((p) => ({ ...p, [f.key]: true }))}\n'''
if old3 not in text:
    raise SystemExit('onFocus anchor not found')
text = text.replace(old3, new3, 1)
old4 = '''                            onClick={() => setLookupOpen((p) => ({ ...p, [f.key]: !p[f.key] }))}\n'''
new4 = '''                            onClick={() => {\n                              if (f.suggestOnlyAfterTyping && !lookupTextValue(f).trim()) return;\n                              setLookupOpen((p) => ({ ...p, [f.key]: !p[f.key] }));\n                            }}\n'''
if old4 not in text:
    raise SystemExit('toggle anchor not found')
text = text.replace(old4, new4, 1)
old5 = '''                        {lookupOpen[f.key] && !disabled && (\n'''
new5 = '''                        {lookupOpen[f.key] && !disabled && (!f.suggestOnlyAfterTyping || lookupTextValue(f).trim()) && (\n'''
if old5 not in text:
    raise SystemExit('dropdown render anchor not found')
text = text.replace(old5, new5, 1)
registry.write_text(text, encoding='utf-8')

business = Path('frontend/src/pages/BusinessPages.jsx')
b = business.read_text(encoding='utf-8')
oldb = 'F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", clearOnChange: ["sede_id"], help:'
newb = 'F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", suggestOnlyAfterTyping: true, clearOnChange: ["sede_id"], help:'
if oldb not in b:
    raise SystemExit('BusinessPages anchor not found')
b = b.replace(oldb, newb, 1)
business.write_text(b, encoding='utf-8')

Path('VERSION').write_text('R11.1\n', encoding='utf-8')
print('Hotfix applicata')
