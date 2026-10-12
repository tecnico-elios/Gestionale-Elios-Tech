const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

const checks = [
  ['src/pages/AdminExtraTabs.jsx', ['Interventi tecnici', 'Elimina tutto', 'nuovo import pulito']],
  ['src/pages/CalendarPage.jsx', ['!migration.finalized && <Button', '!migration.finalized && migrationOpen']],
  ['src/components/AppLayout.jsx', ['notionFinalized', 'elios:notion-finalized', '...(!notionFinalized ? [{ to: "/admin/migrazione-notion"']],
  ['src/pages/NotionMigrationPage.jsx', ['elios:notion-finalized']],
];

for (const [rel, needles] of checks) {
  const text = read(rel);
  for (const needle of needles) {
    if (!text.includes(needle)) throw new Error(`[R64 audit] ${rel}: manca ${needle}`);
  }
}

console.log('[R64 audit frontend] OK: reset totale e UI migrazioni finalizzate verificate.');
