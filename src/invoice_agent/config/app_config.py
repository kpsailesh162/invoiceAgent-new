import os
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseSettings, Field
from functools import lru_cache

class AppSettings(BaseSettings):
    """Application settings with environment variable support"""
    # App Configuration
    APP_NAME: str = "Invoice Processing Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    API_CORS_ORIGINS: list = ["*"]
    API_RATE_LIMIT: int = 100
    API_RATE_LIMIT_PERIOD: int = 60
    
    # Security
    SECRET_KEY: str = Field(..., env='JWT_SECRET_KEY')
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    
    # OCR Settings
    OCR_CONFIDENCE_THRESHOLD: float = 0.85
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Batch Processing
    BATCH_SIZE: int = 100
    MAX_WORKERS: int = 4
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings() 