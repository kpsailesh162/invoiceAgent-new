import yaml
from pathlib import Path
from typing import Dict, Any

def load_config(config_path: str = None) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if not config_path:
        config_path = Path(__file__).parent / 'default_config.yaml'
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_environment_config(environment: str = 'development') -> Dict[str, Any]:
    """Get configuration for specific environment"""
    config = load_config()
    return config['environments'].get(environment, config['environments']['development']) 