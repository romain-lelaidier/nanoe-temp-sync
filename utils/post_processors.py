import pandas as pd
from datetime import datetime
from pathlib import Path
import re

POST_PROCESSORS = {}

def post_processor(key_code: str):
    def deco(fn):
        POST_PROCESSORS[key_code] = fn
        return fn
    return deco

def remove_none(l: list[str]) -> list[str]:
    while None in l:
        l.remove(None)
    return l

def remap(df: pd.DataFrame, colname: str, mapper: dict, separator: str = None):
    if separator is None:
        df[colname] = df[colname].apply(lambda a: mapper.get(a, None))
    else:
        for i, _ in df.iterrows():
            v = df.loc[i, colname]
            if isinstance(v, float): continue
            vs = v.split(separator)
            nvs = remove_none(list(map(lambda a: mapper.get(a), vs)))
            df.loc[i, colname] = ','.join(list(map(lambda a: a.replace(',',''), nvs)))

def ouinon(df: pd.DataFrame, colnames: list[str]):
    def ouinonvalue(s: str) -> str:
        if isinstance(s, float): return s
        if isinstance(s, bool): return "oui" if s else "non"
        s = s.lower()
        if "oui" in s: return "oui"
        if "conforme" in s and "non" not in s: return "oui"
        return "non"
    for colname in colnames:
        if colname in df.columns:
            df[colname] = df[colname].apply(ouinonvalue)

def toint(df: pd.DataFrame, colname: str):
    if colname in df.columns:
        df[colname] = df[colname].astype("Int64")
def tofloat(df: pd.DataFrame, colname: str):
    if colname in df.columns:
        df[colname] = df[colname].astype("Float64")

def kobo_clean_and_map(df: pd.DataFrame, kobo_key: str) -> pd.DataFrame:
    mapper = open(f"{Path(__file__).parent.parent}/kobos/{kobo_key}/mapper.csv", "r").read()
    to_delete = list(df.columns)
    to_remap = {}
    for mapper_line in mapper.split('\n'):
        if ',' in mapper_line:
            kobo, clean = mapper_line.split(',')
            if clean != '' and kobo in to_delete:
                to_remap[kobo] = clean
                to_delete.remove(kobo)
    df.drop(columns=to_delete, inplace=True)
    df.columns = list(map(lambda c: to_remap[c], df.columns))
    return df

def kobo_parse_options(df: pd.DataFrame, kobo_key: str) -> pd.DataFrame:
    template = f"{Path(__file__).parent.parent}/kobos/{kobo_key}/template.xlsx"
    df_survey = pd.read_excel(template, "survey")
    df_choices = pd.read_excel(template, "choices")
    def find_column(nm):
        for col in df.columns:
            if col.split('/')[-1] == nm:
                return col
    def find_choices(group):
        options = {}
        for i, _ in df_choices.iterrows():
            if df_choices.loc[i, "list_name"] == group:
                options[df_choices.loc[i, "name"]] = df_choices.loc[i, "label::Français (fr)"]
        return options
    for i, _ in df_survey.iterrows():
        tp = df_survey.loc[i, "type"]
        nm = df_survey.loc[i, "name"]
        if "select_one" in tp or "select_multiple" in tp:
            nm_df = find_column(nm)
            if nm_df is not None:
                select_type, group = tp.split(' ')
                choices = find_choices(group)
                separator = " " if select_type == "select_multiple" else None
                remap(df, nm_df, choices, separator)
        elif tp == "geopoint":
            nm_df = find_column(nm)
            if nm_df is not None:
                for i, _ in df.iterrows():
                    g = df.loc[i, nm_df]
                    if isinstance(g, float): continue
                    gs = list(map(float, g.split(' ')))
                    for j in range(4):
                        geo_keyword = [ "Latitude", "Longitude", "Altitude", "Précision" ][ j ]
                        df.loc[i, nm_df + "_" + geo_keyword] = gs[j]
    return df

AGENT_MAPPER = {"Bernard": "467","Aimé": "601","Tonganjara": "424","Briel": "619","Anniel": "310","Nicolas": "308","Rama": "589","Angelico": "427","Selson": "624","Tiandray": "438","Romain": "646","Michelin": "439","Sebastien": "314","Arly": "238","Fernandel": "240","Orlando": "622","Chrisley": "592","Karim": "237","Dominique": "600","Barthelemy": "373","Noelson": "315","Flavien": "579","Asto": "604","Lady": "78","Christiano": "441","Ibrahim": "102","Yvon": "575","Sabin": "126","Stephan": "295","Dambel": "618","Elwafa": "593","Hanselme": "316","Pierre": "442","Pierrette": "306","Dieudonné": "321","Sébastien": "314","Ednique": "619","Pascal": "623","Kenny": "242","Roberto": "128","Test": "382","Jean Aimé": "601","Andriatody Jean Aimé": "601","Haja": "295","Elwafa, test": "593","Elwafa test": "593","Aina": "27","Hajalalaina": "587","Sammer": "509","Dullin": "239","Lucas": "119","Aïna": "27","Basilide": "586","Archille": "9","Asni": "518","Jean Cisco": "576","Sanda": "120","Fitiavana": "433","Leo": "495","Stéphan": "295","Anjaratiana": "508","Paul": "606","Jules": "480","Franco": "472","Oliva": "23","Velondrazana": "43","Roméo": "293","Theophile": "34","Stanislas": "313","Guilhem": "580","Arsène": "320","Louis": "309","Lancio": "307","Ferrari": "232","Tony": "305","Stève": "312","Lova": "28","Elodie": "311","Huberto": "296","François": "234"}

TEMPS_PANNE_MAPPER = {
    "1 à 3 jours": "1 à 3 jours",
    "3 à 7 jours": "3 à 7 jours", "3 jours à 1 semaine": "3 à 7 jours",
    "1 à 2 semaines": "1 à 2 semaines", "1 semaine à 2 semaines": "1 à 2 semaines",
    "2 semaines à 2 mois": "2 semaines à 2 mois",
    "plus de 2 mois": "plus de 2 mois", "Plus de 2 mois": "plus de 2 mois",
}

CAUSE_PANNE_MAPPER = {
    "Batterie": "batterie",
    "Contrôleur": "contrôleur",
    "Charge": "charge",
    "Autre": "autre",
    "Micro-Réseau": "micro-réseau",
    "Installations client": "installations client",
    "Problème de charge (Panneau": "charge",
    "Câble solaire": "câble solaire",
    "Régulateur)": None,
    "Probleme du controleur ( Energie épuisé": "contrôleur",
    "Suspend P )": None,
    "Problème de la batterie": "batterie",
    "Problème des installations du client": "installations client"
}

def process_enquetes_techniques_final(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["nr"] = df["nr"].astype("Int64").astype("string")
    remap(df, "orientation_panneau", {
        'Nord':'Nord','Sud':'Sud','Est':'Est','Ouest':'Ouest',
        'Nord-Ouest':'Nord-Ouest','Nord-Est':'Nord-Est','Sud-Est':'Sud-Est','Sud-Ouest':'Sud-Ouest',
        'Nord Ouest':'Nord-Ouest','Nord Est':'Nord-Est','Sud Est':'Sud-Est','Sud Ouest':'Sud-Ouest'
    })
    df["agent_name"] = df["agent"]
    remap(df, "agent", AGENT_MAPPER)
    df["agent"] = df["agent"].astype("Int64").astype("string")
    remap(df, "temps_panne", TEMPS_PANNE_MAPPER)
    remap(df, "causes_panne", CAUSE_PANNE_MAPPER, ",")
    ouinon(df, ["ne_present", "rs_realisee", "presence_carte_sd", "mode_eco_active_apres_passage", "visite_client_coffre", "presence_congel", "presence_cadenas", "coffre_ouvert", "correspondance_kit_batterie_kit_solaire", "pannes_regulieres_nr", "rt_realisee", "traitement_rt_sur_place", "depannage_realise", "panne_resolue", "depannage_par_ne_possible", "panne_causee_par_comprehension_client", "zone_mr", "equipe_mr", "coherence_forfait_materiel_client_1", "probleme_client_1", "coherence_forfait_materiel_client_3", "probleme_client_3", "coherence_forfait_materiel_client_2", "probleme_client_2", "coherence_forfait_materiel_client_4", "probleme_client_4", "coherence_forfait_materiel_client_5", "probleme_client_5", "presence_cpf", "besoin_support_commercial", "visite_doit_etre_mentionnee_reunion_equipe", "presence_poteau","panne_a_l_arrivee"])
    toint(df, "numero_client_coffre")
    toint(df, "nombre_batteries")
    tofloat(df, "note_cq")
    for i, _ in df.iterrows():
        t = 'VST' if 'Visite' in df.loc[i, "type"] else 'CQ'
        d = df.loc[i, 'date']
        df.loc[i, "id"] = t + '_nr' + df.loc[i, "nr"] + '_' + df.loc[i, 'agent_name'] + '_' + datetime.strftime(d, "%Y-%m-%d")
    return df

@post_processor("enquetes-techniques-reimport")
def process_enquetes_techniques_reimport(df: pd.DataFrame) -> pd.DataFrame:
    def url_photo(url):
        if isinstance(url, float): return url
        # https://eu.kobotoolbox.org/api/v2/assets/abnLgy9uugu7DZkU3gpg8c/data/768291610/attachments/attaYGQpdaNBGRZ7b7h7D3PL/
        # https://kobo.nanoe.net/api/v2/assets/aUbS7QfRtq53cBDfKS357T/1000/attCd34pC4WqW8hT9FR6ktcC/
        if "assets" in url: return url.replace("https://eu.kobotoolbox.org/api/v2/assets", "").replace("https://kobo.nanoe.net/api/v2/assets/", "").replace("data/", "").replace("attachments/", "")
    df["photo_nr_url"] = df["photo_nr_url"].apply(url_photo)
    df["photo_congel_url"] = df["photo_congel_url"].apply(url_photo)
    df["photo_interieur_coffre_url"] = df["photo_interieur_coffre_url"].apply(url_photo)
    df["photo_panne_url"] = df["photo_panne_url"].apply(url_photo)
    return process_enquetes_techniques_final(df)

@post_processor("visites-att")
def process_visites_att(df: pd.DataFrame) -> pd.DataFrame:
    df = kobo_parse_options(df, "visites-att")
    df = kobo_clean_and_map(df, "visites-att")
    remap(df, "piquage", {'Rien à signaler': "non", 'Piquage constaté': "oui", "Suspicion de piquage (traitement des relèves, taux de rechargement, le client ne laisse pas rentrer...)": "suspicion"})
    remap(df, "panne_a_l_arrivee", {'Il y avait une panne en arrivant sur le NR': "oui", 'Rien à signaler, le NR fonctionne correctement': "non"})
    remap(df, "kit_panneau", { "1 panneau 100W (Kit1)": "Kit 1", "1 panneau 150W (Kit2)": "Kit 2", "2 panneaux 100W -> 200W (Kit3)": "Kit 3", "2 panneaux 150W -> 300W (Kit4)": "Kit 4", "4 panneaux 100W -> 400W": "4 x 100W", "4 panneaux 150W -> 600W": "4 x 150W", "0 panneau installé": "Aucun panneau", "Autre": "Autre" })
    df["type_controleur"] = df["type_controleur"].apply(lambda s: s.lower())
    for i, _ in df.iterrows():
        clients_visites = df.loc[i, "clients_visites"]
        if not isinstance(clients_visites, float):
            df.loc[i, "clients_visites"] = re.sub("[^0-9,]", "", clients_visites)
    df["type"] = "Visite ATT"
    return process_enquetes_techniques_final(df)

@post_processor("controles-qualite")
def process_controles_qualite(df: pd.DataFrame) -> pd.DataFrame:
    df = kobo_parse_options(df, "controles-qualite")
    df = kobo_clean_and_map(df, "controles-qualite")
    remap(df, "agence", {'Andoharano': 'Andoharano', 'Diego': 'Diego', 'Vohemar': 'Vohémar', 'Anivorano': 'Anivorano', 'Ambilobe': 'Ambilobe', 'Ambanja': 'Ambanja', 'Anaborano': 'Anaborano', 'Antsohihy': 'Antsohihy'})
    remap(df, "motif", {'Contrôle qualité - NR déjà installé': "Contrôle qualité", 'Conformité - Nouvelle installation': "Nouvelle installation"})
    remap(df, "type_controleur", {'Contrôleur V1': 'v1', 'Contrôleur V2': 'v2'})
    remap(df, "kit_panneau", { "1 panneau 100W (Kit1)": "Kit 1", "1 panneau 150W (Kit2)": "Kit 2", "2 panneaux 100W -> 200W (Kit3)": "Kit 3", "2 panneaux 150W -> 300W (Kit4)": "Kit 4", "4 panneaux 100W -> 400W": "4 x 100W", "4 panneaux 150W -> 600W": "4 x 150W", "0 panneau installé": "Aucun panneau", "Autre": "Autre" })
    remap(df, "nombre_batteries", {'1':1, '>2':3, '2':2})
    ouinon(df, "piquage")
    for i, _ in df.iterrows():
        df.loc[i, "depannage_realise"] = isinstance(df.loc[i, "precisions_depannage"], str)
    df["type"] = "CQ v4"
    return process_enquetes_techniques_final(df)


def post_process(key_code: str, df: pd.DataFrame) -> pd.DataFrame:
    fn = POST_PROCESSORS.get(key_code)
    if fn is None: return df
    return fn(df)
