# R44 — Correzioni richieste 03/10/2026

- Calendario: fasce orarie chiuse di default, anteprima compatta degli appuntamenti, apertura/chiusura per singola ora e comando Apri/Chiudi orari.
- Calendario: filtri persone restano selezionabili; dettagli e nuovo evento restano in pannelli/dialog, non occupano la pagina.
- Clienti / Ordini: eliminati KPI globali Fatturato/Wallbox/Report dalla testata; tabella più vicina al layout Notion richiesto; paginazione 25/50/100 righe.
- Amministrazione > Commesse: aggiunte voci Fatturato, Wallbox e Report.
- Fatturato: totale annuale + grafico mensile basato su Capitale e Data firma.
- Wallbox: totale annuale + grafico mensile basato su QTY WB e Data firma.
- Report: grafico N. Contratti mensili, distribuzione contratti per Pagamento e riepilogo report importati.
- Importazione Notion: pulsante esplicito "Anteprima importazione completa" e "Importa tutto da Notion".
- Importazione Notion: l'import non scollega più Notion immediatamente; prima mostra il risultato e richiede una conferma finale protetta.
- Chiusura migrazione: richiede frase CONFERMA MIGRAZIONE + password amministratore; solo dopo elimina le credenziali Notion e nasconde la sezione.
- Compatibilità con installazioni precedenti: vecchi flag completed senza finalized non nascondono più erroneamente l'importazione.
- Pulizia dati: oltre alla frase di conferma ora richiede anche la password dell'amministratore; API già limitata agli admin; Audit/Log restano invariati.
- Dopo finalizzazione: import Google ICS disattivato lato backend; il gestionale resta autonomo.
- Build Render: disabilitate source map di produzione e plugin ESLint nel build Docker per evitare i warning di pubblicazione già visti; gli errori di compilazione React continuano comunque a bloccare il build.
- Backend Python: compilazione verificata con compileall.
