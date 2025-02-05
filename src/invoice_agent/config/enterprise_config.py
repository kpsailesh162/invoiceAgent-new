from typing import Dict, Any, Optional
import yaml
import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class SecurityConfig:
    session_timeout: int = 3600  # 1 hour
    max_login_attempts: int = 5
    password_policy: Dict[str, Any] = None
    ip_whitelist: list = None
    cors_origins: list = None
    mfa_required: bool = True

@dataclass
class TenantConfig:
    tenant_id: str
    name: str
    database_url: str
    email_domain: str
    features: Dict[str, bool]
    rate_limits: Dict[str, int]
    storage_quota: int
    admin_emails: list

class EnterpriseConfig:
    """Enterprise-level configuration management."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.env = os.getenv("INVOICE_AGENT_ENV", "development")
        self.config_path = config_path or os.getenv(
            "INVOICE_AGENT_CONFIG",
            str(Path.home() / ".invoice_agent" / "config.yaml")
        )
        self.tenants: Dict[str, TenantConfig] = {}
        self.security = SecurityConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Load environment-specific config
        env_config = config.get('environments', {}).get(self.env, {})
        
        # Load security settings
        security_config = env_config.get('security', {})
        self.security = SecurityConfig(
            session_timeout=security_config.get('session_timeout', 3600),
            max_login_attempts=security_config.get('max_login_attempts', 5),
            password_policy=security_config.get('password_policy', {
                'min_length': 12,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_special': True
            }),
            ip_whitelist=security_config.get('ip_whitelist'),
            cors_origins=security_config.get('cors_origins', ['*']),
            mfa_required=security_config.get('mfa_required', True)
        )
        
        # Load tenant configurations
        for tenant_id, tenant_data in env_config.get('tenants', {}).items():
            self.tenants[tenant_id] = TenantConfig(
                tenant_id=tenant_id,
                name=tenant_data['name'],
                database_url=tenant_data['database_url'],
                email_domain=tenant_data['email_domain'],
                features=tenant_data.get('features', {}),
                rate_limits=tenant_data.get('rate_limits', {
                    'api_calls_per_minute': 60,
                    'uploads_per_day': 1000
                }),
                storage_quota=tenant_data.get('storage_quota', 10 * 1024 * 1024 * 1024),  # 10GB
                admin_emails=tenant_data.get('admin_emails', [])
            )
    
    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get configuration for a specific tenant."""
        return self.tenants.get(tenant_id)
    
    def is_feature_enabled(self, tenant_id: str, feature_name: str) -> bool:
        """Check if a feature is enabled for a tenant."""
        tenant = self.get_tenant_config(tenant_id)
        if not tenant:
            return False
        return tenant.features.get(feature_name, False)
    
    def get_rate_limit(self, tenant_id: str, limit_name: str) -> int:
        """Get rate limit for a tenant."""
        tenant = self.get_tenant_config(tenant_id)
        if not tenant:
            return 0
        return tenant.rate_limits.get(limit_name, 0)
    
    def is_admin(self, tenant_id: str, email: str) -> bool:
        """Check if an email belongs to a tenant admin."""
        tenant = self.get_tenant_config(tenant_id)
        if not tenant:
            return False
        return email in tenant.admin_emails
    
    def validate_email_domain(self, tenant_id: str, email: str) -> bool:
        """Validate if email domain matches tenant's domain."""
        tenant = self.get_tenant_config(tenant_id)
        if not tenant:
            return False
        return email.lower().endswith(f"@{tenant.email_domain.lower()}")
    
    def get_database_url(self, tenant_id: str) -> Optional[str]:
        """Get database URL for a tenant."""
        tenant = self.get_tenant_config(tenant_id)
        if not tenant:
            return None
        return tenant.database_url 