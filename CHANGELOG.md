# Changelog

## 2.0.2 — 2026-11-06

- Aggiunto `issue_tracker` al manifest, come richiesto dalle regole di
  pubblicazione per le integrazioni del Marketplace.
- Rimosso il `manifest.json` estraneo dalla cartella `translations/`:
  il solo manifest dell'integrazione resta in `custom_components/monitor_treni/`.
- Documentata l'installazione dal Marketplace di Home Assistant 2026.11 e
  la diagnosi degli errori generici del QueueManager.
- Chiarito che i repository GitHub privati non possono essere gestiti dal
  Marketplace: dopo averli resi nuovamente privati possono ricomparire
  errori di accesso, senza impatto necessario sul funzionamento locale.
- Nessuna modifica al funzionamento dei sensori, dei servizi o della card.

## 2.0.1

- Integrazione a istanza singola: si configura una volta sola, i treni si
  gestiscono a runtime dalla card Lovelace o via servizi.
- Card Lovelace nativa (`custom:monitor-treni-card`), auto-registrata come
  risorsa Lovelace all'avvio. Click su un treno apre lo storico/grafico
  del ritardo (dialogo "Più informazioni").
- Servizi `monitor_treni.add_train` / `monitor_treni.remove_train` per
  gestire i treni da automazioni/script.
- **Nuovo**: `monitor_treni.notify_on_delay` / `monitor_treni.cancel_delay_watch`
  — avviso di ritardo senza dover scrivere un'automazione a mano (niente
  più bisogno di riferirsi all'entity_id esatto, che cambia ogni giorno
  per via della data). Attivabile anche dalla card con l'icona 🔔/🔕, con
  destinatario scelto da un menu a tendina (entità `notify.*`, popolato
  automaticamente — restringibile con `notify_targets` nella config della
  card). Il valore impostato è un **passo ricorrente**: notifica ogni
  volta che il ritardo attraversa un multiplo di quel valore (es. 15 →
  avviso a 15, 30, 45, 60... minuti), sia salendo che scendendo, per
  tutta la durata del viaggio, fino all'arrivo o alla disattivazione
  manuale — così un ritardo che continua a crescere non lascia "fermi"
  al primo avviso. Usa l'azione moderna `notify.send_message` con
  `entity_id` (non il vecchio schema a servizio dinamico `notify.<nome>`,
  che nelle versioni recenti di Home Assistant può non esistere più per i
  target basati su entità). Persiste
  ai riavvii (salvato nello stesso storage della lista treni) e viene
  rivalutato subito al riavvio contro i dati reali.
- Persistenza della lista treni tra riavvii; storage ripulito
  automaticamente quando l'integrazione viene eliminata dall'interfaccia.
- Intervallo di polling configurabile (1-10 minuti) e rimozione automatica
  dopo l'arrivo configurabile (1-24 ore, 25 = mai), entrambi dalle
  Opzioni dell'integrazione.
- Primo aggiornamento dati immediato alla creazione di un treno.
- Singola entità sensore per treno (nessun device, per non creare
  "contenitori vuoti" orfani quando un treno viene rimosso), nome pulito
  "Treno &lt;numero&gt; · &lt;data&gt;", `state_class: measurement` per
  statistiche a lungo termine native.
- Icona dell'integrazione locale (`brand/icon.png`), servita
  automaticamente dalla Brands API di Home Assistant 2026.3+: compare
  nell'elenco integrazioni e nelle pagine dispositivo, non nella card
  Lovelace (tenuta volutamente minimale).

### Nota tecnica: cache della card sull'app mobile

Il file `monitor-treni-card.js` viene servito con un parametro `?v=N` in
coda all'URL per forzare il ricaricamento quando cambia. **Ogni volta che
si modifica il contenuto della card, bisogna incrementare quel numero**
in `__init__.py` (`js_url = ...?v=N`), altrimenti l'app companion su
iOS/Android (e in generale i WebView mobili) può continuare a servire la
versione in cache indefinitamente — a differenza dei browser desktop,
dove un refresh forzato (Ctrl+Shift+R) basta ad aggirare il problema, sui
dispositivi mobili non c'è un equivalente semplice, nemmeno riavviando il
dispositivo.
