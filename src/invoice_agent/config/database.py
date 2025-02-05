import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

class DatabaseConfig:
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path or 'config/database.yaml'
        self.env = os.getenv('ENVIRONMENT', 'development')
        self._load_config()
        
    def _load_config(self):
        try:
            load_dotenv()
            
            if not Path(self.config_path).exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            if not self.config:
                raise ValueError("Empty configuration file")
            
            self.db_config = self.config.get(self.env, {})
            if not self.db_config:
                raise ValueError(f"No configuration found for environment: {self.env}")
            
            self._replace_env_vars()
            self._validate_config()
            
        except Exception as e:
            self.logger.error(f"Failed to load database config: {str(e)}")
            raise
    
    def _validate_config(self):
        """Validate required configuration settings"""
        required_settings = ['databases', 'pool_size', 'max_overflow']
        for setting in required_settings:
            if setting not in self.db_config:
                raise ValueError(f"Missing required setting: {setting}")
    
    def test_connection(self, db_type: str = 'postgres') -> bool:
        """Test database connection"""
        from sqlalchemy import create_engine
        
        try:
            url = self.get_database_url(db_type)
            if not url:
                return False
            
            engine = create_engine(url, **self.get_pool_settings())
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except SQLAlchemyError as e:
            self.logger.error(f"Database connection test failed: {str(e)}")
            return False
    
    def _replace_env_vars(self):
        """Replace environment variables in database URLs"""
        for db_type, db_conf in self.db_config.get('databases', {}).items():
            url = db_conf.get('url', '')
            if url.startswith('${') and url.endswith('}'):
                env_var = url[2:-1]
                db_conf['url'] = os.getenv(env_var, '')
    
    def get_database_url(self, db_type: str = 'postgres') -> str:
        """Get database URL for specified type"""
        return self.db_config.get('databases', {}).get(db_type, {}).get('url', '')
    
    def get_pool_settings(self) -> Dict[str, Any]:
        """Get database pool settings"""
        return {
            'pool_size': self.db_config.get('pool_size', 5),
            'max_overflow': self.db_config.get('max_overflow', 10),
            'pool_timeout': self.db_config.get('pool_timeout', 30),
            'pool_recycle': self.db_config.get('pool_recycle', 1800),
        }
    
    def get_security_settings(self) -> Dict[str, Any]:
        """Get security settings"""
        return self.config.get('security', {})
    
    def get_backup_settings(self) -> Dict[str, Any]:
        """Get backup settings"""
        return self.config.get('backup', {}) 