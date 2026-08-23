"""
database.py — thin data-access layer for the inventory system.

Ships configured for SQLite (zero setup, runs anywhere) but is written
so that switching to PostgreSQL or MySQL only means:
  1. pip install psycopg2-binary   (Postgres)  or  pymysql   (MySQL)
  2. set DB_ENGINE=postgresql|mysql in config.py / environment
  3. run schema_postgresql.sql or schema_mysql.sql against your server
The rest of the application (app.py) only calls the functions below,
never raw SQL directly, so the engine swap is contained here.
"""

import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite")  # sqlite | postgresql | mysql


def get_raw_connection():
    """Return a raw connection for the configured engine.

    Only 'sqlite' is wired up by default (no extra install required).
    Postgres/MySQL branches are included so the code is a drop-in
    once the corresponding driver is installed in your environment.
    """
    if DB_ENGINE == "sqlite":
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    if DB_ENGINE == "postgresql":
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            dbname=os.environ.get("DB_NAME", "inventory"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        return conn

    if DB_ENGINE == "mysql":
        import pymysql
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            db=os.environ.get("DB_NAME", "inventory"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            cursorclass=pymysql.cursors.DictCursor,
        )
        return conn

    raise RuntimeError(f"Unsupported DB_ENGINE: {DB_ENGINE}")


@contextmanager
def get_db():
    """Context manager yielding a connection; commits/rolls back and closes."""
    conn = get_raw_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist yet (idempotent)."""
    if DB_ENGINE != "sqlite":
        # For Postgres/MySQL, run schema_postgresql.sql / schema_mysql.sql
        # directly against the server ahead of time (see README).
        return
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    with get_db() as conn:
        conn.executescript(schema)


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)  # already dict-like for psycopg2 RealDictCursor / pymysql DictCursor


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]
