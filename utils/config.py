from datetime import datetime
import yaml
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from utils.logger import setup_logger, get_logger

class ServiceConfig(BaseSettings):
    """
    Application service configuration loaded from environment variables or defaults.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # Environment configuration
    ENV: str = Field(default="dev", description="Environment: dev, staging, prod")
    LOG_LEVEL: str = Field(default="DEBUG", description="Logging level")
    LOG_CONFIG_FILE: str = Field(
        default=f"{Path(__file__).parent}/config/logging.yaml",
        description="Path to logging config file"
    )

    EXPORT_DIR: str = Field(default="", description="temporary exports")

    # Airtable configuration
    AIRTABLE_TOKEN: str = Field(default=None, description="Airtable app token")
    # KOBO configuration
    KOBO_TOKEN: str = Field(default=None, description="KoBo app token")
    # Dropbox configuration
    # "select_user" : "dbmid:AACCI55eCmRrwEkGkMsNoBNOUJfzLj1Qk4s",
    # "app_key" : "k734ea5bmftlb51",
    # "app_secret" : "a63viqshousw1jj",
    # "refresh_token" : "oMGqi7vgOnoAAAAAAAAAAQd61Hjlxtg7UOrEv4CjhJGUO-wpvCTpvs8_6PVgE_zE"
    # SQL configuration
    DB_SSH_HOST: str = Field(default=None, description="Accès SSH SI : adresse IP")
    DB_SSH_PORT: int = Field(default=22, description="Accès SSH SI : port SSH")
    DB_SSH_USERNAME: str = Field(default=None, description="Accès SSH SI : username")
    DB_SSH_PASSWORD: str = Field(default=None, description="Accès SSH SI : password")
    DB_SQL_HOST: str = Field(default="localhost", description="SI")
    DB_SQL_PORT: int = Field(default=5432, description="SI")
    DB_SQL_NAME: str = Field(default=None, description="SI")
    DB_SQL_USERNAME: str = Field(default=None, description="SI")
    DB_SQL_PASSWORD: str = Field(default=None, description="SI")

    QDRANT_HOST: Optional[str] = Field(default=None)

    @field_validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL: {v}. Must be one of {valid_levels}")
        return v


yaml_configs = {}
def yaml_load_config(name: str) -> dict:
    global yaml_configs
    logger = get_logger(__name__)
    if name in yaml_configs: return yaml_configs[name]
    config_file = f"./config/{name}.yaml"
    try:
        logger.debug("Parsing configuration file: %s", config_file)
        today = datetime.now().strftime('%Y-%m-%d')
        with open(config_file, 'r', encoding='utf-8') as f:
            config_text = f.read()
        config_text = config_text.replace('%(date)s', today)
        config = yaml.safe_load(config_text)
        yaml_configs[name] = config
        return config
    except Exception as e:
        logger.error("Could not parse configuration file %s (%s)", config_file, str(e))
