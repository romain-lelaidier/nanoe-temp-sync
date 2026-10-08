import logging
import logging.config
import yaml
from datetime import datetime
from pathlib import Path

def setup_logger(log_level="DEBUG", config_file=f"{Path(__file__).parent}/config/logging.yaml", name: str = None):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_text = f.read()
        config_text = config_text.replace('%(date)s', today)
        config = yaml.safe_load(config_text)

        if log_level and "root" in config:
            config["root"]["level"] = log_level

        Path('logs').mkdir(exist_ok=True)
        logging.config.dictConfig(config)

        logger = logging.getLogger(name) if name else logging.getLogger()
        logger.info(f"Log files created with date: {today}")
        return logger

    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(name) if name else logging.getLogger()
        logger.error(f"Failed to load logging configuration: {e}")
        return logger

def get_logger(name: str = None):
    return logging.getLogger(name)