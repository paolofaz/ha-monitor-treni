/**
 * Monitor Treni Lovelace card
 * Web component nativo: nessuna build, nessuna dipendenza esterna.
 *
 * Nota architetturale importante: `set hass(hass)` viene chiamato ad ogni
 * cambio di stato di QUALSIASI entità in Home Assistant, quindi anche più
 * volte al secondo. Per questo motivo la card NON ricostruisce mai tutto
 * l'HTML ad ogni update: costruisce lo scheletro (header + form "aggiungi")
 * una sola volta e in seguito aggiorna solo il contenitore della lista
 * treni, e solo se i dati sono effettivamente cambiati. Questo evita di
 * distruggere il campo di input mentre l'utente ci sta scrivendo dentro.
 */

const STATO_LABELS = {
  in_viaggio: { label: "In viaggio", dot: "var(--success-color, #43a047)" },
  in_stazione: { label: "In stazione", dot: "var(--info-color, #039be5)" },
  non_partito: { label: "Non ancora partito", dot: "var(--disabled-text-color, #9e9e9e)" },
  arrivato: { label: "Arrivato", dot: "var(--success-color, #43a047)" },
  non_disponibile: { label: "Dati non disponibili", dot: "var(--disabled-text-color, #9e9e9e)" },
};

function delayColor(delay) {
  if (delay === null || delay === undefined || Number.isNaN(delay)) {
    return "var(--disabled-text-color, #9e9e9e)";
  }
  if (delay <= 0) return "var(--success-color, #43a047)";
  if (delay <= 5) return "var(--warning-color, #fb8c00)";
  return "var(--error-color, #e53935)";
}

function fmtDelay(delay) {
  if (delay === null || delay === undefined || Number.isNaN(delay)) return "--";
  if (delay === 0) return "In orario";
  return delay > 0 ? `+${delay} min` : `${delay} min`;
}

function timeOnly(value) {
  if (!value) return null;
  const match = String(value).match(/(\d{2}:\d{2})(:\d{2})?$/);
  return match ? match[1] : value;
}

function todayIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

class MonitorTreniCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._showAddForm = false;
    this._built = false;
    this._lastSignature = null;
  }

  setConfig(config) {
    this._config = config || {};
    if (this._built) {
      this._titleEl.textContent = this._config.title || "🚆 Monitor Treni";
    } else {
      this._build();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._updateTrains();
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return { title: "Monitor Treni" };
  }

  // --- costruzione dello scheletro, UNA SOLA VOLTA -----------------------

  _build() {
    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card>
        <div class="header">
          <div class="title"></div>
          <button class="add-btn" type="button">+ Aggiungi</button>
        </div>
        <div class="add-form-wrapper"></div>
        <div class="watch-form-wrapper"></div>
        <div class="trains"></div>
      </ha-card>
    `;

    this._titleEl = this.shadowRoot.querySelector(".title");
    this._titleEl.textContent = this._config?.title || "🚆 Monitor Treni";

    this._addBtn = this.shadowRoot.querySelector(".add-btn");
    this._addBtn.addEventListener("click", () => this._toggleAddForm());

    this._addWrapper = this.shadowRoot.querySelector(".add-form-wrapper");
    this._watchWrapper = this.shadowRoot.querySelector(".watch-form-wrapper");
    this._watchTarget = null;
    this._trainsEl = this.shadowRoot.querySelector(".trains");

    // Delegazione eventi sulla lista treni: un solo listener, mai
    // riattaccato, quindi non serve ricostruire nulla per farlo funzionare
    // dopo un aggiornamento parziale.
    this._trainsEl.addEventListener("click", (ev) => {
      const wrapper = ev.target.closest(".train");
      if (!wrapper) return;

      const removeBtn = ev.target.closest('[data-action="remove"]');
      if (removeBtn) {
        this._onRemove(wrapper.dataset.number, wrapper.dataset.date);
        return;
      }

      const watchBtn = ev.target.closest('[data-action="watch"]');
      if (watchBtn) {
        if (watchBtn.dataset.active === "true") {
          this._onCancelWatch(wrapper.dataset.number, wrapper.dataset.date);
        } else {
          this._openWatchForm(wrapper.dataset.number, wrapper.dataset.date);
        }
        return;
      }

      // Click sul resto della card: apre il dialogo "Più info" di Home
      // Assistant, che mostra anche lo storico/grafico del ritardo.
      this._openMoreInfo(wrapper.dataset.entityId);
    });

    this._built = true;
    this._lastSignature = null; // forza il primo popolamento della lista
  }

  // --- form "aggiungi treno" ---------------------------------------------

  _toggleAddForm() {
    this._showAddForm = !this._showAddForm;
    this._addBtn.textContent = this._showAddForm ? "✕ Chiudi" : "+ Aggiungi";
    this._renderAddForm();
  }

  _renderAddForm() {
    if (!this._showAddForm) {
      this._addWrapper.innerHTML = "";
      return;
    }

    this._addWrapper.innerHTML = `
      <form class="add-form">
        <input
          class="train-number"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          placeholder="Numero treno"
          maxlength="6"
          required
        />
        <input class="train-date" type="date" value="${todayIso()}" />
        <button type="submit" class="primary">Aggiungi</button>
        <button type="button" class="cancel">Annulla</button>
      </form>
    `;

    const form = this._addWrapper.querySelector("form");
    const numberInput = form.querySelector(".train-number");

    // Campo di testo libero: niente spinner (a differenza di type="number"),
    // ma accettiamo solo cifre mentre l'utente scrive.
    numberInput.addEventListener("input", () => {
      const cleaned = numberInput.value.replace(/\D/g, "");
      if (cleaned !== numberInput.value) numberInput.value = cleaned;
    });

    form.addEventListener("submit", (ev) => this._onAddSubmit(ev));
    form.querySelector(".cancel").addEventListener("click", () => this._toggleAddForm());

    // Porta subito il focus sul campo numero, comodo su desktop.
    numberInput.focus();
  }

  _onAddSubmit(ev) {
    ev.preventDefault();
    const form = ev.currentTarget;
    const number = form.querySelector(".train-number").value.trim();
    const date = form.querySelector(".train-date").value || todayIso();
    if (!number) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Aggiungo…";

    this._callService("monitor_treni", "add_train", { train_number: number, date })
      .then(() => {
        this._showAddForm = false;
        this._addBtn.textContent = "+ Aggiungi";
        this._renderAddForm();
      })
      .catch((err) => {
        console.error("Monitor Treni: errore durante l'aggiunta del treno", err);
        window.alert(
          "Errore durante l'aggiunta del treno. Controlla il numero inserito " +
          "oppure guarda i log di Home Assistant per i dettagli."
        );
        submitBtn.disabled = false;
        submitBtn.textContent = "Aggiungi";
      });
  }

  _openMoreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  _notifyTargets() {
    if (!this._hass) return [];
    // Config opzionale della card: notify_targets: [entity_id, ...].
    // Se presente e non vuota, mostra solo quelle invece di tutte le
    // entità notify.* trovate (utile se ne hai tante e vuoi restringere
    // la scelta a quelle che usi davvero).
    const configured = this._config?.notify_targets;
    const ids =
      Array.isArray(configured) && configured.length
        ? configured
        : Object.keys(this._hass.states).filter((id) => id.startsWith("notify."));

    return ids
      .map((id) => ({
        entityId: id,
        label: this._hass.states[id]?.attributes?.friendly_name || id,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "it"));
  }

  _openWatchForm(number, date) {
    // Un solo form alla volta: chiudiamo l'eventuale form "aggiungi treno"
    // aperto, così non si accavallano due input contemporaneamente.
    if (this._showAddForm) {
      this._showAddForm = false;
      this._addBtn.textContent = "+ Aggiungi";
      this._renderAddForm();
    }

    this._watchTarget = { number, date };
    const targets = this._notifyTargets();

    this._watchWrapper.innerHTML = `
      <form class="add-form watch-form">
        <div class="watch-form-title">
          Avviso ritardo — treno ${escapeHtml(number)}<br />
          <small>ti avviso ogni N minuti di ritardo in più (e quando rientra)</small>
        </div>
        <input
          class="watch-threshold"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          placeholder="Ogni quanti minuti"
          maxlength="3"
          required
        />
        <select class="watch-target" required>
          <option value="" disabled selected>Scegli destinatario…</option>
          ${
            targets.length
              ? targets
                  .map((t) => `<option value="${escapeHtml(t.entityId)}">${escapeHtml(t.label)}</option>`)
                  .join("")
              : ""
          }
        </select>
        <button type="submit" class="primary">Attiva avviso</button>
        <button type="button" class="cancel">Annulla</button>
      </form>
    `;

    if (!targets.length) {
      const select = this._watchWrapper.querySelector(".watch-target");
      select.insertAdjacentHTML(
        "beforeend",
        `<option value="" disabled>Nessuna entità "notify.*" trovata</option>`
      );
    }

    const form = this._watchWrapper.querySelector("form");
    const thresholdInput = form.querySelector(".watch-threshold");
    thresholdInput.addEventListener("input", () => {
      const cleaned = thresholdInput.value.replace(/\D/g, "");
      if (cleaned !== thresholdInput.value) thresholdInput.value = cleaned;
    });

    form.addEventListener("submit", (ev) => this._onWatchSubmit(ev));
    form.querySelector(".cancel").addEventListener("click", () => this._closeWatchForm());

    thresholdInput.focus();
  }

  _closeWatchForm() {
    this._watchTarget = null;
    this._watchWrapper.innerHTML = "";
  }

  _onWatchSubmit(ev) {
    ev.preventDefault();
    const form = ev.currentTarget;
    const threshold = form.querySelector(".watch-threshold").value.trim();
    const notifyTarget = form.querySelector(".watch-target").value;
    if (!threshold || !notifyTarget || !this._watchTarget) return;

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Attivo…";

    const data = {
      train_number: this._watchTarget.number,
      date: this._watchTarget.date,
      threshold_minutes: Number(threshold),
      notify_target: notifyTarget,
    };

    this._callService("monitor_treni", "notify_on_delay", data)
      .then(() => this._closeWatchForm())
      .catch((err) => {
        console.error("Monitor Treni: errore impostando l'avviso di ritardo", err);
        window.alert(
          "Errore impostando l'avviso. Controlla i dati inseriti oppure " +
          "guarda i log di Home Assistant per i dettagli."
        );
        submitBtn.disabled = false;
        submitBtn.textContent = "Attiva avviso";
      });
  }

  _onCancelWatch(number, date) {
    if (!window.confirm(`Disattivare l'avviso di ritardo per il treno ${number}?`)) return;
    this._callService("monitor_treni", "cancel_delay_watch", { train_number: number, date })
      .catch((err) => {
        console.error("Monitor Treni: errore disattivando l'avviso", err);
        window.alert(
          "Errore disattivando l'avviso. Guarda i log di Home Assistant " +
          "per i dettagli."
        );
      });
  }

  _onRemove(number, date) {
    if (!window.confirm(`Rimuovere il treno ${number} (${date}) dal monitoraggio?`)) return;
    this._callService("monitor_treni", "remove_train", { train_number: number, date })
      .catch((err) => {
        console.error("Monitor Treni: errore durante la rimozione del treno", err);
        window.alert(
          "Errore durante la rimozione del treno. Guarda i log di Home " +
          "Assistant per i dettagli."
        );
      });
  }

  _callService(domain, service, data) {
    // hass.callService ritorna una Promise: la propaghiamo così le
    // chiamate sopra possono intercettare eventuali errori invece di
    // fallire silenziosamente senza che l'utente se ne accorga.
    return this._hass.callService(domain, service, data);
  }

  // --- lista treni: aggiornamento parziale e solo se serve --------------

  _trains() {
    if (!this._hass) return [];
    const trains = [];
    for (const entityId of Object.keys(this._hass.states)) {
      if (!entityId.startsWith("sensor.")) continue;
      const state = this._hass.states[entityId];
      const attrs = state.attributes || {};
      // Riconosciamo un sensore Monitor Treni dagli attributi NumeroTreno +
      // Data (sempre presenti, l'entità li imposta comunque anche prima del
      // primo aggiornamento riuscito), NON dal formato dell'entity_id: se
      // l'unique_id esisteva già nel registro entità da un'installazione
      // precedente, Home Assistant può aver mantenuto un entity_id
      // "vecchio" che non seguirebbe più lo schema atteso.
      if (attrs.NumeroTreno === undefined || attrs.Data === undefined) continue;
      trains.push({
        entityId,
        number: String(attrs.NumeroTreno),
        date: String(attrs.Data),
        state,
      });
    }
    trains.sort((a, b) => a.number.localeCompare(b.number, "it", { numeric: true }));
    return trains;
  }

  _updateTrains() {
    const trains = this._trains();
    // Firma leggera: se non cambia nulla di rilevante non tocchiamo il DOM,
    // così non c'è alcun impatto anche se l'utente sta interagendo altrove
    // nella card in quel momento.
    const signature = trains
      // last_updated (non last_changed!) cambia anche quando si
      // aggiornano solo gli attributi (es. attivazione di un avviso di
      // ritardo) senza che cambi il ritardo stesso: last_changed invece
      // resta fermo in quel caso, facendoci credere erroneamente che nulla
      // sia cambiato e saltare il ridisegno della card.
      .map((t) => `${t.entityId}:${t.state.state}:${t.state.last_updated}`)
      .join("|");
    if (signature === this._lastSignature) return;
    this._lastSignature = signature;

    this._trainsEl.innerHTML = trains.length
      ? trains.map((t) => this._renderTrain(t)).join("")
      : `<div class="empty">Nessun treno monitorato. Tocca "+ Aggiungi" per iniziare.</div>`;
  }

  _renderTrain(train) {
    const attrs = train.state.attributes || {};
    const unavailable = train.state.state === "unavailable" || train.state.state === "unknown";
    const delay = unavailable ? null : Number(train.state.state);
    const statoKey = attrs.Stato || (unavailable ? "non_disponibile" : null);
    const stato = STATO_LABELS[statoKey] || STATO_LABELS.non_disponibile;

    const categoria = attrs.Categoria ? `${escapeHtml(attrs.Categoria)} ` : "";
    const origine = escapeHtml(attrs.StazionePartenza || "?");
    const destinazione = escapeHtml(attrs.StazioneArrivo || "?");

    const watchActive = attrs.AvvisoRitardoPasso !== undefined;
    const watchTitle = watchActive
      ? `Avviso attivo ogni ${attrs.AvvisoRitardoPasso} min di ritardo (tocca per disattivare)`
      : "Avvisami se in ritardo";

    return `
      <div class="train" data-number="${escapeHtml(train.number)}" data-date="${escapeHtml(train.date)}" data-entity-id="${escapeHtml(train.entityId)}">
        <div class="train-header">
          <div class="train-title">${categoria}${escapeHtml(train.number)}</div>
          <div class="delay-badge" style="color:${delayColor(delay)}">
            ${fmtDelay(delay)}
          </div>
          <button
            class="watch-btn ${watchActive ? "active" : ""}"
            type="button"
            title="${watchTitle}"
            data-action="watch"
            data-active="${watchActive}"
          >${watchActive ? "🔔" : "🔕"}</button>
          <button class="remove-btn" type="button" title="Rimuovi treno" data-action="remove">🗑</button>
        </div>

        ${
          watchActive
            ? `<div class="watch-badge">
                🔔 avviso ogni ${escapeHtml(attrs.AvvisoRitardoPasso)} min di ritardo
                ${attrs.AvvisoRitardoSogliaAttuale > 0 ? `(soglia superata)` : ""}
              </div>`
            : ""
        }

        <div class="route">${origine} → ${destinazione}</div>

        <div class="status-row">
          <span class="status-dot" style="background:${stato.dot}"></span>
          <span>${stato.label}</span>
        </div>

        ${
          attrs.UltimoRilevamento || attrs.ProssimaFermata
            ? `<div class="track-row">
                ${
                  attrs.UltimoRilevamento
                    ? `<div>📍 ${escapeHtml(attrs.UltimoRilevamento)}${
                        attrs.OraUltimoRilevamento ? ` · ${escapeHtml(timeOnly(attrs.OraUltimoRilevamento))}` : ""
                      }</div>`
                    : "<div></div>"
                }
                ${
                  attrs.ProssimaFermata
                    ? `<div>Prossima: ${escapeHtml(attrs.ProssimaFermata)}${
                        attrs.ArrivoPrevistoProssimaFermata ? ` (${escapeHtml(timeOnly(attrs.ArrivoPrevistoProssimaFermata))})` : ""
                      }</div>`
                    : "<div></div>"
                }
              </div>`
            : ""
        }

        <div class="times-grid">
          <div>
            <div class="times-label">Partenza</div>
            <div>${escapeHtml(timeOnly(attrs.PartenzaPrevista)) || "--"}</div>
            ${
              attrs.PartenzaEffettiva
                ? `<div class="times-actual">Eff. ${escapeHtml(timeOnly(attrs.PartenzaEffettiva))}</div>`
                : ""
            }
          </div>
          <div>
            <div class="times-label">Arrivo</div>
            <div>${escapeHtml(timeOnly(attrs.ArrivoPrevisto)) || "--"}</div>
            ${
              attrs.ArrivoStimato
                ? `<div class="times-actual">Stim. ${escapeHtml(timeOnly(attrs.ArrivoStimato))}</div>`
                : ""
            }
          </div>
        </div>
      </div>
    `;
  }

  _styles() {
    return `
      ha-card {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .title {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--primary-text-color);
        flex: 1;
      }
      .add-btn, .add-form button, .remove-btn {
        font: inherit;
        cursor: pointer;
        border: none;
        border-radius: 8px;
        padding: 6px 12px;
        background: var(--secondary-background-color, #eee);
        color: var(--primary-text-color);
      }
      .add-btn:hover, .add-form button:hover, .remove-btn:hover {
        filter: brightness(0.95);
      }
      .add-form button.primary {
        background: var(--primary-color);
        color: var(--text-primary-color, white);
      }
      .add-form {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        align-items: center;
        padding: 8px;
        border-radius: 8px;
        background: var(--secondary-background-color, #f5f5f5);
      }
      .add-form input {
        font: inherit;
        padding: 6px 8px;
        border-radius: 6px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, white);
        color: var(--primary-text-color);
      }
      .add-form select {
        font: inherit;
        padding: 6px 8px;
        border-radius: 6px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, white);
        color: var(--primary-text-color);
        max-width: 220px;
      }
      .add-form input.train-number,
      .add-form input.watch-threshold {
        width: 110px;
      }
      .watch-form-title {
        width: 100%;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .watch-form-title small {
        font-weight: 400;
        color: var(--secondary-text-color);
      }
      .trains {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .empty {
        color: var(--secondary-text-color);
        text-align: center;
        padding: 16px 0;
      }
      .train {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 12px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        cursor: pointer;
        transition: background-color 0.15s ease;
      }
      .train:hover {
        background: var(--secondary-background-color, #f5f5f5);
      }
      .train-header {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .train-title {
        font-weight: 600;
        font-size: 1.05em;
        color: var(--primary-text-color);
        flex: 1;
      }
      .delay-badge {
        font-weight: 600;
        font-size: 0.95em;
      }
      .remove-btn {
        padding: 2px 8px;
        background: transparent;
        opacity: 0.6;
      }
      .remove-btn:hover {
        opacity: 1;
      }
      .watch-btn {
        padding: 2px 8px;
        background: transparent;
        opacity: 0.5;
      }
      .watch-btn:hover {
        opacity: 1;
      }
      .watch-btn.active {
        opacity: 1;
      }
      .watch-badge {
        font-size: 0.8em;
        color: var(--warning-color, #fb8c00);
      }
      .route {
        color: var(--secondary-text-color);
        font-size: 0.95em;
      }
      .status-row {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.9em;
        color: var(--primary-text-color);
      }
      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
      }
      .track-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.85em;
        color: var(--secondary-text-color);
        gap: 8px;
      }
      .next-stop {
        text-align: right;
      }
      .times-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-top: 4px;
        padding-top: 8px;
        border-top: 1px solid var(--divider-color, #eee);
        font-size: 0.9em;
      }
      .times-label {
        color: var(--secondary-text-color);
        font-size: 0.8em;
      }
      .times-actual {
        color: var(--secondary-text-color);
        font-size: 0.8em;
      }
    `;
  }
}

customElements.define("monitor-treni-card", MonitorTreniCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "monitor-treni-card",
  name: "Monitor Treni",
  description: "Monitora i treni tramite Monitor Treni, con aggiunta/rimozione dalla card.",
});
