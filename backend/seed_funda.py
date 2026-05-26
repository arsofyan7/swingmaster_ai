import requests
import sqlite3
import json
import datetime
from app.core.logger import logger

# 🚨 PASTE URL WEB APP APPS SCRIPT TERBARU LU DI SINI:
GOOGLE_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbz5B2Y_piR9RCssWnZSfzCdVT_3wWvMz8MU_MV4V4iHk1vaywoJwLBZjwzJHZB5N0u9zw/exec"

DB_PATH = "market_data.db"

def init_fundamentals_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_fundamentals (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            raw_info_json TEXT,
            updated_at DATE
        )
    ''')
    conn.commit()
    conn.close()

def run_sheet_fundamental_seeding():
    init_fundamentals_table()
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    logger.info("📡 Menjemput paket data PER & EPS murni langsung dari tab Fundamentals Google Sheet...")
    
    try:
        # Panggil action baru kita
        response = requests.get(GOOGLE_WEBAPP_URL, params={"action": "get_fundamentals_sheet"}, timeout=40)
        res_json = response.json()
        
        if res_json.get("status") != "success":
            logger.error(f"❌ Google Sheet Error: {res_json.get('message')}")
            return
            
        fund_data = res_json.get("data", {})
        total_emiten = len(fund_data)
        logger.info(f"📦 Berhasil mengunduh {total_emiten} data fundamental matang dari Google Hub.")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        db_records = []
        for ticker, metrics in fund_data.items():
            # Bungkus ke format dictionary standar raw_info_json proyek kita
            raw_info_dict = {
                "longName": f"{ticker} Tbk.",
                "trailingPE": float(metrics["pe"]),          # Menggantikan ROE untuk screener V2.5
                "earningsPerShare": float(metrics["eps"]),    # Konfirmasi profitabilitas emiten
                "currency": "IDR"
            }
            
            db_records.append((
                ticker.upper().strip(),
                f"{ticker} Tbk.",
                json.dumps(raw_info_dict),
                today_str
            ))
            
        # Eksekusi massal super cepat
        cursor.executemany('''
            INSERT OR REPLACE INTO company_fundamentals (ticker, company_name, raw_info_json, updated_at)
            VALUES (?, ?, ?, ?)
        ''', db_records)
        
        conn.commit()
        conn.close()
        logger.info(f"🎉 SUKSES MUTLAK! {total_emiten} data fundamental legal Google resmi mengunci posisi di SQLite!")
        
    except Exception as e:
        logger.error(f"💥 Fatal eror saat eksekusi data fundamental sheet: {e}")

if __name__ == "__main__":
    run_sheet_fundamental_seeding()