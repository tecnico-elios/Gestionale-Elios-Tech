# Gestionale Elios Tech — R3

Release di sicurezza e affidabilità successiva alla R2.

Correzioni principali:
- API del Report sotto Tecnico protette con gli stessi permessi Installazioni usati dall’interfaccia;
- utenti senza permesso Installazioni non possono leggere, creare, modificare, generare o eliminare Report tramite API diretta;
- allegati email persistenti: se il file locale viene perso dopo un deploy/riavvio Render, viene ricostruito automaticamente da MongoDB GridFS prima dell’invio;
- test automatici dedicati per permessi Report e ripristino allegati GridFS;
- mantiene integralmente audit, test e correzioni della R2.
