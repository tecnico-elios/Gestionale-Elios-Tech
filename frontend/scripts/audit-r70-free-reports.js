const fs = require('fs');
const path = require('path');
const app = fs.readFileSync(path.join(__dirname, '..', 'src', 'App.js'), 'utf8');
const layout = fs.readFileSync(path.join(__dirname, '..', 'src', 'components', 'AppLayout.jsx'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, '..', 'src', 'pages', 'FreeReportsPage.jsx'), 'utf8');

const checks = {
  import: app.includes('FreeReportsPage'),
  route: app.includes('path="/report-liberi"'),
  menu: layout.includes('key: "report_liberi"'),
  meta: layout.includes('"/report-liberi"'),
  api: page.includes('/free-reports'),
  addField: page.includes('Aggiungi campo'),
  noClient: page.includes('senza cliente, commessa o installazione obbligatori'),
};
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error('R70 audit frontend failed: ' + failed.join(', '));
console.log('[R70 audit frontend] OK: menu Tecnico, rotta e campi liberi verificati.');
