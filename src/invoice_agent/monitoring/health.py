import psutil
import time
from typing import Dict, Any
from sqlalchemy.orm import Session

class HealthCheck:
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def check_system_health(self) -> Dict[str, Any]:
        return {
            'database': self._check_database(),
            'system': self._check_system_resources(),
            'disk': self._check_disk_usage(),
            'memory': self._check_memory_usage()
        }
    
    def _check_database(self) -> Dict[str, Any]:
        try:
            start_time = time.time()
            self.db_session.execute("SELECT 1")
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time': response_time
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        return {
            'cpu_usage': psutil.cpu_percent(),
            'cpu_count': psutil.cpu_count(),
            'load_average': psutil.getloadavg()
        }
    
    def _check_disk_usage(self) -> Dict[str, Any]:
        disk = psutil.disk_usage('/')
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent
        }
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent,
            'used': memory.used,
            'free': memory.free
        } 