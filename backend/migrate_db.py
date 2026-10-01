import sqlite3
import shutil
import os
from datetime import datetime

DB_FILE = 'market_data.db'

def run_migration():
    print("=" * 60)
    print("🚀 SWINGMASTER AI - DATABASE MIGRATION SCRIPT")
    print("=" * 60)

    if not os.path.exists(DB_FILE):
        print(f"⚠️  Database '{DB_FILE}' belum ada. File baru akan dibuat.")
    else:
        # 1. Backup database yang ada di VPS sebelum migrasi
        backup_name = f"{DB_FILE}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copyfile(DB_FILE, backup_name)
        print(f"✅ Backup database tersimpan otomatis di: {backup_name}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 2. Pastikan seluruh tabel terdaftar (CREATE TABLE IF NOT EXISTS)
    print("\n📦 Memeriksa & Menyusun Skema Tabel...")
    
    tables = {
        "daily_prices": """
            CREATE TABLE IF NOT EXISTS daily_prices (
                ticker TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, date)
            )
        """,
        "h1_prices": """
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
        """,
        "h1_Forex_prices": """
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
        """,
        "live_prices": """
            CREATE TABLE IF NOT EXISTS live_prices (
                ticker TEXT PRIMARY KEY,
                price REAL,
                updated_at TIMESTAMP
            )
        """,
        "daily_alerts": """
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
        """,
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                telegram_chat_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "portfolios": """
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                portfolio_type TEXT NOT NULL DEFAULT 'saham',
                initial_capital REAL NOT NULL,
                cash_balance REAL NOT NULL,
                risk_per_trade_pct REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """,
        "active_positions": """
            CREATE TABLE IF NOT EXISTS active_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                buy_date DATE NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                stop_loss REAL,
                target_price REAL,
                position_type TEXT DEFAULT 'LONG',
                FOREIGN KEY (portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE
            )
        """,
        "trade_journals": """
            CREATE TABLE IF NOT EXISTS trade_journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                buy_date DATE NOT NULL,
                sell_date DATE NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                pnl_amount REAL NOT NULL,
                pnl_percentage REAL NOT NULL,
                target_price REAL,
                stop_loss REAL,
                r_multiple REAL,
                psychology_tag TEXT,
                notes TEXT,
                position_type TEXT DEFAULT 'LONG',
                FOREIGN KEY (portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE
            )
        """,
        "equity_history": """
            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                date DATE NOT NULL,
                total_equity REAL NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE,
                UNIQUE(portfolio_id, date)
            )
        """,
        "company_fundamentals": """
            CREATE TABLE IF NOT EXISTS company_fundamentals (
                ticker TEXT PRIMARY KEY,
                pe_ratio REAL,
                pbv_ratio REAL,
                roe REAL,
                der REAL,
                dy REAL,
                updated_at TIMESTAMP
            )
        """,
        "ai_analyses": """
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                model_used TEXT NOT NULL,
                analysis_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, timeframe)
            )
        """
    }

    for table_name, create_sql in tables.items():
        cursor.execute(create_sql)
        print(f"  ✓ Tabel '{table_name}' OK")

    # 3. Safe Column Additions (Mengecek dan menambah kolom yang mungkin belum ada tanpa merusak data)
    print("\n🔍 Memeriksa & Menambahkan Kolom Tambahan (Non-Destructive)...")
    
    def add_column_if_missing(table, column, col_type):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"  + Kolom '{column}' berhasil ditambahkan ke tabel '{table}'")
        else:
            print(f"  ✓ Kolom '{table}.{column}' sudah ada")

    add_column_if_missing("active_positions", "position_type", "TEXT DEFAULT 'LONG'")
    add_column_if_missing("trade_journals", "position_type", "TEXT DEFAULT 'LONG'")
    add_column_if_missing("users", "telegram_chat_id", "TEXT")
    add_column_if_missing("portfolios", "risk_per_trade_pct", "REAL DEFAULT 1.0")

    # 4. Standardisasi Label SMC lama jika ada
    cursor.execute("""
        UPDATE daily_alerts 
        SET strategy_name = REPLACE(strategy_name, 'SMC-Fase1', 'SMC_Reversal_Fase1')
        WHERE strategy_name LIKE '%SMC-Fase1%'
    """)
    cursor.execute("""
        UPDATE daily_alerts 
        SET strategy_name = REPLACE(strategy_name, 'SMC-Fase2', 'SMC_Reversal_Fase2')
        WHERE strategy_name LIKE '%SMC-Fase2%'
    """)

    # 5. Optimasi Indexing untuk Performa Query Cepat
    print("\n⚡ Menyusun Index Database untuk Performa Cepat...")
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

    for idx_sql in indexes:
        cursor.execute(idx_sql)
    print("  ✓ Semua index performa berhasil diverifikasi & dibuat.")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("🎉 MIGRASI SUKSES! Database VPS sudah 100% up-to-date & aman.")
    print("=" * 60)

if __name__ == "__main__":
    run_migration()
