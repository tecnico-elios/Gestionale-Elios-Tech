const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

const app = read('src/App.js');
const layout = read('src/components/AppLayout.jsx');
const install = read('src/pages/InstallazioniCalendarPage.jsx');
const technical = read('src/pages/InterventiTecniciPage.jsx');

for (const marker of ['InterventiTecniciPage', 'path="/interventi-tecnici"']) {
  if (!app.includes(marker)) throw new Error(`[R62 audit] App marker mancante: ${marker}`);
}
for (const marker of ['Interventi tecnici', '/interventi-tecnici', 'interventi_tecnici']) {
  if (!layout.includes(marker)) throw new Error(`[R62 audit] menu marker mancante: ${marker}`);
}
for (const marker of ['periodFilter', 'Prossime del mese', 'Passate del mese', 'grid lg:grid-cols-2', 'cleanDisplayText']) {
  if (!install.includes(marker)) throw new Error(`[R62 audit] installazioni marker mancante: ${marker}`);
}
if (install.includes('grouped.length')) throw new Error('[R62 audit] vecchio raggruppamento giornaliero ancora attivo');
for (const marker of ['/crm/interventi-tecnici', 'Interventi tecnici', 'RICCARDO', 'Prossimi interventi', 'Interventi passati']) {
  if (!technical.includes(marker)) throw new Error(`[R62 audit] pagina interventi marker mancante: ${marker}`);
}
console.log('[R62 audit frontend] OK: vista mese bilanciata e Interventi tecnici verificati.');
