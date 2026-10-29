from pathlib import Path

p = Path('frontend/src/pages/RegistryPage.jsx')
text = p.read_text(encoding='utf-8')

old_import = 'import { Plus, MagnifyingGlass, PencilSimple, Trash, FileText, Archive, ArrowCounterClockwise } from "@phosphor-icons/react";'
new_import = 'import { Plus, MagnifyingGlass, PencilSimple, Trash, FileText, Archive, ArrowCounterClockwise, MapPin } from "@phosphor-icons/react";'
if old_import not in text:
    raise SystemExit('import anchor not found')
text = text.replace(old_import, new_import, 1)

old = '''            {resource === "installazioni" && (() => {\n              const selectedSite = (lookups.sedi || []).find((x) => String(x.id) === String(form.sede_id));\n              return <div className="mb-4"><InstallationWeather date={form.data} site={selectedSite}/></div>;\n            })()}'''
new = '''            {(resource === "installazioni" || resource === "sopralluoghi") && (() => {\n              const selectedSite = (lookups.sedi || []).find((x) => String(x.id) === String(form.sede_id));\n              const siteAddress = selectedSite\n                ? [[selectedSite.indirizzo, selectedSite.civico].filter(Boolean).join(" "), selectedSite.cap, selectedSite.comune, selectedSite.provincia].filter(Boolean).join(", ")\n                : "";\n              const freeAddress = String(form.indirizzo_libero || "").trim();\n              const mapAddress = freeAddress || siteAddress;\n              return <div className="mb-4 space-y-3">\n                {mapAddress && <a\n                  className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-bold text-[#1A456B] hover:bg-blue-100"\n                  href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapAddress)}`}\n                  target="_blank" rel="noreferrer"\n                ><MapPin size={18} weight="fill"/>Apri in Google Maps · {mapAddress}</a>}\n                <InstallationWeather\n                  date={form.data}\n                  site={selectedSite}\n                  address={freeAddress}\n                  comune={selectedSite?.comune || ""}\n                  provincia={selectedSite?.provincia || ""}\n                  cap={selectedSite?.cap || ""}\n                />\n              </div>;\n            })()}'''
if old not in text:
    raise SystemExit('weather block anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')
Path('VERSION').write_text('R13\n', encoding='utf-8')
print('R13 patch applicata')
