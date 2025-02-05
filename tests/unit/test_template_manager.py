import pytest
from invoice_agent.templates.template_manager import TemplateManager
from pathlib import Path

def test_create_template(sample_template, temp_dir):
    """Test template creation"""
    manager = TemplateManager()
    manager.template_dir = temp_dir
    
    # Test successful creation
    assert manager.create_template(sample_template["name"], sample_template["fields"]) == True
    
    # Test duplicate template
    assert manager.create_template(sample_template["name"], sample_template["fields"]) == False
    
    # Verify file was created
    template_path = temp_dir / f"{sample_template['name']}.json"
    assert template_path.exists()

def test_get_template(sample_template, temp_dir):
    """Test template retrieval"""
    manager = TemplateManager()
    manager.template_dir = temp_dir
    
    # Create template first
    manager.create_template(sample_template["name"], sample_template["fields"])
    
    # Test successful retrieval
    template = manager.get_template(sample_template["name"])
    assert template == sample_template["fields"]
    
    # Test non-existent template
    assert manager.get_template("non_existent") is None

def test_list_templates(sample_template, temp_dir):
    """Test template listing"""
    manager = TemplateManager()
    manager.template_dir = temp_dir
    
    # Create multiple templates
    templates = [
        {"name": "template1", "fields": sample_template["fields"]},
        {"name": "template2", "fields": sample_template["fields"]},
        {"name": "template3", "fields": sample_template["fields"]}
    ]
    
    for template in templates:
        manager.create_template(template["name"], template["fields"])
    
    # Test listing
    template_list = manager.list_templates()
    assert len(template_list) == 3
    assert all(t["name"] in template_list for t in templates)

def test_update_template(sample_template, temp_dir):
    """Test template update"""
    manager = TemplateManager()
    manager.template_dir = temp_dir
    
    # Create template first
    manager.create_template(sample_template["name"], sample_template["fields"])
    
    # Update fields
    updated_fields = sample_template["fields"].copy()
    updated_fields["new_field"] = {"type": "string", "required": False}
    
    # Test successful update
    assert manager.update_template(sample_template["name"], updated_fields) == True
    
    # Verify update
    template = manager.get_template(sample_template["name"])
    assert template == updated_fields
    
    # Test update non-existent template
    assert manager.update_template("non_existent", updated_fields) == False

def test_delete_template(sample_template, temp_dir):
    """Test template deletion"""
    manager = TemplateManager()
    manager.template_dir = temp_dir
    
    # Create template first
    manager.create_template(sample_template["name"], sample_template["fields"])
    
    # Test successful deletion
    assert manager.delete_template(sample_template["name"]) == True
    
    # Verify template was deleted
    template_path = temp_dir / f"{sample_template['name']}.json"
    assert not template_path.exists()
    
    # Test delete non-existent template
    assert manager.delete_template("non_existent") == False 