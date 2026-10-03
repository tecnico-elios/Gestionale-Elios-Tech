# R45 - correzioni operative

## Menu
Le voci `Fatturato`, `Wallbox` e `Report` non condividono più la configurazione di `Commesse`. Ognuna ha una chiave di navigazione indipendente.

## Fatturato
La pagina mostra esclusivamente i dati di fatturato: totale dell'anno selezionato, grafico mensile e confronto/andamento annuale.

## Wallbox
La pagina mostra esclusivamente le quantità di wallbox: totale dell'anno selezionato, grafico mensile e confronto/andamento annuale.

## Report
La voce Report è ora operativa e non è più un pannello statistico. Aggrega i moduli report locali/importati da Notion. Il modello standard replica la struttura verificata nel database Notion `Report`: Data, Account owner/Persona, Mansione, Ore lavorate e Note. Sono supportati inserimento, modifica, cancellazione, ricerca, paginazione e creazione di ulteriori tipi di report.

## Calendario
- `Tutti` mostra tutti i calendari.
- Ogni persona può essere mostrata/nascosta direttamente dai chip.
- Nei filtri sono disponibili `Mostra tutti`, `Nascondi tutti` e `SOLO` per isolare una persona.
- Se una risorsa è collegata a un utente viene mostrato il nome completo quando disponibile.
- Gli eventi provenienti da moduli personalizzati/importati vengono associati alla persona cercando i campi di assegnazione (agente, owner, persona, commerciale, tecnico, responsabile, ecc.), così i filtri per persona funzionano anche sui lead importati.

## Import Notion Report
L'import del database Report aggiorna anche record già importati, converte Account owner in un nome leggibile e riallinea lo schema locale con i campi realmente usati in Notion.
