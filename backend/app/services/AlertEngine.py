import sqlite3
import pandas as pd
import json
import asyncio
from datetime import datetime
from app.core.logger import logger
from app.services.telegram_service import broadcast_telegram_message

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate necessary indicators for V8, V3, and V6 strategies.
    Requires columns: date, open, high, low, close, volume
    """
    df = df.sort_values('date').reset_index(drop=True)
    if len(df) == 0:
        return df

    # Handle missing volumes (often 0 from intraday syncing)
    df['volume'] = df['volume'].replace(0, pd.NA).ffill().fillna(0)

    # EMA 20 & 200
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()

    # VMA 20
    df['VMA_20'] = df['volume'].rolling(window=20).mean()

    # MACD
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26

    # OBV
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['OBV'] = obv
    df['OBV_EMA_20'] = df['OBV'].ewm(span=20, adjust=False).mean()

    # ADL
    multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
    multiplier = multiplier.fillna(0) # In case high == low
    adv = multiplier * df['volume']
    df['ADL'] = adv.cumsum()
    df['ADL_EMA_20'] = df['ADL'].ewm(span=20, adjust=False).mean()

    # Previous values needed for conditions
    df['close_prev'] = df['close'].shift(1)
    df['EMA_20_prev'] = df['EMA_20'].shift(1)
    df['MACD_prev'] = df['MACD'].shift(1)

    # RSI 14
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    df['RSI_14_prev'] = df['RSI_14'].shift(1)

    # Values for Swing Reversal (Pivot Low) - 8 bar lookback
    df['low_prev'] = df['low'].shift(1)
    df['low_prev2'] = df['low'].shift(2)
    df['low_prev3'] = df['low'].shift(3)
    df['low_prev4'] = df['low'].shift(4)
    df['low_prev5'] = df['low'].shift(5)
    df['low_prev6'] = df['low'].shift(6)
    df['low_prev7'] = df['low'].shift(7)
    df['low_prev8'] = df['low'].shift(8)
    df['high_prev'] = df['high'].shift(1)

    return df

def check_strategies(df: pd.DataFrame, ticker: str, matrix: dict) -> dict:
    if len(df) < 20: # Not enough data even for EMA 20
        return None
        
    latest = df.iloc[-1]
    
    # Check if we have matrix config for this ticker
    ticker_config = matrix.get(ticker, {})
    if not ticker_config:
        return None

    # V8_Pullback Logic
    def check_v8(latest):
        cond1 = latest['close'] > latest['EMA_200']
        cond2 = (latest['low'] <= latest['EMA_20']) and (latest['close'] >= latest['EMA_20']) and (latest['close'] <= (latest['EMA_20'] * 1.02))
        cond3 = latest['close'] < latest['close_prev']
        cond4 = latest['volume'] < latest['VMA_20']
        cond5 = latest['VMA_20'] >= 5_000_000  # Minimum liquidity filter based on VMA
        return cond1 and cond2 and cond3 and cond4 and cond5

    # V3_Breakout Logic
    def check_v3(latest):
        cond1 = latest['volume'] >= (2 * latest['VMA_20'])
        cond2 = (latest['close'] > latest['EMA_20']) and (latest['close_prev'] <= latest['EMA_20_prev'])
        cond3 = latest['MACD'] > latest['MACD_prev']
        cond4 = latest['VMA_20'] >= 5_000_000
        return cond1 and cond2 and cond3 and cond4

    # V6_Bandar Logic
    def check_v6(latest):
        cond1 = latest['close'] > latest['EMA_200']
        cond2 = (latest['low'] <= latest['EMA_20']) and (latest['close'] >= latest['EMA_20']) and (latest['close'] <= (latest['EMA_20'] * 1.02))
        cond3 = (latest['OBV'] > latest['OBV_EMA_20']) and (latest['ADL'] > latest['ADL_EMA_20'])
        cond4 = latest['volume'] >= 5_000_000  # Minimum volume filter
        return cond1 and cond2 and cond3 and cond4

    # Swing_Reversal Logic
    def check_swing_reversal(latest):
        # is_pivot_low: low_prev harus terendah di antara 8 bar sebelumnya
        cond1 = (
            latest['low_prev'] <= latest['low_prev2'] and
            latest['low_prev'] <= latest['low_prev3'] and
            latest['low_prev'] <= latest['low_prev4'] and
            latest['low_prev'] <= latest['low_prev5'] and
            latest['low_prev'] <= latest['low_prev6'] and
            latest['low_prev'] <= latest['low_prev7'] and
            latest['low_prev'] <= latest['low_prev8']
        ) # is_pivot_low (8 bars lookback)
        cond2 = latest['close'] > latest['high_prev'] # Reversal Confirmation
        cond3 = latest['RSI_14_prev'] < 50 # RSI Filter (Moderate)
        cond4 = latest['close'] > 150 # Filter minimal harga
        cond5 = latest['volume'] >= 5_000_000  # Minimum volume filter
        return cond1 and cond2 and cond3 and cond4 and cond5

    strategies = {
        "V8_Pullback": check_v8(latest),
        "V3_Breakout": check_v3(latest),
        "V6_Bandar": check_v6(latest),
        "Swing_Reversal": check_swing_reversal(latest)
    }

    # Evaluate based on rank
    for rank in ['peringkat_1', 'peringkat_2', 'peringkat_3', 'peringkat_4']:
        if rank in ticker_config:
            strategy_name = ticker_config[rank]['strategi']
            if strategies.get(strategy_name, False):
                return {
                    "strategy_name": strategy_name,
                    "price_at_signal": float(latest['close']),
                    "target_price": float(latest['close'] * 1.05), # Default 5% TP
                    "stop_loss": float(latest['close'] * 0.95)     # Default 5% SL
                }
    
    return None

async def run_daily_alerts(target_date: str = None):
    logger.info(f"[ALERT ENGINE] Starting daily alert generation for {target_date or 'today'}...")
    try:
        # Load Matrix
        with open('matrix_saham.json', 'r') as f:
            matrix = json.load(f)

        conn = sqlite3.connect('market_data.db')
        
        # Get all unique tickers from daily_prices
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ticker FROM daily_prices")
        tickers = [row[0] for row in cursor.fetchall()]
        
        alerts_to_insert = []
        
        # Get the latest date from daily_prices to handle weekends gracefully
        cursor.execute("SELECT MAX(date) FROM daily_prices")
        max_date_row = cursor.fetchone()
        latest_market_date = max_date_row[0] if max_date_row and max_date_row[0] else datetime.now().strftime("%Y-%m-%d")
        
        today_str = target_date if target_date else latest_market_date

        # Delete today's existing daily alerts before re-generating (exclude SMC alerts)
        cursor.execute("DELETE FROM daily_alerts WHERE signal_date = ? AND strategy_name NOT LIKE 'SMC%'", (today_str,))
        conn.commit()
        logger.info(f"[ALERT ENGINE] Cleared existing alerts for {today_str}, re-generating...")

        for ticker in tickers:
            if ticker not in matrix:
                continue

            # Fetch last 250 days for accurate EMA200
            if target_date:
                query = f"""
                SELECT date, open, high, low, close, volume 
                FROM daily_prices 
                WHERE ticker = '{ticker}' AND date <= '{target_date}'
                ORDER BY date DESC 
                LIMIT 250
                """
            else:
                query = f"""
                SELECT date, open, high, low, close, volume 
                FROM daily_prices 
                WHERE ticker = '{ticker}' 
                ORDER BY date DESC 
                LIMIT 250
                """
            df = pd.read_sql_query(query, conn)
            
            if len(df) < 30:
                continue
                
            # Reverse to chronological order for indicator calculation
            df = df.sort_values('date').reset_index(drop=True)
            
            # Calculate Indicators
            df = calculate_indicators(df)
            
            # Check Strategies
            signal = check_strategies(df, ticker, matrix)
            if signal:
                alerts_to_insert.append((
                    ticker, 
                    signal['strategy_name'], 
                    today_str, 
                    signal['price_at_signal'], 
                    signal['target_price'], 
                    signal['stop_loss'], 
                    'open'
                ))
                logger.info(f"[ALERT ENGINE] Ticker {ticker} triggered {signal['strategy_name']}")

            # Sleep to prevent high CPU load on batch processing
            await asyncio.sleep(0.01)
            
        # Insert into daily_alerts
        if alerts_to_insert:
            cursor.executemany('''
                INSERT INTO daily_alerts (ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', alerts_to_insert)
            conn.commit()
            logger.info(f"[ALERT ENGINE] Successfully saved {len(alerts_to_insert)} alerts to database.")
            
            # Send Telegram Notification
            grouped_alerts = {}
            for alert in alerts_to_insert:
                ticker = alert[0]
                strategy = alert[1]
                entry = f"{alert[3]:,.0f}" if alert[3] >= 100 else f"{alert[3]:.2f}"
                tp = f"{alert[4]:,.0f}" if alert[4] >= 100 else f"{alert[4]:.2f}"
                sl = f"{alert[5]:,.0f}" if alert[5] >= 100 else f"{alert[5]:.2f}"
                
                tv_link = f"<a href='https://id.tradingview.com/chart/?symbol=IDX%3A{ticker}'>{ticker}</a>"
                
                msg = (
                    f"🔹 <b>{tv_link}</b>\n"
                    f"🏷️ <b>Current Price:</b> {entry}\n"
                    f"💰 <b>Entry:</b> {entry}\n"
                    f"🎯 <b>TP:</b> {tp}\n"
                    f"🛑 <b>SL:</b> {sl}"
                )
                
                group_header = f"🔥 <b>{strategy}:</b>"
                if group_header not in grouped_alerts:
                    grouped_alerts[group_header] = []
                grouped_alerts[group_header].append(msg)
                
            msg_lines = [
                "<b>🚀 SWINGMASTER AI ALERTS 🚀</b>",
                f"<i>📅 Date: {today_str}</i>\n"
            ]
            
            for header_title, msgs in grouped_alerts.items():
                msg_lines.append(header_title)
                msg_lines.append("\n\n".join(msgs))
                msg_lines.append("────────────────────\n")
                
            msg_lines.append(f"💡 <i>Total Alerts Today: {len(alerts_to_insert)}</i>")
            msg_lines.append("⚠️ <i>Disclaimer: Always do your own research (DYOR). Trading carries risks!</i>")
            
            broadcast_telegram_message("\n".join(msg_lines), category="saham")
            
        else:
            logger.info("[ALERT ENGINE] No alerts triggered today.")
            
        conn.close()
    except Exception as e:
        logger.error(f"[ALERT ENGINE] Error running daily alerts: {e}")
