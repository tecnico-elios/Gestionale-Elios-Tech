const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const admin = fs.readFileSync(path.join(ROOT, 'src/pages/AdminPage.jsx'), 'utf8');
const tech = fs.readFileSync(path.join(ROOT, 'src/pages/InterventiTecniciPage.jsx'), 'utf8');

for (const marker of [
  'function DataBackupOnlyPane()',
  'if (category === "data") return <DataBackupOnlyPane />;',
  'data-testid="data-backup-only-pane"',
]) {
  if (!admin.includes(marker)) throw new Error(`[R63 audit] AdminPage marker mancante: ${marker}`);
}
if (admin.includes('if (category === "data") return <NotionMigrationPane />;')) {
  throw new Error('[R63 audit] Notion è ancora visibile dentro Impostazioni');
}
for (const marker of [
  'axios.put(`${API}/crm/interventi-tecnici/${selected.id}`',
  'axios.delete(`${API}/crm/interventi-tecnici/${selected.id}`',
  'Dettaglio intervento tecnico',
  'Modifica intervento tecnico',
  'Elimina intervento tecnico',
]) {
  if (!tech.includes(marker)) throw new Error(`[R63 audit] Interventi tecnici marker mancante: ${marker}`);
}
console.log('[R63 audit frontend] OK: Interventi apribili/modificabili/eliminabili e Notion visibile in un solo punto.');
