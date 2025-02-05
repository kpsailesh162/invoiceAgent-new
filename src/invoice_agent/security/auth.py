from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from datetime import datetime, timedelta, date
import json
from cryptography.fernet import Fernet
import os
from pathlib import Path
import secrets
import requests
import streamlit as st
import logging
from urllib.parse import urlencode
import hashlib
import psycopg2
from psycopg2 import Error as PostgresError
from psycopg2.extras import DictCursor
import bcrypt

class AuthenticationProvider(ABC):
    """Base class for authentication providers."""
    
    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate and return credentials."""
        pass
    
    @abstractmethod
    def refresh_token(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh the access token."""
        pass

class OAuthProvider(AuthenticationProvider):
    """Base class for OAuth-based authentication."""
    
    def __init__(self, client_id: str, client_secret: str, scopes: list):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.token_encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for token storage."""
        key_path = Path.home() / '.invoice_agent' / 'token.key'
        key_path.parent.mkdir(parents=True, exist_ok=True)
        
        if key_path.exists():
            return key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            return key
    
    def encrypt_token(self, token_info: Dict[str, Any]) -> str:
        """Encrypt token information."""
        f = Fernet(self.token_encryption_key)
        return f.encrypt(json.dumps(token_info).encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> Dict[str, Any]:
        """Decrypt token information."""
        f = Fernet(self.token_encryption_key)
        return json.loads(f.decrypt(encrypted_token.encode()).decode())

class ServiceAccountProvider(AuthenticationProvider):
    """Base class for service account/API key authentication."""
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def authenticate(self) -> Dict[str, Any]:
        """Return API key credentials."""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "type": "service_account"
        }
    
    def refresh_token(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """No token refresh needed for API keys."""
        return token_info 

class AuthManager:
    def __init__(self):
        """Initialize AuthManager with PostgreSQL database"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # PostgreSQL connection parameters
        self.db_params = {
            'dbname': 'invoice_agent',
            'user': 'sailesh',
            'password': '',
            'host': 'localhost',
            'port': '5432'
        }
        
        # Initialize database
        self._init_db()
    
    def _get_connection(self):
        """Get a PostgreSQL database connection"""
        try:
            return psycopg2.connect(**self.db_params)
        except PostgresError as e:
            self.logger.error(f"Database connection error: {str(e)}")
            raise
    
    def _init_db(self):
        """Initialize the PostgreSQL database with users table"""
        try:
            # First try to connect to the database
            try:
                conn = self._get_connection()
            except PostgresError:
                # If database doesn't exist, create it
                temp_params = self.db_params.copy()
                temp_params['dbname'] = 'postgres'  # Connect to default database
                with psycopg2.connect(**temp_params) as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'invoice_agent'")
                        if not cur.fetchone():
                            cur.execute("CREATE DATABASE invoice_agent")
                # Now connect to the new database
                conn = self._get_connection()
            
            with conn:
                with conn.cursor() as cur:
                    # Create users table if it doesn't exist
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(50) UNIQUE NOT NULL,
                            email VARCHAR(100) UNIQUE NOT NULL,
                            password_hash VARCHAR(256) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP
                        )
                    ''')
            conn.close()
            self.logger.info("Database initialized successfully")
        except PostgresError as e:
            self.logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        # Convert the password to bytes
        password_bytes = password.encode('utf-8')
        # Generate a salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Return the hash as a string
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against a hash using bcrypt"""
        try:
            # Convert strings to bytes for bcrypt
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed.encode('utf-8')
            # Check if the password matches
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            self.logger.error(f"Password verification error: {str(e)}")
            return False
    
    def register_user(self, username: str, email: str, password: str) -> bool:
        """Register a new user"""
        try:
            password_hash = self._hash_password(password)
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                        (username, email, password_hash)
                    )
                    conn.commit()
                    self.logger.info(f"User registered successfully: {username}")
                    return True
                    
        except PostgresError as e:
            if 'unique constraint' in str(e).lower():
                self.logger.warning(f"User registration failed: {username} already exists")
            else:
                self.logger.error(f"User registration error: {str(e)}")
            return False
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user and return user info if successful"""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # First get the stored hash for the user
                    cur.execute(
                        '''
                        SELECT id, username, email, password_hash
                        FROM users 
                        WHERE username = %s
                        ''',
                        (username,)
                    )
                    user = cur.fetchone()
                    
                    if user and self._verify_password(password, user['password_hash']):
                        # Update last login time
                        cur.execute(
                            'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s',
                            (user['id'],)
                        )
                        conn.commit()
                        
                        return {
                            'id': user['id'],
                            'username': user['username'],
                            'email': user['email'],
                            'auth_method': 'local'
                        }
                    
                    return None
                    
        except PostgresError as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return None
    
    def user_exists(self, username: str = None, email: str = None) -> bool:
        """Check if a user exists by username or email"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if username:
                        cur.execute('SELECT 1 FROM users WHERE username = %s', (username,))
                    elif email:
                        cur.execute('SELECT 1 FROM users WHERE email = %s', (email,))
                    else:
                        return False
                        
                    return cur.fetchone() is not None
                    
        except PostgresError as e:
            self.logger.error(f"User check error: {str(e)}")
            return False

auth_manager = AuthManager() 