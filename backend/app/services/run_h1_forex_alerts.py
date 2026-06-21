import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
import logging
import os
import sys

# Add parent path so we can import from app.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.services.SMCEngine import get_smc_buy_signals, get_smc_sell_signals
from app.services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

def run_h1_forex_alerts_job():
    logger.info("[SMC FOREX H1] Memulai proses fetch data H1 dan scanning SMC...")
    try:
        conn = sqlite3.connect('market_data.db')
        cursor = conn.cursor()
        
        # Buat tabel h1_Forex_prices jika belum ada
        cursor.execute("""
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
        """)
        conn.commit()
        
        forex_pairs = {
            "EURUSD=X": "EURUSD",
            "GBPUSD=X": "GBPUSD",
            "JPY=X": "USDJPY",
            "CHF=X": "USDCHF",
            "GC=F": "XAUUSD" # Gold Futures sebagai substitusi XAUUSD Spot
        }
        
        logger.info(f"[SMC FOREX H1] Mendownload data H1 untuk {len(forex_pairs)} pair...")
        
        alerts_to_insert = []
        telegram_lines = []
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        for yf_ticker, db_ticker in forex_pairs.items():
            try:
                # Ambil data H1 terbaru (1 bulan cukup untuk scanning SMC, tapi kita ambil 2mo biar aman)
                df = yf.download(yf_ticker, interval="1h", period="2mo", progress=False)
                
                if df.empty:
                    logger.warning(f"[SMC FOREX H1] Data kosong untuk {db_ticker} ({yf_ticker})")
                    continue
                    
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                # Standardize columns for database
                df_db = df.copy()
                df_db.columns = [c.lower() for c in df_db.columns]
                
                # Simpan ke tabel h1_Forex_prices
                records = []
                for dt, row in df_db.iterrows():
                    records.append((
                        db_ticker,
                        dt.isoformat(),
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    ))
                
                cursor.executemany("""
                INSERT OR REPLACE INTO h1_Forex_prices 
                (ticker, datetime, open, high, low, close, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
                
                # SMC Scanning
                # SMCEngine expects capitalized columns
                df_smc = df.copy()
                df_smc.columns = [c.capitalize() for c in df_smc.columns]
                df_smc = df_smc.dropna(subset=['Close'])
                
                buy_signals_list = get_smc_buy_signals(df_smc)
                if buy_signals_list:
                    for buy_signal in buy_signals_list:
                        candle_time_str = df_smc.index[-1].strftime("%H:%M")
                        strategy_label_buy = f"{buy_signal['strategy_name']}_Forex_Buy_{candle_time_str}"
                        alerts_to_insert.append((
                            db_ticker,
                            strategy_label_buy,
                            current_date_str,
                            buy_signal['price_at_signal'],
                            buy_signal['target_price'],
                            buy_signal['stop_loss'],
                            'open'
                        ))
                        entry = f"{buy_signal['price_at_signal']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['price_at_signal']:.3f}"
                        
                        if buy_signal['type'] == 'BUY_PHASE1':
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Reversal_Fase1 Forex BUY - {candle_time_str})\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"⚠️ <b>Status:</b> Persiapan nunggu Pullback, bisa aktifkan Buy Limit di Zona FVG atau Golden Fibo\n"
                            )
                        elif buy_signal['type'] == 'BUY':
                            tp = f"{buy_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['target_price']:.3f}"
                            sl = f"{buy_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['stop_loss']:.3f}"
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Reversal_Fase2 Forex BUY - {candle_time_str})\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"🟢 <b>Entry:</b> {entry}\n"
                                f"🎯 <b>TP:</b> {tp}\n"
                                f"🛑 <b>SL:</b> {sl}\n"
                            )
                        elif buy_signal['type'] == 'BUY_TREND_PHASE1':
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Trend_Fase1 Forex BUY - {candle_time_str})\n"
                                f"📈 <b>BOS Bullish - Trend Continuation</b>\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"⏳ <b>Status:</b> Persiapan nunggu Pullback ke OB/FVG, bisa aktifkan Buy Limit\n"
                            )
                        elif buy_signal['type'] == 'BUY_TREND':
                            tp = f"{buy_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['target_price']:.3f}"
                            sl = f"{buy_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['stop_loss']:.3f}"
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Trend_Fase2 Forex BUY - {candle_time_str})\n"
                                f"📈 <b>BUY - Trend Continuation</b>\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"🟢 <b>Entry:</b> {entry}\n"
                                f"🎯 <b>TP:</b> {tp}\n"
                                f"🛑 <b>SL:</b> {sl}\n"
                            )
                        telegram_lines.append(f"────────────────────")
                        logger.info(f"[SMC FOREX H1] BUY TRIGGERED: {db_ticker} at {buy_signal['price_at_signal']} ({candle_time_str})")
                    
                sell_signals_list = get_smc_sell_signals(df_smc)
                if sell_signals_list:
                    for sell_signal in sell_signals_list:
                        candle_time_str = df_smc.index[-1].strftime("%H:%M")
                        strategy_label_sell = f"{sell_signal['strategy_name']}_Forex_Sell_{candle_time_str}"
                        alerts_to_insert.append((
                            db_ticker,
                            strategy_label_sell,
                            current_date_str,
                            sell_signal['price_at_signal'],
                            sell_signal['target_price'],
                            sell_signal['stop_loss'],
                            'open'
                        ))
                        entry = f"{sell_signal['price_at_signal']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['price_at_signal']:.3f}"
                        
                        if sell_signal['type'] == 'SELL_PHASE1':
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Reversal_Fase1 Forex SELL - {candle_time_str})\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"⚠️ <b>Status:</b> Persiapan nunggu Pullback, bisa aktifkan Sell Limit di Zona FVG atau Golden Fibo\n"
                            )
                        elif sell_signal['type'] == 'SELL':
                            tp = f"{sell_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['target_price']:.3f}"
                            sl = f"{sell_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['stop_loss']:.3f}"
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Reversal_Fase2 Forex SELL - {candle_time_str})\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"🔴 <b>Entry:</b> {entry}\n"
                                f"🎯 <b>TP:</b> {tp}\n"
                                f"🛑 <b>SL:</b> {sl}\n"
                            )
                        elif sell_signal['type'] == 'SELL_TREND_PHASE1':
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Trend_Fase1 Forex SELL - {candle_time_str})\n"
                                f"📉 <b>BOS Bearish - Trend Continuation</b>\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"⏳ <b>Status:</b> Persiapan nunggu Pullback ke OB/FVG, bisa aktifkan Sell Limit\n"
                            )
                        elif sell_signal['type'] == 'SELL_TREND':
                            tp = f"{sell_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['target_price']:.3f}"
                            sl = f"{sell_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['stop_loss']:.3f}"
                            telegram_lines.append(
                                f"<b>{len(telegram_lines)+1}. {db_ticker}</b> (SMC_Trend_Fase2 Forex SELL - {candle_time_str})\n"
                                f"📉 <b>SELL - Trend Continuation</b>\n"
                                f"🏷️ <b>Current Price:</b> {entry}\n"
                                f"🔴 <b>Entry:</b> {entry}\n"
                                f"🎯 <b>TP:</b> {tp}\n"
                                f"🛑 <b>SL:</b> {sl}\n"
                            )
                        telegram_lines.append(f"────────────────────")
                        logger.info(f"[SMC FOREX H1] SELL TRIGGERED: {db_ticker} at {sell_signal['price_at_signal']} ({candle_time_str})")
                    
            except Exception as e:
                logger.error(f"[SMC FOREX H1] Error memproses {db_ticker}: {e}")

        # Simpan ke database daily_alerts
        if alerts_to_insert:
            # Delete old alerts with exact same time/date (idempotent)
            for alert in alerts_to_insert:
                cursor.execute("DELETE FROM daily_alerts WHERE signal_date = ? AND ticker = ? AND strategy_name = ?", (alert[2], alert[0], alert[1]))
            
            cursor.executemany('''
                INSERT INTO daily_alerts (ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', alerts_to_insert)
            conn.commit()
            logger.info(f"[SMC FOREX H1] Disimpan {len(alerts_to_insert)} alert ke database.")
            
            # Kirim notifikasi Telegram
            run_time_str = datetime.now().strftime("%H:%M")
            header = f"<b>🌍 SMC FOREX H1 ALERTS 🌍</b>\n<i>⏰ Waktu: {run_time_str}</i>\n\n"
            footer = f"\n💡 <i>Total Alerts: {len(alerts_to_insert)}</i>\n⚠️ <i>Disclaimer: Always do your own research (DYOR). Trading carries risks!</i>"
            msg = header + "\n".join(telegram_lines) + footer
            send_telegram_message(msg)
        else:
            logger.info("[SMC FOREX H1] Tidak ada alert SMC Forex H1 pada jam ini.")
            
        conn.close()
    except Exception as e:
        logger.error(f"[SMC FOREX H1] Terjadi kesalahan utama: {e}")

if __name__ == "__main__":
    run_h1_forex_alerts_job()
