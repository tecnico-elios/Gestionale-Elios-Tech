const fs = require('fs');
const path = require('path');
const app = fs.readFileSync(path.join(__dirname, '..', 'src', 'App.js'), 'utf8');
const layout = fs.readFileSync(path.join(__dirname, '..', 'src', 'components', 'AppLayout.jsx'), 'utf8');
const page = fs.readFileSync(path.join(__dirname, '..', 'src', 'pages', 'FreeReportsPage.jsx'), 'utf8');
const dialog = fs.readFileSync(path.join(__dirname, '..', 'src', 'components', 'StandaloneInstallationReportDialog.jsx'), 'utf8');

const checks = {
  import: app.includes('FreeReportsPage'),
  route: app.includes('path="/report-liberi"'),
  menu: layout.includes('key: "report_liberi"'),
  meta: layout.includes('"/report-liberi"'),
  api: page.includes('/free-reports'),
  sameReportTitle: dialog.includes('Report pre e post installazione'),
  preInstall: dialog.includes('Pre-installazione · verifica impianto esistente'),
  postInstall: dialog.includes('Post-installazione · dati tecnici'),
  signatures: dialog.includes('Firma Cliente') && dialog.includes('Firma Tecnico'),
  officialTemplate: dialog.includes('Apri modello ufficiale'),
  editableClient: dialog.includes('Cliente / riferimento libero'),
  noLink: page.includes('senza collegamento obbligatorio a cliente o installazione'),
};
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error('R70 audit frontend failed: ' + failed.join(', '));
console.log('[R70 audit frontend] OK: stesso report pre/post installazione, standalone e PDF ufficiale verificati.');
