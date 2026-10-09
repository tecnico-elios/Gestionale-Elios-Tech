const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '..', 'src');

// R54: linguaggio dell'interfaccia.
// Manteniamo qui solo testi visibili e non valori tecnici/stati usati dalla logica.
const replacements = [
  // Header e descrizioni principali
  ['Situazione generale del gestionale, attività da gestire e indicatori principali.', 'Attività, scadenze e dati principali.'],
  ['Agenda condivisa di installazioni, sopralluoghi, assistenze e attività interne.', 'Settimana operativa: interventi, sopralluoghi e assistenze.'],
  ['Anagrafica clienti, ordini, dati commerciali e storico in un\'unica vista ordinata.', 'Clienti e ordini, dal più recente.'],
  ['Gestione completa delle commesse, materiali, servizi, avanzamento e collegamenti operativi.', 'Commesse attive, materiali e avanzamento.'],
  ['Lettura sintetica del fatturato e dell\'andamento economico delle commesse.', 'Valore delle commesse per periodo.'],
  ['Analisi delle wallbox gestite, quantità e distribuzione per attività e commessa.', 'Wallbox gestite e installate.'],
  ['Report operativi e riepiloghi esportabili del lavoro svolto.', 'Riepiloghi ed esportazioni delle attività.'],
  ['Pianificazione e gestione dei sopralluoghi con cliente, sede, note e stato.', 'Sopralluoghi programmati e completati.'],
  ['Creazione, revisione e gestione dei preventivi collegati a clienti e commesse.', 'Preventivi, revisioni e stato.'],
  ['Programmazione degli interventi, tecnici assegnati, attività e avanzamento installazioni.', 'Interventi programmati e completati.'],
  ['Richieste di assistenza, interventi, assegnazioni e storico tecnico.', 'Richieste e interventi di assistenza.'],
  ['Disponibilità, articoli, seriali e giacenze del Magazzino Elios Tech.', 'Giacenze e seriali · sede Elios Tech.'],
  ['Disponibilità, articoli, seriali e giacenze del Magazzino Verona.', 'Giacenze e seriali · sede Verona.'],
  ['Trasferimenti di materiale tra le sedi con quantità, seriali e tracciabilità.', 'Spostamenti tra Elios Tech e Verona.'],
  ['Registrazione degli arrivi a magazzino e aggiornamento delle disponibilità.', 'Materiale ricevuto e caricato a magazzino.'],
  ['Preparazione e controllo delle spedizioni collegate a clienti e commesse.', 'Materiale in uscita verso clienti e commesse.'],
  ['Storico dei movimenti di magazzino e tracciamento delle variazioni.', 'Storico di carichi, scarichi e rettifiche.'],
  ['Anomalie da verificare e situazioni che richiedono attenzione operativa.', 'Segnalazioni da controllare.'],
  ['Assistente interno per consultare e interpretare i dati del gestionale.', 'Consulta i dati del gestionale.'],
  ['Configurazione generale del gestionale e delle preferenze aziendali.', 'Preferenze generali e comportamento del sistema.'],
  ['Gestione utenti, ruoli, autorizzazioni e accessi al gestionale.', 'Utenti, ruoli e accessi.'],
  ['Creazione e configurazione dei moduli personalizzati del gestionale.', 'Pagine, campi e moduli personalizzati.'],
  ['Migrazione una tantum dei dati legacy verso il database autonomo del gestionale.', 'Importazione una tantum dei dati storici.'],
  ['Database gestionale locale', 'Dati locali'],

  // Navigazione e nomi pagina
  ['Clienti / Ordini', 'Clienti e ordini'],
  ['Utenti e permessi', 'Utenti e accessi'],
  ['Assistente AI', 'Assistente'],
  ['Costruttore gestionale', 'Struttura gestionale'],
  ['Importazione Notion', 'Importa da Notion'],

  // Azioni comuni
  ['Nuovo cliente', 'Aggiungi cliente'],
  ['Salva e apri cliente', 'Crea cliente'],
  ['Nuovo ordine', 'Aggiungi ordine'],
  ['Nuovo preventivo', 'Crea preventivo'],
  ['Nuova commessa', 'Crea commessa'],
  ['Nuovo sopralluogo', 'Pianifica sopralluogo'],
  ['Nuova installazione', 'Pianifica installazione'],
  ['Nuova assistenza', 'Apri assistenza'],
  ['Nuovo evento', 'Aggiungi attività'],
  ['Nuovo prodotto', 'Aggiungi prodotto'],
  ['Conferma trasferimento', 'Registra trasferimento'],
  ['Nuovo arrivo', 'Registra arrivo'],
  ['Nuova spedizione', 'Crea spedizione'],
  ['Salva e chiudi', 'Salva'],

  // Clienti
  ['Tipo cliente', 'Tipo'],
  ['Referente principale', 'Referente'],
  ['Provenienza cliente', 'Origine cliente'],
  ['Lead, referenza, cliente attivo…', 'Es. referenza, sito, cliente esistente'],
  ['Scadenza Backend', 'Scadenza backend'],
  ['Scadenza Assistenza SMART', 'Scadenza assistenza SMART'],
  ['Numero caso Wallbox', 'Caso Wallbox'],
  ['Nessuna scadenza registrata', 'Senza scadenza'],
  ['Servizio non attivo', 'Non attivo'],
  ['ATTIVO', 'Attivo'],

  // Ordini: lessico più diretto
  ['Stato commerciale', 'Stato ordine'],
  ['Stato contratto', 'Contratto'],
  ['Modalità pagamento', 'Pagamento'],
  ['Stato finanziaria', 'Finanziamento'],
  ['Numero pratica finanziaria', 'N. pratica'],
  ['Data invio finanziaria', 'Invio pratica'],
  ['Data esito finanziaria', 'Esito pratica'],
  ['Motivo esito finanziaria', 'Note esito'],
  ['Importo finanziato', 'Finanziato'],
  ['Durata mesi', 'Durata (mesi)'],
  ['Rata canone', 'Rata / canone'],
  ['Note finanziaria', 'Note finanziamento'],
  ['Stato amministrativo', 'Amministrazione'],
  ['Stato logistico', 'Logistica'],
  ['Stato installazione', 'Installazione'],
  ['Data firma', 'Firma'],

  // Ricerca / filtri
  ['Cerca numero, cliente o stato...', 'Cerca per numero, cliente o stato'],
  ['Cerca cliente...', 'Cerca cliente'],
  ['Cerca prodotto...', 'Cerca prodotto'],
  ['Cerca nome o codice...', 'Cerca per nome o codice'],
  ['Cerca nome, codice, categoria, marca, posizione o fornitore', 'Cerca prodotto, codice o posizione'],
  ['Tutti gli stati', 'Tutti'],

  // Magazzino e trasferimenti
  ['Storico trasferimenti', 'Trasferimenti recenti'],
  ['Cerca prodotto nel deposito di origine', 'Prodotto da trasferire'],
  ['Quantità da trasferire', 'Quantità'],
  ['Seriali da trasferire', 'Seriali'],
  ['Motivo o riferimento del trasferimento (obbligatorio)', 'Motivo o riferimento'],
  ['Nessun trasferimento registrato.', 'Nessun trasferimento.'],
  ['Nessun prodotto presente.', 'Nessun prodotto.'],

  // Preventivi / commesse / tecnico
  ['Genera / scarica PDF', 'PDF'],
  ['Segna come inviato', 'Segna inviato'],
  ['Accetta e crea commessa', 'Accetta'],
  ['Storico revisioni', 'Revisioni'],
  ['PDF non generato', 'PDF da creare'],
  ['PDF da rigenerare', 'PDF da aggiornare'],
  ['PDF aggiornato', 'PDF pronto'],
  ['Nessun preventivo presente.', 'Nessun preventivo.'],

  // Sistema
  ['Impostazioni generali', 'Generale'],
  ['Gestione utenti', 'Utenti'],
  ['Gestione permessi', 'Permessi'],
  ['Configurazione moduli', 'Moduli'],
  ['Salva impostazioni', 'Salva'],
  ['Ripristina predefiniti', 'Ripristina'],

  // Messaggi vuoti / microcopy comuni
  ['Nessun risultato trovato.', 'Nessun risultato.'],
  ['Nessun elemento presente.', 'Nessun elemento.'],
  ['Nessun dato disponibile.', 'Nessun dato.'],
  ['Caricamento in corso…', 'Caricamento…'],
  ['Operazione completata con successo', 'Operazione completata'],
];

function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.(jsx?|tsx?)$/.test(entry.name)) out.push(full);
  }
  return out;
}

let filesChanged = 0;
let totalReplacements = 0;

for (const file of walk(SRC)) {
  let text = fs.readFileSync(file, 'utf8');
  const before = text;
  for (const [from, to] of replacements) {
    if (!text.includes(from)) continue;
    const parts = text.split(from);
    const hits = parts.length - 1;
    text = parts.join(to);
    totalReplacements += hits;
  }
  if (text !== before) {
    fs.writeFileSync(file, text, 'utf8');
    filesChanged += 1;
  }
}

console.log(`[R54 copy] ${totalReplacements} testi aggiornati in ${filesChanged} file.`);
