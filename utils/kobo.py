import os, requests
import pandas as pd
from pathlib import Path
from utils.config import ServiceConfig

class KoboFetcher:
    PAGE_SIZE = 3000

    def fetch(self, source: dict) -> pd.DataFrame:
        if "csv_folder" in source: return self.fetch_from_csv(source["csv_folder"])

        # return pd.read_csv("./exports/2026-11-09_11:44:03/enquetes-techniques.csv")

        config = ServiceConfig()
        token = getattr(config, source["token_env"])
        url = f"{source['server']}/api/v2/assets/{source['asset_uid']}/data/"
        headers = {"Authorization": f"Token {token}"}
        params = {"format": "json", "limit": self.PAGE_SIZE}

        rows = []
        with requests.Session() as s:
            while url:
                r = s.get(url, headers=headers, params=params, timeout=60)
                r.raise_for_status()
                payload = r.json()
                rows.extend(payload["results"])
                url = payload.get("next")
                params = None
        return pd.json_normalize(rows)

    def fetch_from_csv(self, csv_folder: str) -> pd.DataFrame:
        columns_mapper_file = open(f"{Path(__file__).parent.parent}/kobos/{csv_folder}/mapper.csv", "r").read()
        columns_mapper = {}
        for line in columns_mapper_file.split('\n'):
            c1, c2 = line.split(',')
            columns_mapper[c1] = c2
        df = pd.read_csv(f"{Path(__file__).parent.parent}/kobos/{csv_folder}/data.csv")
        new_columns = []
        for column in df.columns:
            new_columns.append(columns_mapper.get(column, column))
        df.columns = new_columns
        return df

kobo_fetcher = None
def get_kobo_fetcher() -> KoboFetcher:
    global kobo_fetcher
    if kobo_fetcher is None:
        kobo_fetcher = KoboFetcher()
    return kobo_fetcher
