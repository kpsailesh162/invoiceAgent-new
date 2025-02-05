import boto3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

class DatabaseBackup:
    def __init__(self, db_config: dict):
        self.logger = logging.getLogger(__name__)
        self.config = db_config
        self.s3_client = boto3.client('s3')
    
    def create_backup(self, db_type: str = 'postgres') -> bool:
        try:
            backup_path = self._perform_backup(db_type)
            if backup_path:
                return self._upload_to_s3(backup_path)
            return False
        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")
            return False
    
    def _perform_backup(self, db_type: str) -> Optional[Path]:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        
        if db_type == 'postgres':
            return self._backup_postgres(backup_dir, timestamp)
        elif db_type == 'mysql':
            return self._backup_mysql(backup_dir, timestamp)
        elif db_type == 'oracle':
            return self._backup_oracle(backup_dir, timestamp)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _upload_to_s3(self, backup_path: Path) -> bool:
        try:
            bucket = self.config['storage']['bucket']
            s3_path = f"{self.config['storage']['path']}/{backup_path.name}"
            
            self.s3_client.upload_file(
                str(backup_path),
                bucket,
                s3_path
            )
            return True
        except Exception as e:
            self.logger.error(f"S3 upload failed: {str(e)}")
            return False 