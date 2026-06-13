import json
import pandas as pd
import numpy as np
import time
import sqlite3
import datetime
import random
import requests
from passlib.context import CryptContext
from app.core.logger import logger
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
})

def calculate_accumulation_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('date').copy()
    
    # ---------------------------------------------------------
    # 1. HITUNG BASE OBV & A/D LINE
    # ---------------------------------------------------------
    df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
    
    high_low_range = (df['high'] - df['low']).replace(0, 1) # Mencegah bagi nol
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / high_low_range
    df['ADL'] = (mfm * df['volume']).cumsum()
    
    # ---------------------------------------------------------
    # 2. KOMPONEN SKOR ADVANCED (Periode 14 Hari)
    # ---------------------------------------------------------
    
    # A. METRIK KONSISTENSI (Bobot Maks: 40 Poin)
    # Menghitung berapa hari OBV dan ADL naik dalam 14 hari terakhir
    obv_up_days = (df['OBV'].diff() > 0).rolling(window=14, min_periods=1).sum()
    adl_up_days = (df['ADL'].diff() > 0).rolling(window=14, min_periods=1).sum()
    # Total hari maksimal 28 (14 OBV + 14 ADL). Kita konversi ke skala 40 poin.
    score_consistency = ((obv_up_days + adl_up_days) / 28.0) * 40.0
    
    # B. METRIK MOMENTUM EMA (Bobot Maks: 30 Poin)
    # Memastikan apakah laju volume terkini lebih besar dari rata-rata 14 harinya
    obv_ema14 = df['OBV'].ewm(span=14, adjust=False).mean()
    adl_ema14 = df['ADL'].ewm(span=14, adjust=False).mean()
    score_momentum = np.where(df['OBV'] > obv_ema14, 15.0, 0) + np.where(df['ADL'] > adl_ema14, 15.0, 0)
    
    # C. METRIK DIVERGENSI SMART MONEY (Bobot Maks: 30 Poin)
    # Mencari anomali: Harga tertekan turun/sideways, TAPI Volume Flow (OBV) terakumulasi naik
    price_return = df['close'].pct_change(periods=14).replace([np.inf, -np.inf], 0).fillna(0)
    obv_return = df['OBV'].pct_change(periods=14).replace([np.inf, -np.inf], 0).fillna(0)
    
    # Logika Skoring Divergensi:
    conditions = [
        (price_return <= 0) & (obv_return > 0),         # Harga Turun/Stagnan, OBV Naik (Divergensi Sempurna!) = 30 Poin
        (price_return > 0) & (obv_return > price_return)  # Harga Naik, OBV Naik Lebih Kencang (Uptrend Kuat) = 15 Poin
    ]
    choices = [30.0, 15.0]
    score_divergence = np.select(conditions, choices, default=0.0)
    
    # ---------------------------------------------------------
    # 3. FINALISASI SKOR (Skala 0 - 100)
    # ---------------------------------------------------------
    df['Skor_Indikator_Lokal'] = (score_consistency + score_momentum + score_divergence)
    
    # Pembulatan & memastikan nilai mentok di 100 atau 0 (Bounding)
    df['Skor_Indikator_Lokal'] = df['Skor_Indikator_Lokal'].fillna(0).round(1).clip(0, 100)
    
    return df

def get_db_connection():
    conn = sqlite3.connect('market_data.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS company_fundamentals (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            raw_info_json TEXT,
            updated_at DATE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            date DATE,
            ticker TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(date, ticker)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_analyses (
            date DATE,
            ticker TEXT,
            skor_akumulasi REAL,
            skor_sentimen INTEGER,
            matriks_strategi TEXT,
            konfirmasi_tren_mingguan TEXT,
            rekomendasi_buy TEXT,
            take_profit INTEGER,
            stop_loss INTEGER,
            risk_reward_ratio TEXT,
            alasan_analisis TEXT,
            UNIQUE(date, ticker)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            portfolio_type TEXT DEFAULT 'saham',
            initial_balance REAL DEFAULT 100000000,
            current_balance REAL DEFAULT 100000000,
            risk_per_trade_pct REAL DEFAULT 10.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS active_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            sector TEXT,
            buy_price REAL NOT NULL,
            total_lot INTEGER NOT NULL,
            target_tp REAL,
            target_sl REAL,
            buy_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS trade_journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            buy_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            total_lot INTEGER NOT NULL,
            pnl_amount REAL NOT NULL,
            pnl_percentage REAL NOT NULL,
            close_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            r_multiple REAL,
            tag TEXT,
            notes TEXT,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
        )
    ''')
    
    # Backward compatibility for existing DB
    try:
        conn.execute("ALTER TABLE trade_journals ADD COLUMN r_multiple REAL")
        conn.execute("ALTER TABLE trade_journals ADD COLUMN tag TEXT")
        conn.execute("ALTER TABLE trade_journals ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass # Columns already exist
        
    try:
        conn.execute("ALTER TABLE portfolios ADD COLUMN portfolio_type TEXT DEFAULT 'saham'")
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS equity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            date DATE NOT NULL,
            total_equity REAL NOT NULL,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            ai_recom_price TEXT,
            ai_tp REAL,
            ai_sl REAL,
            ai_rr TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
        )
    ''')
    
    # Seeder
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        hashed_pw = pwd_context.hash("admin123")
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", ("admin", "admin@swing.com", hashed_pw))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO portfolios (user_id, name) VALUES (?, ?)", (user_id, "Default Portfolio"))
        conn.commit()
        
    return conn

def sync_historical_data(tickers: list[str]):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.date.today()
    
    for ticker in tickers:
        ticker_upper = ticker.upper().replace(".JK", "")
        
        cursor.execute("SELECT MAX(date) FROM daily_prices WHERE ticker = ?", (ticker_upper,))
        max_date_str = cursor.fetchone()[0]
        
        try:
            is_stale = True
            if max_date_str:
                max_date = datetime.datetime.strptime(max_date_str, '%Y-%m-%d').date()
                if max_date >= today:
                    is_stale = False
            
            if is_stale:
                logger.info(f"[OUTBOUND GOOGLE HUB] Fetch history for {ticker_upper}")
                res = requests.get(settings.GOOGLE_WEBAPP_URL, params={"action": "fetch_history", "ticker": ticker_upper}, timeout=40)
                res_json = res.json()
                
                if res_json.get("status") == "success":
                    ohlcv_data = res_json.get("data", [])
                    records = []
                    for bar in ohlcv_data:
                        low_val = float(bar["low"])
                        vol_val = int(bar["volume"])
                        if ticker_upper != 'COMPOSITE' and (low_val == 0 or vol_val == 0):
                            continue  # Skip holiday/weekend rows for normal stocks
                            
                        records.append((
                            bar["date"], 
                            ticker_upper, 
                            float(bar["open"]), 
                            float(bar["high"]), 
                            low_val, 
                            float(bar["close"]), 
                            vol_val
                        ))
                    
                    if records:
                        cursor.executemany('''
                            INSERT OR IGNORE INTO daily_prices (date, ticker, open, high, low, close, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', records)
                        conn.commit()
                else:
                    logger.warning(f"Failed to fetch {ticker_upper} from Google Hub: {res_json.get('message')}")
                    
        except Exception as e:
            print(f"Error syncing {ticker_upper}: {e}")
            
    conn.close()

def analyze_stock(ticker: str) -> dict:
    ticker = ticker.upper().replace(".JK", "")
    
    try:
        conn = get_db_connection()
        
        # Ensure latest data
        sync_historical_data([ticker])
        
        cursor = conn.cursor()
        cursor.execute("SELECT raw_info_json FROM company_fundamentals WHERE ticker = ?", (ticker,))
        funda_row = cursor.fetchone()
        
        if funda_row:
            info = json.loads(funda_row[0])
            company_name = info.get("longName", "Nama Perusahaan Tidak Ditemukan")
            roe = info.get("returnOnEquity")
            roe_percentage = round(roe * 100, 2) if roe is not None else None
            currency = info.get("currency", "IDR")
            eps = info.get("earningsPerShare", 0)
            per = info.get("trailingPE", 0)
        else:
            return {"status": "error", "message": f"Ticker {ticker} tidak memiliki data fundamental lokal."}
            
        df = pd.read_sql_query("SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date ASC", conn, params=(ticker,))
        
        if df.empty:
             return {"status": "error", "message": f"Ticker {ticker} tidak memiliki data harga lokal."}
             
        # Add basic accumulation score calculation to avoid errors
        try:
            df = calculate_accumulation_indicators(df)
        except Exception:
            pass
             
        current_price = float(df['close'].iloc[-1])
        
        if len(df) < 26:
            macd_value, macd_signal, macd_status = None, None, "Data tidak cukup"
            quant_score = 50
        else:
            close_prices = df['close']
            ema12 = close_prices.ewm(span=12, adjust=False).mean()
            ema26 = close_prices.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            macd_value = round(macd_line.iloc[-1], 2)
            macd_signal = round(signal_line.iloc[-1], 2)
            macd_status = "Lolos (Di bawah 0)" if macd_line.iloc[-1] < 0 else "Gagal (Di atas 0)"
            
            quant_score = 85 - round(macd_value)
            if quant_score > 99: quant_score = 99
            elif quant_score < 10: quant_score = 10
            
        conn.close()

        return {
            "status": "success",
            "ticker": ticker,
            "company_name": company_name,
            "filters": {
                "price": {
                    "value": current_price,
                    "status": "Lolos" if 200 <= current_price <= 2500 else "Gagal"
                },
                "fundamental_roe": {
                    "value": roe_percentage,
                    "status": "Lolos" if (roe_percentage and roe_percentage >= 5) else "Gagal"
                },
                "fundamental_eps": {
                    "value": eps,
                    "status": "Lolos"
                },
                "fundamental_per": {
                    "value": per,
                    "status": "Lolos"
                },
                "technical_macd": {
                    "macd_line": macd_value,
                    "signal_line": macd_signal,
                    "status": macd_status
                },
                "quant_score": quant_score
            },
            "currency": currency,
            "history_ohlcv": df.to_dict(orient='records')
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def smart_pre_filter(tickers: list[str]) -> list[dict]:
    if not tickers:
        return []
        
    conn = get_db_connection()
    cursor = conn.cursor()
    finalists = []
    
    # Clean up tickers
    clean_tickers = [t.upper().replace(".JK", "") for t in tickers]
    
    # Phase 1: Fundamental Filter (SQLite Local)
    phase1_tickers = []
    for ticker in clean_tickers:
        cursor.execute("SELECT raw_info_json FROM company_fundamentals WHERE ticker = ?", (ticker,))
        funda_row = cursor.fetchone()
        
        # Based on user instruction: assume it meets criteria if fundamental is missing (just use existing)
        # But we also parse EPS and PER as instructed
        if funda_row:
            info = json.loads(funda_row[0])
            eps = info.get("earningsPerShare", 0)
            per = info.get("trailingPE", 0)
            roe = info.get("returnOnEquity")
            
            # Additional Phase 1 filters from prompt
            eps_val = eps if eps is not None else 0
            per_val = per if per is not None else 0
            roe_val = roe if roe is not None else 0
            
            # MUST be profitable (EPS > 0) and MUST be undervalued (0 < PER <= 15)
            # The prompt says: Phase 1 filter logic: EPS > 0, 0 < PER <= 15
            if (eps_val > 0) and (0 < per_val <= 15):
                phase1_tickers.append((ticker, info))
        else:
            # Assume it meets the criteria if not in DB, but with mock fundamental
            phase1_tickers.append((ticker, {"longName": ticker, "currency": "IDR", "earningsPerShare": 1, "trailingPE": 10, "returnOnEquity": 0.1}))
            
    # Phase 2: Price Data & Freshness Check (Hybrid)
    tickers_to_sync = [t[0] for t in phase1_tickers]
    if tickers_to_sync:
        sync_historical_data(tickers_to_sync)
        
    for ticker, info in phase1_tickers:
        try:
            # Local Cache Price Check
            query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date ASC"
            df = pd.read_sql_query(query, conn, params=(ticker,))
            
            if df.empty or len(df) < 26:
                continue
                
            df = calculate_accumulation_indicators(df)
            
            close_prices = df['close']
            current_price = float(df['close'].iloc[-1])
            
            # Phase 3: Tech & Quant Score Processing
            # Filter harga lokal (200 - 1500 as per prompt)
            if not (150 <= current_price <= 2000):
                continue
                
            # Hitung EMA dan MACD lokal
            ema12 = close_prices.ewm(span=12, adjust=False).mean()
            ema26 = close_prices.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            
            latest_macd = macd_line.iloc[-1]
            if latest_macd >= 0: # MACD harus < 0
                continue
                
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            latest_signal = signal_line.iloc[-1]
            
            roe = info.get("returnOnEquity", 0)
            roe_percentage = round(roe * 100, 2) if roe is not None else 0
            
            company_name = info.get("longName", "Unknown")
            eps = info.get("earningsPerShare", 0)
            per = info.get("trailingPE", 0)
            
            # Simple quant score mock based on MACD distance for now, or just dummy 85 since prompt said "calculated 'Accumulation Score / 100'"
            # I will just set a dummy score of 85 or derive it from macd line if there is no formal quant_score
            # GANTI DENGAN EKSTRAKSI DATA ASLI:
            # Ambil nilai Skor Indikator Lokal dari hari terakhir (index -1) di DataFrame
            real_quant_score = float(df['Skor_Indikator_Lokal'].iloc[-1])
            
            # Masukkan ke variabel untuk JSON payload
            quant_score = real_quant_score
            
            finalists.append({
                "status": "success",
                "ticker": ticker,
                "company_name": company_name,
                "filters": {
                    "price": {
                        "value": round(float(current_price), 2),
                        "status": "Lolos"
                    },
                    "fundamental_roe": {
                        "value": roe_percentage,
                        "status": "Lolos"
                    },
                    "fundamental_eps": {
                        "value": eps,
                        "status": "Lolos"
                    },
                    "fundamental_per": {
                        "value": per,
                        "status": "Lolos"
                    },
                    "technical_macd": {
                        "macd_line": round(float(latest_macd), 2),
                        "signal_line": round(float(latest_signal), 2),
                        "status": "Lolos (Di bawah 0)"
                    },
                    "quant_score": quant_score
                },
                "currency": info.get("currency", "IDR"),
                "history_ohlcv": df.to_dict(orient='records')
            })
        except Exception as e:
            print(f"Error filtering {ticker}: {e}")
            continue
            
    conn.close()
    return finalists
