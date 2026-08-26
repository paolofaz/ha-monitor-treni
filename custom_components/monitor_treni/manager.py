import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import (
    AUTO_REMOVE_NEVER,
    CONF_AUTO_REMOVE_HOURS,
    CONF_SCAN_INTERVAL,
    DEFAULT_AUTO_REMOVE_HOURS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import MonitorTreniCoordinator

_LOGGER = logging.getLogger(__name__)


class MonitorTreniManager:
    """Tiene traccia dei treni monitorati per una config entry.

    I treni non sono più legati a una config entry per treno: vengono
    aggiunti/rimossi a runtime (tipicamente dalla card Lovelace, tramite i
    servizi viaggiatreno.add_train / viaggiatreno.remove_train) e la lista è
    persistita su disco cosi' sopravvive ai riavvii di Home Assistant.
    """

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self.coordinators: dict[str, MonitorTreniCoordinator] = {}
        self.entities: dict[str, object] = {}
        self._async_add_entities = None
        self._entity_factory = None
        # Rimozione automatica dopo l'arrivo: teniamo traccia di quali treni
        # hanno già un timer programmato e del relativo "annulla" per poterlo
        # cancellare se il treno viene rimosso manualmente prima che scatti.
        self._auto_remove_scheduled: set[str] = set()
        self._auto_remove_unsub: dict[str, object] = {}
        # Avvisi di ritardo ad-hoc (servizio notify_on_delay): un solo
        # avviso per volta per treno, poi si disattiva da solo finché non
        # ne viene impostato uno nuovo.
        self._delay_watches: dict[str, dict] = {}

    @property
    def scan_interval(self):
        return self.entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    @property
    def auto_remove_hours(self):
        return self.entry.options.get(CONF_AUTO_REMOVE_HOURS, DEFAULT_AUTO_REMOVE_HOURS)

    def _make_update_listener(self, key):
        """Callback invocata dal coordinator ad ogni aggiornamento dati.

        Fa due cose indipendenti:
        - se il treno risulta arrivato, programma la rimozione automatica
          (vedi _check_and_schedule_arrival);
        - se c'è un avviso di ritardo attivo per questo treno, controlla se
          va notificato (vedi _check_delay_watch).
        """

        def _listener():
            self._check_and_schedule_arrival(key)
            self._check_delay_watch(key)

        return _listener

    def _check_and_schedule_arrival(self, key):
        coordinator = self.coordinators.get(key)
        if coordinator is None:
            return
        data = coordinator.data or {}
        if not data.get("arrivato"):
            return
        if key in self._auto_remove_scheduled:
            return

        hours = self.auto_remove_hours
        if hours >= AUTO_REMOVE_NEVER:
            return

        self._auto_remove_scheduled.add(key)
        delay = timedelta(hours=hours)
        _LOGGER.info(
            "Treno %s (%s) risulta arrivato: verrà rimosso automaticamente "
            "tra %s",
            coordinator.train_number, coordinator.date, delay,
        )
        self._auto_remove_unsub[key] = async_call_later(
            self.hass, delay.total_seconds(), self._make_auto_remove_callback(key)
        )

    def update_auto_remove_settings(self):
        """Chiamato quando cambiano le opzioni dell'integrazione."""
        if self.auto_remove_hours >= AUTO_REMOVE_NEVER:
            # L'utente ha scelto "mai": annulliamo eventuali rimozioni già
            # programmate in precedenza con un valore diverso.
            for key in list(self._auto_remove_unsub.keys()):
                self._cancel_auto_remove(key)
        else:
            # L'utente ha impostato/cambiato un valore: rivalutiamo subito
            # i treni già arrivati che magari non erano ancora programmati
            # (es. prima l'auto-rimozione era su "mai").
            for key in list(self.coordinators.keys()):
                self._check_and_schedule_arrival(key)

    def _make_auto_remove_callback(self, key):
        async def _callback(_now):
            self._auto_remove_unsub.pop(key, None)
            self._auto_remove_scheduled.discard(key)
            coordinator = self.coordinators.get(key)
            if coordinator is None:
                return  # rimosso manualmente nel frattempo
            _LOGGER.info(
                "Rimozione automatica del treno %s (%s) dopo l'arrivo",
                coordinator.train_number, coordinator.date,
            )
            await self.async_remove_train(coordinator.train_number, coordinator.date)

        return _callback

    def _cancel_auto_remove(self, key):
        self._auto_remove_scheduled.discard(key)
        unsub = self._auto_remove_unsub.pop(key, None)
        if unsub:
            unsub()

    async def async_set_delay_watch(
        self, train_number, date, threshold_minutes, notify_target, message=None
    ):
        """Registra un avviso persistente per tutta la durata del viaggio:
        il numero di minuti impostato viene usato come "passo" ricorrente,
        non come soglia singola — notifica ogni volta che il ritardo
        attraversa un multiplo di quel valore (15, 30, 45, 60... sia
        salendo che scendendo), finché il treno non risulta arrivato o
        l'avviso non viene annullato manualmente. Se il treno non è già
        monitorato, lo aggiunge da solo. Persistito su disco, sopravvive
        ai riavvii di Home Assistant.

        notify_target è l'entity_id di un'entità del dominio "notify"
        (es. "notify.mobile_app_iphone_di_paolo").
        """
        train_number = str(train_number).strip()
        date = str(date).strip()
        key = f"{train_number}_{date}"

        self._delay_watches[key] = {
            "threshold": threshold_minutes,
            "notify_target": notify_target,
            "message": message,
            "level": 0,  # quanti multipli della soglia sono già stati superati
        }
        _LOGGER.info(
            "Avviso di ritardo impostato per il treno %s (%s): passo %s min, "
            "notifica a %s",
            train_number, date, threshold_minutes, notify_target,
        )

        if key not in self.coordinators:
            await self.async_add_train(train_number, date)  # salva già trains+watches
        else:
            # Il treno è già monitorato: valutiamo subito lo stato attuale
            # invece di aspettare il prossimo ciclo di polling.
            self._check_delay_watch(key)
        self._sync_coordinator_watch(key)
        await self.async_save()

    async def async_cancel_delay_watch(self, train_number, date):
        key = f"{train_number}_{date}"
        removed = self._delay_watches.pop(key, None)
        if removed:
            _LOGGER.info("Avviso di ritardo annullato per il treno %s", key)
        self._sync_coordinator_watch(key)
        await self.async_save()

    def _sync_coordinator_watch(self, key):
        """Riflette lo stato attuale dell'avviso sul coordinator, e forza
        un aggiornamento immediato dell'entità (senza aspettare il
        prossimo polling) così la card Lovelace lo vede subito."""
        coordinator = self.coordinators.get(key)
        if coordinator is None:
            return
        watch = self._delay_watches.get(key)
        if watch:
            coordinator.delay_watch = {
                "threshold": watch["threshold"],
                "notify_target": watch["notify_target"],
                "level": watch["level"],
            }
        else:
            coordinator.delay_watch = None
        coordinator.async_update_listeners()

    def _check_delay_watch(self, key):
        watch = self._delay_watches.get(key)
        if not watch:
            return
        coordinator = self.coordinators.get(key)
        if coordinator is None:
            return
        data = coordinator.data or {}

        if data.get("arrivato"):
            # Viaggio concluso: l'avviso si disattiva da solo.
            _LOGGER.info(
                "Il treno %s è arrivato: disattivo l'avviso di ritardo", key
            )
            self.hass.async_create_task(
                self.async_cancel_delay_watch(coordinator.train_number, coordinator.date)
            )
            return

        delay = data.get("ritardo")
        if delay is None:
            return
        try:
            delay = int(delay)
        except (TypeError, ValueError):
            return

        step = watch["threshold"]
        new_level = max(0, delay) // step
        old_level = watch["level"]
        if new_level == old_level:
            return  # nessun multiplo della soglia attraversato, non notificare

        watch["level"] = new_level
        if watch["message"]:
            message = watch["message"]
        elif new_level > old_level:
            message = (
                f"Il treno {coordinator.train_number} ha accumulato "
                f"{delay} minuti di ritardo"
            )
        else:
            message = (
                f"Il treno {coordinator.train_number} è sceso a "
                f"{delay} minuti di ritardo"
            )

        _LOGGER.info(
            "Multiplo della soglia attraversato per il treno %s (ora %s min, "
            "livello %s→%s): invio notifica a %s",
            key, delay, old_level, new_level, watch["notify_target"],
        )
        self.hass.async_create_task(
            self.hass.services.async_call(
                "notify",
                "send_message",
                {
                    "entity_id": watch["notify_target"],
                    "message": message,
                    "title": "Ritardo treno",
                },
                blocking=False,
            )
        )
        self._sync_coordinator_watch(key)
        self.hass.async_create_task(self.async_save())

    async def async_load(self):
        """Ricrea i coordinator per i treni salvati in precedenza, e
        ripristina gli eventuali avvisi di ritardo attivi, rivalutandoli
        subito contro i dati reali (nel caso il ritardo sia cambiato
        mentre Home Assistant era spento)."""
        stored = await self.store.async_load() or {}
        for item in stored.get("trains", []):
            await self._async_create_coordinator(
                item["train_number"], item["date"], notify=False
            )

        self._delay_watches = stored.get("watches", {}) or {}
        for key in list(self._delay_watches.keys()):
            self._check_delay_watch(key)
            self._sync_coordinator_watch(key)

    async def async_save(self):
        trains = [
            {"train_number": c.train_number, "date": c.date}
            for c in self.coordinators.values()
        ]
        await self.store.async_save({"trains": trains, "watches": self._delay_watches})

    def register_entity_platform(self, async_add_entities, entity_factory):
        """Chiamato da sensor.py: collega il manager alla piattaforma sensori."""
        self._async_add_entities = async_add_entities
        self._entity_factory = entity_factory
        if self.coordinators:
            async_add_entities([entity_factory(c) for c in self.coordinators.values()])

    async def _async_create_coordinator(self, train_number, date, notify):
        key = f"{train_number}_{date}"
        if key in self.coordinators:
            return self.coordinators[key]

        coordinator = MonitorTreniCoordinator(
            self.hass, train_number, date, self.scan_interval
        )
        self.coordinators[key] = coordinator
        coordinator.async_add_listener(self._make_update_listener(key))

        # Primo aggiornamento sempre sincrono, come nella versione
        # originaria: il treno appare già con i dati corretti invece che
        # "non disponibile" fino al prossimo ciclo di polling. La card
        # copre l'attesa mostrando "Aggiungo…" sul pulsante.
        await self._async_first_refresh(coordinator)

        if notify and self._async_add_entities and self._entity_factory:
            self._async_add_entities([self._entity_factory(coordinator)])

        return coordinator

    async def _async_first_refresh(self, coordinator):
        # async_config_entry_first_refresh() nelle versioni recenti di Home
        # Assistant richiede un coordinator associato a una config entry
        # (lancia ConfigEntryError altrimenti) - non è il nostro caso, dato
        # che ogni treno non è una config entry a sé. async_refresh() fa lo
        # stesso lavoro senza quel vincolo, ed è il metodo corretto per un
        # aggiornamento "al volo" fuori dal setup di una config entry.
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.warning(
                "Primo aggiornamento fallito per il treno %s (%s): %s. "
                "Riproverò al prossimo ciclo di polling.",
                coordinator.train_number, coordinator.date, coordinator.last_exception,
            )

    async def async_add_train(self, train_number, date):
        train_number = str(train_number).strip()
        date = str(date).strip()
        key = f"{train_number}_{date}"
        if key in self.coordinators:
            _LOGGER.info("Il treno %s del %s è già monitorato", train_number, date)
            return
        await self._async_create_coordinator(train_number, date, notify=True)
        await self.async_save()

    async def async_remove_train(self, train_number, date):
        train_number = str(train_number).strip()
        date = str(date).strip()
        key = f"{train_number}_{date}"

        coordinator = self.coordinators.pop(key, None)
        if coordinator is None:
            _LOGGER.warning("Treno %s del %s non era monitorato", train_number, date)
            return

        self._cancel_auto_remove(key)
        self._delay_watches.pop(key, None)

        if hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()

        entity = self.entities.pop(key, None)
        if entity is not None:
            await entity.async_remove(force_remove=True)

        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{train_number}_{date}_delay"
        )
        if entity_id:
            registry.async_remove(entity_id)

        await self.async_save()

    def update_scan_interval(self, minutes):
        if not minutes:
            return
        for coordinator in self.coordinators.values():
            coordinator.set_scan_interval(minutes)

    async def async_unload(self):
        for key in list(self._auto_remove_unsub.keys()):
            self._cancel_auto_remove(key)
        for coordinator in self.coordinators.values():
            if hasattr(coordinator, "async_shutdown"):
                await coordinator.async_shutdown()
