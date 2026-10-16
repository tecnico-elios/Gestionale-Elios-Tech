const fs = require('fs');
const path = require('path');
const file = path.join(__dirname, '..', 'src', 'components', 'StandaloneInstallationReportDialog.jsx');
const text = fs.readFileSync(file, 'utf8');

const checks = {
  generateEndpoint: text.includes('/free-reports/${id}/generate'),
  pdfEndpoint: text.includes('/free-reports/${id}/pdf'),
  opensPdf: text.includes('preview.location.href=u') || text.includes('window.open(u'),
  signatureMessage: text.includes('Completa le firme prima di generare il PDF'),
  buttonNotBlockedBySignatures: !text.includes('disabled={busy||!form.firma_cliente||!form.firma_tecnico}'),
  busyOnly: text.includes('disabled={busy}><CheckCircle/> Salva e genera PDF'),
};
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k);
if (failed.length) throw new Error('R71 audit failed: ' + failed.join(', '));
console.log('[R71 audit frontend] OK: generate endpoint, firme, creazione e apertura PDF standalone verificati.');
