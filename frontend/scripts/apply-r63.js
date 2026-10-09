const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const adminPath = path.join(ROOT, 'src', 'pages', 'AdminPage.jsx');
let src = fs.readFileSync(adminPath, 'utf8');

src = src.replace(
  '{ key: "data", label: "Dati e backup", icon: Database, desc: "Importazione, export e copie di sicurezza" },',
  '{ key: "data", label: "Dati e backup", icon: Database, desc: "Export, copie di sicurezza e pulizia dati" },'
);

if (!src.includes('function DataBackupOnlyPane()')) {
  const marker = 'export default function AdminPage()';
  if (!src.includes(marker)) throw new Error('[R63] AdminPage export marker non trovato');
  const pane = `function DataBackupOnlyPane() {\n  const [busy, setBusy] = useState(false);\n  const downloadBackup = async () => {\n    setBusy(true);\n    try {\n      const response = await axios.get(\`${'${API}'}/admin/backup/download\`, { responseType: "blob" });\n      const href = URL.createObjectURL(response.data);\n      const a = document.createElement("a");\n      a.href = href;\n      a.download = \`gestionale-elios-backup-${'${new Date().toISOString().slice(0,10)}'}.zip\`;\n      document.body.appendChild(a);\n      a.click();\n      a.remove();\n      URL.revokeObjectURL(href);\n    } catch (e) {\n      toast.error("Creazione backup fallita", { description: formatError(e) });\n    } finally { setBusy(false); }\n  };\n  return (\n    <div className="space-y-5" data-testid="data-backup-only-pane">\n      <SectionCard title="Esportazione movimenti" description="Scarica una copia CSV dello storico operativo locale."><ExportMovimentiTab /></SectionCard>\n      <SectionCard title="Backup completo" description="Scarica un archivio ZIP con database, foto, contratti, report e altri allegati del gestionale.">\n        <Button onClick={downloadBackup} disabled={busy} className="h-11"><DownloadSimple size={18} /> {busy ? "Creazione backup…" : "Scarica backup completo"}</Button>\n      </SectionCard>\n      <SectionCard title="Pulizia dati operativi" description="Svuota i dati operativi mantenendo utenti, impostazioni e log."><DataResetTab /></SectionCard>\n    </div>\n  );\n}\n\n`;
  src = src.replace(marker, pane + marker);
}

const oldData = 'if (category === "data") return <NotionMigrationPane />;';
const newData = 'if (category === "data") return <DataBackupOnlyPane />;';
if (!src.includes(newData)) {
  if (!src.includes(oldData)) throw new Error('[R63] ramo Dati e backup non trovato');
  src = src.replace(oldData, newData);
}

fs.writeFileSync(adminPath, src, 'utf8');
console.log('[R63] Notion rimosso da Impostazioni: resta solo nella pagina dedicata.');
