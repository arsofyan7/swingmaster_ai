import yfinance as yf
import pandas as pd
from datetime import datetime
import logging
import os
import sys

# Add parent path so we can import from app.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.core.database import get_db_connection
from app.services.SMCEngine import get_smc_buy_signals, get_smc_sell_signals
from app.services.telegram_service import broadcast_telegram_message

logger = logging.getLogger(__name__)

def run_h1_forex_alerts_job():
    logger.info("[SMC FOREX H1] Memulai proses fetch data H1 dan scanning SMC...")
    try:
        # Pre-fetch existing alerts for deduplication without holding DB lock during download
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, strategy_name, signal_date FROM daily_alerts WHERE signal_date >= date('now', '-2 days')")
            existing_alert_set = {(r[0], r[1], r[2]) for r in cursor.fetchall()}
        finally:
            conn.close()
        
        forex_pairs = {
            "EURUSD=X": "EURUSD",
            "GBPUSD=X": "GBPUSD",
            "JPY=X": "USDJPY",
            "CHF=X": "USDCHF",
            "GC=F": "XAUUSD" # Gold Futures sebagai substitusi XAUUSD Spot
        }
        
        logger.info(f"[SMC FOREX H1] Mendownload data H1 untuk {len(forex_pairs)} pair...")
        
        alerts_to_insert = []
        grouped_alerts = {}
        telegram_lines = []
        all_forex_records = []
        
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
                
                for dt, row in df_db.iterrows():
                    dt_str = dt.isoformat()
                    all_forex_records.append((
                        db_ticker,
                        dt_str,
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume']) if 'volume' in row else 0
                    ))
                
                # Format DataFrame untuk SMCEngine (Open, High, Low, Close, Volume)
                df_smc = df.copy()
                df_smc.columns = [c.capitalize() for c in df_smc.columns]
                
                # Scan BUY Signals
                buy_signals = get_smc_buy_signals(df_smc)
                if buy_signals:
                    for buy_signal in buy_signals:
                        signal_time = buy_signal.get('signal_time', df_smc.index[-1])
                        candle_date_str = signal_time.strftime("%Y-%m-%d")
                        candle_time_str = signal_time.strftime("%H:%M")
                        strategy_label = f"{buy_signal['strategy_name']}_{candle_time_str}"
                        
                        is_duplicate = (db_ticker, strategy_label, candle_date_str) in existing_alert_set
                        
                        alerts_to_insert.append((
                            db_ticker,
                            strategy_label,
                            candle_date_str,
                            buy_signal['price_at_signal'],
                            buy_signal['target_price'],
                            buy_signal['stop_loss'],
                            'open'
                        ))
                        
                        if not is_duplicate:
                            entry = f"{buy_signal['price_at_signal']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['price_at_signal']:.3f}"
                            clean_symbol = "XAUUSD" if db_ticker == "XAUUSD" else db_ticker
                            tv_link = f"<a href='https://id.tradingview.com/chart/?symbol=FX%3A{clean_symbol}'>📊</a>"
                            
                            readable_type = ""
                            msg = ""
                            if buy_signal['type'] == 'BUY_PHASE1':
                                readable_type = "SMC_Reversal_Fase1 Forex BUY"
                                alert_str = "CHoCH"
                                status_str = "Tunggu Pullback"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {status_str}</code> {tv_link}"
                            elif buy_signal['type'] == 'BUY':
                                readable_type = "SMC_Reversal_Fase2 Forex BUY"
                                alert_str = "Buy Limit"
                                tp = f"{buy_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['target_price']:.3f}"
                                sl = f"{buy_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['stop_loss']:.3f}"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {entry:>8} | {tp:>8} | {sl:>8}</code> {tv_link}"
                            elif buy_signal['type'] == 'BUY_TREND_PHASE1':
                                readable_type = "SMC_Trend_Fase1 Forex BUY"
                                alert_str = "BOS"
                                status_str = "Tunggu OB/FVG"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {status_str}</code> {tv_link}"
                            elif buy_signal['type'] == 'BUY_TREND':
                                readable_type = "SMC_Trend_Fase2 Forex BUY"
                                alert_str = "Buy Trend"
                                tp = f"{buy_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['target_price']:.3f}"
                                sl = f"{buy_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{buy_signal['stop_loss']:.3f}"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {entry:>8} | {tp:>8} | {sl:>8}</code> {tv_link}"
                            
                            if readable_type:
                                group_header = f"🔥 <b>{readable_type} {candle_time_str}:</b>"
                                if group_header not in grouped_alerts:
                                    grouped_alerts[group_header] = []
                                grouped_alerts[group_header].append(msg)
                        logger.info(f"[SMC FOREX H1] BUY TRIGGERED: {db_ticker} at {buy_signal['price_at_signal']} ({candle_time_str})")
                        
                # Scan SELL Signals
                sell_signals = get_smc_sell_signals(df_smc)
                if sell_signals:
                    for sell_signal in sell_signals:
                        signal_time = sell_signal.get('signal_time', df_smc.index[-1])
                        candle_date_str = signal_time.strftime("%Y-%m-%d")
                        candle_time_str = signal_time.strftime("%H:%M")
                        strategy_label = f"{sell_signal['strategy_name']}_{candle_time_str}"
                        
                        is_duplicate = (db_ticker, strategy_label, candle_date_str) in existing_alert_set
                        
                        alerts_to_insert.append((
                            db_ticker,
                            strategy_label,
                            candle_date_str,
                            sell_signal['price_at_signal'],
                            sell_signal['target_price'],
                            sell_signal['stop_loss'],
                            'open'
                        ))
                        
                        if not is_duplicate:
                            entry = f"{sell_signal['price_at_signal']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['price_at_signal']:.3f}"
                            clean_symbol = "XAUUSD" if db_ticker == "XAUUSD" else db_ticker
                            tv_link = f"<a href='https://id.tradingview.com/chart/?symbol=FX%3A{clean_symbol}'>📊</a>"
                            
                            readable_type = ""
                            msg = ""
                            if sell_signal['type'] == 'SELL_PHASE1':
                                readable_type = "SMC_Reversal_Fase1 Forex SELL"
                                alert_str = "CHoCH"
                                status_str = "Tunggu Retest"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {status_str}</code> {tv_link}"
                            elif sell_signal['type'] == 'SELL':
                                readable_type = "SMC_Reversal_Fase2 Forex SELL"
                                alert_str = "Sell Limit"
                                tp = f"{sell_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['target_price']:.3f}"
                                sl = f"{sell_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['stop_loss']:.3f}"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {entry:>8} | {tp:>8} | {sl:>8}</code> {tv_link}"
                            elif sell_signal['type'] == 'SELL_TREND_PHASE1':
                                readable_type = "SMC_Trend_Fase1 Forex SELL"
                                alert_str = "BOS"
                                status_str = "Tunggu OB/FVG"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {status_str}</code> {tv_link}"
                            elif sell_signal['type'] == 'SELL_TREND':
                                readable_type = "SMC_Trend_Fase2 Forex SELL"
                                alert_str = "Sell Trend"
                                tp = f"{sell_signal['target_price']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['target_price']:.3f}"
                                sl = f"{sell_signal['stop_loss']:.5f}" if db_ticker != 'USDJPY' and db_ticker != 'XAUUSD' else f"{sell_signal['stop_loss']:.3f}"
                                msg = f"<code>{db_ticker:<6} | {alert_str:<9} | {entry:>8} | {entry:>8} | {tp:>8} | {sl:>8}</code> {tv_link}"
                            
                            if readable_type:
                                group_header = f"🔥 <b>{readable_type} {candle_time_str}:</b>"
                                if group_header not in grouped_alerts:
                                    grouped_alerts[group_header] = []
                                grouped_alerts[group_header].append(msg)
                        logger.info(f"[SMC FOREX H1] SELL TRIGGERED: {db_ticker} at {sell_signal['price_at_signal']} ({candle_time_str})")
                        
            except Exception as e:
                logger.error(f"[SMC FOREX H1] Error memproses {db_ticker}: {e}")

        # Batch database write with safe error handling
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if all_forex_records:
                cursor.executemany("""
                INSERT OR REPLACE INTO h1_Forex_prices 
                (ticker, datetime, open, high, low, close, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, all_forex_records)

            if alerts_to_insert:
                for alert in alerts_to_insert:
                    cursor.execute("DELETE FROM daily_alerts WHERE signal_date = ? AND ticker = ? AND strategy_name = ?", (alert[2], alert[0], alert[1]))
                
                cursor.executemany('''
                    INSERT INTO daily_alerts (ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', alerts_to_insert)
                logger.info(f"[SMC FOREX H1] Disimpan {len(alerts_to_insert)} alert ke database.")
            
            conn.commit()
        finally:
            conn.close()

        # Kirim notifikasi Telegram
        if grouped_alerts:
            for header_title, msgs in grouped_alerts.items():
                telegram_lines.append(header_title)
                if 'Fase1' in header_title:
                    col_header = f"{'Kode':<6} | {'Alert':<9} | {'Harga':<8} | Status"
                    telegram_lines.append(f"<code>{col_header}</code>")
                    telegram_lines.append(f"<code>{'-' * len(col_header)}</code>")
                else:
                    col_header = f"{'Kode':<6} | {'Alert':<9} | {'Cur':<8} | {'Ent':<8} | {'TP':<8} | {'SL':<8}"
                    telegram_lines.append(f"<code>{col_header}</code>")
                    telegram_lines.append(f"<code>{'-' * len(col_header)}</code>")
                telegram_lines.append("\n".join(msgs))
                telegram_lines.append("────────────────────\n")
                
            run_time_str = datetime.now().strftime("%H:%M")
            header = f"<b>🌍 SMC FOREX H1 ALERTS 🌍</b>\n<i>⏰ Waktu: {run_time_str}</i>\n\n"
            footer = f"💡 <i>Total Alerts Triggered: {len(alerts_to_insert)}</i>\n⚠️ <i>Disclaimer: Always do your own research (DYOR). Trading carries risks!</i>"
            msg = header + "\n".join(telegram_lines) + footer
            broadcast_telegram_message(msg, category="forex")
        else:
            logger.info("[SMC FOREX H1] Tidak ada alert SMC Forex H1 pada jam ini.")
            
    except Exception as e:
        logger.error(f"[SMC FOREX H1] Terjadi kesalahan utama: {e}")

if __name__ == "__main__":
    run_h1_forex_alerts_job()
