import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "market_data.db"

def run_update():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ambil semua ticker
    cursor.execute("SELECT DISTINCT ticker FROM daily_prices")
    tickers = [row[0] for row in cursor.fetchall() if row[0] != 'COMPOSITE']
    
    # Kita cari tanggal terjauh dari data terakhir yang dimiliki masing-masing ticker
    cursor.execute("SELECT MIN(max_date) FROM (SELECT MAX(date) as max_date FROM daily_prices GROUP BY ticker)")
    min_date_str = cursor.fetchone()[0]
    
    if not min_date_str:
        start_date = "2024-01-01" # Default kalau kosong banget
    else:
        min_date = datetime.strptime(min_date_str, "%Y-%m-%d")
        # Mundur 14 hari dari max date paling jadul untuk me-replace (override) volume yang bernilai 0 dari Google Finance
        start_date = (min_date - timedelta(days=14)).strftime("%Y-%m-%d")
        
    end_date = "2026-06-13" # Eksklusif, jadi akan narik maksimal sampai 12 Juni 2026
    
    logger.info(f"Mulai batch download yfinance untuk {len(tickers)} emiten dari {start_date} s/d {end_date}...")
    
    yf_tickers = [f"{t}.JK" for t in tickers]
    
    # Batasi batch agar tidak error memori (misal 500 per batch)
    batch_size = 300
    db_records = []
    
    for i in range(0, len(yf_tickers), batch_size):
        batch = yf_tickers[i:i+batch_size]
        logger.info(f"Downloading batch {i//batch_size + 1}...")
        
        df = yf.download(batch, start=start_date, end=end_date, group_by='ticker', progress=False)
        
        if df.empty:
            continue
            
        for yf_t in batch:
            t = yf_t.replace(".JK", "")
            if len(batch) == 1:
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
                vol = int(row['Volume'])
                
                db_records.append((
                    date_str,
                    t,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    vol
                ))
                
    if db_records:
        logger.info(f"Menyimpan dan meng-overwrite {len(db_records)} baris data ke database (INSERT OR REPLACE)...")
        cursor.executemany('''
            INSERT OR REPLACE INTO daily_prices (date, ticker, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', db_records)
        conn.commit()
        logger.info("Sukses update database!")
    else:
        logger.warning("Tidak ada data baru yang ditarik dari yfinance.")
        
    conn.close()

if __name__ == "__main__":
    run_update()
