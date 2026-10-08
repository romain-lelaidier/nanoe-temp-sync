import pandas as pd
import os
from datetime import datetime

from utils.config import ServiceConfig, yaml_load_config
from utils.logger import setup_logger, get_logger
from utils.sql import get_sql_fetcher
from utils.airtable.sync_engine import get_airtable_sync_engine
from utils.airtable.config import get_airtable_config


def fetch_all_external_data():
    logger = get_logger(__name__)
    try:
        sources_config = yaml_load_config("sources")
        data = {}
        for source in sources_config:
            s_name = source.get("name")
            s_type = source.get("type")
            s_active = source.get("active", True)
            if not s_active: continue

            if s_name is None or s_type is None:
                logger.warning("Source (%s) has missing name or type", str(source))
                continue

            logger.info(f"Fetching source '{s_name}' (type: '{s_type}')")

            if s_type == "sql":
                s_sql_file = source.get("sql_file")
                if s_sql_file is None:
                    logger.warning("Source %s (type: sql) has missing sql file", s_name)
                    continue
                data[s_name] = get_sql_fetcher().fetch(source)

        return data

    except Exception as e:
        logger.error("Could not fetch external data (%s)", str(e))


def export_as_csv(data: dict):
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
    for key, df in data.items():
        df.to_csv(f"{path}/{key}.csv")


def run_airtable_full_sync():
    logger = get_logger(__name__)
    try:
        data = fetch_all_external_data()
        export_as_csv(data)
        airtable_config = get_airtable_config()
        airtable_sync_engine = get_airtable_sync_engine()
        for table_key in airtable_config.tables:
            if table_key in data:
                logger.info("Uploading to Airtable: table '%s' (%i rows)", table_key, len(data[table_key]))
                # table = airtable_config.get_table(table_key)
                # print(table.get_fields())
                airtable_sync_engine.sync_dataframe(
                    table_key,
                    data[table_key],
                )

    except Exception as e:
        logger.error("Could not do full sync (%s)", str(e))

if __name__ == "__main__":
    # processor lancé par command-line directement
    config = ServiceConfig()
    setup_logger(log_level=config.LOG_LEVEL, config_file=config.LOG_CONFIG_FILE)
    logger = get_logger(__name__)
    run_airtable_full_sync()
