import schedule
import time

from utils.config import ServiceConfig
from utils.logger import setup_logger, get_logger
from processor import run_airtable_full_sync


if __name__ == "__main__":
    config = ServiceConfig()
    setup_logger(log_level=config.LOG_LEVEL, config_file=config.LOG_CONFIG_FILE)
    logger = get_logger(__name__)

    schedule.every(30).minutes.do(run_airtable_full_sync)

    run_airtable_full_sync()
    while True:
        schedule.run_pending()
        time.sleep(1)
