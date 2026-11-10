import pandas as pd
import os
from datetime import datetime

from utils.config import ServiceConfig, yaml_load_config
from utils.logger import setup_logger, get_logger
from utils.sql import get_sql_fetcher
from utils.kobo import get_kobo_fetcher
from utils.airtable.sync_engine import get_airtable_sync_engine
from utils.airtable.config import get_airtable_config
from utils.post_processors import post_process

FETCHERS = {
    "sql": lambda: get_sql_fetcher(),
    "kobo": lambda: get_kobo_fetcher(),
}

def export_as_csv(key: str, df: pd.DataFrame):
    config = ServiceConfig()
    if config.EXPORT_DIR is None or config.EXPORT_DIR == '':
        return
    if not os.path.exists(config.EXPORT_DIR):
        os.mkdir(config.EXPORT_DIR)
    folder = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    path = f"{config.EXPORT_DIR}/{folder}"
    logger.info("Exporting to csv (%s)", path)
    if not os.path.exists(path):
        os.mkdir(path)
    df.to_csv(f"{path}/{key}.csv")

def run_airtable_full_sync():
    logger = get_logger(__name__)
    errors = {}
    airtable_config = get_airtable_config()
    airtable_sync_engine = get_airtable_sync_engine()

    for source in yaml_load_config("sources"):
        s_name, s_type = source.get("name"), source.get("type")
        table_key = source.get("airtable_key", s_name)

        if not s_name or not s_type:
            logger.warning("Source (%s) has missing name or type. Skipping", source)
            continue
        if not source.get("active", True):
            logger.info("Skipping source '%s' (active: false)", s_name)
            continue
        if s_type not in FETCHERS:
            logger.warning("Source '%s': unknown type '%s'. Skipping", s_name, s_type)
            continue
        if table_key not in airtable_config.tables:
            logger.warning("Source '%s': unknown Airtable table configuration '%s'. Skipping", s_name, table_key)

        try:
            logger.info("Fetching source '%s' (type: '%s')", s_name, s_type)
            data = post_process(s_name, FETCHERS[s_type]().fetch(source))
            export_as_csv(s_name, data)
            logger.info("Uploading to Airtable: table '%s' (%i rows)", table_key, len(data))
            airtable_sync_engine.sync_dataframe(table_key, data, source.get("airtable_options"))
        except Exception:
            logger.exception("Source '%s' failed", s_name)  # keeps traceback
            errors[s_name] = True

if __name__ == "__main__":
    # processor lancé par command-line directement
    config = ServiceConfig()
    setup_logger(log_level=config.LOG_LEVEL, config_file=config.LOG_CONFIG_FILE)
    logger = get_logger(__name__)
    run_airtable_full_sync()
