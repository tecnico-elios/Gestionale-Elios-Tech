import { useEffect, useState } from "react";
import axios from "axios";
import { API } from "../lib/apiBase";
import RegistryPage from "./RegistryPage";
import InstallazioniCalendarPage from "./InstallazioniCalendarPage";

const F = (key, label, extra = {}) => ({ key, label, ...extra });

const clientLabel = (x) => x?.ragione_sociale || [x?.nome, x?.cognome].filter(Boolean).join(" ") || x?.codice_fiscale || "Cliente";
const contactLabel = (x) => [x?.nome, x?.cognome].filter(Boolean).join(" ") || x?.email || "Contatto";
const siteLabel = (x) => [x?.nome, x?.comune].filter(Boolean).join(" · ") || x?.indirizzo || "Sede";
const surveyLabel = (x) => [x?.data, x?.tecnico, x?.stato].filter(Boolean).join(" · ") || "Sopralluogo";
const quoteLabel = (x) => [x?.numero, x?.data, x?.stato].filter(Boolean).join(" · ") || "Preventivo";
const orderLabel = (x) => [x?.numero, x?.data, x?.stato].filter(Boolean).join(" · ") || "Ordine";
const installationLabel = (x) => [x?.data, x?.tecnico, x?.stato].filter(Boolean).join(" · ") || "Installazione";
const commessaLabel = (x) => [x?.number ? `#${x.number}` : null, x?.cliente, x?.stato].filter(Boolean).join(" · ") || "Commessa";

const CLIENT_LOOKUP = { lookupResource: "clienti", lookupLabel: clientLabel };
const SITE_LOOKUP = { lookupResource: "sedi", lookupLabel: siteLabel };
const ORDER_LOOKUP = { lookupResource: "ordini-clienti", lookupLabel: orderLabel };
const COMMESSA_LOOKUP = { lookupEndpoint: "crm/lookups/commesse", lookupKey: "commesse", lookupLabel: commessaLabel };

const DEFAULT_OPERATIONAL_OPTIONS = {
  sopralluoghi_stati: ["Da programmare", "Programmato", "Eseguito", "Annullato"],
  assistenza_tipi: ["Remota", "In loco"],
  assistenza_priorita: ["Bassa", "Normale", "Alta", "Urgente"],
  assistenza_stati: ["Aperta", "Da programmare", "Programmata", "In lavorazione", "In attesa cliente / fornitore", "Tecnico in intervento", "Risolta", "Completata", "Chiusa"],
};

function useOperationalOptions() {
  const [options, setOptions] = useState(DEFAULT_OPERATIONAL_OPTIONS);
  useEffect(() => {
    let active = true;
    axios.get(`${API}/operational-options`).then(({ data }) => {
      if (!active || !data) return;
      setOptions({ ...DEFAULT_OPERATIONAL_OPTIONS, ...data });
    }).catch(() => {
      // Fallback locale: le pagine restano operative anche durante un errore di rete temporaneo.
    });
    return () => { active = false; };
  }, []);
  return options;
}

export const ClientiPage = () => (
  <RegistryPage
    resource="clienti"
    title="Clienti"
    subtitle="Anagrafica centrale: da qui dipendono contatti, sedi, sopralluoghi, preventivi e ordini."
    fields={[
      F("tipo", "Tipo", { options: ["Azienda", "Privato"], default: "Azienda" }),
      F("ragione_sociale", "Ragione sociale / Nome e cognome", { required: true }),
      F("partita_iva", "Partita IVA"),
      F("codice_fiscale", "Codice fiscale"),
      F("sdi", "Codice SDI"),
      F("pec", "PEC", { type: "email" }),
      F("telefono", "Telefono"),
      F("email", "Email", { type: "email" }),
      F("note", "Note", { type: "textarea", full: true }),
    ]}
    columns={[
      F("ragione_sociale", "Cliente"),
      F("tipo", "Tipo"),
      F("partita_iva", "P. IVA"),
      F("telefono", "Telefono"),
      F("email", "Email"),
    ]}
  />
);

export const ContattiPage = () => (
  <RegistryPage
    resource="contatti"
    title="Contatti"
    subtitle="Referenti collegati a clienti reali: niente più nomi cliente scritti a mano."
    fields={[
      F("cliente_id", "Cliente", { ...CLIENT_LOOKUP, required: true }),
      F("nome", "Nome", { required: true }),
      F("cognome", "Cognome", { required: true }),
      F("ruolo", "Ruolo"),
      F("telefono", "Telefono"),
      F("cellulare", "Cellulare"),
      F("email", "Email", { type: "email" }),
      F("principale", "Contatto principale", { options: ["Sì", "No"], default: "No" }),
      F("note", "Note", { type: "textarea", full: true }),
    ]}
    columns={[
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("nome", "Nome"),
      F("cognome", "Cognome"),
      F("ruolo", "Ruolo"),
      F("telefono", "Telefono"),
    ]}
  />
);

export const SediPage = () => (
  <RegistryPage
    resource="sedi"
    title="Sedi"
    subtitle="Sedi operative e luoghi di installazione collegati all'anagrafica cliente."
    fields={[
      F("cliente_id", "Cliente", { ...CLIENT_LOOKUP, required: true, clearOnChange: ["contatto_id"] }),
      F("nome", "Nome sede", { required: true }),
      F("tipo", "Tipo sede", { options: ["Operativa", "Legale", "Installazione", "Fatturazione"], default: "Operativa" }),
      F("indirizzo", "Indirizzo", { required: true }),
      F("civico", "Civico"),
      F("cap", "CAP"),
      F("comune", "Comune", { required: true }),
      F("provincia", "Provincia"),
      F("contatto_id", "Referente", {
        lookupResource: "contatti",
        lookupLabel: contactLabel,
        dependsOn: "cliente_id",
        lookupFilterBy: "cliente_id",
      }),
      F("telefono", "Telefono sede"),
      F("note", "Note", { type: "textarea", full: true }),
    ]}
    columns={[
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("nome", "Sede"),
      F("indirizzo", "Indirizzo"),
      F("comune", "Comune"),
      F("provincia", "Prov."),
    ]}
  />
);

export const SopralluoghiPage = () => {
  const operational = useOperationalOptions();
  return (
  <RegistryPage
    resource="sopralluoghi"
    title="Sopralluoghi"
    subtitle="Il sopralluogo può essere collegato a un cliente esistente oppure creato per un prospect non ancora acquisito."
    fields={[
      F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, allowFreeText: true, freeTextTarget: "nominativo", clearOnChange: ["sede_id"], help: "Se non selezioni un cliente esistente, il nominativo resta un prospect e non viene creata alcuna anagrafica cliente." }),
      F("sede_id", "Sede cliente", {
        ...SITE_LOOKUP,
        dependsOn: "cliente_id",
        lookupFilterBy: "cliente_id",
        inlineCreateSite: true,
      }),
      F("telefono", "Telefono"),
      F("email", "Email", { type: "email" }),
      F("indirizzo_libero", "Indirizzo sopralluogo", { full: true }),
      F("tecnico", "Tecnico"),
      F("data", "Data", { type: "date", required: true }),
      F("ora", "Ora", { type: "time" }),
      F("stato", "Stato", { options: operational.sopralluoghi_stati, default: operational.sopralluoghi_stati?.[0] || "Da programmare" }),
      F("potenza", "Potenza disponibile"),
      F("impianto", "Impianto"),
      F("distanza", "Distanza indicativa"),
      F("note", "Note tecniche", { type: "textarea", full: true }),
    ]}
    columns={[
      F("cliente_id", "Cliente / prospect", { ...CLIENT_LOOKUP, fallbackKey: "nominativo" }),
      F("sede_id", "Sede", SITE_LOOKUP),
      F("data", "Data"),
      F("tecnico", "Tecnico"),
      F("stato", "Stato"),
    ]}
  />
  );
};

export const PreventiviPage = () => (
  <RegistryPage
    resource="preventivi"
    title="Preventivi"
    subtitle="Offerte economiche collegate al cliente e, quando presente, al sopralluogo."
    fields={[
      F("numero", "Numero", { required: true }),
      F("cliente_id", "Cliente", { ...CLIENT_LOOKUP, required: true, clearOnChange: ["sopralluogo_id"] }),
      F("sopralluogo_id", "Sopralluogo", {
        lookupResource: "sopralluoghi",
        lookupLabel: surveyLabel,
        dependsOn: "cliente_id",
        lookupFilterBy: "cliente_id",
      }),
      F("data", "Data", { type: "date", required: true }),
      F("importo", "Importo €", { type: "number" }),
      F("stato", "Stato", { options: ["Bozza", "Inviato", "Accettato", "Rifiutato", "Scaduto"], default: "Bozza" }),
      F("note", "Note", { type: "textarea", full: true }),
    ]}
    columns={[
      F("numero", "Numero"),
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("data", "Data"),
      F("importo", "Importo €"),
      F("stato", "Stato"),
    ]}
  />
);

export const OrdiniClientiPage = () => (
  <RegistryPage
    resource="ordini-clienti"
    title="Ordini cliente"
    subtitle="Ordini acquisiti collegati a cliente, sede e preventivo. Da qui nasce la commessa operativa."
    fields={[
      F("numero", "Numero", { required: true }),
      F("cliente_id", "Cliente", { ...CLIENT_LOOKUP, required: true, clearOnChange: ["sede_id", "preventivo_id"] }),
      F("sede_id", "Sede di installazione", {
        ...SITE_LOOKUP,
        required: true,
        dependsOn: "cliente_id",
        lookupFilterBy: "cliente_id",
        inlineCreateSite: true,
      }),
      F("preventivo_id", "Preventivo", {
        lookupResource: "preventivi",
        lookupLabel: quoteLabel,
        dependsOn: "cliente_id",
        lookupFilterBy: "cliente_id",
      }),
      F("data", "Data", { type: "date", required: true }),
      F("stato", "Stato", { options: ["Ricevuto", "Confermato", "In lavorazione", "Completato", "Annullato"], default: "Ricevuto" }),
      F("note", "Note", { type: "textarea", full: true }),
    ]}
    columns={[
      F("numero", "Numero"),
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("sede_id", "Sede", SITE_LOOKUP),
      F("preventivo_id", "Preventivo", { lookupResource: "preventivi", lookupLabel: quoteLabel }),
      F("data", "Data"),
      F("stato", "Stato"),
    ]}
  />
);

export const InstallazioniPage = () => <InstallazioniCalendarPage />;

export const AssistenzaPage = () => {
  const operational = useOperationalOptions();
  return (
  <RegistryPage
    resource="assistenza"
    title="Assistenza"
    subtitle="Ticket remoti e interventi in loco collegabili all'installazione o direttamente alla commessa."
    fields={[
      F("numero", "Numero ticket"),
      F("installazione_id", "Installazione", {
        lookupResource: "installazioni",
        lookupLabel: installationLabel,
        fillFromLookup: {
          commessa_id: "commessa_id",
          cliente_id: "cliente_id",
          sede_id: "sede_id",
        },
      }),
      F("commessa_id", "Commessa", {
        ...COMMESSA_LOOKUP,
        fillFromLookup: { cliente_id: "cliente_id", sede_id: "sede_id" },
      }),
      F("cliente_id", "Cliente", { ...CLIENT_LOOKUP, required: true, clearOnChange: ["sede_id"] }),
      F("sede_id", "Sede", { ...SITE_LOOKUP, dependsOn: "cliente_id", lookupFilterBy: "cliente_id" }),
      F("tipo", "Tipo assistenza", { options: operational.assistenza_tipi, default: operational.assistenza_tipi?.[0] || "Remota" }),
      F("priorita", "Priorità", { options: operational.assistenza_priorita, default: operational.assistenza_priorita?.includes("Normale") ? "Normale" : (operational.assistenza_priorita?.[0] || "Normale") }),
      F("tecnico", "Tecnico"),
      F("numero_caso_wallbox", "Caso Wallbox"),
      F("data", "Data", { type: "date" }),
      F("stato", "Stato", { options: operational.assistenza_stati, default: operational.assistenza_stati?.[0] || "Aperta" }),
      F("descrizione", "Descrizione problema / intervento", { type: "textarea", full: true }),
      F("note_tecniche", "Note tecniche", { type: "textarea", full: true }),
    ]}
    columns={[
      F("numero", "Ticket"),
      F("commessa_id", "Commessa", COMMESSA_LOOKUP),
      F("cliente_id", "Cliente", CLIENT_LOOKUP),
      F("sede_id", "Sede", SITE_LOOKUP),
      F("tipo", "Tipo"),
      F("stato", "Stato"),
    ]}
  />
  );
};
