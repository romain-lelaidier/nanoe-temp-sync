import numpy as np
import pandas as pd
import os
from datetime import datetime, date, timedelta

from utils.config import ServiceConfig, yaml_load_config
from utils.logger import setup_logger, get_logger
from utils.sql import get_sql_fetcher
from utils.kobo import get_kobo_fetcher
from utils.airtable.sync_engine import get_airtable_sync_engine
from utils.airtable.config import get_airtable_config
from utils.post_processors import post_process, reset_id_counter
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

@addon("tr")
def addon_tr() -> pd.DataFrame:
    def union_decalee_df(df):
        # Segments ]debut, fin] triés. Si un segment commence avant la fin du précédent (décalé), il est repoussé juste après lui, en conservant sa longueur.
        # Exemple : ]1,5] puis ]3,7] -> ]1,5] puis ]5,9]
        df = df.sort_values(["debut", "fin"])
        debuts, fins = [], []
        fin_prec = -float("inf")
        for d, f in zip(df["debut"], df["fin"]):
            d2 = max(int(d), fin_prec)
            fin_prec = d2 + (int(f) - int(d))
            debuts.append(d2)
            fins.append(fin_prec)
        return pd.DataFrame({"debut": debuts, "fin": fins})
    def longueur_intersection(df, a, b):
        """
        Arguments:
            df : DataFrame avec colonnes debut, fin (segments ]debut, fin], sans intersection).
            a, b : bornes du segment requête ]a, b].
        Retourne la longueur totale de l'intersection des segments de df avec ]a, b]."""
        out = df[(df["debut"] < b) & (df["fin"] > a)].copy()
        out["debut"] = out["debut"].clip(lower=a)
        out["fin"] = out["fin"].clip(upper=b)
        return (out["fin"] - out["debut"]).sum()

    ajd = (date.today() - date(1970, 1, 1)).days
    plages = {
        "tr_t0": (ajd-92*(0+1), ajd-92*0),  # trimestre T-0
        "tr_t1": (ajd-92*(1+1), ajd-92*1),  # trimestre T-1
        "tr_t2": (ajd-92*(2+1), ajd-92*2),  # trimestre T-2
        "tr_t3": (ajd-92*(3+1), ajd-92*3),  # trimestre T-3
        "tr_m0": (ajd-30*(0+1), ajd-30*0),  # mois M-0
        "tr_m1": (ajd-30*(1+1), ajd-30*1),  # mois M-1
        "tr_m2": (ajd-30*(2+1), ajd-30*2),  # mois M-2
        "tr_m3": (ajd-30*(3+1), ajd-30*3),  # mois M-3
    }

    transactions = FETCHERS["sql"]().fetch({ "sql_file": "addons/tr.sql" })
    df_c = pd.DataFrame([ { 'n': id_client } for id_client in transactions['id_client'].unique() ])
    for i, _ in df_c.iterrows():
        df_ct = transactions[transactions['id_client'] == df_c.loc[i, 'n']]
        if len(df_ct) > 0:
            df_ct = df_ct.sort_values(["debut", "fin"])
            derniere_transaction_debut = int(df_ct["debut"].iloc[-1])
            derniere_transaction_fin = int(df_ct["fin"].iloc[-1])
            df_c.loc[i, 'derniere_transaction_date'] = datetime(1970, 1, 1) + timedelta(derniere_transaction_debut)
            df_c.loc[i, 'derniere_transaction_duree_jours'] = derniere_transaction_fin - derniere_transaction_debut
            df_ct = union_decalee_df(df_ct)
            for key, (a, b) in plages.items():
                df_c.loc[i, key] = longueur_intersection(df_ct, a, b) / (b - a)
    return df_c

@addon("revenus")
def addon_revenus() -> pd.DataFrame:
    ajd = (date.today() - date(1970, 1, 1)).days
    transactions = FETCHERS["sql"]().fetch({ "sql_file": "addons/revenus.sql" })
    df_c = pd.DataFrame([ { 'n': id_client } for id_client in transactions['id_client'].unique() ])
    for i, _ in df_c.iterrows():
        df_ct = transactions[transactions['id_client'] == df_c.loc[i, 'n']]
        def revenus(a, b):
            return df_ct[(df_ct['debut'] > a) & (df_ct['debut'] <= b)]['montant'].sum()
        if len(df_ct) > 0:
            df_c.loc[i, "revenu_total"] = revenus(-np.inf, ajd)
            df_c.loc[i, "revenu_s0"]    = revenus(ajd-92*2, ajd-92*0)       # semestre S-0
            df_c.loc[i, "revenu_s1"]    = revenus(ajd-92*4, ajd-92*2)       # semestre S-1
            df_c.loc[i, "revenu_s2"]    = revenus(ajd-92*6, ajd-92*4)       # semestre S-2
            df_c.loc[i, "revenu_s3"]    = revenus(ajd-92*8, ajd-92*6)       # semestre S-3
            df_c.loc[i, "revenu_m0"]    = revenus(ajd-30*(0+1), ajd-30*0)   # mois M-0
            df_c.loc[i, "revenu_m1"]    = revenus(ajd-30*(1+1), ajd-30*1)   # mois M-1
            df_c.loc[i, "revenu_m2"]    = revenus(ajd-30*(2+1), ajd-30*2)   # mois M-2
            df_c.loc[i, "revenu_m3"]    = revenus(ajd-30*(3+1), ajd-30*3)   # mois M-2
            df_c.loc[i, "revenu_m12"]   = revenus(ajd-92*8-30, ajd-92*8)    # mois M-12
    return df_c


def run_airtable_full_sync():
    global data_to_export

    logger = get_logger(__name__)
    errors = {}
    airtable_config = get_airtable_config()
    airtable_sync_engine = get_airtable_sync_engine()
    reset_id_counter()

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
            continue

        # 2. export csv + airtable
        try:
            export_as_csv(s_name, data)
            logger.info("Uploading to Airtable: table '%s' (%i rows)", table_key, len(data))
            airtable_sync_engine.sync_dataframe(table_key, data, source.get("airtable_options"))
        except Exception:
            logger.exception("Synchronization '%s' failed", s_name)
            errors[s_name] = True
    
if __name__ == "__main__":
    # processor lancé par command-line directement
    config = ServiceConfig()
    setup_logger(log_level=config.LOG_LEVEL, config_file=config.LOG_CONFIG_FILE)
    logger = get_logger(__name__)
    run_airtable_full_sync()
