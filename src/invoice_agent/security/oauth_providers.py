from typing import Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import msal
import requests
from datetime import datetime, timedelta
from .auth import OAuthProvider

class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth implementation."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        super().__init__(client_id, client_secret, scopes)
        self.redirect_uri = redirect_uri
    
    def authenticate(self) -> Dict[str, Any]:
        """Perform Google OAuth authentication."""
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            self.scopes
        )
        
        # Run local server for auth callback
        credentials = flow.run_local_server(port=0)
        
        token_info = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat(),
            "type": "google_oauth"
        }
        
        return token_info
    
    def refresh_token(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh Google OAuth token."""
        credentials = Credentials(
            token=token_info["token"],
            refresh_token=token_info["refresh_token"],
            token_uri=token_info["token_uri"],
            client_id=token_info["client_id"],
            client_secret=token_info["client_secret"],
            scopes=token_info["scopes"]
        )
        
        if credentials.expired:
            credentials.refresh(Request())
            
            token_info.update({
                "token": credentials.token,
                "expiry": credentials.expiry.isoformat()
            })
        
        return token_info

class MicrosoftOAuthProvider(OAuthProvider):
    """Microsoft OAuth implementation."""
    
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        scopes = [
            'https://graph.microsoft.com/Mail.Read',
            'https://graph.microsoft.com/Mail.ReadWrite'
        ]
        super().__init__(client_id, client_secret, scopes)
        self.tenant_id = tenant_id
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
    
    def authenticate(self) -> Dict[str, Any]:
        """Perform Microsoft OAuth authentication."""
        app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority
        )
        
        # Trigger interactive login
        result = app.acquire_token_interactive(scopes=self.scopes)
        
        if "error" in result:
            raise Exception(f"Authentication failed: {result.get('error_description')}")
        
        token_info = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_in": result["expires_in"],
            "scope": result["scope"],
            "token_type": result["token_type"],
            "expires_at": (datetime.now() + timedelta(seconds=result["expires_in"])).isoformat(),
            "type": "microsoft_oauth"
        }
        
        return token_info
    
    def refresh_token(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh Microsoft OAuth token."""
        app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority
        )
        
        expires_at = datetime.fromisoformat(token_info["expires_at"])
        if datetime.now() >= expires_at:
            result = app.acquire_token_by_refresh_token(
                token_info["refresh_token"],
                scopes=self.scopes
            )
            
            if "error" in result:
                raise Exception(f"Token refresh failed: {result.get('error_description')}")
            
            token_info.update({
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token", token_info["refresh_token"]),
                "expires_in": result["expires_in"],
                "expires_at": (datetime.now() + timedelta(seconds=result["expires_in"])).isoformat()
            })
        
        return token_info 