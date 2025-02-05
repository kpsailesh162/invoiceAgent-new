import pytest
from pathlib import Path
from invoice_agent.security.auth import AuthManager, OAuthProvider, ServiceAccountProvider
from invoice_agent.workflow.workflow_manager import WorkflowManager
from invoice_agent.templates.template_manager import TemplateManager

class TestAuthFlow:
    def test_google_auth_workflow_access(self, temp_dir, sample_template):
        """Test Google OAuth authentication and workflow access"""
        # Setup components
        auth_manager = AuthManager()
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        
        # Set test directories
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        
        # Authenticate with Google
        auth_result = auth_manager.handle_google_auth()
        assert auth_result["auth_method"] == "Google"
        assert "client_id" in auth_result
        assert "login_time" in auth_result
        
        # Create session data
        session_data = {
            "authenticated": True,
            "user_info": auth_result
        }
        
        # Verify session is valid
        assert auth_manager.validate_session(session_data) == True
        
        # Test workflow access
        workflow_id = workflow_manager.create_workflow(
            invoice_id="test_invoice",
            workflow_type="test_workflow"
        )
        assert workflow_id is not None
        
        # Test template access
        assert template_manager.create_template(
            sample_template["name"],
            sample_template["fields"]
        ) == True
    
    def test_microsoft_auth_workflow_access(self, temp_dir, sample_template):
        """Test Microsoft OAuth authentication and workflow access"""
        # Setup components
        auth_manager = AuthManager()
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        
        # Set test directories
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        
        # Authenticate with Microsoft
        auth_result = auth_manager.handle_microsoft_auth()
        assert auth_result["auth_method"] == "Microsoft"
        assert "client_id" in auth_result
        assert "login_time" in auth_result
        
        # Create session data
        session_data = {
            "authenticated": True,
            "user_info": auth_result
        }
        
        # Verify session is valid
        assert auth_manager.validate_session(session_data) == True
        
        # Test workflow access
        workflow_id = workflow_manager.create_workflow(
            invoice_id="test_invoice",
            workflow_type="test_workflow"
        )
        assert workflow_id is not None
        
        # Test template access
        assert template_manager.create_template(
            sample_template["name"],
            sample_template["fields"]
        ) == True
    
    def test_service_account_workflow_access(self, temp_dir, sample_template):
        """Test service account authentication and workflow access"""
        # Setup components
        auth_manager = AuthManager()
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        
        # Set test directories
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        
        # Authenticate with service account
        service_account_key = "test_service_account_key"
        auth_result = auth_manager.handle_service_account_auth(service_account_key)
        assert auth_result["auth_method"] == "Service Account"
        assert auth_result["client_id"] == service_account_key
        assert "login_time" in auth_result
        
        # Create session data
        session_data = {
            "authenticated": True,
            "user_info": auth_result
        }
        
        # Verify session is valid
        assert auth_manager.validate_session(session_data) == True
        
        # Test workflow access
        workflow_id = workflow_manager.create_workflow(
            invoice_id="test_invoice",
            workflow_type="test_workflow"
        )
        assert workflow_id is not None
        
        # Test template access
        assert template_manager.create_template(
            sample_template["name"],
            sample_template["fields"]
        ) == True
    
    def test_invalid_session_access(self, temp_dir):
        """Test access with invalid session"""
        # Setup components
        auth_manager = AuthManager()
        workflow_manager = WorkflowManager()
        template_manager = TemplateManager()
        
        # Set test directories
        WorkflowManager.workflow_dir = temp_dir / "workflows"
        TemplateManager.template_dir = temp_dir / "templates"
        
        # Test with invalid session data
        invalid_sessions = [
            {},
            {"authenticated": False},
            {"authenticated": True, "user_info": {}},
            {"user_info": {"auth_method": "Invalid"}}
        ]
        
        for session_data in invalid_sessions:
            assert auth_manager.validate_session(session_data) == False 