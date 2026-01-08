"""Database connection management for DataWarp v2."""

import os
import psycopg2
from contextlib import contextmanager


@contextmanager
def get_connection():
    """Get PostgreSQL connection with automatic commit/rollback."""
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'datawarp'),
        user=os.getenv('POSTGRES_USER', 'datawarp'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        # Support UK date format (DD/MM/YYYY) in NHS data
        options='-c DateStyle=DMY,ISO'
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
