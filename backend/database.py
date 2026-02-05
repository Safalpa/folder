import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import logging
from config import settings

logger = logging.getLogger(__name__)


class PostgresDB:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                settings.postgres_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            self.conn.autocommit = True  # 🔥 REQUIRED
            logger.info("Connected to PostgreSQL successfully")
        except Exception as e:
            logger.critical(f"PostgreSQL connection failed: {e}")
            raise

    @contextmanager
    def get_cursor(self):
        cursor = self.conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


postgres = PostgresDB()
