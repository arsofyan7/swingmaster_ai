import sqlite3
import pandas as pd
import json
import asyncio
from datetime import datetime
from app.core.logger import logger

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate necessary indicators for V8, V3, and V6 strategies.
    Requires columns: date, open, high, low, close, volume
    """
    df = df.sort_values('date').reset_index(drop=True)
    if len(df) == 0:
        return df

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
        return cond1 and cond2 and cond3 and cond4

    # V3_Breakout Logic
    def check_v3(latest):
        cond1 = latest['volume'] >= (2 * latest['VMA_20'])
        cond2 = (latest['close'] > latest['EMA_20']) and (latest['close_prev'] <= latest['EMA_20_prev'])
        cond3 = latest['MACD'] > latest['MACD_prev']
        return cond1 and cond2 and cond3

    # V6_Bandar Logic
    def check_v6(latest):
        cond1 = latest['close'] > latest['EMA_200']
        cond2 = (latest['low'] <= latest['EMA_20']) and (latest['close'] >= latest['EMA_20']) and (latest['close'] <= (latest['EMA_20'] * 1.02))
        cond3 = (latest['OBV'] > latest['OBV_EMA_20']) and (latest['ADL'] > latest['ADL_EMA_20'])
        return cond1 and cond2 and cond3

    strategies = {
        "V8_Pullback": check_v8(latest),
        "V3_Breakout": check_v3(latest),
        "V6_Bandar": check_v6(latest)
    }

    # Evaluate based on rank
    for rank in ['peringkat_1', 'peringkat_2', 'peringkat_3']:
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

async def run_daily_alerts():
    logger.info("[ALERT ENGINE] Starting daily alert generation...")
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
        today_str = datetime.now().strftime("%Y-%m-%d")

        for ticker in tickers:
            if ticker not in matrix:
                continue

            # Fetch last 250 days for accurate EMA200
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
        else:
            logger.info("[ALERT ENGINE] No alerts triggered today.")
            
        conn.close()
    except Exception as e:
        logger.error(f"[ALERT ENGINE] Error running daily alerts: {e}")
