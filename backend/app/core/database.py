import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# Base database path (can be overridden by environment variable)
DB_PATH = os.getenv("DB_PATH", "market_data.db")

def get_db_connection(timeout: float = 30.0) -> sqlite3.Connection:
    """
    Creates and configures an optimized SQLite connection:
    - High busy timeout (30 seconds) to avoid database locked errors under concurrency.
    - Write-Ahead Logging (WAL) journal mode for concurrent read/write operations.
    - NORMAL synchronous mode for high performance without risking database corruption.
    - Foreign keys enabled.
    """
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db(timeout: float = 30.0) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for safe database transactions.
    Ensures connection is always closed and row_factory is set to sqlite3.Row.
    """
    conn = get_db_connection(timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db_schema():
    """
    Idempotent database schema initialization.
    Executed ONLY ONCE at application startup in lifespan, never during per-request queries.
    """
    logger.info("[DATABASE] Initializing and verifying database schema...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Core Tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_fundamentals (
                ticker TEXT PRIMARY KEY,
                company_name TEXT,
                raw_info_json TEXT,
                pe_ratio REAL,
                pbv_ratio REAL,
                roe REAL,
                der REAL,
                dy REAL,
                updated_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_prices (
                date DATE,
                ticker TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (date, ticker)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS h1_prices (
                ticker TEXT,
                datetime TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, datetime)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS h1_Forex_prices (
                ticker TEXT,
                datetime TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, datetime)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_prices (
                ticker TEXT PRIMARY KEY,
                price REAL,
                updated_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                signal_date DATE NOT NULL,
                price_at_signal REAL NOT NULL,
                target_price REAL,
                stop_loss REAL,
                status TEXT DEFAULT 'open'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password TEXT,
                telegram_chat_id TEXT,
                telegram_username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                portfolio_type TEXT DEFAULT 'saham',
                initial_capital REAL DEFAULT 100000000,
                cash_balance REAL DEFAULT 100000000,
                initial_balance REAL DEFAULT 100000000,
                current_balance REAL DEFAULT 100000000,
                risk_per_trade_pct REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                sector TEXT,
                buy_date DATE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                entry_price REAL DEFAULT 0,
                buy_price REAL DEFAULT 0,
                shares INTEGER DEFAULT 0,
                total_lot INTEGER DEFAULT 0,
                stop_loss REAL,
                target_sl REAL,
                target_price REAL,
                target_tp REAL,
                position_type TEXT DEFAULT 'LONG',
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                buy_date DATE DEFAULT CURRENT_TIMESTAMP,
                sell_date DATE DEFAULT CURRENT_TIMESTAMP,
                close_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entry_price REAL DEFAULT 0,
                buy_price REAL DEFAULT 0,
                exit_price REAL DEFAULT 0,
                sell_price REAL DEFAULT 0,
                shares INTEGER DEFAULT 0,
                total_lot INTEGER DEFAULT 0,
                pnl_amount REAL NOT NULL DEFAULT 0,
                pnl_percentage REAL NOT NULL DEFAULT 0,
                status TEXT DEFAULT 'CLOSED',
                target_price REAL,
                stop_loss REAL,
                r_multiple REAL,
                psychology_tag TEXT,
                tag TEXT,
                notes TEXT,
                position_type TEXT DEFAULT 'LONG',
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                date DATE NOT NULL,
                total_equity REAL NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
                UNIQUE(portfolio_id, date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timeframe TEXT DEFAULT 'D1',
                model_used TEXT DEFAULT 'gemini-2.5-flash',
                analysis_text TEXT,
                date DATE,
                skor_akumulasi REAL,
                skor_sentimen INTEGER,
                matriks_strategi TEXT,
                konfirmasi_tren_mingguan TEXT,
                rekomendasi_buy TEXT,
                take_profit INTEGER,
                stop_loss INTEGER,
                risk_reward_ratio TEXT,
                alasan_analisis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, timeframe)
            )
        ''')

        # 2. Performance Indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_daily_alerts_date ON daily_alerts(signal_date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_alerts_ticker ON daily_alerts(ticker)",
            "CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices(ticker, date)",
            "CREATE INDEX IF NOT EXISTS idx_h1_prices_ticker_dt ON h1_prices(ticker, datetime)",
            "CREATE INDEX IF NOT EXISTS idx_forex_h1_ticker_dt ON h1_Forex_prices(ticker, datetime)",
            "CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_active_pos_port ON active_positions(portfolio_id)",
            "CREATE INDEX IF NOT EXISTS idx_journals_port ON trade_journals(portfolio_id)"
        ]
        for idx in indexes:
            cursor.execute(idx)

        conn.commit()
        logger.info("[DATABASE] Schema verification and index creation completed successfully.")
    except Exception as e:
        logger.error(f"[DATABASE] Error during schema initialization: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
