# R48 — Flusso gestionale, Notion e configurazione

## Obiettivi
- rimuovere dal gestionale operativo l'area Commerciale/Lead e il ruolo Commerciale;
- mantenere intatti i dati storici senza esporre il vecchio flusso commerciale;
- rendere l'importazione Notion guidata, verificabile e sicura;
- rendere reale la configurazione del gestionale da pannello admin;
- consolidare il calendario come agenda operativa unica.

## Modifiche principali
- rimossa la route UI Lead e il Lead dalla destinazione iniziale;
- rimossa la voce/ruolo Commerciale dalla creazione utenti; gli account storici possono essere convertiti senza cancellazione;
- eliminati i permessi Lead dalla matrice utente e filtrati i vecchi permessi Lead;
- menu riorganizzato in Amministrazione, Tecnico, Gestione e Sistema;
- le configurazioni storiche in sezione `commerciale` vengono ricondotte automaticamente ad Amministrazione;
- aggiunta pagina dedicata `/admin/notion` con flusso: configurazione → test → anteprima → importazione → esito → conferma finale;
- anteprima Notion mostra conteggi e tutte le fonti rilevate; importazione bloccata se non ci sono fonti accessibili;
- la conferma finale viene resa disponibile solo dopo un import completato senza anomalie segnalate dalla UI;
- aggiunto accesso diretto a backup prima/dopo la migrazione;
- ricostruita la pagina “Configura gestionale” per modificare menu/pagine native, liste/stati e moduli personalizzati;
- moduli personalizzati: creazione, modifica, duplicazione, archiviazione e cancellazione definitiva; configurazione calendario e permessi operativi;
- il layout ricarica dinamicamente menu, moduli e impostazioni senza richiedere rebuild;
- il nome applicazione, il nome azienda e il colore principale delle impostazioni vengono applicati realmente al layout.

## Compatibilità e sicurezza dati
- nessuna cancellazione automatica di clienti, ordini, commesse, magazzino o dati Notion importati;
- le vecchie API Lead restano solo per compatibilità/archivio e non sono più raggiungibili dalla UI operativa;
- l'importazione Notion resta idempotente e continua a usare la logica backend esistente di auto-rilevamento, paginazione, allegati e archivio universale;
- R47 resta il punto di rollback immediato.
