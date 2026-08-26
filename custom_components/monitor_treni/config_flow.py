import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_REMOVE_HOURS,
    CONF_SCAN_INTERVAL,
    DEFAULT_AUTO_REMOVE_HOURS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_AUTO_REMOVE_HOURS,
    MAX_SCAN_INTERVAL,
    MIN_AUTO_REMOVE_HOURS,
    MIN_SCAN_INTERVAL,
)

INTEGRATION_TITLE = "Monitor Treni"


def _scan_interval_selector():
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            mode=selector.NumberSelectorMode.SLIDER,
            unit_of_measurement="min",
        )
    )


def _auto_remove_selector():
    # mode BOX (non slider): con un intervallo 1-25 è più comodo digitare
    # il valore esatto, specialmente per centrare il 25 ("mai").
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_AUTO_REMOVE_HOURS,
            max=MAX_AUTO_REMOVE_HOURS,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="h",
        )
    )


def _shared_schema(scan_interval_default, auto_remove_default):
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL, default=scan_interval_default
            ): _scan_interval_selector(),
            vol.Required(
                CONF_AUTO_REMOVE_HOURS, default=auto_remove_default
            ): _auto_remove_selector(),
        }
    )


class MonitorTreniConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow a istanza singola: i treni si gestiscono dalla card, non da qui."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=INTEGRATION_TITLE,
                data={},
                options={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_AUTO_REMOVE_HOURS: user_input[CONF_AUTO_REMOVE_HOURS],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_shared_schema(DEFAULT_SCAN_INTERVAL, DEFAULT_AUTO_REMOVE_HOURS),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MonitorTreniOptionsFlow()


class MonitorTreniOptionsFlow(config_entries.OptionsFlow):
    """Nota: NON sovrascrivere __init__ per salvare config_entry.

    Nelle versioni recenti di Home Assistant, config_entry è già esposto
    automaticamente dalla classe base come proprietà; assegnarlo a mano qui
    va in conflitto con quella proprietà e causa un 500 Internal Server
    Error quando si apre il flusso di opzioni.
    """

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_auto_remove = self.config_entry.options.get(
            CONF_AUTO_REMOVE_HOURS, DEFAULT_AUTO_REMOVE_HOURS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_shared_schema(current_scan, current_auto_remove),
        )
