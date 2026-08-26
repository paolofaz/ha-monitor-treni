from datetime import datetime
import re

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def extract_category(value):
    if not value:
        return None
    match = re.search(r"^\s*([A-Za-z]+)", value)
    return match.group(1).upper() if match else None


def first(data, *names):
    for name in names:
        value = data.get(name)
        if value is not None and value != "":
            return value
    return None


def millis_to_local(value):
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000).isoformat(timespec="minutes")
    except (TypeError, ValueError, OSError):
        return None


def last_completed_stop(stops):
    completed = [
        s for s in stops or []
        if s.get("arrivoReale") is not None or s.get("partenzaReale") is not None
    ]
    return completed[-1] if completed else None


def next_stop(stops):
    for stop in stops or []:
        if stop.get("arrivoReale") is None and stop.get("partenzaReale") is None:
            return stop
    return None


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    manager.register_entity_platform(async_add_entities, TrainDelaySensor)


class TrainDelaySensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:train"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator)
        safe_date = coordinator.date.replace("-", "")
        self._attr_unique_id = f"{coordinator.train_number}_{coordinator.date}_delay"
        # Nome pulito impostato direttamente sull'entità (niente device: un
        # device per treno con una sola entità dentro restava "orfano e
        # vuoto" nel registro dispositivi quando il treno veniva rimosso).
        self._attr_name = f"Treno {coordinator.train_number} · {coordinator.date}"
        # entity_id deterministico e stabile: comodo per riferirsi al
        # sensore da automazioni/dashboard scritte a mano. La card
        # Lovelace, invece, riconosce i treni dagli attributi
        # NumeroTreno/Data e non dipende da questo formato.
        self.entity_id = f"sensor.treno_{coordinator.train_number}_{safe_date}_ritardo"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        for manager in self.hass.data.get(DOMAIN, {}).values():
            if self.coordinator.unique_key in manager.coordinators:
                manager.entities[self.coordinator.unique_key] = self
                break

    async def async_will_remove_from_hass(self):
        for manager in self.hass.data.get(DOMAIN, {}).values():
            manager.entities.pop(self.coordinator.unique_key, None)
        await super().async_will_remove_from_hass()

    @property
    def icon(self):
        value = self.native_value
        if value is not None and value > 5:
            return "mdi:clock-alert-outline"
        return "mdi:train"

    @property
    def native_value(self):
        value = first(self.coordinator.data or {}, "ritardo")
        try:
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        stops = data.get("fermate", [])
        last = last_completed_stop(stops)
        upcoming = next_stop(stops)
        category = extract_category(data.get("compNumeroTreno")) or first(data, "categoria")
        attrs = {
            "NumeroTreno": first(data, "numeroTreno") or self.coordinator.train_number,
            "Data": self.coordinator.date,
            "Categoria": category,
            "StazionePartenza": first(data, "origine"),
            "StazioneArrivo": first(data, "destinazione"),
            "UltimoRilevamento": first(data, "stazioneUltimoRilevamento"),
            "OraUltimoRilevamento": first(data, "compOraUltimoRilevamento"),
            "UltimaFermata": last.get("stazione") if last else None,
            "OraUltimaFermata": millis_to_local(
                last.get("partenzaReale") if last and last.get("partenzaReale") is not None
                else last.get("arrivoReale") if last else None
            ),
            "ProssimaFermata": upcoming.get("stazione") if upcoming else None,
            "ArrivoPrevistoProssimaFermata": millis_to_local(upcoming.get("arrivo_teorico")) if upcoming else None,
            "PartenzaPrevistaProssimaFermata": millis_to_local(upcoming.get("partenza_teorica")) if upcoming else None,
            "Ritardo": first(data, "ritardo"),
            "PartenzaPrevista": first(data, "compOrarioPartenzaZero"),
            "PartenzaEffettiva": first(data, "compOrarioPartenzaZeroEffettivo"),
            "ArrivoPrevisto": first(data, "compOrarioArrivoZero"),
            "ArrivoStimato": first(data, "compOrarioArrivoZeroEffettivo"),
            "Stato": (
                "arrivato" if data.get("arrivato")
                else "in_stazione" if data.get("inStazione")
                else "non_partito" if data.get("nonPartito")
                else "in_viaggio" if data.get("circolante")
                else "non_disponibile"
            ),
        }
        watch = getattr(self.coordinator, "delay_watch", None)
        if watch:
            attrs["AvvisoRitardoPasso"] = watch["threshold"]
            attrs["AvvisoRitardoTarget"] = watch["notify_target"]
            attrs["AvvisoRitardoSogliaAttuale"] = watch["level"] * watch["threshold"]
        return {k: v for k, v in attrs.items() if v is not None and v != ""}
