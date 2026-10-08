"""
Client Airtable wrapper
"""
from pyairtable import Api, Table
from typing import List, Dict, Any, Optional
from utils.airtable.config import get_airtable_config
from utils.config import ServiceConfig, yaml_load_config
from utils.logger import get_logger

logger = get_logger(__name__)


class AirtableClient:
    """
    Wrapper pour l'API Airtable
    """
    
    def __init__(self):
        config = ServiceConfig()
        # self.airtable_config = yaml_load_config("airtable")
        self.airtable_config = get_airtable_config()
        self.base_id = self.airtable_config.base_id
        self.api = Api(config.AIRTABLE_TOKEN)
        self._table_cache = {}
    
    def get_table(self, table_id: str) -> Table:
        """
        Retourne une instance de Table Airtable
        
        Args:
            base_id: ID de la base Airtable
            table_name: Nom de la table
        
        Returns:
            Instance de Table
        """
        cache_key = f"{self.base_id}:{table_id}"
        
        if cache_key not in self._table_cache:
            self._table_cache[cache_key] = self.api.table(self.base_id, table_id)
            logger.debug(f"Table chargee: {table_id} ({self.base_id})")
        
        return self._table_cache[cache_key]
    
    def get_all_records(self, table_key: str, view: Optional[str] = None, formula: Optional[str] = None) -> List[Dict]:
        """
        Recupere tous les enregistrements d'une table
        
        Args:
            table_key: Clé de la table (airtable.yaml)
            view: Nom de la vue (optionnel)
            formula: Formule de filtrage (optionnel)
        
        Returns:
            Liste des enregistrements
        """
        try:
            params = {}
            if view:
                params['view'] = view
            if formula:
                params['formula'] = formula

            table = self.airtable_config.get_table(table_key).table
            
            records = table.all(**params)
            logger.debug(f"Enregistrements recuperes: {len(records)}")
            return records
        
        except Exception as e:
            logger.error(f"Erreur lors de la recuperation des enregistrements: {e}")
            raise
    
    def create_records(self, table: Table, records: List[Dict], typecast: bool = True) -> List[Dict]:
        """
        Cree plusieurs enregistrements
        
        Args:
            table: Instance de Table
            records: Liste des enregistrements a creer
            typecast: Activer le typecast automatique
        
        Returns:
            Liste des enregistrements crees
        """
        try:
            created = table.batch_create(records, typecast=typecast)
            logger.debug(f"Enregistrements crees: {len(created)}")
            return created
        
        except Exception as e:
            logger.error(f"Erreur lors de la creation des enregistrements: {e}")
            raise
    
    def update_records(self, table: Table, records: List[Dict], typecast: bool = True) -> List[Dict]:
        """
        Met a jour plusieurs enregistrements
        
        Args:
            table: Instance de Table
            records: Liste des enregistrements a mettre a jour (avec 'id')
            typecast: Activer le typecast automatique
        
        Returns:
            Liste des enregistrements mis a jour
        """
        try:
            updated = table.batch_update(records, typecast=typecast)
            logger.debug(f"Enregistrements mis a jour: {len(updated)}")
            return updated
        
        except Exception as e:
            logger.error(f"Erreur lors de la mise a jour des enregistrements: {e}")
            raise
    
    def delete_records(self, table: Table, record_ids: List[str]) -> List[Dict]:
        """
        Supprime plusieurs enregistrements
        
        Args:
            table: Instance de Table
            record_ids: Liste des IDs d'enregistrements a supprimer
        
        Returns:
            Liste des enregistrements supprimes
        """
        try:
            deleted = table.batch_delete(record_ids)
            logger.info(f"Enregistrements supprimes: {len(deleted)}")
            return deleted
        
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des enregistrements: {e}")
            raise


_airtable_client_instance = None
def get_airtable_client() -> AirtableClient:
    global _airtable_client_instance
    if _airtable_client_instance is None:
        _airtable_client_instance = AirtableClient()
    return _airtable_client_instance
