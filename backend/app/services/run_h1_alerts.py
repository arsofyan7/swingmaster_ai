import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
import logging
import os
import sys

# Add parent path so we can import from app.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.services.SMCEngine import get_smc_buy_signals
from app.services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

def run_h1_alerts_job():
    logger.info("[SMC H1] Memulai proses fetch data H1 dan scanning SMC...")
    try:
        conn = sqlite3.connect('market_data.db')
        cursor = conn.cursor()
        
        # 1. Cari saham dengan harga 150 - 5000 (berdasarkan daily_prices terakhir)
        cursor.execute("""
            SELECT ticker, close 
            FROM daily_prices 
            WHERE date = (SELECT MAX(date) FROM daily_prices)
        """)
        rows = cursor.fetchall()
        
        valid_tickers = []
        for t, c in rows:
            if 150 <= c <= 5000 and t != 'COMPOSITE':
                valid_tickers.append(t)
                
        if not valid_tickers:
            logger.info("[SMC H1] Tidak ada saham di range harga 150-5000.")
            return
            
        logger.info(f"[SMC H1] Menemukan {len(valid_tickers)} saham dalam range harga.")
        
        # 2. Fetch H1 data via yfinance (Ambil 1 bulan data hourly)
        yf_tickers = [f"{t}.JK" for t in valid_tickers]
        
        logger.info("[SMC H1] Mendownload data H1 dari yfinance...")
        df = yf.download(yf_tickers, period="1mo", interval="1h", group_by='ticker', progress=False)
        
        alerts_to_insert = []
        telegram_lines = []
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        h1_records = []
        
        for t in valid_tickers:
            yf_t = f"{t}.JK"
            
            if len(yf_tickers) == 1:
                ticker_df = df
            else:
                if yf_t not in df.columns.levels[0]:
                    continue
                ticker_df = df[yf_t]
                
            ticker_df = ticker_df.dropna(subset=['Close']).copy()
            if ticker_df.empty:
                continue
            
            # Persiapkan data untuk h1_prices (menyimpan history H1)
            for dt, row in ticker_df.iterrows():
                dt_str = dt.isoformat()
                h1_records.append((
                    t,
                    dt_str,
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
            
            # SMC Scanning
            # SMCEngine expects standard columns
            ticker_df.columns = [c.capitalize() for c in ticker_df.columns]
            
            signal = get_smc_buy_signals(ticker_df)
            if signal:
                candle_time_str = ticker_df.index[-1].strftime("%H:%M")
                strategy_label = f"SMC_H1_{candle_time_str}"
                
                alerts_to_insert.append((
                    t,
                    strategy_label,
                    current_date_str,
                    signal['price_at_signal'],
                    signal['target_price'],
                    signal['stop_loss'],
                    'open'
                ))
                
                # Format pesan Telegram
                telegram_lines.append(
                    f"🚀 <b>{t}</b> | {signal['price_at_signal']} (Jam {candle_time_str})\n"
                    f"└ TP: {signal['target_price']} | SL: {signal['stop_loss']}"
                )
                logger.info(f"[SMC H1] ALERT TRIGGERED: {t} at {signal['price_at_signal']} ({candle_time_str})")
                
        # 3. Update database h1_prices
        if h1_records:
            cursor.executemany("""
            INSERT OR REPLACE INTO h1_prices 
            (ticker, datetime, open, high, low, close, volume) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, h1_records)
            conn.commit()

        # 4. Simpan ke database daily_alerts
        if alerts_to_insert:
            # Delete old alerts with exact same time/date (idempotent)
            for alert in alerts_to_insert:
                cursor.execute("DELETE FROM daily_alerts WHERE signal_date = ? AND ticker = ? AND strategy_name = ?", (alert[2], alert[0], alert[1]))
            
            cursor.executemany('''
                INSERT INTO daily_alerts (ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', alerts_to_insert)
            conn.commit()
            logger.info(f"[SMC H1] Disimpan {len(alerts_to_insert)} alert ke database.")
            
            # 5. Kirim notifikasi Telegram
            run_time_str = datetime.now().strftime("%H:%M")
            msg = f"<b>🔔 SMC H1 ALERTS ({run_time_str})</b>\n\n" + "\n\n".join(telegram_lines)
            send_telegram_message(msg)
        else:
            logger.info("[SMC H1] Tidak ada alert SMC H1 pada jam ini.")
            
        conn.close()
    except Exception as e:
        logger.error(f"[SMC H1] Terjadi kesalahan: {e}")

if __name__ == "__main__":
    run_h1_alerts_job()
