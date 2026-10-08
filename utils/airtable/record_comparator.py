"""
Comparaison intelligente d'enregistrements Airtable
"""
import pandas as pd
from typing import Any, Dict, List, Set, Optional
from decimal import Decimal
from datetime import datetime, date
from utils.logger import get_logger
from utils.airtable.config import AirtableTable
import re

logger = get_logger(__name__)

def normalize_singleselect_value(value: str, options: List[str]) -> Optional[str]:
    """
    Normalise une valeur pour un champ singleSelect en trouvant la meilleure correspondance
    parmi les options disponibles.
    
    Args:
        value: Valeur à normaliser (ex: "12V")
        options: Liste des options valides (ex: ["12", "12 V", "24"])
    
    Returns:
        Option correspondante ou None si aucune correspondance
    """
    if not value or not isinstance(value, str):
        return None
    
    value = value.strip()
    if not value:
        return None
    
    # Correspondance exacte
    if value in options:
        return value
    
    # Normaliser les espaces multiples
    value_normalized = re.sub(r'\s+', ' ', value)
    if value_normalized in options:
        return value_normalized
    
    # Cas spécial: "12V" -> "12 V" (ajouter espace avant V/v)
    # Pattern: nombre suivi de V (avec ou sans espace)
    match = re.match(r'^(\d+)\s*[Vv]\s*$', value)
    if match:
        number = match.group(1)
        # Essayer "12 V" puis "12"
        for option in options:
            if option.strip() == f"{number} V" or option.strip() == number:
                return option.strip()
    
    # Correspondance insensible à la casse
    value_lower = value.lower()
    for option in options:
        if option.lower() == value_lower:
            return option
    
    # Correspondance après normalisation des espaces (insensible à la casse)
    value_normalized_lower = value_normalized.lower()
    for option in options:
        if option.lower().strip() == value_normalized_lower:
            return option
    
    # Essayer de trouver une correspondance partielle (ex: "12V" correspond à "12 V")
    # En normalisant les espaces et en comparant après avoir enlevé les espaces
    value_no_spaces = re.sub(r'\s+', '', value).lower()
    for option in options:
        option_no_spaces = re.sub(r'\s+', '', option).lower()
        if option_no_spaces == value_no_spaces:
            return option
    
    # Aucune correspondance trouvée
    logger.warning(f"Aucune correspondance trouvée pour singleSelect '{value}' parmi les options: {options}")
    return None


def convert_value_for_airtable(value: Any, field_config: Optional[Dict] = None) -> Any:
    """
    Convertit une valeur Python en format compatible Airtable JSON
    
    Args:
        value: Valeur à convertir
        field_config: Configuration optionnelle du champ
    
    Returns:
        Valeur convertie compatible JSON
    """
    # Vérifier si la valeur est None ou NaN
    # Gérer le cas spécial des arrays NumPy/Pandas
    if value is None:
        return None
    
    # Vérifier pd.isna de manière sûre pour les arrays
    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        # Si pd.isna échoue (array multi-éléments), laisser la valeur telle quelle
        # et gérer dans les sections suivantes
        pass
    
    # Gérer les Timestamp Pandas (le problème principal)
    if isinstance(value, pd.Timestamp):
        try:
            # Si timezone-aware, convertir en UTC puis formatter
            if value.tz is not None:
                value = value.tz_convert('UTC').tz_localize(None)
            # Convertir en pydatetime puis en ISO string pour JSON
            dt = value.to_pydatetime()
            return dt.isoformat() + 'Z'
        except Exception as e:
            logger.warning(f"Erreur conversion Timestamp: {e}")
            # Fallback: convertir en chaîne simple
            try:
                return value.strftime('%Y-%m-%d')
            except:
                return str(value)
    
    # Gérer les datetime.datetime
    if isinstance(value, datetime):
        try:
            return value.isoformat() + 'Z'
        except Exception as e:
            logger.warning(f"Erreur conversion datetime: {e}")
            return str(value)
    
    # Gérer les date
    if isinstance(value, date):
        try:
            return value.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Erreur conversion date: {e}")
            return str(value)
    
    # Gérer les Decimal
    if isinstance(value, Decimal):
        return float(value)
    
    # Gérer les listes
    if isinstance(value, (list, tuple)):
        return [convert_value_for_airtable(item) for item in value]
    
    # Gérer les arrays NumPy/Pandas (convertissez en list)
    if hasattr(value, '__array__'):
        # C'est un array NumPy ou série Pandas
        try:
            array_value = value.__array__()
            if array_value.ndim == 0:
                # Array scalaire
                return convert_value_for_airtable(array_value.item())
            elif array_value.ndim == 1:
                # Array 1D - convertir en liste
                return [convert_value_for_airtable(item) for item in array_value]
            else:
                # Array multi-dimensionnel - convertir en liste de listes
                return [convert_value_for_airtable(item) for item in array_value.tolist()]
        except Exception as e:
            logger.warning(f"Erreur conversion array: {e}")
            return str(value)
    
    # Gérer les dictionnaires
    if isinstance(value, dict):
        return {k: convert_value_for_airtable(v) for k, v in value.items()}
    
    # Gérer les autres types Pandas
    if isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):
        return value
    
    # String avec NaN, None, etc.
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in ['nan', 'none', 'nat', '']:
            return None
        
        # Pour les champs singleSelect, on retourne la valeur telle quelle
        # La validation sera faite par Airtable lui-même
        return cleaned
    
    # Gérer les valeurs numériques (float NaN)
    if isinstance(value, float) and pd.isna(value):
        return None
    
    # Si aucune conversion n'a été faite, retourner la valeur telle quelle
    # (mais ça ne devrait jamais arriver si on a bien tous les cas)
    return value


def normalize_date_string(date_str: str) -> Optional[str]:
    """
    Normalise une chaîne de date en format ISO date simple (YYYY-MM-DD)
    
    Args:
        date_str: Chaîne contenant une date
    
    Returns:
        Chaîne normalisée ou None si ce n'est pas une date
    """
    from dateutil import parser as date_parser
    import warnings
    import re
    
    # Rejeter les valeurs qui ressemblent a des numeros de version (ex: 6.4, 2.0.0)
    version_pattern = re.compile(r'^\d+\.\d+(\.\d+)?$')
    if version_pattern.match(str(date_str).strip()):
        return None
    
    try:
        # Supprimer les warnings de timezone pendant le parsing
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=UserWarning, module='dateutil')
            # Ignorer aussi UnknownTimezoneWarning si disponible
            try:
                from dateutil.parser._parser import UnknownTimezoneWarning
                warnings.filterwarnings('ignore', category=UnknownTimezoneWarning, module='dateutil')
            except ImportError:
                pass
            # Ignorer tous les warnings de dateutil de manière générale
            warnings.filterwarnings('ignore', module='dateutil')
            # Essayer de parser la date
            dt = date_parser.parse(str(date_str))
            # Retourner juste la date sans l'heure
            return dt.strftime('%Y-%m-%d')
    except:
        return None


def normalize_multiselect_value(value: Any) -> Optional[List[str]]:
    """
    Normalise une valeur de multiple select pour la comparaison.
    Gère les cas suivants:
    - Liste d'objets avec .name (format Airtable): [{'name': 'A'}, {'name': 'B'}] -> ['A', 'B']
    - Liste de strings: ['A', 'B'] -> ['A', 'B']
    - String avec séparateurs: 'A, B' ou 'A|B' -> ['A', 'B']
    - None ou vide -> None
    
    Args:
        value: Valeur à normaliser
    
    Returns:
        Liste normalisée de strings triées, ou None si vide
    """
    if value is None:
        return None
    
    # Gérer les arrays numpy/pandas
    if hasattr(value, '__array__'):
        try:
            array_val = value.__array__()
            if array_val.ndim == 0:
                value = array_val.item()
            elif array_val.ndim == 1:
                value = array_val.tolist()
            else:
                return None
        except:
            return None
    
    # Vérifier si c'est NaN
    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass
    
    # Si c'est une liste
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return None
        
        normalized = []
        for item in value:
            # Si c'est un objet avec .name (format Airtable multiple select)
            if isinstance(item, dict) and 'name' in item:
                name = item['name']
                if name and not pd.isna(name):
                    normalized.append(str(name).strip())
            # Si c'est déjà une string
            elif isinstance(item, str):
                cleaned = item.strip()
                if cleaned and cleaned.lower() not in ['none', 'nan', 'null', '']:
                    normalized.append(cleaned)
            # Sinon, convertir en string
            else:
                try:
                    if not pd.isna(item):
                        normalized.append(str(item).strip())
                except:
                    pass
        
        if not normalized:
            return None
        
        # Trier et dédupliquer
        return sorted(list(set(normalized)))
    
    # Si c'est une string, essayer de la parser
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in ['none', 'nan', 'null', '']:
            return None
        
        # Essayer de séparer par virgule, point-virgule, ou pipe
        # Format possible: "Incomplet, 2" ou "Incomplet|2" ou "Incomplet; 2"
        parts = re.split(r'[,;|]', cleaned)
        normalized = [p.strip() for p in parts if p.strip()]
        
        if not normalized:
            return None
        
        # Trier et dédupliquer
        return sorted(list(set(normalized)))
    
    return None


def are_values_equal(val1: Any, val2: Any, tolerance: float = 0.0001) -> bool:
    """
    Compare deux valeurs de maniere intelligente
    
    Args:
        val1: Premiere valeur
        val2: Deuxieme valeur
        tolerance: Tolerance pour les comparaisons numeriques
    
    Returns:
        True si les valeurs sont considerees egales
    """
    # Convertir les arrays numpy/pandas en valeurs scalaires si nécessaire
    # Cela évite l'erreur "ambiguous truth value" avec pd.isna() sur les arrays
    def extract_scalar(value):
        """Extrait une valeur scalaire d'un array si nécessaire"""
        if value is None:
            return None
        # Vérifier si c'est un array numpy/pandas
        if hasattr(value, '__array__'):
            try:
                array_val = value.__array__()
                if array_val.ndim == 0:
                    # Array scalaire - extraire la valeur
                    return array_val.item()
                elif array_val.ndim == 1 and len(array_val) == 1:
                    # Array 1D avec un seul élément
                    return array_val[0]
                # Array multi-éléments - on ne peut pas utiliser pd.isna() directement
                # Vérifier si tous les éléments sont NaN
                try:
                    if pd.isna(array_val).all():
                        return None
                except (ValueError, TypeError):
                    pass
                # Si ce n'est pas tout NaN, prendre le premier élément
                if len(array_val) > 0:
                    return array_val[0]
                return None
            except Exception:
                pass
        return value
    
    # Extraire les valeurs scalaires avant la comparaison
    val1 = extract_scalar(val1)
    val2 = extract_scalar(val2)
    
    if val1 is None and val2 is None:
        return True
    
    if (val1 is None and val2 is not None) or (val1 is not None and val2 is None):
        return False
    
    # Maintenant que les valeurs sont scalaires, on peut utiliser pd.isna() en sécurité
    try:
        is_na1 = pd.isna(val1)
        is_na2 = pd.isna(val2)
        
        if is_na1 and is_na2:
            return True
        
        if (is_na1 and not is_na2) or (not is_na1 and is_na2):
            return False
    except (ValueError, TypeError):
        # Si pd.isna() échoue encore (cas rare), traiter comme valeurs non-NaN
        pass
    
    if isinstance(val1, (int, float, Decimal)) and isinstance(val2, (int, float, Decimal)):
        try:
            num1 = float(val1)
            num2 = float(val2)
            
            if pd.isna(num1) and pd.isna(num2):
                return True
            
            return abs(num1 - num2) < tolerance
        except:
            return False
    
    # Gérer le cas où une valeur est une chaîne et l'autre est une liste (ou vice versa)
    # Cela arrive souvent avec Airtable qui stocke des chaînes simples comme des listes
    # OU avec des multiple select: string "A, B" vs liste [{'name': 'A'}, {'name': 'B'}]
    if isinstance(val1, str) and isinstance(val2, list):
        # Essayer de normaliser comme multiple select d'abord
        val1_ms = normalize_multiselect_value(val1)
        val2_ms = normalize_multiselect_value(val2)
        if val1_ms is not None or val2_ms is not None:
            return val1_ms == val2_ms
        
        # Si la liste est vide, considérer comme None/vide
        if len(val2) == 0:
            try:
                val1_clean = val1.strip().lower() if isinstance(val1, str) else str(val1).lower()
                is_empty = val1_clean in ['', 'none', 'nan', 'null']
                is_na = pd.isna(val1)
                return is_empty or is_na
            except:
                return False
        # Si la liste contient un seul élément qui est la chaîne, elles sont égales
        if len(val2) == 1:
            return are_values_equal(val1, val2[0], tolerance)
        # Sinon, convertir la chaîne en liste et comparer
        return are_values_equal([val1], val2, tolerance)
    
    if isinstance(val1, list) and isinstance(val2, str):
        # Essayer de normaliser comme multiple select d'abord
        val1_ms = normalize_multiselect_value(val1)
        val2_ms = normalize_multiselect_value(val2)
        if val1_ms is not None or val2_ms is not None:
            return val1_ms == val2_ms
        
        # Si la liste est vide, considérer comme None/vide
        if len(val1) == 0:
            try:
                val2_clean = val2.strip().lower() if isinstance(val2, str) else str(val2).lower()
                is_empty = val2_clean in ['', 'none', 'nan', 'null']
                is_na = pd.isna(val2)
                return is_empty or is_na
            except:
                return False
        # Si la liste contient un seul élément qui est la chaîne, elles sont égales
        if len(val1) == 1:
            return are_values_equal(val1[0], val2, tolerance)
        return are_values_equal(val1, [val2], tolerance)
    
    if isinstance(val1, str) and isinstance(val2, str):
        val1_clean = val1.strip()
        val2_clean = val2.strip()
        
        # Gérer les cas où une chaîne représente None/NaN
        val1_is_none = val1_clean.lower() in ['none', 'nan', 'null', '']
        val2_is_none = val2_clean.lower() in ['none', 'nan', 'null', '']
        if val1_is_none and val2_is_none:
            return True
        if val1_is_none or val2_is_none:
            return False
        
        # Vérifier si ce sont des dates avant de comparer
        normalized_date1 = normalize_date_string(val1_clean)
        normalized_date2 = normalize_date_string(val2_clean)
        
        if normalized_date1 is not None and normalized_date2 is not None:
            # Les deux sont des dates, comparer les dates normalisées
            return normalized_date1 == normalized_date2
        
        return val1_clean == val2_clean
    
    if isinstance(val1, (datetime, date)) and isinstance(val2, (datetime, date)):
        try:
            if hasattr(val1, 'replace'):
                val1_naive = val1.replace(tzinfo=None) if hasattr(val1, 'tzinfo') else val1
            else:
                val1_naive = val1
            
            if hasattr(val2, 'replace'):
                val2_naive = val2.replace(tzinfo=None) if hasattr(val2, 'tzinfo') else val2
            else:
                val2_naive = val2
            
            return val1_naive == val2_naive
        except:
            return False
    
    # Gérer les multiple select: normaliser avant de comparer
    # Cela évite les faux positifs comme "Incomplet, 2" vs [{'name': 'Incomplet'}, {'name': '2'}]
    val1_multiselect = normalize_multiselect_value(val1)
    val2_multiselect = normalize_multiselect_value(val2)
    
    # Si les deux valeurs peuvent être normalisées comme multiple select, comparer les versions normalisées
    if val1_multiselect is not None or val2_multiselect is not None:
        if val1_multiselect == val2_multiselect:
            return True
        # Si l'une peut être normalisée mais pas l'autre, elles ne sont pas égales
        if (val1_multiselect is None) != (val2_multiselect is None):
            return False
    
    # Comparaison standard des listes (si ce n'est pas un multiple select)
    if isinstance(val1, list) and isinstance(val2, list):
        if len(val1) != len(val2):
            return False
        
        val1_sorted = sorted([str(v) for v in val1])
        val2_sorted = sorted([str(v) for v in val2])
        
        return val1_sorted == val2_sorted
    
    try:
        return str(val1) == str(val2)
    except:
        return False


def compare_records(record1: Dict, record2: Dict, ignore_keys: Set[str] = None) -> Dict:
    """
    Compare deux enregistrements et retourne les differences
    
    Args:
        record1: Premier enregistrement
        record2: Deuxieme enregistrement
        ignore_keys: Cles a ignorer dans la comparaison
    
    Returns:
        Dictionnaire des differences
    """
    if ignore_keys is None:
        ignore_keys = set()
    
    differences = {}
    all_keys = set(record1.keys()) | set(record2.keys())
    
    for key in all_keys:
        if key in ignore_keys:
            continue
        
        val1 = record1.get(key)
        val2 = record2.get(key)
        
        if not are_values_equal(val1, val2):
            differences[key] = {
                'old_value': val1,
                'new_value': val2
            }
    
    return differences


def has_changes(record1: Dict, record2: Dict, ignore_keys: Set[str] = None) -> bool:
    """
    Determine si deux enregistrements ont des differences
    
    Args:
        record1: Premier enregistrement
        record2: Deuxieme enregistrement
        ignore_keys: Cles a ignorer
    
    Returns:
        True si des differences existent
    """
    differences = compare_records(record1, record2, ignore_keys)
    return len(differences) > 0


def clean_record_for_comparison(record: Dict, table: Optional[AirtableTable] = None) -> Dict:
    """
    Nettoie un enregistrement pour la comparaison et la synchronisation avec Airtable
    
    Args:
        record: Enregistrement a nettoyer
        table: Configuration optionnelle de la table
    
    Returns:
        Enregistrement nettoye avec valeurs compatibles JSON
    """
    cleaned = {}
    
    for key, value in record.items():
        # Récupérer la config du champ si disponible
        field_config = table.get_field_config(key)
        
        # Utiliser la fonction de conversion pour gérer tous les types
        cleaned[key] = convert_value_for_airtable(value, field_config)
    
    return cleaned


def batch_compare_records(
    new_records: List[Dict],
    existing_records: List[Dict],
    key_field: str,
    ignore_fields: Set[str] = None,
    table: Optional[AirtableTable] = None
) -> Dict[str, List[Dict]]:
    """
    Compare un lot d'enregistrements nouveaux avec les existants
    
    Args:
        new_records: Nouveaux enregistrements
        existing_records: Enregistrements existants
        key_field: Champ cle pour matcher les enregistrements
        ignore_fields: Champs a ignorer dans la comparaison
    
    Returns:
        Dictionnaire avec 'to_create', 'to_update', 'unchanged'
    """
    if ignore_fields is None:
        ignore_fields = set()
    
    existing_by_key = {}
    for record in existing_records:
        fields = record.get('fields', {})
        key_value = fields.get(key_field)
        if key_value:
            existing_by_key[str(key_value)] = record
    
    to_create = []
    to_update = []
    unchanged = []
    
    for new_record in new_records:
        key_value = new_record.get(key_field)
        if not key_value:
            continue
        
        existing_record = existing_by_key.get(str(key_value))
        
        if not existing_record:
            to_create.append(new_record)
        else:
            existing_fields = existing_record.get('fields', {})
            
            clean_new = clean_record_for_comparison(new_record, table)
            clean_existing = clean_record_for_comparison(existing_fields, table)
            
            # IMPORTANT: Ne comparer que les champs présents dans le nouveau record
            # Les champs calculés/générés par Airtable sont ignorés
            fields_to_compare = set(clean_new.keys()) | ignore_fields
            
            # Filtrer les champs existants pour ne garder que ceux à comparer
            clean_existing_filtered = {
                k: v for k, v in clean_existing.items()
                if k in fields_to_compare
            }

            differences = compare_records(clean_new, clean_existing_filtered, ignore_fields)
            
            if len(differences) > 0:
                # Logs de debug supprimés - trop verbeux pour la production
                to_update.append({
                    'id': existing_record['id'],
                    'fields': new_record
                })
            else:
                unchanged.append(new_record)
    
    logger.debug(f"Comparaison batch: {len(to_create)} a creer, {len(to_update)} a MAJ, {len(unchanged)} inchanges")
    
    return {
        'to_create': to_create,
        'to_update': to_update,
        'unchanged': unchanged
    }
