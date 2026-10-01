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

from app.core.database import get_db_connection, get_db


def sync_historical_data(tickers: list[str]):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.date.today()
    
    stale_tickers = []
    
    for ticker in tickers:
        ticker_upper = ticker.upper().replace(".JK", "")
        
        cursor.execute("SELECT MAX(date) FROM daily_prices WHERE ticker = ?", (ticker_upper,))
        max_date_str = cursor.fetchone()[0]
        
        is_stale = True
        if max_date_str:
            max_date = datetime.datetime.strptime(max_date_str, '%Y-%m-%d').date()
            if max_date >= today:
                is_stale = False
                
        if is_stale:
            stale_tickers.append(ticker_upper)
            
    if not stale_tickers:
        conn.close()
        return
        
    tickers_for_yf_fallback = []
    
    for ticker_upper in stale_tickers:
        logger.info(f"[OUTBOUND GOOGLE HUB] Fetch history for {ticker_upper}")
        try:
            res = requests.get(settings.GOOGLE_WEBAPP_URL, params={"action": "fetch_history", "ticker": ticker_upper}, timeout=40)
            res_json = res.json()
            
            if res_json.get("status") == "success":
                ohlcv_data = res_json.get("data", [])
                records = []
                has_zero_volume = False
                
                for bar in ohlcv_data:
                    low_val = float(bar["low"])
                    vol_val = int(bar["volume"])
                    if ticker_upper != 'COMPOSITE' and (low_val == 0 or vol_val == 0):
                        has_zero_volume = True
                        break  # Langsung masuk fallback
                        
                    records.append((
                        bar["date"], 
                        ticker_upper, 
                        float(bar["open"]), 
                        float(bar["high"]), 
                        low_val, 
                        float(bar["close"]), 
                        vol_val
                    ))
                
                if has_zero_volume:
                    logger.warning(f"[{ticker_upper}] Google Hub ngasih volume 0, masukin antrean yfinance batch...")
                    tickers_for_yf_fallback.append(ticker_upper)
                elif records:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO daily_prices (date, ticker, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    conn.commit()
            else:
                logger.warning(f"Failed to fetch {ticker_upper} from Google Hub: {res_json.get('message')}")
                tickers_for_yf_fallback.append(ticker_upper)
                
        except Exception as e:
            print(f"Error syncing {ticker_upper} dari Google Hub: {e}")
            tickers_for_yf_fallback.append(ticker_upper)
            
    # YFINANCE BATCH FALLBACK
    if tickers_for_yf_fallback:
        logger.info(f"[YFINANCE FALLBACK] Memulai batch download untuk {len(tickers_for_yf_fallback)} emiten...")
        try:
            import yfinance as yf
            def get_yf_ticker(t):
                if t == 'COMPOSITE':
                    return "^JKSE"
                if len(t) == 6 and t.endswith("USD"):
                    return f"{t}=X"
                return f"{t}.JK"

            yf_tickers = [get_yf_ticker(t) for t in tickers_for_yf_fallback]
            
            df = yf.download(yf_tickers, period="1mo", group_by='ticker', progress=False)
            
            fallback_records = []
            for t in tickers_for_yf_fallback:
                yf_t = get_yf_ticker(t)
                
                if len(yf_tickers) == 1:
                    ticker_df = df
                else:
                    if yf_t not in df.columns.levels[0]:
                        continue
                    ticker_df = df[yf_t]
                    
                ticker_df = ticker_df.dropna(subset=['Close'])
                if ticker_df.empty:
                    continue
                    
                for dt, row in ticker_df.iterrows():
                    date_str = dt.strftime("%Y-%m-%d")
                    vol_val = int(row['Volume'])
                    low_val = float(row['Low'])
                    
                    if t != 'COMPOSITE' and (low_val == 0 or vol_val == 0):
                        continue
                        
                    fallback_records.append((
                        date_str,
                        t,
                        float(row['Open']),
                        float(row['High']),
                        low_val,
                        float(row['Close']),
                        vol_val
                    ))
                    
            if fallback_records:
                cursor.executemany('''
                    INSERT OR REPLACE INTO daily_prices (date, ticker, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', fallback_records)
                conn.commit()
                logger.info(f"[YFINANCE FALLBACK] Berhasil fallback dan menyimpan {len(fallback_records)} baris data.")
        except Exception as e:
            logger.error(f"[YFINANCE FALLBACK] Gagal melakukan batch download: {e}")

    conn.close()

def analyze_stock(ticker: str) -> dict:
    ticker = ticker.upper().replace(".JK", "")
    conn = None
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
    finally:
        if conn:
            conn.close()

def smart_pre_filter(tickers: list[str]) -> list[dict]:
    if not tickers:
        return []
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        finalists = []
        
        # Clean up tickers
        clean_tickers = [t.upper().replace(".JK", "") for t in tickers]
        
        # Phase 1: Fundamental Filter (SQLite Local)
        phase1_tickers = []
        for ticker in clean_tickers:
            cursor.execute("SELECT raw_info_json FROM company_fundamentals WHERE ticker = ?", (ticker,))
            funda_row = cursor.fetchone()
            
            if funda_row:
                info = json.loads(funda_row[0])
                eps = info.get("earningsPerShare", 0)
                per = info.get("trailingPE", 0)
                roe = info.get("returnOnEquity")
                
                eps_val = eps if eps is not None else 0
                per_val = per if per is not None else 0
                roe_val = roe if roe is not None else 0
                
                if (eps_val > 0) and (0 < per_val <= 15):
                    phase1_tickers.append((ticker, info))
            else:
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
                if not (150 <= current_price <= 2000):
                    continue
                    
                ema12 = close_prices.ewm(span=12, adjust=False).mean()
                ema26 = close_prices.ewm(span=26, adjust=False).mean()
                macd_line = ema12 - ema26
                
                latest_macd = macd_line.iloc[-1]
                if latest_macd >= 0:
                    continue
                    
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                latest_signal = signal_line.iloc[-1]
                
                roe = info.get("returnOnEquity", 0)
                roe_percentage = round(roe * 100, 2) if roe is not None else 0
                
                company_name = info.get("longName", "Unknown")
                eps = info.get("earningsPerShare", 0)
                per = info.get("trailingPE", 0)
                
                real_quant_score = float(df['Skor_Indikator_Lokal'].iloc[-1])
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
                logger.error(f"Error filtering {ticker}: {e}")
                continue
                
        return finalists
    finally:
        conn.close()
