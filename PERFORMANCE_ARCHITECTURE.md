# Gestionale Elios Tech — Backend Performance Architecture

## Obiettivo

Ridurre TTFB, saturazione dell'event loop e code di richieste concorrenti senza alterare le logiche di scrittura del CRM.

## Regole architetturali

1. Tutte le rotte I/O sono `async def` e devono usare driver/librerie asincrone.
2. Le liste sono sempre bounded: `page=1`, `limit=50`, massimo configurabile (default 200).
3. Filtri, ordinamenti e paginazione vengono eseguiti da MongoDB, non in Python dopo aver materializzato migliaia di record.
4. Le viste tabellari usano proiezioni e non devono trasferire payload binari/raw.
5. Le relazioni di lista vengono caricate in batch, mai con query N+1.
6. Le GET non eseguono sincronizzazioni esterne o altre operazioni con side effect.
7. Lookup e dataset semi-statici usano cache TTL con single-flight per evitare cache stampede.
8. Query indipendenti usano `asyncio.gather` quando è sicuro eseguirle in parallelo.
9. Tutte le query hot-path devono avere indici coerenti con filtri e ordinamento.
10. Le richieste lente e il lag dell'event loop vengono loggati in produzione.

## Runtime introdotto

`backend/performance_runtime.py` sostituisce in modo mirato i percorsi critici senza duplicare il backend storico:

- `/api/crm/{resource}`: paginazione, ricerca Mongo, query bounded, `maxTimeMS`.
- Installazioni: rimosso il sync calendario dal GET e sostituite le query record-per-record con fetch batch.
- `/api/crm/meta/dashboard`: conteggi paralleli e cache breve.
- Lookup commesse/tecnici: proiezione + cache.
- `clienti-summary` e `ordini-insights`: single-flight cache breve per evitare refresh storm mentre vengono progressivamente convertiti in aggregation Mongo native.
- `/api/bootstrap`: endpoint aggregato per migrare il frontend da chiamate lookup multiple a un'unica inizializzazione.

## Cache

La cache è in memoria per processo ed è adatta all'attuale singolo worker Render. Se il servizio passerà a più worker/istanze, l'interfaccia dovrà essere mantenuta ma il backend cache dovrà essere spostato a Redis per condivisione e invalidazione coerente.

## MongoDB

Il progetto usa già `AsyncIOMotorClient`. Motor è però deprecato upstream; il nuovo codice evita dipendenze Motor-specifiche dove possibile per consentire una successiva migrazione a `pymongo.AsyncMongoClient` senza cambiare l'architettura Router → Service/Repository → Database.

## Checklist audit

- Cercare `requests.*`, `time.sleep`, `MongoClient` sincrono dentro `async def`.
- Cercare `.to_list(length=N)` con N elevato e sostituire con paginazione/limit.
- Cercare filtri/list comprehension/sort Python applicati dopo grandi query Mongo.
- Cercare GET che eseguono sync calendario/Notion/email/PDF o altre chiamate esterne.
- Verificare per ogni endpoint lento: durata, numero documenti, payload, query plan e indici.

`backend/performance_audit.py` automatizza una parte di questa checklist e viene eseguito dalla GitHub Action di audit.
