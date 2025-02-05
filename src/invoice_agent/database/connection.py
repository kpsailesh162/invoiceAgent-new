from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from ..config.database import DatabaseConfig
import os

# Create database directory if it doesn't exist
DB_DIR = "data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

# Database URL
DATABASE_URL = f"sqlite:///{DB_DIR}/invoice_agent.db"

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = sessionmaker(bind=engine)

def get_database_session():
    """Get a database session."""
    return Session()

class DatabaseConnection:
    def __init__(self, db_config: DatabaseConfig):
        self.db_config = db_config
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        url = self.db_config.get_database_url()
        pool_settings = self.db_config.get_pool_settings()
        
        self.engine = create_engine(
            url,
            **pool_settings,
            echo=self.db_config.db_config.get('echo', False)
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close() 