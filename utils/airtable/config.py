from pyairtable import Table
import pandas as pd
from utils.config import ServiceConfig, yaml_load_config
from utils.logger import get_logger

class AirtableTable:
    def __init__(self, airtable_token: str, base_id: str, obj: dict = {}):
        self.key = obj.get("key")
        self.id = obj.get("id")
        self.primary_key = obj.get("primary_key")
        self.table = Table(airtable_token, base_id, self.id)
        self.config = {}
        self._schema = None
        self._fields = obj.get("fields", [])

    def get_schema(self):
        if self._schema is None:
            self._schema = self.table.schema()
        return self._schema

    def get_primary_field(self):
        schema = self.get_schema()
        for field in schema.fields:
            if field.id == schema.primary_field_id:
                return field.name

    def get_field_config(self, name: str) -> dict:
        schema = self.get_schema()
        for field in schema.fields:
            if field.name == name:
                return field

    def convert_sql_fields_to_field_names(self, df: pd.Dataframe) -> pd.DataFrame:
        schema = self.get_schema()
        remapper = {}
        to_remove = []
        for col in df.columns:
            is_mapped = False
            for field in self._fields:
                id, key = field.split(':')
                if key == col:
                    for schema_field in schema.fields:
                        if schema_field.id == id:
                            remapper[col] = schema_field.name
                            is_mapped = True
            if not is_mapped:
                to_remove.append(col)

        if len(to_remove) > 0:
            get_logger(__name__).warning("SQL field conversion (%s): fields [%s] could not be matched", self.key, ','.join(to_remove))

        dfn = df.copy()
        dfn = dfn.drop(to_remove, axis=1)
        dfn = dfn.rename(columns=remapper)
        return dfn


class AirtableConfig:
    def __init__(self):
        config = ServiceConfig()
        _airtable_config = yaml_load_config("airtable")
        self.base_id = _airtable_config.get("base_id")
        self.tables = {}
        for table_config in _airtable_config.get("tables", []):
            table_key = table_config.get("key")
            if table_key is not None:
                self.tables[table_key] = AirtableTable(config.AIRTABLE_TOKEN, self.base_id, table_config)

    def get_table(self, table_key: str) -> AirtableTable:
        return self.tables.get(table_key)

_airtable_config_instance = None
def get_airtable_config():
    global _airtable_config_instance
    if _airtable_config_instance is None:
        _airtable_config_instance = AirtableConfig()
    return _airtable_config_instance