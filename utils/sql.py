import logging
import pandas as pd
from pathlib import Path
from typing import Optional
import psycopg2
from sshtunnel import SSHTunnelForwarder
from typing import Optional
from contextlib import contextmanager

from utils.config import ServiceConfig
from utils.logger import get_logger

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Gestionnaire de connexion a PostgreSQL via tunnel SSH
    """
    
    def __init__(self):
        self.tunnel: Optional[SSHTunnelForwarder] = None
        self.connection: Optional[psycopg2.extensions.connection] = None
    
    def start_ssh_tunnel(self) -> SSHTunnelForwarder:
        """
        Demarre le tunnel SSH
        
        Returns:
            Instance du tunnel SSH
        """
        if self.tunnel and self.tunnel.is_active:
            return self.tunnel
        
        try:
            config = ServiceConfig()
            self.tunnel = SSHTunnelForwarder(
                (config.DB_SSH_HOST, config.DB_SSH_PORT),
                ssh_username=config.DB_SSH_USERNAME,
                ssh_password=config.DB_SSH_PASSWORD,
                remote_bind_address=(config.DB_SQL_HOST, config.DB_SQL_PORT),
                local_bind_address=('127.0.0.1', 0),
                host_pkey_directories=[],
                allow_agent=False
            )
            self.tunnel.start()
            return self.tunnel
        
        except Exception as e:
            raise
    
    def stop_ssh_tunnel(self):
        """Arrete le tunnel SSH"""
        if self.tunnel and self.tunnel.is_active:
            self.tunnel.stop()
            self.tunnel = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """
        Etablit la connexion a PostgreSQL via le tunnel SSH
        
        Returns:
            Connexion PostgreSQL
        """
        if not self.tunnel or not self.tunnel.is_active:
            self.start_ssh_tunnel()
        
        try:
            config = ServiceConfig()
            self.connection = psycopg2.connect(
                host='127.0.0.1',
                port=self.tunnel.local_bind_port,
                database=config.DB_SQL_NAME,
                user=config.DB_SQL_USERNAME,
                password=config.DB_SQL_PASSWORD
            )
            return self.connection
        
        except Exception as e:
            self.stop_ssh_tunnel()
            raise
    
    def disconnect(self):
        """Ferme la connexion et le tunnel SSH"""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        self.stop_ssh_tunnel()
    
    @contextmanager
    def get_connection(self):
        try:
            conn = self.connect()
            yield conn
        finally:
            pass
    
    def __enter__(self):
        """Support du context manager"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support du context manager"""
        self.disconnect()


class QueryExecutor:
    def __init__(self):
        self.db_connection = DatabaseConnection()
    
    def execute_query(self, sql: str) -> pd.DataFrame:
        try:
            with self.db_connection.get_connection() as conn:
                df = pd.read_sql(sql, conn)
                return df
        except Exception as e:
            raise
    
    def execute_query_from_file(self, file_path: Path) -> pd.DataFrame:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier SQL introuvable: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            return self.execute_query(sql)
        except Exception as e:
            raise
    

class SqlFetcher:

    def __init__(self):
        self._query_executor: Optional[QueryExecutor] = None
        self.logger = get_logger("SqlFetcher")

    def _get_query_executor(self):
        if self._query_executor is None:
            self._query_executor = QueryExecutor()
        return self._query_executor

    def fetch(self, source: dict) -> pd.DataFrame:
        try:
            sql_file = source.get("sql_file")
            qe = self._get_query_executor()
            df = qe.execute_query_from_file(f"{Path(__file__).parent.parent}/si_queries/{sql_file}")
            for col in df.columns:
                if col.startswith("date_"):
                    df[col] = pd.to_datetime(df[col], utc=True)
            return df
        except Exception as e:
            self.logger.error(e)

sql_fetcher = None
def get_sql_fetcher() -> SqlFetcher:
    global sql_fetcher
    if sql_fetcher is None:
        sql_fetcher = SqlFetcher()
    return sql_fetcher