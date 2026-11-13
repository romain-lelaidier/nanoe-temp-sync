import pandas as pd
import datetime
from pathlib import Path
import re

POST_PROCESSORS = {}

def post_processor(key_code: str):
    def deco(fn):
        POST_PROCESSORS[key_code] = fn
        return fn
    return deco

def post_process(key_code: str, df: pd.DataFrame, addons: dict = {}) -> pd.DataFrame:
    fn = POST_PROCESSORS.get(key_code)
    df = df if fn is None else fn(df, **addons)
    if "agence" in df.columns: remap(df, "agence", AGENCE_MAPPER)
    return df

def remove_none(l: list[str]) -> list[str]:
    while None in l:
        l.remove(None)
    return l

_id_counter = {}
def new_id(id: str) -> str:
    global _id_counter
    if id not in _id_counter:
        _id_counter[id] = 0
    _id_counter[id] += 1
    if _id_counter[id] == 1: return id
    return f"{id} ({_id_counter[id]})"

def reset_id_counter():
    global _id_counter
    _id_counter = {}

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

AGENCE_MAPPER = {
    'Ambanja': 'Ambanja',
    'Andoharano': 'Andoharano', "Antsirasira": "Andoharano",
    'Ambilobe': 'Ambilobe',
    'Anaborano': 'Anaborano',
    'Antsohihy': 'Antsohihy',
    'Diego': 'Diego-Suarez', 'Diego-Suarez': 'Diego-Suarez',
    'Anivorano': 'Anivorano',
    'Sambava': 'Sambava',
    'Vohémar': 'Vohémar', 'Vohemar': 'Vohémar',
}

AGENT_MAPPER = {
    "Bernard": "467","Aimé": "601","Tonganjara": "424","Briel": "619","Anniel": "310","Nicolas": "308","Rama": "589","Angelico": "427","Selson": "624","Tiandray": "438","Romain": "646","Michelin": "439","Sebastien": "314","Arly": "238","Fernandel": "240","Orlando": "622","Chrisley": "592","Karim": "237","Dominique": "600","Barthelemy": "373","Noelson": "315","Flavien": "579","Asto": "604","Lady": "78","Christiano": "441","Ibrahim": "102","Yvon": "575","Sabin": "126","Stephan": "295","Dambel": "618","Elwafa": "593","Hanselme": "316","Pierre": "442","Pierrette": "306","Dieudonné": "321","Sébastien": "314","Ednique": "619","Pascal": "623","Kenny": "242","Roberto": "128","Test": "382","Jean Aimé": "601","Andriatody Jean Aimé": "601","Haja": "295","Elwafa, test": "593","Elwafa test": "593","Aina": "27","Hajalalaina": "587","Sammer": "509","Dullin": "239","Lucas": "119","Aïna": "27","Basilide": "586","Archille": "9","Asni": "518","Jean Cisco": "576","Sanda": "120","Fitiavana": "433","Leo": "495","Stéphan": "295","Anjaratiana": "508","Paul": "606","Jules": "480","Franco": "472","Oliva": "23","Velondrazana": "43","Roméo": "293","Theophile": "34","Stanislas": "313","Guilhem": "580","Arsène": "320","Louis": "309","Lancio": "307","Ferrari": "232","Tony": "305","Stève": "312","Lova": "28","Elodie": "311","Huberto": "296","François": "234",   # TECH
    "Martial": "81","Eduvain": "216","Jean Louis": "309","Brindo": "297","Bruton": "127","Maele": "481","Adonis": "230","Francis": "172","Stephane": "31","Stéphane":"31","Olive": "241","Pierre": "442","Nitram": "487","Eliot": "599","Nicolas B.": "308","Sylvain": "598","Stafford": "446","Marice": "648"  # COMM
}

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
        df.loc[i, "id"] = new_id(t + '_nr' + df.loc[i, "nr"] + '_' + df.loc[i, 'agent_name'] + '_' + datetime.datetime.strftime(d, "%Y-%m-%d"))
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

@post_processor("tech-visites-att")
def process_tech_visites_att(df: pd.DataFrame) -> pd.DataFrame:
    df = kobo_parse_options(df, "tech-visites-att")
    df = kobo_clean_and_map(df, "tech-visites-att")
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

@post_processor("tech-controles-qualite")
def process_tech_controles_qualite(df: pd.DataFrame) -> pd.DataFrame:
    df = kobo_parse_options(df, "tech-controles-qualite")
    df = kobo_clean_and_map(df, "tech-controles-qualite")
    remap(df, "agence", AGENCE_MAPPER)
    remap(df, "motif", {'Contrôle qualité - NR déjà installé': "Contrôle qualité", 'Conformité - Nouvelle installation': "Nouvelle installation"})
    remap(df, "type_controleur", {'Contrôleur V1': 'v1', 'Contrôleur V2': 'v2'})
    remap(df, "kit_panneau", { "1 panneau 100W (Kit1)": "Kit 1", "1 panneau 150W (Kit2)": "Kit 2", "2 panneaux 100W -> 200W (Kit3)": "Kit 3", "2 panneaux 150W -> 300W (Kit4)": "Kit 4", "4 panneaux 100W -> 400W": "4 x 100W", "4 panneaux 150W -> 600W": "4 x 150W", "0 panneau installé": "Aucun panneau", "Autre": "Autre" })
    remap(df, "nombre_batteries", {'1':1, '>2':3, '2':2})
    ouinon(df, "piquage")
    for i, _ in df.iterrows():
        df.loc[i, "depannage_realise"] = isinstance(df.loc[i, "precisions_depannage"], str)
    df["type"] = "CQ v4"
    return process_enquetes_techniques_final(df)

@post_processor("rs")
def process_rs(df: pd.DataFrame) -> pd.DataFrame:
    df["agent"] = df["agent"].astype("Int64").astype("string")
    df["nr"] = df["nr"].astype("Int64").astype("string")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["date_releve_precedente"] = pd.to_datetime(df["date_releve_precedente"], utc=True)
    ouinon(df, ["rs_ok","rtc_ok","sd_ok","heure_ok"])
    return df

def preprocess_enquete_commerciale(df: pd.DataFrame, key: str, clients: dict = {}) -> pd.DataFrame:
    df["agent_name"] = df["agent"]
    remap(df, "agent", AGENT_MAPPER)
    remap(df, "agence", AGENCE_MAPPER)
    df["agent"] = df["agent"].astype("Int64").astype("string")
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["nr"] = df["nr"].astype("Int64").astype("string")
    df["n_client"] = df["n_client"].astype("Int64")
    df["client"] = df["nr"] + df["n_client"].astype("string")
    remap(df, "client", clients)
    df["type"] = { "clients-inactifs": "Enquête clients inactifs", "tournees-recharge": "Tournée de recharge" }[key]
    t = { "clients-inactifs": "ECI", "tournees-recharge": "TDR" }[key]
    for i, _ in df.iterrows():
        d = df.loc[i, 'date']
        df.loc[i, "id"] = new_id(t + '_nr' + df.loc[i, "nr"] + '_c' + str(df.loc[i, "n_client"]) + '_' + df.loc[i, 'agent_name'] + '_' + datetime.datetime.strftime(d, "%Y-%m-%d"))
        if pd.isnull(df.loc[i, 'agent']):
            if pd.isnull(df.loc[i, "agent_autre"]):
                df.loc[i, "agent_autre"] = df.loc[i, "agent_name"]
    if "probleme_nanoe" in df.columns:
        for i, _ in df.iterrows():
            probleme_nanoe = df.loc[i, "probleme_nanoe"]
            if not pd.isnull(probleme_nanoe):
                probleme_nanoe_normalise = []
                for key, value in {
                    "Trop de problèmes": "Trop de problèmes techniques sur l'installation", 
                    "du client ne marche pas": "Le matériel intérieur (ampoule, TV, congel, USB...) du client ne marche pas",
                    "ne suffit pas": "Le matériel intérieur (ampoule, TV, congel, USB...) ne suffit pas",
                    "retards sur les dépannages": "Trop de retards sur les dépannages",
                    "comportement du NE": "Problème de comportement du NE",
                    "Prix": "Prix trop élevé",
                    "Autre": "Autre"
                }.items():
                    if key in probleme_nanoe:
                        probleme_nanoe_normalise.append(value.replace(',', ';'))
                    df.loc[i, "probleme_nanoe"] = ','.join(probleme_nanoe_normalise)
    df.drop(columns=["agent_name"], inplace=True)
    return df

@post_processor("comm-clients-inactifs")
def process_comm_clients_inactifs(df: pd.DataFrame, clients: dict = {}) -> pd.DataFrame:
    df = kobo_parse_options(df, "comm-clients-inactifs")
    df = kobo_clean_and_map(df, "comm-clients-inactifs")
    df = preprocess_enquete_commerciale(df, "clients-inactifs", clients)
    df["deplacement_client_nr"] = df["deplacement_client_nr"].astype("Int64").astype("string")
    remap(df, "situation_client", {"Le client est complètement inactif": "client inactif","Le client consomme peu": "client presque inactif","C'est un client fantôme": "client fantôme","Le client fait du piquage": "client piqueur","Le client a déménagé": "client a déménagé","Le client est décédé": "client décédé","Le client est déjà déraccordé": "client déraccordé"})
    remap(df, "nouveau_forfait_souhaite", {"Non": "aucun","Oui (Eco)": "Eco","Oui (Eclairage)": "Eclairage","Oui (Eclairage +)": "Eclairage +","Oui (Multimedia)": "Multimedia","Oui (Multimedia +)": "Multimedia +"})
    ouinon(df, ["client_veut_etre_deraccorde","dernier_client_actif_sur_nr","nouveau_client_potentiel","demenagement_client_interesse"])
    df["deplacement_client_nr"] = df["deplacement_client_nr"].astype("Int64").apply(lambda x: None if x == 0 else x).astype("string")
    return df

@post_processor("comm-clients-inactifs-reimport")
def process_comm_clients_inactifs(df: pd.DataFrame, clients: dict = {}) -> pd.DataFrame:
    df["agent_autre"] = df["agent"]
    for i, _ in df.iterrows():
        causes_inactivite = df.loc[i, "causes_inactivite"]
        if not pd.isnull(causes_inactivite):
            causes_inactivite = ','.join(causes_inactivite.split(', '))
    df = preprocess_enquete_commerciale(df, "clients-inactifs", clients)
    remap(df, "situation_client", {"Le client est complètement inactif": "client inactif","Le client consomme peu": "client presque inactif","C'est un client fantôme": "client fantôme","Le client fait du piquage": "client piqueur","Le client a déménagé": "client a déménagé","Le client est décédé": "client décédé","Le client est déjà déraccordé": "client déraccordé"})
    remap(df, "nouveau_forfait_souhaite", {"Non": "aucun","Oui (Eco)": "Eco","Oui (Eclairage)": "Eclairage","Oui (Eclairage +)": "Eclairage +","Oui (Multimedia)": "Multimedia","Oui (Multimedia +)": "Multimedia +"})
    ouinon(df, ["client_veut_etre_deraccorde","dernier_client_actif_sur_nr","nouveau_client_potentiel","demenagement_client_interesse"])
    df["deplacement_client_nr"] = df["deplacement_client_nr"].astype("Int64").astype("string")
    df["deplacement_client_nr"] = df["deplacement_client_nr"].astype("Int64").apply(lambda x: None if x == 0 else x).astype("string")
    return df

@post_processor("comm-tournees-recharge")
def process_comm_tournees_recharge(df: pd.DataFrame, clients: dict = {}) -> pd.DataFrame:
    df = kobo_parse_options(df, "comm-tournees-recharge")
    df = kobo_clean_and_map(df, "comm-tournees-recharge")
    df = preprocess_enquete_commerciale(df, "tournees-recharge", clients)
    ouinon(df, ["presence_client","credit_client_disponible_avant_passage","recharge_client_effectuee","probleme_commercial_6_mois","probleme_technique_6_mois","probleme_commercial_6_mois_resolu","a_evoquer_en_reunion_equipe","rs_effectuee","client_avec_coffre","presence_cadenas","piquage"])
    return df

@post_processor("comm-tournees-recharge-reimport")
def process_comm_tournees_recharge(df: pd.DataFrame, clients: dict = {}) -> pd.DataFrame:
    df["agent_autre"] = df["agent"]
    df = preprocess_enquete_commerciale(df, "tournees-recharge", clients)
    ouinon(df, ["presence_client","credit_client_disponible_avant_passage","recharge_client_effectuee","probleme_commercial_6_mois","probleme_technique_6_mois","probleme_commercial_6_mois_resolu","a_evoquer_en_reunion_equipe","rs_effectuee","client_avec_coffre","presence_cadenas","piquage"])
    return df

@post_processor("prospect")
def process_prospects(df_c: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
    def union_segments_df(df):
        df = df.sort_values(["debut", "fin"])
        # fusion glissante vectorisée : nouveau segment quand debut > fin courant
        fin = df["fin"].cummax()
        nouveau = df["debut"] > fin.shift(fill_value=-float("inf"))
        groupe = nouveau.cumsum()
        return (df.assign(fin=fin)
                .groupby(groupe)
                .agg(debut=("debut", "first"), fin=("fin", "max"))
                .reset_index(drop=True))
    def intersection_segments(df, a, b):
        """
        Arguments:
            df : DataFrame avec colonnes debut, fin (segments [debut, fin[, potentiellement intersectés).
            a, b : bornes du segment requête [a, b[.
        Retourne la longueur totale de l'intersection des segments de df avec [a, b[."""
        out = df[(df["debut"] > a) & (df["fin"] < b)].copy()
        out["debut"] = out["debut"].clip(lower=a)
        out["fin"] = out["fin"].clip(upper=b)
        return (out["fin"] - out["debut"]).sum()

    ajd = (datetime.date.today() - datetime.date(1970, 1, 1)).days
    plages = {
        "tr3m_0": (ajd-92*(0+1), ajd-92*0),
        "tr3m_1": (ajd-92*(1+1), ajd-92*1),
        "tr3m_2": (ajd-92*(2+1), ajd-92*2),
        "tr3m_3": (ajd-92*(3+1), ajd-92*3),
    }

    for i, _ in df_c.iterrows():
        df_ct = transactions[transactions['id_client'] == df_c.loc[i, 'n']]
        df_ct = union_segments_df(df_ct)
        for key, (a, b) in plages.items():
            df_c.loc[i, key] = intersection_segments(df_ct, a, b) / (b - a)

    return df_c