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
from utils.addons import addon, get_addons

def export_as_csv(key: str, df: pd.DataFrame):
    config = ServiceConfig()
    if config.EXPORT_DIR is None or config.EXPORT_DIR == '':
        return
    if not os.path.exists(config.EXPORT_DIR):
        os.mkdir(config.EXPORT_DIR)
    folder = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    path = f"{config.EXPORT_DIR}/{folder}"
    if not os.path.exists(path):
        os.mkdir(path)
    df.to_csv(f"{path}/{key}.csv")

FETCHERS = {
    "sql": lambda: get_sql_fetcher(),
    "kobo": lambda: get_kobo_fetcher(),
}

data_to_export = {}

@addon("clients")
def addon_clients() -> dict:
    df_prospects = data_to_export["prospect"]["data"] if "prospect" in data_to_export else FETCHERS["sql"]().fetch({ "sql_file": "addons/clients.sql" })
    clients_mapper = {}
    for _, row in df_prospects.iterrows():
        n = row.loc["n"]
        n_client = row.loc["n_client"]
        if not pd.isnull(n) and not pd.isnull(n_client):
            clients_mapper[str(int(n_client))] = str(int(n))
    return clients_mapper

def run_airtable_full_sync():
    global data_to_export

    logger = get_logger(__name__)
    errors = {}
    airtable_config = get_airtable_config()
    airtable_sync_engine = get_airtable_sync_engine()

    # 1. téléchargement et traitement
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
            data = FETCHERS[s_type]().fetch(source)
            data = post_process(s_name, data, get_addons(source))
            data_to_export[s_name] = {
                "table_key": table_key,
                "airtable_options": source.get("airtable_options"),
                "data": data
            }
        except Exception:
            logger.exception("Source '%s' failed", s_name)  # keeps traceback
            errors[s_name] = True

    # 2. export csv + airtable
    for s_name, entry in data_to_export.items():
        data = entry["data"]
        table_key = entry["table_key"]
        try:
            export_as_csv(s_name, data)
            logger.info("Uploading to Airtable: table '%s' (%i rows)", table_key, len(data))
            airtable_sync_engine.sync_dataframe(table_key, data, entry["airtable_options"])
        except Exception:
            logger.exception("Synchronization '%s' failed", s_name)
            errors[s_name] = True

if __name__ == "__main__":
    # processor lancé par command-line directement
    config = ServiceConfig()
    setup_logger(log_level=config.LOG_LEVEL, config_file=config.LOG_CONFIG_FILE)
    logger = get_logger(__name__)
    run_airtable_full_sync()
