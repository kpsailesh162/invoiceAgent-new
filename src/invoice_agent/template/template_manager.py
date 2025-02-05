from typing import Dict, List, Optional
import uuid
from datetime import datetime
import json
from pathlib import Path
from ..config.settings import config

class TemplateManager:
    def __init__(self):
        self.templates = {}
        self.template_dir = config.BASE_DIR / "templates"
        self.template_dir.mkdir(exist_ok=True)
        self._load_templates()
    
    def create_template(self, name: str, template_data: Dict) -> bool:
        """Create a new template with pattern-based fields"""
        try:
            template_id = str(uuid.uuid4())
            
            template = {
                "id": template_id,
                "name": name,
                "patterns": template_data["patterns"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            self.templates[name] = template
            self._save_template(template)
            return True
        except Exception as e:
            print(f"Error creating template: {str(e)}")
            return False
    
    def update_template(self, name: str, template_data: Dict) -> bool:
        """Update an existing template"""
        try:
            if name not in self.templates:
                return False
            
            template = self.templates[name]
            template["patterns"] = template_data["patterns"]
            template["updated_at"] = datetime.now().isoformat()
            
            self._save_template(template)
            return True
        except Exception as e:
            print(f"Error updating template: {str(e)}")
            return False
    
    def delete_template(self, name: str) -> bool:
        """Delete a template by name"""
        try:
            if name not in self.templates:
                return False
            
            template = self.templates[name]
            template_path = self.template_dir / f"{template['id']}.json"
            template_path.unlink(missing_ok=True)
            del self.templates[name]
            return True
        except Exception as e:
            print(f"Error deleting template: {str(e)}")
            return False
    
    def get_template(self, name: str) -> Optional[Dict]:
        """Get template details by name"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List all template names"""
        return list(self.templates.keys())
    
    def _save_template(self, template: Dict) -> None:
        """Save template to file system"""
        template_path = self.template_dir / f"{template['id']}.json"
        with open(template_path, "w") as f:
            json.dump(template, f, indent=2)
    
    def _load_templates(self) -> None:
        """Load all templates from file system"""
        for template_path in self.template_dir.glob("*.json"):
            with open(template_path) as f:
                template = json.load(f)
                self.templates[template["name"]] = template 