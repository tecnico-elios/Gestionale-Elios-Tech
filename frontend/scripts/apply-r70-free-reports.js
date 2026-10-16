const fs = require('fs');
const path = require('path');

const appPath = path.join(__dirname, '..', 'src', 'App.js');
const layoutPath = path.join(__dirname, '..', 'src', 'components', 'AppLayout.jsx');

let app = fs.readFileSync(appPath, 'utf8');
let layout = fs.readFileSync(layoutPath, 'utf8');

if (!app.includes('FreeReportsPage')) {
  const importAnchor = 'import ReportsPage from "@/pages/ReportsPage";\n';
  if (!app.includes(importAnchor)) throw new Error('R70 frontend: import anchor non trovato');
  app = app.replace(importAnchor, importAnchor + 'import FreeReportsPage from "@/pages/FreeReportsPage";\n');

  const routeAnchor = '                      <Route path="/installazioni" element={<ProtectedRoute permission="installazioni"><InstallazioniPage /></ProtectedRoute>} />\n';
  if (!app.includes(routeAnchor)) throw new Error('R70 frontend: route anchor non trovato');
  app = app.replace(routeAnchor, routeAnchor + '                      <Route path="/report-liberi" element={<ProtectedRoute permission="installazioni"><FreeReportsPage /></ProtectedRoute>} />\n');
}

if (!layout.includes('key: "report_liberi"')) {
  const navAnchor = '  { key: "installazioni", to: "/installazioni", label: "Installazioni", icon: Wrench, testid: "nav-installazioni", module: "installazioni", section: "tecnico", order: 30 },\n';
  if (!layout.includes(navAnchor)) throw new Error('R70 frontend: nav anchor non trovato');
  layout = layout.replace(navAnchor, navAnchor + '  { key: "report_liberi", to: "/report-liberi", label: "Report liberi", icon: FileText, testid: "nav-report-liberi", module: "installazioni", section: "tecnico", order: 35 },\n');

  const metaAnchor = '  "/installazioni": { section: "tecnico", eyebrow: "Tecnico", icon: Wrench, description: "Programmazione degli interventi, tecnici assegnati, attività e avanzamento installazioni." },\n';
  if (!layout.includes(metaAnchor)) throw new Error('R70 frontend: page meta anchor non trovato');
  layout = layout.replace(metaAnchor, metaAnchor + '  "/report-liberi": { section: "tecnico", eyebrow: "Tecnico", icon: FileText, description: "Report tecnici liberi e indipendenti, compilabili con campi personalizzati senza collegamenti obbligatori." },\n');
}

fs.writeFileSync(appPath, app);
fs.writeFileSync(layoutPath, layout);
console.log('[R70 frontend] Report liberi collegati a menu e routing.');
