from typing import Dict, Any, List
import jsonschema
from pathlib import Path
import yaml
import json
import logging
from datetime import datetime

class ConfigurationValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.schemas = self._load_schemas()
    
    def _load_schemas(self) -> Dict[str, Any]:
        """Load JSON schemas for configuration validation"""
        schema_dir = Path('config/schemas')
        schemas = {}
        
        for schema_file in schema_dir.glob('*.json'):
            with open(schema_file) as f:
                schemas[schema_file.stem] = json.load(f)
        
        return schemas
    
    def validate_config(
        self,
        config: Dict[str, Any],
        config_type: str
    ) -> List[str]:
        """Validate configuration against schema"""
        try:
            schema = self.schemas.get(config_type)
            if not schema:
                return [f"No schema found for config type: {config_type}"]
            
            jsonschema.validate(instance=config, schema=schema)
            return []
            
        except jsonschema.exceptions.ValidationError as e:
            return [str(e)]
        except Exception as e:
            return [f"Validation error: {str(e)}"]
    
    def validate_all_configs(self) -> Dict[str, List[str]]:
        """Validate all configuration files"""
        config_dir = Path('config')
        results = {}
        
        for config_file in config_dir.glob('*.{yaml,yml,json}'):
            try:
                # Load configuration
                with open(config_file) as f:
                    if config_file.suffix in ['.yaml', '.yml']:
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                
                # Validate
                errors = self.validate_config(
                    config,
                    config_file.stem
                )
                
                if errors:
                    results[config_file.name] = errors
                    
            except Exception as e:
                results[config_file.name] = [f"Failed to load config: {str(e)}"]
        
        return results
    
    def generate_config_report(self) -> str:
        """Generate configuration validation report"""
        results = self.validate_all_configs()
        
        report = f"""
# Configuration Validation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
Total configurations checked: {len(results)}
Configurations with errors: {len([r for r in results.values() if r])}

## Details
"""
        
        for config_file, errors in results.items():
            report += f"\n### {config_file}\n"
            if errors:
                report += "❌ Validation Failed:\n"
                for error in errors:
                    report += f"- {error}\n"
            else:
                report += "✅ Validation Passed\n"
        
        return report 