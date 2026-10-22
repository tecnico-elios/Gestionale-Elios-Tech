const fs = require('fs');
const path = require('path');

const report = fs.readFileSync(path.join(__dirname, '..', 'src', 'components', 'InstallationReportDialog.jsx'), 'utf8');
const layout = fs.readFileSync(path.join(__dirname, '..', 'src', 'components', 'AppLayout.jsx'), 'utf8');

const checks = {
  editableR76: report.includes("I dati vengono precompilati dall'installazione solo come base"),
  editableClient: report.includes('onChange={e=>set("cliente",e.target.value)}'),
  editableAddress: report.includes('onChange={e=>set("indirizzo",e.target.value)}'),
  editableTechnician: report.includes('onChange={e=>set("tecnico",e.target.value)}'),
  editableSerials: report.includes('onChange={e=>set("seriali",e.target.value.split(",")'),
  pagesState: report.includes('const [pdfPages,setPdfPages]'),
  allPages: report.includes('Tutte e 3 le pagine'),
  pages23: report.includes('Solo pagine 2 e 3'),
  payloadPages: report.includes('pdf_pages:pdfPages'),
  optionalSignatures: !report.includes('disabled={busy||!form.firma_cliente||!form.firma_tecnico}'),
  imageSignature: report.includes('loadTechnicianSignature'),
  imageAccept: report.includes('accept="image/png,image/jpeg,image/webp"'),
  opensPdf: report.includes('responseType:"blob"') && report.includes('preview.location.href=u'),
  technicalMenuLabel: layout.includes('key: "report_liberi", to: "/report-liberi", label: "Report"'),
};

const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error('R77 audit frontend fallito: ' + failed.join(', '));
console.log('[R77 audit frontend] OK: report Installazioni e Report Tecnico hanno le stesse opzioni principali.');
