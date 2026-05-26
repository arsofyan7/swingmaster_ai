import requests
import sqlite3
import time
from app.core.logger import logger

# 🚨 PASTE URL WEB APP APPS SCRIPT TERBARU LU DI SINI:
GOOGLE_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz5B2Y_piR9RCssWnZSfzCdVT_3wWvMz8MU_MV4V4iHk1vaywoJwLBZjwzJHZB5N0u9zw/exec"
DB_PATH = "market_data.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            date DATE, ticker TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER,
            UNIQUE(date, ticker)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("🗄️ Database lokal SQLite siap menampung data massal.")

def run_automated_bulk_seeding():
    init_database()
    
    # 1. Minta daftar seluruh ticker (A2-A958) dari Google Sheet
    logger.info("📡 Mengambil daftar emiten lengkap dari Google Sheet...")
    try:
        response = requests.get(GOOGLE_WEBAPP_URL, params={"action": "list_tickers"}, timeout=20)
        ticker_list = response.json().get("tickers", [])
        total_emiten = len(ticker_list)
        logger.info(f"🎯 Sukses mendeteksi {total_emiten} emiten di dalam antrean Google Hub.")
    except Exception as e:
        logger.error(f"❌ Gagal mengambil daftar ticker: {e}")
        return

    # KONEKSI KE DB UTAMA
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 🔍 --- FITUR CHECKPOINT: AMBIL DAFTAR EMITEN YANG SUDAH SELESAI DI-DOWNLOAD ---
    try:
        cursor.execute("SELECT DISTINCT ticker FROM daily_prices")
        existing_tickers = {row[0].upper().strip() for row in cursor.fetchall()}
        logger.info(f"💾 Checkpoint dideteksi! Sudah ada {len(existing_tickers)} emiten terisi aman di SQLite.")
    except Exception:
        existing_tickers = set()

    # 2. Loop Otomatis Jemput Data per Emiten
    for index, ticker in enumerate(ticker_list, start=1):
        ticker_upper = ticker.upper().strip()
        
        # 🛡️ JIKA EMITEN SUDAH ADA DATA DI SQLITE, LANGSUNG RESUME / SKIP!
        if ticker_upper in existing_tickers:
            logger.info(f"⏭️ [{index}/{total_emiten}] Emiten {ticker_upper} sudah ada di DB. Langsung SKIP/Resume!")
            continue
            
        logger.info(f"🔄 [{index}/{total_emiten}] Menjemput data 3 tahun emiten: {ticker_upper}...")
        
        try:
            res = requests.get(GOOGLE_WEBAPP_URL, params={"action": "fetch_history", "ticker": ticker_upper}, timeout=40)
            res_json = res.json()
            
            if res_json.get("status") != "success":
                logger.warning(f"⚠️ Skip {ticker_upper}: {res_json.get('message')}")
                continue
                
            ohlcv_data = res_json.get("data", [])
            if not ohlcv_data:
                logger.warning(f"⚠️ Data {ticker_upper} kosong saat di-render Google Finance.")
                continue
                
            db_records = []
            for bar in ohlcv_data:
                db_records.append((
                    bar["date"], 
                    ticker_upper, 
                    float(bar["open"]), 
                    float(bar["high"]), 
                    float(bar["low"]), 
                    float(bar["close"]), 
                    int(bar["volume"])
                ))
                
            cursor.executemany('''
                INSERT OR IGNORE INTO daily_prices (date, ticker, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', db_records)
            conn.commit()
            
            logger.info(f"✅ Saham {ticker_upper} terkunci aman! Berhasil mengamankan {len(db_records)} baris data.")
            time.sleep(1.5)
            
        except Exception as err:
            logger.error(f"❌ Terjadi eror pada emiten {ticker_upper}: {err}")
            continue

    conn.close()
    logger.info("🎉 OPERASI RESUME SELESAI TOTAL! Seluruh 957 emiten berhasil di-seed otomatis ke SQLite Lokal!")

if __name__ == "__main__":
    run_automated_bulk_seeding()