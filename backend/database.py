import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
from config import settings

logger = logging.getLogger(__name__)

# MongoDB connection
mongo_client = AsyncIOMotorClient(settings.mongo_url)
mongo_db = mongo_client[settings.db_name]

# PostgreSQL connection pool
class PostgresDB:
    def __init__(self):
        self.conn_params = psycopg2.extensions.parse_dsn(settings.postgres_url)
    
    @contextmanager
    def get_cursor(self):
        conn = psycopg2.connect(**self.conn_params)
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def init_schema(self):
        """Initialize PostgreSQL schema"""
        with self.get_cursor() as cursor:
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    display_name VARCHAR(255),
                    email VARCHAR(255),
                    ad_groups TEXT[],
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)
            
            # Files metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    file_path VARCHAR(1000) UNIQUE NOT NULL,
                    filename VARCHAR(500) NOT NULL,
                    file_type VARCHAR(50),
                    size BIGINT,
                    owner_id INTEGER REFERENCES users(id),
                    parent_path VARCHAR(1000),
                    is_folder BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Shares/ACL table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shares (
                    id SERIAL PRIMARY KEY,
                    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                    shared_by INTEGER REFERENCES users(id),
                    shared_with INTEGER REFERENCES users(id),
                    permission VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Audit logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    action VARCHAR(100) NOT NULL,
                    resource VARCHAR(500),
                    details TEXT,
                    ip_address VARCHAR(50),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_owner ON files(owner_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shares_with ON shares(shared_with)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")

postgres = PostgresDB()

# Initialize schema on import
try:
    postgres.init_schema()
    logger.info("Database schema initialized")
except Exception as e:
    logger.error(f"Failed to initialize database schema: {e}")
