import os
import sys
import sqlite3
from pathlib import Path

def get_db_path() -> str:
    app_support = Path.home() / "Library/Application Support/HardwareVerwaltung"
    app_support.mkdir(parents=True, exist_ok=True)
    return str(app_support / "inventory.db")

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            name TEXT NOT NULL,
            serial TEXT NOT NULL UNIQUE,
            purchase_date TEXT,
            location TEXT,
            qr_id TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()
