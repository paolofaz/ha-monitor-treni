from datetime import timedelta
import logging
import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)


class MonitorTreniCoordinator(DataUpdateCoordinator):
    """Recupera i dati di un singolo treno da ViaggiaTreno."""

    def __init__(self, hass, train_number, date, scan_interval_minutes):
        self.train_number = train_number
        self.date = date
        self.identity = None
        # Impostato/svuotato dal manager quando si attiva/annulla un
        # avviso di ritardo (servizio notify_on_delay); letto da sensor.py
        # per esporlo come attributo e farlo vedere alla card Lovelace.
        self.delay_watch = None
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"ViaggiaTreno {train_number} ({date})",
            update_interval=timedelta(minutes=scan_interval_minutes),
        )

    @property
    def unique_key(self):
        return f"{self.train_number}_{self.date}"

    def set_scan_interval(self, minutes):
        """Aggiorna l'intervallo di polling (applicato dal prossimo ciclo)."""
        self.update_interval = timedelta(minutes=minutes)

    async def _resolve(self, session):
        async with session.get(
            f"{BASE_URL}/cercaNumeroTrenoTrenoAutocomplete/{self.train_number}"
        ) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"ViaggiaTreno HTTP {resp.status}")
            text = await resp.text()

        wanted = f"{self.date[8:10]}/{self.date[5:7]}/{self.date[2:4]}"
        for raw in text.splitlines():
            if "|" not in raw:
                continue
            label, value = raw.strip().split("|", 1)
            if wanted not in label:
                continue
            parts = value.strip().split("-")
            if len(parts) == 3 and parts[0] == self.train_number:
                self.identity = (parts[1], parts[2])
                return self.identity
        raise UpdateFailed(f"Treno {self.train_number} non trovato per {self.date}")

    async def _async_update_data(self):
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/plain, */*",
            },
        ) as session:
            station, millis = self.identity or await self._resolve(session)
            url = f"{BASE_URL}/andamentoTreno/{station}/{self.train_number}/{millis}"
            async with session.get(url) as resp:
                if resp.status == 204:
                    raise UpdateFailed("ViaggiaTreno: nessun dato disponibile")
                if resp.status != 200:
                    raise UpdateFailed(f"ViaggiaTreno HTTP {resp.status}")
                try:
                    data = await resp.json(content_type=None)
                except Exception as err:
                    raise UpdateFailed("Risposta JSON non valida") from err

            if not isinstance(data, dict):
                raise UpdateFailed("Formato andamentoTreno inatteso")
            _LOGGER.debug("Risposta ViaggiaTreno treno %s: %s", self.train_number, data)
            return data
