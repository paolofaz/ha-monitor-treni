import logging
from datetime import date as date_cls

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import (
    CONF_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_ADD_TRAIN,
    SERVICE_CANCEL_DELAY_WATCH,
    SERVICE_NOTIFY_ON_DELAY,
    SERVICE_REMOVE_TRAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .manager import MonitorTreniManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

ADD_TRAIN_SCHEMA = vol.Schema(
    {
        vol.Required("train_number"): cv.string,
        vol.Optional("date"): cv.string,
    }
)
REMOVE_TRAIN_SCHEMA = vol.Schema(
    {
        vol.Required("train_number"): cv.string,
        vol.Required("date"): cv.string,
    }
)
NOTIFY_ON_DELAY_SCHEMA = vol.Schema(
    {
        vol.Required("train_number"): cv.string,
        vol.Optional("date"): cv.string,
        vol.Required("threshold_minutes"): vol.Coerce(int),
        vol.Required("notify_target"): cv.string,
        vol.Optional("message"): cv.string,
    }
)
CANCEL_DELAY_WATCH_SCHEMA = vol.Schema(
    {
        vol.Required("train_number"): cv.string,
        vol.Required("date"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = MonitorTreniManager(hass, entry)
    await manager.async_load()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    await _async_register_frontend(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        manager: MonitorTreniManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_unload()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TRAIN)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TRAIN)
            hass.services.async_remove(DOMAIN, SERVICE_NOTIFY_ON_DELAY)
            hass.services.async_remove(DOMAIN, SERVICE_CANCEL_DELAY_WATCH)
    return ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Chiamato da Home Assistant solo quando l'utente ELIMINA l'integrazione
    (non ad ogni riavvio/reload). Puliamo qui lo storage dei treni che ci
    eravamo creati noi per questa entry: HA non lo sa gestire da solo,
    altrimenti resta come file orfano in .storage per sempre.
    """
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    try:
        await store.async_remove()
    except Exception:  # noqa: BLE001 - il file potrebbe già non esistere
        pass


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    manager: MonitorTreniManager = hass.data[DOMAIN][entry.entry_id]
    manager.update_scan_interval(entry.options.get(CONF_SCAN_INTERVAL))
    manager.update_auto_remove_settings()


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_TRAIN):
        return

    async def _add_train(call: ServiceCall) -> None:
        train_number = str(call.data["train_number"]).strip()
        service_date = call.data.get("date") or date_cls.today().isoformat()
        for manager in hass.data.get(DOMAIN, {}).values():
            await manager.async_add_train(train_number, service_date)

    async def _remove_train(call: ServiceCall) -> None:
        train_number = str(call.data["train_number"]).strip()
        service_date = str(call.data["date"]).strip()
        for manager in hass.data.get(DOMAIN, {}).values():
            await manager.async_remove_train(train_number, service_date)

    async def _notify_on_delay(call: ServiceCall) -> None:
        train_number = str(call.data["train_number"]).strip()
        service_date = call.data.get("date") or date_cls.today().isoformat()
        threshold = call.data["threshold_minutes"]
        notify_target = str(call.data["notify_target"]).strip()
        message = call.data.get("message")
        for manager in hass.data.get(DOMAIN, {}).values():
            await manager.async_set_delay_watch(
                train_number, service_date, threshold, notify_target, message
            )

    async def _cancel_delay_watch(call: ServiceCall) -> None:
        train_number = str(call.data["train_number"]).strip()
        service_date = str(call.data["date"]).strip()
        for manager in hass.data.get(DOMAIN, {}).values():
            await manager.async_cancel_delay_watch(train_number, service_date)

    hass.services.async_register(DOMAIN, SERVICE_ADD_TRAIN, _add_train, schema=ADD_TRAIN_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_TRAIN, _remove_train, schema=REMOVE_TRAIN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NOTIFY_ON_DELAY, _notify_on_delay, schema=NOTIFY_ON_DELAY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_DELAY_WATCH, _cancel_delay_watch, schema=CANCEL_DELAY_WATCH_SCHEMA
    )


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Registra (o aggiorna) la risorsa nella collezione Lovelace vera e
    propria: la stessa che vedi in Impostazioni → Dashboard → Risorse.

    Funziona solo se i dashboard sono in modalità "storage" (quella di
    default, gestita da UI). In modalità YAML la collezione non è
    scrivibile da codice: in quel caso ritorna False e va aggiunta a mano.
    """
    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        return False

    resources = (
        lovelace_data.get("resources")
        if isinstance(lovelace_data, dict)
        else getattr(lovelace_data, "resources", None)
    )
    if resources is None:
        return False

    try:
        await resources.async_load()
    except Exception:  # noqa: BLE001 - può essere già caricata, non è un problema
        pass

    if not hasattr(resources, "async_create_item"):
        # Modalità YAML: la collezione è read-only.
        return False

    base_url = url.split("?")[0]
    existing = None
    for item in resources.async_items():
        if str(item.get("url", "")).split("?")[0] == base_url:
            existing = item
            break

    if existing is None:
        await resources.async_create_item({"res_type": "module", "url": url})
    elif existing.get("url") != url:
        await resources.async_update_item(existing["id"], {"res_type": "module", "url": url})

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve la card Lovelace e la registra automaticamente, senza che
    l'utente debba aggiungere manualmente una risorsa Lovelace."""
    flag = f"{DOMAIN}_frontend_registered"
    if hass.data.get(flag):
        return
    hass.data[flag] = True

    www_path = hass.config.path("custom_components", DOMAIN, "www")
    url_base = "/monitor_treni_files"
    js_url = f"{url_base}/monitor-treni-card.js?v=6"

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(url_base, www_path, False)]
        )
    except Exception:  # noqa: BLE001 - fallback per core HA più datati
        try:
            hass.http.register_static_path(url_base, www_path, cache_headers=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Impossibile registrare i file statici della card: %s", err)

    registered = False
    try:
        registered = await _async_register_lovelace_resource(hass, js_url)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Errore registrando la risorsa Lovelace di Monitor Treni")
        registered = False

    if not registered:
        try:
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, js_url)
            registered = True
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Impossibile registrare automaticamente monitor-treni-card.js")

    if not registered:
        try:
            from homeassistant.components import persistent_notification

            persistent_notification.async_create(
                hass,
                (
                    "Non sono riuscito a registrare automaticamente la card "
                    "Monitor Treni (probabilmente i dashboard sono in "
                    "modalità YAML).\n\n"
                    "Aggiungila manualmente da Impostazioni → Dashboard → "
                    "Risorse, come modulo JavaScript, con URL:\n\n"
                    f"`{js_url}`"
                ),
                title="Monitor Treni: card non registrata",
                notification_id=f"{DOMAIN}_frontend_registration_failed",
            )
        except Exception:  # noqa: BLE001
            pass
