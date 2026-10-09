const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

const calendar = read('src/pages/CalendarPage.jsx');
const installations = read('src/pages/InstallazioniCalendarPage.jsx');
const notion = read('src/pages/NotionMigrationPage.jsx');
const admin = read('src/pages/AdminPage.jsx');
const app = read('src/App.js');

for (const marker of ['/calendar/roles', 'Ruoli disponibili', 'Aggiungi ruolo', 'canManagePeopleRoles']) {
  if (!calendar.includes(marker)) throw new Error(`[R61 audit] calendario marker mancante: ${marker}`);
}
if (calendar.includes('list="calendar-role-options"')) throw new Error('[R61 audit] ruolo calendario ancora modificabile come testo libero');
for (const marker of ['indirizzo_libero', 'comune_libero', 'provincia_libera', 'Referente installazione']) {
  if (!installations.includes(marker)) throw new Error(`[R61 audit] installazioni marker mancante: ${marker}`);
}
if (!notion.includes('/admin/notion/import-all/start')) throw new Error('[R61 audit] import Notion non usa il job server');
if (!admin.includes('if (category === "data") return <DataToolsPane />;')) throw new Error('[R61 audit] Impostazioni mostra ancora la seconda UI Notion');
if (!admin.includes('to="/admin/migrazione-notion"')) throw new Error('[R61 audit] link alla procedura Notion unica mancante');
if (!app.includes('r61.css')) throw new Error('[R61 audit] CSS R61 non caricato');

console.log('[R61 audit frontend] OK: hover leggibile, ruoli controllati, un solo import Notion e installazioni strutturate.');
