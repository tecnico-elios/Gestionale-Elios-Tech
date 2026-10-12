const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, 'apply-r64.js');
let text = fs.readFileSync(file, 'utf8');
const replacements = [
  ['Utenti e permessi', 'Utenti e accessi'],
  ['Costruttore gestionale', 'Struttura gestionale'],
];
let changed = false;
for (const [from, to] of replacements) {
  if (text.includes(from)) {
    text = text.split(from).join(to);
    changed = true;
  }
}
if (changed) fs.writeFileSync(file, text, 'utf8');
console.log('[R64 prepare frontend] target menu allineato alle trasformazioni R54.');
