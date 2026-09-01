import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "bot_data.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            symbol TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            profit_usdt REAL,
            ai_confidence REAL,
            status TEXT
        )
    ''')
    # Таблица логов/статуса
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            message TEXT,
            ai_confidence REAL
        )
    ''')
    conn.commit()
    conn.close()

def get_trades_df():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM trades", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def get_latest_status():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT message, ai_confidence, timestamp FROM bot_status ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"message": row[0], "ai_confidence": row[1], "timestamp": row[2]}
        return None
    except Exception:
        return None
