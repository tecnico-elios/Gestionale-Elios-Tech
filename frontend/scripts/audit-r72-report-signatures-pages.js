const fs = require('fs');
const path = require('path');
const file = path.join(__dirname, '..', 'src', 'components', 'StandaloneInstallationReportDialog.jsx');
const text = fs.readFileSync(file, 'utf8');

const checks = {
  pagesState: text.includes('const [pdfPages,setPdfPages]'),
  allPages: text.includes('Tutte e 3 le pagine'),
  pages23: text.includes('Solo pagine 2 e 3'),
  payloadPages: text.includes('pdf_pages:pdfPages'),
  imageSignature: text.includes('loadTechnicianSignature'),
  imageAccept: text.includes('accept="image/png,image/jpeg,image/webp"'),
  noMandatoryClientSignature: !text.includes('Completa le firme prima di generare il PDF'),
  generateEndpoint: text.includes('/generate`'),
  pdfOpen: text.includes('/pdf`'),
};
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error('R72 audit frontend failed: ' + failed.join(', '));
console.log('[R72 audit frontend] OK: firma cliente facoltativa, firma tecnico da immagine e selezione pagine PDF.');
