from typing import Dict, Any, Optional
import json
from pathlib import Path
import boto3
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from datetime import datetime
import os

class SecretsManager:
    """Manages secure storage and retrieval of authentication credentials."""
    
    def __init__(self, storage_type: str = "file", **kwargs):
        """
        Initialize secrets manager.
        
        Args:
            storage_type: Type of storage ("file", "aws", or "azure")
            **kwargs: Additional arguments for cloud services
        """
        self.storage_type = storage_type
        self.storage_path = Path.home() / '.invoice_agent' / 'secrets'
        
        if storage_type == "aws":
            self.aws_client = boto3.client(
                'secretsmanager',
                region_name=kwargs.get('region_name', 'us-east-1')
            )
        elif storage_type == "azure":
            vault_url = kwargs.get('vault_url')
            if not vault_url:
                raise ValueError("vault_url is required for Azure Key Vault")
            self.azure_client = SecretClient(
                vault_url=vault_url,
                credential=DefaultAzureCredential()
            )
    
    def store_secret(self, key: str, value: Dict[str, Any]) -> None:
        """Store a secret."""
        if self.storage_type == "file":
            self._store_file_secret(key, value)
        elif self.storage_type == "aws":
            self._store_aws_secret(key, value)
        elif self.storage_type == "azure":
            self._store_azure_secret(key, value)
    
    def get_secret(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a secret."""
        if self.storage_type == "file":
            return self._get_file_secret(key)
        elif self.storage_type == "aws":
            return self._get_aws_secret(key)
        elif self.storage_type == "azure":
            return self._get_azure_secret(key)
    
    def _store_file_secret(self, key: str, value: Dict[str, Any]) -> None:
        """Store secret in local file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        secrets = {}
        if self.storage_path.exists():
            with open(self.storage_path, 'r') as f:
                secrets = json.load(f)
        
        secrets[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat()
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(secrets, f)
    
    def _get_file_secret(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret from local file."""
        if not self.storage_path.exists():
            return None
        
        with open(self.storage_path, 'r') as f:
            secrets = json.load(f)
            secret_data = secrets.get(key)
            return secret_data["value"] if secret_data else None
    
    def _store_aws_secret(self, key: str, value: Dict[str, Any]) -> None:
        """Store secret in AWS Secrets Manager."""
        self.aws_client.put_secret_value(
            SecretId=key,
            SecretString=json.dumps(value)
        )
    
    def _get_aws_secret(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret from AWS Secrets Manager."""
        try:
            response = self.aws_client.get_secret_value(SecretId=key)
            return json.loads(response['SecretString'])
        except self.aws_client.exceptions.ResourceNotFoundException:
            return None
    
    def _store_azure_secret(self, key: str, value: Dict[str, Any]) -> None:
        """Store secret in Azure Key Vault."""
        self.azure_client.set_secret(key, json.dumps(value))
    
    def _get_azure_secret(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret from Azure Key Vault."""
        try:
            secret = self.azure_client.get_secret(key)
            return json.loads(secret.value)
        except Exception:
            return None 