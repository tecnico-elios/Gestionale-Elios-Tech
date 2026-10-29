from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new, label):
    text = read(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: atteso 1 match per {label}, trovati {count}")
    write(rel, text.replace(old, new, 1))


# Import override UI dopo il consolidato R1/R55/R56.
replace_once(
    "frontend/src/App.js",
    'import "@/r1.css";\n',
    'import "@/r1.css";\nimport "@/r6.css";\n',
    "import r6.css",
)

layout = "frontend/src/components/AppLayout.jsx"
replace_once(
    layout,
    '{ key: "report", to: "/report", label: "Report", icon: FileText, testid: "nav-report", module: "commesse", section: "amministrazione", order: 50 },',
    '{ key: "report", to: "/report", label: "Report attività", icon: FileText, testid: "nav-report", module: "commesse", section: "amministrazione", order: 50 },',
    "rinomina report amministrazione",
)
replace_once(
    layout,
    '{ key: "report_liberi", to: "/report-liberi", label: "Report", icon: FileText, testid: "nav-report-liberi", module: "installazioni", section: "tecnico", order: 35 },',
    '{ key: "report_liberi", to: "/report-liberi", label: "Report installazione", icon: FileText, testid: "nav-report-liberi", module: "installazioni", section: "tecnico", order: 35 },',
    "rinomina report tecnico",
)
replace_once(
    layout,
    '  "/report": { section: "amministrazione", eyebrow: "Amministrazione", icon: FileText, description: "Riepiloghi ed esportazioni delle attività." },\n',
    '  "/report": { section: "amministrazione", eyebrow: "Amministrazione", icon: FileText, description: "Attività giornaliere, ore lavorate e riepiloghi operativi." },\n  "/report-liberi": { section: "tecnico", eyebrow: "Tecnico", icon: FileText, description: "Report pre e post installazione, anche senza collegamento obbligatorio." },\n',
    "meta report distinti",
)
replace_once(
    layout,
    '      label: cfg.label || item.label,\n',
    '      label: ((item.key === "report" || item.key === "report_liberi") && String(cfg.label || "").trim().toLowerCase() === "report") ? item.label : (cfg.label || item.label),\n',
    "normalizza vecchie etichette report",
)

css = r'''/* R6 — correzioni responsive e chiarezza navigazione.
   Il redesign R55 sposta il titolo pagina nella topbar solo su desktop.
   Alcune regole R52 nascondevano però il titolo interno anche su mobile/tablet,
   lasciando pagine senza intestazione. Qui ripristiniamo il titolo sotto 1024px
   senza duplicarlo su desktop. */

@media (max-width: 1023px) {
  /* Header legacy con titolo + pulsanti: titolo visibile e comandi affiancati. */
  .r52-page-host > div > div:first-child:not(.commessa-detail):has(h1):has(button) {
    justify-content: space-between !important;
    align-items: flex-start !important;
    flex-wrap: wrap !important;
  }
  .r52-page-host > div > div:first-child:not(.commessa-detail):has(h1):has(button) > div:first-child {
    display: block !important;
    min-width: min(100%, 240px);
    flex: 1 1 240px;
  }

  /* Header legacy con solo titolo: non va nascosto quando la topbar compatta
     non mostra il titolo della pagina. */
  .r52-page-host > div > div:first-child:not(.commessa-detail):has(h1):not(:has(button)) {
    display: block !important;
  }

  /* Eccezioni R52 più specifiche per registri e Clienti/Ordini. */
  .r52-route-sopralluoghi [data-testid="sopralluoghi-page"] > div:first-child,
  .r52-route-assistenza [data-testid="assistenza-page"] > div:first-child,
  .r52-route-clienti-ordini [data-testid="elios-tech-ordini-page"] > div:first-child {
    justify-content: space-between !important;
    align-items: flex-start !important;
    flex-wrap: wrap !important;
  }

  .r52-route-sopralluoghi [data-testid="sopralluoghi-page"] > div:first-child > div:first-child,
  .r52-route-assistenza [data-testid="assistenza-page"] > div:first-child > div:first-child,
  .r52-route-clienti-ordini [data-testid="elios-tech-ordini-page"] > div:first-child > div:first-child {
    display: block !important;
    min-width: min(100%, 240px);
    flex: 1 1 240px;
  }

  /* Su mobile il titolo deve avere una gerarchia chiara ma compatta. */
  .r52-page-host h1.et-page-heading,
  .r52-page-host > div > div:first-child h1 {
    font-size: 1.35rem !important;
    line-height: 1.15 !important;
    margin: 0 !important;
  }
}
'''
write("frontend/src/r6.css", css)
write("VERSION", "R6\n")

# Controlli finali contro regressioni note.
app = read("frontend/src/App.js")
layout_body = read(layout)
css_body = read("frontend/src/r6.css")
assert 'import "@/r6.css";' in app
assert 'label: "Report attività"' in layout_body
assert 'label: "Report installazione"' in layout_body
assert '"/report-liberi":' in layout_body
assert 'toLowerCase() === "report"' in layout_body
assert '@media (max-width: 1023px)' in css_body
assert 'display: block !important' in css_body
print("R6 UI cleanup applicata correttamente")
