"""
Database Configuration Module - Centralized database connection management
Jednolita konfiguracja bazy danych dla całej aplikacji
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env')

class DatabaseConfig:
    """Centralized database configuration"""
    
    def __init__(self):
        # Get database configuration from environment
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD') 
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME')
        
        # Validate configuration
        self._validate_config()
        
        # Build connection string
        self.db_uri = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.db_uri,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False  # Set to True for SQL debugging
        )
        
        logger.info(f"✅ Database configured: {self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}")
    
    def _validate_config(self):
        """Validate that all required configuration is present"""
        required_vars = ['db_user', 'db_password', 'db_host', 'db_name']
        missing_vars = [var for var in required_vars if not getattr(self, var)]
        
        if missing_vars:
            missing_env_vars = [var.upper() for var in missing_vars]
            raise ValueError(f"Missing required database environment variables: {missing_env_vars}")
    
    def get_connection(self):
        """Get a database connection"""
        return self.engine.connect()
    
    def test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                row = result.fetchone()
                if row and row[0] == 1:
                    logger.info("✅ Database connection test successful")
                    return True
                else:
                    logger.error("❌ Database connection test failed - unexpected result")
                    return False
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False
    
    def get_companies_count(self):
        """Get count of companies in database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM companies"))
                row = result.fetchone()
                count = row[0] if row else 0
                logger.info(f"📊 Found {count} companies in database")
                return count
        except Exception as e:
            logger.error(f"❌ Error getting companies count: {e}")
            return 0

# Global database configuration instance
db_config = DatabaseConfig()

def get_database_engine():
    """Get the global database engine"""
    return db_config.engine

def get_database_connection():
    """Get a database connection"""
    return db_config.get_connection()

def test_database_connection():
    """Test database connection"""
    return db_config.test_connection()

def get_database_uri():
    """Get database URI for SQLAlchemy"""
    return db_config.db_uri
