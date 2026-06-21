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
from app.services.telegram_service import broadcast_telegram_message

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
            
            signals_list = get_smc_buy_signals(ticker_df)
            if signals_list:
                for signal in signals_list:
                    last_candle_dt = ticker_df.index[-1]
                    candle_date_str = last_candle_dt.strftime("%Y-%m-%d")
                    candle_time_str = last_candle_dt.strftime("%H:%M")
                    strategy_label = f"{signal['strategy_name']}_{candle_time_str}"
                    
                    alerts_to_insert.append((
                        t,
                        strategy_label,
                        candle_date_str,
                        signal['price_at_signal'],
                        signal['target_price'],
                        signal['stop_loss'],
                        'open'
                    ))
                    
                    # Format pesan Telegram
                    entry = f"{signal['price_at_signal']:,.0f}" if signal['price_at_signal'] >= 100 else f"{signal['price_at_signal']:.2f}"
                    
                    if signal['type'] == 'BUY_PHASE1':
                        telegram_lines.append(
                            f"<b>{len(telegram_lines)+1}. {t}</b> (SMC_Reversal_Fase1 {candle_time_str})\n"
                            f"🏷️ <b>Current Price:</b> {entry}\n"
                            f"⚠️ <b>Status:</b> Persiapan nunggu Pullback, bisa aktifkan Buy Limit di Zona FVG atau Golden Fibo\n"
                        )
                    elif signal['type'] == 'BUY':
                        tp = f"{signal['target_price']:,.0f}" if signal['target_price'] >= 100 else f"{signal['target_price']:.2f}"
                        sl = f"{signal['stop_loss']:,.0f}" if signal['stop_loss'] >= 100 else f"{signal['stop_loss']:.2f}"
                        
                        telegram_lines.append(
                            f"<b>{len(telegram_lines)+1}. {t}</b> (SMC_Reversal_Fase2 {candle_time_str})\n"
                            f"🏷️ <b>Current Price:</b> {entry}\n"
                            f"💰 <b>Entry:</b> {entry}\n"
                            f"🎯 <b>TP:</b> {tp}\n"
                            f"🛑 <b>SL:</b> {sl}\n"
                        )
                    elif signal['type'] == 'BUY_TREND_PHASE1':
                        telegram_lines.append(
                            f"<b>{len(telegram_lines)+1}. {t}</b> (SMC_Trend_Fase1 {candle_time_str})\n"
                            f"📈 <b>BOS Bullish - Trend Continuation</b>\n"
                            f"🏷️ <b>Current Price:</b> {entry}\n"
                            f"⏳ <b>Status:</b> Persiapan nunggu Pullback ke OB/FVG, bisa aktifkan Buy Limit\n"
                        )
                    elif signal['type'] == 'BUY_TREND':
                        tp = f"{signal['target_price']:,.0f}" if signal['target_price'] >= 100 else f"{signal['target_price']:.2f}"
                        sl = f"{signal['stop_loss']:,.0f}" if signal['stop_loss'] >= 100 else f"{signal['stop_loss']:.2f}"
                        
                        telegram_lines.append(
                            f"<b>{len(telegram_lines)+1}. {t}</b> (SMC_Trend_Fase2 {candle_time_str})\n"
                            f"📈 <b>BUY - Trend Continuation</b>\n"
                            f"🏷️ <b>Current Price:</b> {entry}\n"
                            f"💰 <b>Entry:</b> {entry}\n"
                            f"🎯 <b>TP:</b> {tp}\n"
                            f"🛑 <b>SL:</b> {sl}\n"
                        )
                    
                    telegram_lines.append(f"────────────────────")
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
            header = f"<b>⏱️ SMC H1 ALERTS ⏱️</b>\n<i>⏰ Waktu: {run_time_str}</i>\n\n"
            footer = f"\n💡 <i>Total Alerts: {len(alerts_to_insert)}</i>\n⚠️ <i>Disclaimer: Always do your own research (DYOR). Trading carries risks!</i>"
            msg = header + "\n".join(telegram_lines) + footer
            broadcast_telegram_message(msg, category="saham")
        else:
            logger.info("[SMC H1] Tidak ada alert SMC H1 pada jam ini.")
            
        conn.close()
    except Exception as e:
        logger.error(f"[SMC H1] Terjadi kesalahan: {e}")

if __name__ == "__main__":
    run_h1_alerts_job()
