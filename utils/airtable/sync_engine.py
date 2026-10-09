"""
Moteur de synchronisation Airtable
"""
import pandas as pd
from alive_progress import alive_bar
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from utils.airtable.client import get_airtable_client
from utils.airtable.record_comparator import batch_compare_records, clean_record_for_comparison
from utils.airtable.options_manager import get_options_manager
from utils.airtable.config import get_airtable_config
from utils.logger import get_logger
# from alive_progress import alive_bar

logger = get_logger(__name__)


class AirtableSyncEngine:
    """
    Moteur principal de synchronisation avec Airtable
    """
    
    def __init__(self):
        self.client = get_airtable_client()
        self.airtable_config = get_airtable_config()
        # self.options_manager = get_options_manager()
        self.batch_size = 10
    
    def sync_dataframe(
        self,
        table_key: str,
        df: pd.DataFrame,
        dry_run: bool = False,
        delete_missing_records: bool = True,
    ) -> Dict:
        """
        Synchronise un DataFrame complet avec une table Airtable
        
        Args:
            table_key: Cle de la table (ex: 'nr', 'staff')
            df: DataFrame a synchroniser
            dry_run: Si True, simule la synchronisation sans ecrire
            select_fields: Liste des champs select pour gestion auto des options
            delete_missing_records: Si True, supprime les enregistrements qui n'existent pas dans le DataFrame
        
        Returns:
            Dictionnaire avec les statistiques de synchronisation
        """

        # logger.info("Synchronisation de la table '%s'; %i rows. Options : %s", table_key, len(df), str({ "dry_run": dry_run, "delete_missing_records": delete_missing_records }))
        
        table = self.airtable_config.get_table(table_key)
        df["last_sync"] = datetime.now()
        df = table.convert_sql_fields_to_field_names(df)
        df_clean = df.copy()
        
        records_to_sync = df_clean.to_dict('records')
        
        logger.debug("sync.fetch_existing.start (table %s)", table_key)
        existing_records = self.client.get_all_records(table_key)
        logger.debug("sync.fetch_existing.completed (table %s) : %i rows", table_key, len(existing_records))
        
        # Identifier les enregistrements à supprimer (présents dans Airtable mais pas dans le DataFrame ou présents en double dans Airtable)
        to_delete = []

        # Supprimer les enregistrements en double dans la table déjà existante
        existing_records_keys = set()
        for existing_record in existing_records:
            fields = existing_record.get('fields', {})
            key_value = fields.get(table.get_primary_field())
            if key_value:
                if str(key_value) in existing_records_keys:
                    to_delete.append(existing_record)
                    existing_records.remove(existing_record)
                existing_records_keys.add(str(key_value))
        
        if delete_missing_records:

            # Créer un set des clés primaires du DataFrame et supprimer les enregistrements existants en double
            df_keys = set()
            for record in records_to_sync:
                key_value = record.get(table.get_primary_field())
                if key_value:
                    df_keys.add(str(key_value))

            # Trouver les enregistrements existants qui ne sont pas dans le DataFrame
            for existing_record in existing_records:
                fields = existing_record.get('fields', {})
                key_value = fields.get(table.get_primary_field())
                if key_value and str(key_value) not in df_keys:
                    to_delete.append(existing_record)

        comparison_result = batch_compare_records(
            new_records=records_to_sync,
            existing_records=existing_records,
            key_field=table.get_primary_field(),
            ignore_fields={'id', 'createdTime'},
            table=table
        )
        
        to_create = comparison_result['to_create']
        to_update = comparison_result['to_update']
        unchanged = comparison_result['unchanged']
        
        logger.info("sync.diff.summary (table %s) : %i records to create, %i to update, %i to delete, %i to leave as", table_key, len(to_create), len(to_update), len(to_delete), len(unchanged))
        
        stats = {
            'total_rows': len(df),
            'to_create': len(to_create),
            'to_update': len(to_update),
            'unchanged': len(unchanged),
            'to_delete': len(to_delete),
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0,
            'error_details': []
        }
        
        if dry_run:
            return stats
        
        if to_delete:
            deleted_count, delete_errors = self._delete_records_in_batches(table_key, to_delete)
            stats['deleted'] = deleted_count
            stats['errors'] += len(delete_errors)
            stats['error_details'].extend(delete_errors)
        
        if to_create:
            created_count, create_errors = self._create_records_in_batches(table_key, to_create)
            stats['created'] = created_count
            stats['errors'] += len(create_errors)
            stats['error_details'].extend(create_errors)
        
        if to_update:
            updated_count, update_errors = self._update_records_in_batches(table_key, to_update)
            stats['updated'] = updated_count
            stats['errors'] += len(update_errors)
            stats['error_details'].extend(update_errors)
        
        logger.info("sync.completed (table %s) : %i records created, %i updated, %i deleted ; %i errors", table_key, stats['created'], stats['updated'], stats.get('deleted', 0), stats['errors'])
        
        return stats
    
    def _create_records_in_batches(self, table_key: str, records: List[Dict]) -> Tuple[int, List[str]]:
        """
        Cree des enregistrements par lots
        
        Args:
            table_key: Clé de la table (airtable.yaml)
            records: Enregistrements a creer
        
        Returns:
            Tuple (nombre_crees, liste_erreurs)
        """
        created_count = 0
        errors = []

        table = self.airtable_config.get_table(table_key)
        
        # Calculer le nombre total de batches
        total_batches = len(records) // self.batch_size + (1 if len(records) % self.batch_size else 0)
        
        # Utiliser progress bar conditionnelle
        # from utils.server_mode import get_progress_bar
        # progress_wrapper = get_progress_bar(
        #     total=len(records), 
        #     desc="Creation enregistrements", 
        #     unit="",
        #     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        # )
        
        with alive_bar(len(records)) as pbar:
            for i in range(0, len(records), self.batch_size):
                batch = records[i:i + self.batch_size]
                batch_formatted = [clean_record_for_comparison(r, table) for r in batch]
                
                try:
                    created = self.client.create_records(table.table, batch_formatted, typecast=True)
                    created_count += len(created)
                    pbar(len(batch))
                
                except Exception as e:
                    # logger.warning(
                    #     format_log_context(
                    #         "sync.batch.create.retry",
                    #         table=table_key,
                    #         error=str(e)
                    #     )
                    # )
                    
                    for record in batch:
                        try:
                            formatted = clean_record_for_comparison(record, table)
                            self.client.create_records(table.table, [formatted], typecast=True)
                            created_count += 1
                            pbar()
                        except Exception as unit_error:
                            key_value = record.get(table.get_primary_field(), 'INCONNU')
                            # errors.append(
                            #     format_log_context(
                            #         "sync.batch.create.error",
                            #         table=table_key,
                            #         key_field=primary_key,
                            #         key_value=key_value,
                            #         error=str(unit_error)
                            #     )
                            # )
                            # logger.error(errors[-1])
                            pbar()
        
        return created_count, errors
    
    def _update_records_in_batches(self, table_key: str, records: List[Dict]) -> Tuple[int, List[str]]:
        """
        Met a jour des enregistrements par lots
        
        Args:
            table: Table Airtable
            records: Enregistrements a mettre a jour (avec 'id')
        
        Returns:
            Tuple (nombre_maj, liste_erreurs)
        """
        updated_count = 0
        errors = []

        table = self.airtable_config.get_table(table_key)
        
        # Deduplication: garder le dernier enregistrement pour chaque id unique
        # pour eviter l'erreur "You cannot update the same record multiple times in a single request"
        seen_ids = {}
        deduplicated_records = []
        for record in records:
            record_id = record.get('id')
            if record_id:
                seen_ids[record_id] = record
        
        deduplicated_records = list(seen_ids.values())
        
        # if len(deduplicated_records) < len(records):
        #     logger.warning(
        #         format_log_context(
        #             "sync.batch.update.deduplication",
        #             table=table_key,
        #             original_count=len(records),
        #             deduplicated_count=len(deduplicated_records),
        #             duplicates_removed=len(records) - len(deduplicated_records)
        #         )
        #     )
        
        # Calculer le nombre total de batches
        total_batches = len(deduplicated_records) // self.batch_size + (1 if len(deduplicated_records) % self.batch_size else 0)
        
        # # Utiliser progress bar conditionnelle
        # from utils.server_mode import get_progress_bar
        # progress_wrapper = get_progress_bar(
        #     total=len(deduplicated_records), 
        #     desc="Mise a jour enregistrements", 
        #     unit="",
        #     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        # )
        
        with alive_bar(len(deduplicated_records)) as pbar:
            for i in range(0, len(deduplicated_records), self.batch_size):
                batch = deduplicated_records[i:i + self.batch_size]
                
                batch_formatted = []
                for record in batch:
                    batch_formatted.append({
                        'id': record['id'],
                        'fields': clean_record_for_comparison(record['fields'], table)
                    })
                
                try:
                    updated = self.client.update_records(table.table, batch_formatted, typecast=True)
                    updated_count += len(updated)
                    pbar(len(batch))
                
                except Exception as e:
                    # logger.warning(
                    #     format_log_context(
                    #         "sync.batch.update.retry",
                    #         table=table_key,
                    #         error=str(e)
                    #     )
                    # )
                    
                    for record in batch:
                        try:
                            formatted = {
                                'id': record['id'],
                                'fields': clean_record_for_comparison(record['fields'], table)
                            }
                            self.client.update_records(table.table, [formatted], typecast=True)
                            updated_count += 1
                            pbar(1)
                        except Exception as unit_error:
                            key_value = record['fields'].get(table.get_primary_field(), 'INCONNU')
                            # errors.append(
                            #     format_log_context(
                            #         "sync.batch.update.error",
                            #         table=table_key,
                            #         key_field=primary_key,
                            #         key_value=key_value,
                            #         error=str(unit_error)
                            #     )
                            # )
                            # logger.error(errors[-1])
                            pbar(1)
            
        return updated_count, errors
    
    def _delete_records_in_batches(self, table_key: str, records: List[Dict]) -> Tuple[int, List[str]]:
        """
        Supprime des enregistrements par lots
        
        Args:
            table: Table Airtable
            records: Enregistrements a supprimer (avec 'id')
        
        Returns:
            Tuple (nombre_supprimes, liste_erreurs)
        """
        deleted_count = 0
        errors = []

        table = self.airtable_config.get_table(table_key)
        
        # Extraire les IDs à supprimer
        record_ids = [record['id'] for record in records if 'id' in record]
        
        if not record_ids:
            return 0, []
        
        # Utiliser progress bar conditionnelle
        # from utils.server_mode import get_progress_bar
        # progress_wrapper = get_progress_bar(
        #     total=len(record_ids), 
        #     desc="Suppression enregistrements", 
        #     unit="",
        #     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        # )
        
        with alive_bar(len(record_ids)) as pbar:
            for i in range(0, len(record_ids), self.batch_size):
                batch_ids = record_ids[i:i + self.batch_size]
                
                try:
                    deleted = self.client.delete_records(table.table, batch_ids)
                    deleted_count += len(deleted)
                    pbar(len(batch_ids))
                
                except Exception as e:
                    # logger.warning(
                    #     format_log_context(
                    #         "sync.batch.delete.retry",
                    #         table=table_key,
                    #         error=str(e)
                    #     )
                    # )
                    
                    for record_id in batch_ids:
                        try:
                            self.client.delete_records(table.table, [record_id])
                            deleted_count += 1
                            pbar(1)
                        except Exception as unit_error:
                            # Trouver la clé primaire pour le message d'erreur
                            key_value = 'INCONNU'
                            for record in records:
                                if record.get('id') == record_id:
                                    fields = record.get('fields', {})
                                    key_value = fields.get(table.get_primary_field(), 'INCONNU')
                                    break
                            
                            # errors.append(
                            #     format_log_context(
                            #         "sync.batch.delete.error",
                            #         table=table_key,
                            #         key_field=primary_key,
                            #         key_value=key_value,
                            #         error=str(unit_error)
                            #     )
                            # )
                            # logger.error(errors[-1])
                            pbar(1)
        
        return deleted_count, errors


_sync_engine_instance = None
def get_airtable_sync_engine() -> AirtableSyncEngine:
    global _sync_engine_instance
    if _sync_engine_instance is None:
        _sync_engine_instance = AirtableSyncEngine()
    return _sync_engine_instance
