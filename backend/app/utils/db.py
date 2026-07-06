import os
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Read database URL from env
DATABASE_URL = os.getenv("DATABASE_URL")

# Default SQLite paths
_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "stockgpt.db")
)

def is_postgres() -> bool:
    """Return True if PostgreSQL database URL is configured."""
    return bool(DATABASE_URL)

def q(sql: str) -> str:
    """
    Translate SQL placeholder syntax.
    Converts SQLite '?' placeholders to PostgreSQL '%s' if using PostgreSQL.
    """
    if is_postgres():
        return sql.replace("?", "%s")
    return sql

@contextmanager
def get_db_cursor(sqlite_path: str = _DB_PATH):
    """
    Context manager that yields a cursor and connection.
    Automatically commits or rolls back, and closes the connection.
    Supports both SQLite and PostgreSQL.
    """
    if is_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Open PostgreSQL connection
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor, conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    else:
        # Open SQLite connection
        conn = sqlite3.connect(sqlite_path, timeout=10)
        conn.row_factory = sqlite3.Row
        
        # SQLite journal mode WAL for concurrent write performance
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
            
        cursor = conn.cursor()
        try:
            yield cursor, conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
