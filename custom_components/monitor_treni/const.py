DOMAIN = "monitor_treni"

CONF_TRAIN_NUMBER = "train_number"
CONF_DATE = "date"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_AUTO_REMOVE_HOURS = "auto_remove_hours"

DEFAULT_SCAN_INTERVAL = 2  # minuti
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 10

# Ore dopo l'arrivo prima della rimozione automatica del sensore.
# Il valore massimo (25) è usato come convenzione per "non rimuovere mai".
DEFAULT_AUTO_REMOVE_HOURS = 3
MIN_AUTO_REMOVE_HOURS = 1
MAX_AUTO_REMOVE_HOURS = 25
AUTO_REMOVE_NEVER = 25

BASE_URL = "http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_trains"

SERVICE_ADD_TRAIN = "add_train"
SERVICE_REMOVE_TRAIN = "remove_train"
SERVICE_NOTIFY_ON_DELAY = "notify_on_delay"
SERVICE_CANCEL_DELAY_WATCH = "cancel_delay_watch"
