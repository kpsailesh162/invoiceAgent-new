from typing import Dict, Any, List
import json
from pathlib import Path
import os
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class MatchingThresholds:
    AMOUNT_TOLERANCE: float = 0.01  # 1% tolerance for amount matching
    CONFIDENCE_THRESHOLD: float = 0.85  # Minimum confidence score
    HIGH_CONFIDENCE_THRESHOLD: float = 0.95  # High confidence threshold
    PARTIAL_MATCH_MAX_DISCREPANCIES: int = 2  # Maximum discrepancies for partial match
    LINE_ITEM_QUANTITY_TOLERANCE: int = 0  # Tolerance for quantity differences
    PRICE_TOLERANCE_PERCENTAGE: float = 0.001  # 0.1% tolerance for price differences

@dataclass
class ProcessingLimits:
    MAX_BATCH_SIZE: int = 100  # Maximum invoices in a batch
    MAX_FILE_SIZE_MB: int = 25  # Maximum file size in MB
    SUPPORTED_FORMATS: tuple = ("pdf", "csv", "xlsx", "docx")
    PROCESSING_TIMEOUT: timedelta = timedelta(minutes=5)
    MAX_RETRIES: int = 3  # Maximum processing retries
    RETRY_DELAY: int = 1  # seconds
    POLL_INTERVAL: int = 5  # seconds
    MIN_CONFIDENCE_SCORE: float = 0.8

@dataclass
class SecuritySettings:
    REQUIRED_ROLES: tuple = ("invoice_processor", "finance_manager", "admin")
    ENCRYPTION_ENABLED: bool = True
    AUDIT_LOGGING_ENABLED: bool = True
    DATA_RETENTION_DAYS: int = 90
    SENSITIVE_FIELDS: tuple = ("tax_id", "bank_account", "credit_card")

@dataclass
class ValidationRules:
    REQUIRED_FIELDS: List[str] = None
    DATE_FORMAT: str = "%Y-%m-%d"
    CURRENCY_FORMATS: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.REQUIRED_FIELDS is None:
            self.REQUIRED_FIELDS = [
                "invoice_number",
                "invoice_date",
                "vendor_info.id",
                "vendor_info.name",
                "po_number",
                "total_amount",
                "currency"
            ]
        if self.CURRENCY_FORMATS is None:
            self.CURRENCY_FORMATS = {
                "USD": {"symbol": "$", "decimal_places": 2, "thousand_separator": ","},
                "EUR": {"symbol": "€", "decimal_places": 2, "thousand_separator": "."},
                "GBP": {"symbol": "£", "decimal_places": 2, "thousand_separator": ","},
                "JPY": {"symbol": "¥", "decimal_places": 0, "thousand_separator": ","}
            }

class Config:
    def __init__(self):
        # Base paths
        self.BASE_DIR = Path(__file__).parent.parent.parent.parent
        self.UPLOAD_DIR = self.BASE_DIR / "uploads"
        self.LOG_DIR = self.BASE_DIR / "logs"
        
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Logging configuration
        self.LOG_FILE = self.LOG_DIR / "workflow.log"
        self.LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.LOG_LEVEL = "INFO"
        
        # API endpoints
        self.API_BASE_URL = "http://localhost:8000"
        self.API_VERSION = "v1"
        
        # Database configuration
        self.DB_CONFIG = {
            "host": "localhost",
            "port": 5432,
            "database": "invoice_db",
            "user": "invoice_user",
            "password": "invoice_pass"
        }
        
        # Redis configuration
        self.REDIS_CONFIG = {
            "host": "localhost",
            "port": 6379,
            "db": 0
        }
        
        # Initialize settings classes
        self.matching = MatchingThresholds()
        self.processing = ProcessingLimits()
        self.security = SecuritySettings()
        self.validation = ValidationRules()
        
        # Feature flags
        self.FEATURE_FLAGS = {
            "advanced_matching": True,
            "ml_extraction": True,
            "blockchain_verification": False,
            "automated_approval": False
        }
    
    def load_from_env(self):
        """Load configuration from environment variables"""
        # API configuration
        self.API_BASE_URL = os.getenv('INVOICE_API_BASE_URL', self.API_BASE_URL)
        
        # Database configuration
        self.DB_CONFIG.update({
            "host": os.getenv('INVOICE_DB_HOST', self.DB_CONFIG["host"]),
            "port": int(os.getenv('INVOICE_DB_PORT', self.DB_CONFIG["port"])),
            "database": os.getenv('INVOICE_DB_NAME', self.DB_CONFIG["database"]),
            "user": os.getenv('INVOICE_DB_USER', self.DB_CONFIG["user"]),
            "password": os.getenv('INVOICE_DB_PASS', self.DB_CONFIG["password"])
        })
        
        # Redis configuration
        self.REDIS_CONFIG.update({
            "host": os.getenv('INVOICE_REDIS_HOST', self.REDIS_CONFIG["host"]),
            "port": int(os.getenv('INVOICE_REDIS_PORT', self.REDIS_CONFIG["port"])),
            "db": int(os.getenv('INVOICE_REDIS_DB', self.REDIS_CONFIG["db"]))
        })
    
    @property
    def environment(self) -> str:
        """Get current environment"""
        return os.getenv("INVOICE_AGENT_ENV", "development")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"
    
    def get_feature_flag(self, feature_name: str) -> bool:
        """Get feature flag status"""
        return self.FEATURE_FLAGS.get(feature_name, False)

class EnterpriseConfig(Config):
    def __init__(self):
        super().__init__()
        # Override with enterprise-specific settings
        self.matching.CONFIDENCE_THRESHOLD = 0.90  # Higher threshold for enterprise
        self.matching.HIGH_CONFIDENCE_THRESHOLD = 0.98
        self.matching.PARTIAL_MATCH_MAX_DISCREPANCIES = 1  # Stricter matching
        self.matching.AMOUNT_TOLERANCE = 0.005  # 0.5% tolerance
        self.matching.PRICE_TOLERANCE_PERCENTAGE = 0.0005  # 0.05% tolerance
        
        # Enterprise-specific feature flags
        self.FEATURE_FLAGS.update({
            "advanced_matching": True,
            "ml_extraction": True,
            "blockchain_verification": True,
            "automated_approval": True
        })
        
        # Enterprise validation rules
        self.validation.REQUIRED_FIELDS.extend([
            "cost_center",
            "department_code",
            "tax_code",
            "payment_terms"
        ])

# Create global config instances
config = Config()
config.load_from_env()

enterprise_config = EnterpriseConfig()
enterprise_config.load_from_env() 