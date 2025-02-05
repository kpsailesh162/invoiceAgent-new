import streamlit as st
from typing import Optional, Dict, Any
import os
from ..security.auth import AuthenticationProvider
from ..security.oauth_providers import GoogleOAuthProvider, MicrosoftOAuthProvider
from ..security.secrets import SecretsManager
from pathlib import Path

class AuthenticationComponent:
    """Streamlit component for authentication UI."""
    
    def __init__(self):
        self.secrets_manager = SecretsManager()
        
        # Initialize session state
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
        if "auth_method" not in st.session_state:
            st.session_state.auth_method = None
    
    def render_auth_ui(self) -> None:
        """Render the authentication UI."""
        if not st.session_state.authenticated:
            st.header("Connect Email Account")
            
            auth_method = st.selectbox(
                "Select Authentication Method",
                ["Google OAuth", "Microsoft OAuth", "Service Account"],
                key="auth_method_select"
            )
            
            if auth_method == "Google OAuth":
                self._render_google_oauth_ui()
            elif auth_method == "Microsoft OAuth":
                self._render_microsoft_oauth_ui()
            else:
                self._render_service_account_ui()
        else:
            st.success("✓ Connected to email account")
            if st.button("Disconnect"):
                self._handle_logout()
    
    def _render_google_oauth_ui(self) -> None:
        """Render Google OAuth specific UI."""
        st.write("Connect with Google")
        st.write("This will allow the AI agent to:")
        st.write("- Read emails with PDF attachments")
        st.write("- Download invoice attachments")
        
        if st.button("Connect Google Account"):
            try:
                provider = GoogleOAuthProvider(
                    client_id=os.getenv("GOOGLE_CLIENT_ID"),
                    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                    redirect_uri="http://localhost:8501/oauth/callback"
                )
                
                token_info = provider.authenticate()
                encrypted_token = provider.encrypt_token(token_info)
                
                # Store encrypted token
                self.secrets_manager.store_secret(
                    f"google_oauth_{token_info['client_id']}",
                    {"encrypted_token": encrypted_token}
                )
                
                st.session_state.authenticated = True
                st.session_state.auth_method = "google"
                st.success("Successfully connected Google account!")
                st.rerun()
            
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
    
    def _render_microsoft_oauth_ui(self) -> None:
        """Render Microsoft OAuth specific UI."""
        st.write("Connect with Microsoft")
        st.write("This will allow the AI agent to:")
        st.write("- Read emails with PDF attachments")
        st.write("- Download invoice attachments")
        
        if st.button("Connect Microsoft Account"):
            try:
                provider = MicrosoftOAuthProvider(
                    client_id=os.getenv("MICROSOFT_CLIENT_ID"),
                    client_secret=os.getenv("MICROSOFT_CLIENT_SECRET"),
                    tenant_id=os.getenv("MICROSOFT_TENANT_ID")
                )
                
                token_info = provider.authenticate()
                encrypted_token = provider.encrypt_token(token_info)
                
                # Store encrypted token
                self.secrets_manager.store_secret(
                    f"microsoft_oauth_{token_info['client_id']}",
                    {"encrypted_token": encrypted_token}
                )
                
                st.session_state.authenticated = True
                st.session_state.auth_method = "microsoft"
                st.success("Successfully connected Microsoft account!")
                st.rerun()
            
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
    
    def _render_service_account_ui(self) -> None:
        """Render service account specific UI."""
        st.write("Connect with Service Account")
        st.write("For enterprise automation with shared mailboxes")
        
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret (optional)", type="password")
        
        if st.button("Connect Service Account"):
            if not api_key:
                st.error("API Key is required")
                return
            
            try:
                # Store API credentials
                self.secrets_manager.store_secret(
                    "service_account",
                    {
                        "api_key": api_key,
                        "api_secret": api_secret
                    }
                )
                
                st.session_state.authenticated = True
                st.session_state.auth_method = "service_account"
                st.success("Successfully connected service account!")
                st.rerun()
            
            except Exception as e:
                st.error(f"Failed to store credentials: {str(e)}")
    
    def _handle_logout(self) -> None:
        """Handle logout and cleanup."""
        if st.session_state.auth_method == "google":
            self.secrets_manager.store_secret("google_oauth", {})
        elif st.session_state.auth_method == "microsoft":
            self.secrets_manager.store_secret("microsoft_oauth", {})
        elif st.session_state.auth_method == "service_account":
            self.secrets_manager.store_secret("service_account", {})
        
        st.session_state.authenticated = False
        st.session_state.auth_method = None
        st.rerun()
    
    def get_current_credentials(self) -> Optional[Dict[str, Any]]:
        """Get current authentication credentials."""
        if not st.session_state.authenticated:
            return None
        
        if st.session_state.auth_method == "google":
            secret = self.secrets_manager.get_secret("google_oauth")
            if secret and "encrypted_token" in secret:
                provider = GoogleOAuthProvider(
                    client_id=os.getenv("GOOGLE_CLIENT_ID"),
                    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                    redirect_uri="http://localhost:8501/oauth/callback"
                )
                token_info = provider.decrypt_token(secret["encrypted_token"])
                return provider.refresh_token(token_info)
        
        elif st.session_state.auth_method == "microsoft":
            secret = self.secrets_manager.get_secret("microsoft_oauth")
            if secret and "encrypted_token" in secret:
                provider = MicrosoftOAuthProvider(
                    client_id=os.getenv("MICROSOFT_CLIENT_ID"),
                    client_secret=os.getenv("MICROSOFT_CLIENT_SECRET"),
                    tenant_id=os.getenv("MICROSOFT_TENANT_ID")
                )
                token_info = provider.decrypt_token(secret["encrypted_token"])
                return provider.refresh_token(token_info)
        
        elif st.session_state.auth_method == "service_account":
            return self.secrets_manager.get_secret("service_account")
        
        return None 