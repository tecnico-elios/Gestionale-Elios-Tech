const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

const activePages = [
  'src/pages/DashboardPage.jsx',
  'src/pages/CalendarPage.jsx',
  'src/pages/EliosTechOrdiniPage.jsx',
  'src/pages/CommessePage.jsx',
  'src/pages/CommesseInsightsPage.jsx',
  'src/pages/ReportsPage.jsx',
  'src/pages/BusinessPages.jsx',
  'src/pages/PreventiviPage.jsx',
  'src/pages/InventarioPage.jsx',
  'src/pages/TrasferimentiPage.jsx',
  'src/pages/ArriviPage.jsx',
  'src/pages/ChecklistPage.jsx',
  'src/pages/MovimentiPage.jsx',
  'src/pages/AnomaliePage.jsx',
  'src/pages/AIAssistantPage.jsx',
  'src/pages/AdminPage.jsx',
  'src/pages/AdminUsersPage.jsx',
  'src/pages/ModuleBuilderPage.jsx',
  'src/pages/NotionMigrationPage.jsx',
  'src/pages/LoginPage.jsx',
  'src/pages/ResetPasswordPage.jsx',
  'src/pages/ForceChangePasswordPage.jsx',
  'src/pages/CustomModulePage.jsx',
];

for (const rel of activePages) {
  if (!fs.existsSync(path.join(ROOT, rel))) throw new Error(`[R59 audit] pagina mancante: ${rel}`);
}

const app = read('src/App.js');
for (const route of [
  '/dashboard','/calendario','/clienti-ordini','/commesse','/fatturato','/wallbox','/report',
  '/sopralluoghi','/preventivi','/installazioni','/assistenza','/inventario','/magazzino-verona',
  '/trasferimenti','/arrivi','/spedizioni','/movimenti','/anomalie','/assistente-ai','/admin','/admin/utenti'
]) {
  if (!app.includes(`path="${route}"`)) throw new Error(`[R59 audit] rotta frontend mancante: ${route}`);
}

const calendar = read('src/pages/CalendarPage.jsx');
for (const marker of ['calendar:manage_people_roles','calendar-role-options','Direttore tecnico','personRoles.map']) {
  if (!calendar.includes(marker)) throw new Error(`[R59 audit] Calendario: marker mancante ${marker}`);
}

const users = read('src/pages/AdminUsersPage.jsx');
if (!users.includes('calendar:manage_people_roles') || !users.includes('Calendario · gestisci persone e ruoli')) {
  throw new Error('[R59 audit] gestione permesso Calendario non presente nella pagina utenti');
}

const orders = read('src/pages/EliosTechOrdiniPage.jsx');
for (const marker of ['<Label>PEC</Label>','<Label>Codice SDI</Label>','Tutti i pagamenti','Tutti gli agenti','Tutti gli stati','Azzera filtri']) {
  if (!orders.includes(marker)) throw new Error(`[R59 audit] Clienti/Ordini: marker mancante ${marker}`);
}

const weather = read('src/components/InstallationWeather.jsx');
if (!weather.includes('/weather-installation')) throw new Error('[R59 audit] collegamento meteo installazioni mancante');

// Intercetta alcuni placeholder tipici di pulsanti presenti ma volutamente/non volutamente inerti.
const suspicious = ['onClick={() => {}}', 'onClick={undefined}', 'href="#"', 'javascript:void(0)'];
const scanFiles = [...activePages, 'src/components/AppLayout.jsx', 'src/components/InstallationWeather.jsx'];
for (const rel of scanFiles) {
  const text = read(rel);
  for (const pattern of suspicious) {
    if (text.includes(pattern)) throw new Error(`[R59 audit] controllo inerte sospetto in ${rel}: ${pattern}`);
  }
}

console.log(`[R59 audit frontend] OK: ${activePages.length} pagine attive, rotte e flussi critici verificati.`);
