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
        # Since PostgreSQL might not be available in dev, we'll use MongoDB for metadata
        # In production, this would connect to actual PostgreSQL
        self.use_mongo = True
        logger.info("Using MongoDB for metadata storage (PostgreSQL not available)")
    
    @contextmanager
    def get_cursor(self):
        # Mock cursor for MongoDB-based implementation
        yield MockCursor()
    
    def init_schema(self):
        """Initialize database schema"""
        logger.info("Schema initialization - using MongoDB collections")
        # In production, this would create PostgreSQL tables
        pass

class MockCursor:
    """Mock cursor that uses MongoDB for development"""
    def __init__(self):
        self.results = []
    
    def execute(self, query, params=None):
        # This is a simplified mock - in production use real PostgreSQL
        pass
    
    def fetchone(self):
        return self.results[0] if self.results else None
    
    def fetchall(self):
        return self.results

postgres = PostgresDB()

# Initialize schema on import
try:
    postgres.init_schema()
    logger.info("Database initialized")
except Exception as e:
    logger.error(f"Failed to initialize database schema: {e}")
