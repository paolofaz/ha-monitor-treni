# Monitor Treni — Home Assistant

[![Release](https://img.shields.io/github/v/release/paolofaz/ha-monitor-treni)](https://github.com/paolofaz/ha-monitor-treni/releases/latest)

Integrazione + card Lovelace per monitorare il ritardo dei treni tramite le
API pubbliche di ViaggiaTreno (Trenitalia / RFI).

> ⚠️ **Uso privato**: le API di ViaggiaTreno non sono un servizio
> ufficialmente aperto/documentato con una licenza d'uso chiara. Per
> prudenza, questo repository è pensato per uso personale: tienilo privato
> su GitHub e installalo solo sulla tua istanza.
>
> Nota pratica: **né il Marketplace integrato in Home Assistant 2026.11+
> né HACS supportano i repository GitHub privati**. Anche collegando GitHub,
> il Marketplace legge solo repository pubblici. Se vuoi mantenere privato
> il codice, usa l'installazione manuale descritta sotto; non aggiungere
> questo repository al Marketplace.
> Riferimento ufficiale: https://www.home-assistant.io/integrations/marketplace/

## Installazione

### Manuale (consigliata per repository privati)

1. Scarica/clona il repository.
2. Copia `custom_components/monitor_treni` dentro
   `config/custom_components/` della tua istanza Home Assistant.
3. Riavvia Home Assistant.

### Tramite Marketplace (solo se il repository è pubblico)

Home Assistant 2026.11+ integra HACS come Marketplace. La funzione
**Impostazioni → Marketplace → Aggiungi da link** accetta **solo repository
GitHub pubblici**. Un repository privato può dare errori come
`can not be reached on GitHub: Not Found` e far apparire la versione
installata come scomparsa, anche quando il codice è ancora presente
nell'istanza di Home Assistant. **Non occorre rendere pubblico il
repository per utilizzare l'integrazione: installala manualmente.**

Se questo repository era stato registrato nel Marketplace prima di essere
reso privato, il Marketplace può continuare a tentare gli aggiornamenti.
La rimozione di una integrazione *installata* tramite Marketplace può
eliminare i file da `custom_components/`: prima di procedere esegui un
backup completo di Home Assistant e della cartella dell'integrazione.
L'installazione manuale non viene aggiornata automaticamente dal Marketplace.

Per Home Assistant 2026.10 o versioni precedenti, HACS prevede
**Integrazioni → menu (⋮) → Repository personalizzati**, ma richiede
comunque un repository pubblico.

### Aggiornamento temporaneo con repository pubblico

Per un aggiornamento occasionale tramite Marketplace:

1. Verifica prima che il repository **e la cronologia dei commit** non
   contengano credenziali o dati riservati: anche pochi minuti di
   visibilità pubblica permettono ad altri di copiarli.
2. Esegui un backup di Home Assistant.
3. Cambia temporaneamente la visibilità GitHub in **Public**.
4. Verifica che sia pubblicata una [release GitHub](https://github.com/paolofaz/ha-monitor-treni/releases/latest) con tag coerente con `manifest.json`.
5. Nel Marketplace aggiorna Monitor Treni, verifica la versione installata
   e riavvia Home Assistant se richiesto.
6. Riporta il repository in **Private**.

**Attenzione:** il passaggio di nuovo a Private non è una soluzione agli
errori del Marketplace. Quest'ultimo continuerà a tentare gli aggiornamenti
di un repository non più accessibile e potrebbe riportare `Not Found`
o altri messaggi. L'integrazione già installata resta sul disco e può
continuare a funzionare; per evitare le verifiche del Marketplace occorre
gestirla manualmente.

## Novità v2.0.3

- Le soglie di ritardo devono essere di almeno un minuto; le configurazioni salvate non valide vengono ignorate e rimosse all'avvio.
- Validazione del numero del treno e utilizzo del fuso orario di Home Assistant per la data di riferimento.
- Test automatici, Hassfest e validazione HACS prima delle future release.

## Configurazione

1. Impostazioni → Dispositivi e servizi → Aggiungi integrazione → cerca
   "Monitor Treni".
2. Imposta l'intervallo di aggiornamento (default 2 minuti, 1-10) e dopo
   quante ore rimuovere automaticamente un treno arrivato (default 3 ore;
   25 = disattiva la rimozione automatica). Entrambi modificabili in
   seguito dalle Opzioni dell'integrazione.
3. Aggiungi la card alla tua dashboard (vedi sotto): da lì aggiungi e
   rimuovi i treni da monitorare.

## Card Lovelace

Si registra automaticamente come risorsa Lovelace all'avvio (nessun setup
manuale richiesto, salvo dashboard in modalità YAML — in quel caso compare
una notifica con le istruzioni per aggiungerla a mano).

```yaml
type: custom:monitor-treni-card
title: I miei treni
```

Dalla card puoi:
- premere **+ Aggiungi**, inserire numero treno e data (default oggi) e
  confermare;
- premere l'icona 🗑 su un treno per rimuoverlo (con conferma);
- premere l'icona 🔕/🔔 per attivare/disattivare un avviso di ritardo
  (soglia in minuti + destinatario scelto da un menu a tendina — vedi
  sezione "Avviso di ritardo" più sotto);
- **cliccare su un treno** per aprire lo storico/grafico del ritardo
  (dialogo "Più informazioni" nativo di Home Assistant).

## Icona dell'integrazione

Il file `custom_components/monitor_treni/brand/icon.png` (128×128) viene
servito automaticamente da Home Assistant tramite la Brands API locale
(disponibile da Home Assistant 2026.3) e compare nell'elenco integrazioni,
nella pagina del dispositivo, ecc. Non compare invece nella card Lovelace
(rimossa volutamente: la card resta minimale, solo testo/icone mdi).

Per cambiarla, sostituisci quel file con un'altra immagine PNG 128×128 e
riavvia Home Assistant.

## Servizi

Utili per automazioni, script o dashboard alternative:

- `monitor_treni.add_train` — campi `train_number` (obbligatorio), `date`
  (opzionale, default oggi).
- `monitor_treni.remove_train` — campi `train_number`, `date` (entrambi
  obbligatori).
- `monitor_treni.notify_on_delay` — avvisami se un treno raggiunge un
  certo ritardo, senza scrivere un'automazione (vedi sezione dedicata
  sotto).
- `monitor_treni.cancel_delay_watch` — annulla un avviso impostato in
  precedenza.

### Avviso di ritardo, senza scrivere automazioni

Per il caso "controllo un treno solo ogni tanto e voglio un avviso se
tarda", non serve scrivere un'automazione a mano (con tutte le
complicazioni di dover riferirsi all'entity_id esatto, che cambia ogni
giorno per via della data).

**Il numero che imposti è un passo ricorrente, non una soglia singola**:
con 15 minuti ricevi un avviso a 15, 30, 45, 60... minuti di ritardo (e di
nuovo quando rientra sotto ciascuno di quei valori), non solo alla prima
soglia raggiunta — così un ritardo che continua a crescere non ti lascia
"fermo" al primo avviso.

**Dalla card**: tocca l'icona 🔕 su un treno, scegli ogni quanti minuti
essere avvisato e il destinatario da un menu a tendina (le tue entità
`notify.*` — telefono, gruppi di notifica, ecc. — vengono elencate
automaticamente, non serve ricordarsele a memoria). L'icona diventa 🔔
quando l'avviso è attivo; toccala di nuovo per disattivarlo.

**Da automazioni/script**, oppure da Strumenti per sviluppatori → Azioni:

```yaml
action: monitor_treni.notify_on_delay
data:
  train_number: "2028"
  date: "2026-08-25"        # opzionale, default oggi
  threshold_minutes: 15     # passo: avviso a 15, 30, 45, 60... minuti
  notify_target: notify.mobile_app_iphone_di_paolo
  message: "Il regionale è in ritardo, prenditela comoda"  # opzionale
```

Cosa succede:
- se il treno non è ancora monitorato, viene aggiunto automaticamente;
- l'avviso resta attivo per **tutta la durata del viaggio**: notifica ogni
  volta che il ritardo attraversa un **multiplo del passo impostato**, sia
  salendo che scendendo;
- si disattiva da solo quando il treno risulta arrivato, oppure a mano con
  🔔 sulla card o col servizio `monitor_treni.cancel_delay_watch`
  (`train_number` + `date`).

Il destinatario (`notify_target`) è l'entity_id di un'entità del dominio
`notify` (es. `notify.mobile_app_iphone_di_paolo`) — nello YAML/Strumenti
per sviluppatori compare come menu a tendina nativo di Home Assistant,
grazie al selettore `entity: domain: notify`.

✅ Gli avvisi impostati con questo servizio **sopravvivono ai riavvii** di
Home Assistant (salvati nello stesso file di storage della lista treni).
Al riavvio, ogni avviso attivo viene rivalutato subito contro i dati reali
del treno, nel caso il ritardo sia cambiato mentre Home Assistant era
spento.

#### Restringere il menu a tendina dei destinatari

Se hai molte entità `notify.*` (dispositivi Alexa, Telegram, telefoni...)
e vuoi vedere nel menu solo quelle che usi davvero, aggiungi
`notify_targets` alla configurazione della card:

```yaml
type: custom:monitor-treni-card
title: I miei treni
notify_targets:
  - notify.mobile_app_iphone_di_paolo
  - notify.telegram_paolo
```

Se ometti `notify_targets` (comportamento di default), il menu mostra
tutte le entità `notify.*` presenti in Home Assistant.

## Entità create

Per ogni treno monitorato viene creata una singola entità sensore
`sensor.treno_<numero>_<AAAAMMGG>_ritardo` (nessun device: un device con
dentro una sola entità sarebbe stato solo rumore extra nel registro
dispositivi):

- **stato**: ritardo in minuti (negativo = anticipo, 0 = in orario), con
  `state_class: measurement` per grafici e statistiche a lungo termine
  native di Home Assistant;
- **nome**: "Treno &lt;numero&gt; · &lt;data&gt;";
- **attributi**: categoria, stazione di partenza/arrivo, ultimo
  rilevamento, prossima fermata, orari previsti/effettivi, stato del
  treno (in viaggio, in stazione, non partito, arrivato); se hai un
  avviso di ritardo attivo su quel treno, anche `AvvisoRitardoPasso`,
  `AvvisoRitardoTarget` e `AvvisoRitardoSogliaAttuale` (vedi sezione
  dedicata sopra).

**Rimozione automatica**: quando lo stato del treno diventa "arrivato", il
sensore viene rimosso automaticamente dopo il numero di ore impostato in
configurazione/opzioni (default 3, valore 25 = mai).

⚠️ **Nota sulla data per i treni notturni**: la data indica il giorno di
*partenza* del treno (la "data di circolazione" secondo ViaggiaTreno), non
il giorno in cui lo aggiungi. Per un notturno che parte alle 22:00 del
giorno X e arriva alle 10:00 del giorno Y, inserisci X come data anche se
lo stai aggiungendo dopo mezzanotte del giorno Y — altrimenti la ricerca
del treno fallisce.


## Licenza

MIT, vedi `LICENSE`.
