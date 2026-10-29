from pathlib import Path

# --- Frontend: nuovo sopralluogo sempre pulito + meteo solo su posizione confermata ---
p = Path('frontend/src/pages/RegistryPage.jsx')
text = p.read_text(encoding='utf-8')
old = '''  const startNew = () => {\n    setEditing(null);\n    setForm({ ...empty });\n    setLookupSearch({});\n    setLookupOpen({});\n    setOpen(true);\n  };\n'''
new = '''  const startNew = () => {\n    setEditing(null);\n    const nextForm = { ...empty };\n    if (resource === "sopralluoghi") {\n      Object.assign(nextForm, {\n        indirizzo_libero: "",\n        indirizzo_verificato: false,\n        indirizzo_latitudine: "",\n        indirizzo_longitudine: "",\n        comune_libero: "",\n        provincia_libera: "",\n        cap_libero: "",\n        sede_id: "",\n      });\n      setAddressSearch({ query: "", loading: false, items: [], open: false, error: "" });\n    }\n    setForm(nextForm);\n    setLookupSearch({});\n    setLookupOpen({});\n    setOpen(true);\n  };\n'''
if old not in text:
    raise SystemExit('startNew atteso non trovato')
text = text.replace(old, new, 1)

old = '''              const freeAddress = String(form.indirizzo_libero || "").trim();\n              const mapAddress = freeAddress || siteAddress;\n              return <div className="mb-4 space-y-3">\n                {mapAddress && <a\n'''
new = '''              const freeAddress = String(form.indirizzo_libero || "").trim();\n              const verifiedFreeAddress = Boolean(form.indirizzo_verificato && form.indirizzo_latitudine && form.indirizzo_longitudine);\n              const hasConfirmedLocation = Boolean(selectedSite || verifiedFreeAddress);\n              const mapAddress = resource === "sopralluoghi"\n                ? (verifiedFreeAddress ? freeAddress : siteAddress)\n                : (freeAddress || siteAddress);\n              return <div className="mb-4 space-y-3">\n                {mapAddress && <a\n'''
if old not in text:
    raise SystemExit('blocco mapAddress atteso non trovato')
text = text.replace(old, new, 1)

old = '''                <InstallationWeather\n                  date={form.data}\n                  site={selectedSite}\n                  address={freeAddress}\n                  comune={selectedSite?.comune || form.comune_libero || ""}\n                  provincia={selectedSite?.provincia || form.provincia_libera || ""}\n                  cap={selectedSite?.cap || form.cap_libero || ""}\n                  latitude={form.indirizzo_verificato ? form.indirizzo_latitudine : null}\n                  longitude={form.indirizzo_verificato ? form.indirizzo_longitudine : null}\n                  verified={Boolean(form.indirizzo_verificato)}\n                  subject={resource === "sopralluoghi" ? "sopralluogo" : "installazione"}\n                />\n'''
new = '''                {(resource !== "sopralluoghi" || hasConfirmedLocation) && <InstallationWeather\n                  date={form.data}\n                  site={selectedSite}\n                  address={verifiedFreeAddress ? freeAddress : ""}\n                  comune={selectedSite?.comune || (verifiedFreeAddress ? form.comune_libero : "") || ""}\n                  provincia={selectedSite?.provincia || (verifiedFreeAddress ? form.provincia_libera : "") || ""}\n                  cap={selectedSite?.cap || (verifiedFreeAddress ? form.cap_libero : "") || ""}\n                  latitude={verifiedFreeAddress ? form.indirizzo_latitudine : null}\n                  longitude={verifiedFreeAddress ? form.indirizzo_longitudine : null}\n                  verified={verifiedFreeAddress}\n                  subject={resource === "sopralluoghi" ? "sopralluogo" : "installazione"}\n                />}\n'''
if old not in text:
    raise SystemExit('InstallationWeather atteso non trovato')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# --- Backend: identificazione client + errori meteo leggibili ---
p = Path('backend/server.py')
text = p.read_text(encoding='utf-8')
old = '        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:\n            loc = None\n'
new = '        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Gestionale-Elios-Tech/1.0 weather"}) as client:\n            loc = None\n'
if old not in text:
    raise SystemExit('AsyncClient meteo atteso non trovato')
text = text.replace(old, new, 1)

old = '''    except httpx.TimeoutException:\n        raise HTTPException(504, "Servizio meteo non raggiungibile: timeout")\n    except httpx.HTTPError as e:\n        raise HTTPException(502, f"Servizio meteo non raggiungibile: {type(e).__name__}")\n'''
new = '''    except httpx.TimeoutException:\n        raise HTTPException(504, "Servizio meteo temporaneamente non raggiungibile: timeout")\n    except httpx.HTTPStatusError as e:\n        status = e.response.status_code\n        if status == 429:\n            raise HTTPException(503, "Servizio meteo temporaneamente occupato. Riprova tra poco.")\n        raise HTTPException(502, f"Servizio meteo non disponibile (HTTP {status})")\n    except httpx.HTTPError:\n        raise HTTPException(502, "Servizio meteo temporaneamente non raggiungibile")\n'''
if old not in text:
    raise SystemExit('gestione errore meteo attesa non trovata')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

Path('VERSION').write_text('R16\n', encoding='utf-8')
