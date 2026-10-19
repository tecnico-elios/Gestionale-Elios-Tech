const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'src', 'components', 'InstallationReportDialog.jsx');
const text = fs.readFileSync(file, 'utf8');

const checks = {
  emptyFields: text.includes('data:"", cliente:"", indirizzo:"", tecnico:"", seriali:[]'),
  editableDate: text.includes('onChange={e=>set("data",e.target.value)}'),
  editableClient: text.includes('onChange={e=>set("cliente",e.target.value)}'),
  editableAddress: text.includes('onChange={e=>set("indirizzo",e.target.value)}'),
  editableTechnician: text.includes('onChange={e=>set("tecnico",e.target.value)}'),
  editableSerials: text.includes('onChange={e=>set("seriali",e.target.value.split(",")'),
  freeFieldsNotice: text.includes("I dati vengono precompilati dall'installazione solo come base"),
};

const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) throw new Error('R76 audit frontend failed: ' + failed.join(', '));
console.log('[R76 audit frontend] OK: dati anagrafici report installazione editabili liberamente.');
