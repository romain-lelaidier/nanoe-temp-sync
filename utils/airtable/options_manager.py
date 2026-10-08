"""
Gestion automatique des options pour les champs select
"""
from typing import Dict, List, Set
from pyairtable import Table
from utils.logger import get_logger

logger = get_logger(__name__)

class OptionsManager:
    """
    Gestionnaire des options pour les champs select/multiselect
    """
    
    def __init__(self):
        self.select_fields_cache = {}
    
    def get_select_field_options(self, table: Table, field_name: str) -> Set[str]:
        """
        Recupere les options existantes d'un champ select
        
        Args:
            table: Table Airtable
            field_name: Nom du champ select
        
        Returns:
            Ensemble des options existantes
        """
        cache_key = f"{table.base_id}:{table.table_name}:{field_name}"
        
        if cache_key in self.select_fields_cache:
            return self.select_fields_cache[cache_key]
        
        try:
            schema = table.schema()
            
            for field in schema.fields:
                if field.name == field_name:
                    if hasattr(field, 'options') and hasattr(field.options, 'choices'):
                        options = {choice.name for choice in field.options.choices}
                        self.select_fields_cache[cache_key] = options
                        logger.debug("Options du champ '%s': %i", field_name, len(options))
                        return options
            
            logger.warning("Champ '%s' non trouve ou pas de type select", field_name)
            return set()
        
        except Exception as e:
            logger.error("Erreur lors de la recuperation des options pour '%s': %s", field_name, str(e))
            return set()
    
    def find_missing_options(self, table: Table, field_name: str, values: List[str]) -> Set[str]:
        """
        Trouve les options manquantes pour un champ select
        
        Args:
            table: Table Airtable
            field_name: Nom du champ
            values: Valeurs presentes dans les donnees
        
        Returns:
            Ensemble des options manquantes
        """
        existing_options = self.get_select_field_options(table, field_name)
        
        cleaned_values = set()
        for value in values:
            if value:
                if isinstance(value, list):
                    cleaned_values.update(str(v).strip() for v in value if v)
                else:
                    cleaned_values.add(str(value).strip())
        
        cleaned_values = {v for v in cleaned_values if v and v.lower() not in ['nan', 'none', '']}
        
        missing = cleaned_values - existing_options
        
        if missing:
            logger.info("Options manquantes pour '%s': %i", field_name, len(missing))
        
        return missing
    
    def check_all_select_fields(self, table: Table, records: List[Dict], select_fields: List[str]) -> Dict[str, Set[str]]:
        """
        Verifie toutes les options manquantes pour tous les champs select
        
        Args:
            table: Table Airtable
            records: Enregistrements a verifier
            select_fields: Liste des noms de champs select
        
        Returns:
            Dictionnaire {field_name: set_of_missing_options}
        """
        missing_by_field = {}
        
        for field_name in select_fields:
            values = []
            for record in records:
                value = record.get(field_name)
                if value:
                    values.append(value)
            
            if values:
                missing = self.find_missing_options(table, field_name, values)
                if missing:
                    missing_by_field[field_name] = missing
        
        return missing_by_field


_options_manager_instance = None
def get_options_manager() -> OptionsManager:
    global _options_manager_instance
    if _options_manager_instance is None:
        _options_manager_instance = OptionsManager()
    return _options_manager_instance
