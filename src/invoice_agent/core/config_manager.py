import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_field_mapping(self) -> Dict[str, str]:
        return self.config.get('field_mapping', {})
    
    def get_validation_rules(self) -> Dict[str, Any]:
        return self.config.get('validation_rules', {})
    
    def get_erp_config(self) -> Dict[str, Any]:
        return self.config.get('erp_config', {}) 