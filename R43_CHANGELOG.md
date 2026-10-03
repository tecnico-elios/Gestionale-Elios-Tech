# Gestionale Elios Tech — R43

## Obiettivi della revisione
R43 parte da R41/R42 e concentra le modifiche richieste su autonomia del gestionale, migrazione iniziale completa, Dashboard, Clienti / Ordini e Calendario.

## Dashboard e accesso
- Route iniziale verso Dashboard per gli utenti autorizzati.
- Error boundary applicativo: in caso di errore UI non resta una pagina bianca e offre ritorno Dashboard / ricarica.
- KPI Dashboard ridisegnati in card bianche compatte con informazioni operative.

## Clienti / Ordini
- La voce "Elios Tech Ordini" è diventata "Clienti / Ordini".
- Pagina CRM con ricerca, filtri, ordinamento e riepiloghi Clienti, Fatturato, Wallbox, Report e Da ricontattare.
- Tabella desktop e vista mobile con dati commerciali/operativi.
- Scheda cliente estesa con ordini, sedi, commesse, sopralluoghi, preventivi, installazioni, assistenze, documenti e dati tecnici migrati.
- Conteggio report/documenti in riepilogo cliente.
- Stati e metodi principali degli ordini sono configurabili dal Costruttore gestionale.

## Calendario
- Un'unica pagina calendario con viste giorno/settimana/mese.
- Filtri richiudibili: calendario più ampio quando non servono.
- Selettore rapido delle persone/calendari da mostrare o nascondere.
- Eventi con più partecipanti nello stesso evento.
- Riunioni, cliente, sede, commessa, luogo, link riunione, priorità, stato, reminder, ricorrenza, tutto il giorno e note.
- Tipi/stati/priorità configurabili senza modifica codice.
- Rimossa l'importazione Google Calendar dall'interfaccia operativa.

## Migrazione iniziale
- Un solo flusso di importazione iniziale in sola lettura.
- Scoperta automatica delle fonti accessibili all'integrazione.
- Importazione delle fonti note nei moduli nativi.
- Fonti non note trasformate in moduli locali modificabili, per non perdere dati.
- Archiviazione delle proprietà originali, relazioni, valori formula/rollup restituiti dalla sorgente e snapshot dei record.
- Lettura e archiviazione del contenuto delle pagine/blocchi e download locale degli allegati accessibili.
- Importazione anche delle pagine autonome accessibili.
- Import idempotente basato sugli identificativi sorgente per evitare duplicazioni al rilancio.
- Progressione e riepilogo della migrazione.
- A migrazione conclusa: eliminazione delle credenziali di importazione e funzionamento operativo sul database interno.

## Autonomia / Costruttore gestionale
- Creazione, modifica, duplicazione, archiviazione ed eliminazione definitiva dei moduli personalizzati.
- Campi configurabili, ordinabili e ricercabili; permessi create/edit/delete e visibilità per ruolo/utente.
- Allegati sui moduli personalizzati.
- Pagine native/menu: rinomina, sezione, ordine e visibilità configurabili senza cambiare codice.
- Liste/stati configurabili: calendario, clienti, pagamenti, ordini, preventivi, commesse, installazioni e assistenze.
- Moduli personalizzati integrabili nel calendario.

## Verifiche eseguite nell'ambiente di sviluppo
- `python -m compileall -q backend`: OK.
- Controllo sintattico di tutti i 101 file JS/JSX del frontend tramite parser/transpiler TypeScript: OK.
- Il build React di produzione non è stato eseguito perché lo ZIP sorgente non include `node_modules` e l'installazione pacchetti non ha potuto completarsi nell'ambiente corrente.
- La migrazione reale dei dati può essere validata soltanto collegando il token/workspace effettivo e verificando ciò a cui l'integrazione ha accesso.
