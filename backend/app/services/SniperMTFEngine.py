import numpy as np
import pandas as pd
import sqlite3
import yfinance as yf
from datetime import datetime
from app.core.logger import logger

def detect_d1_sniper_setup(df_d1: pd.DataFrame) -> dict | None:
    """
    Detect if D1 daily timeframe has:
    1. Bullish CHoCH (Break above previous Swing High).
    2. Bullish FVG (Fair Value Gap) associated with the move (before, during, or after CHoCH).
    3. Retest/Tap: Current/recent daily candle touches the D1 FVG zone.
    
    Returns setup info dict or None.
    """
    if len(df_d1) < 25:
        return None

    df = df_d1.sort_values('date').reset_index(drop=True)
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    opens = df['open'].values
    dates = df['date'].values
    n = len(df)

    # 1. Identify Swing Highs & Swing Lows (Pivot lookback = 2)
    lookback = 2
    swing_highs = [] # list of (index, high_price)
    swing_lows = []  # list of (index, low_price)

    for i in range(lookback, n - 1):
        # Local peak (Swing High)
        left_valid = all(highs[i] >= highs[i - j] for j in range(1, min(lookback + 1, i + 1)))
        right_valid = (i == n - 1) or all(highs[i] >= highs[i + j] for j in range(1, min(lookback + 1, n - i)))
        if left_valid and right_valid:
            swing_highs.append((i, highs[i]))
            
        # Local trough (Swing Low)
        left_low_valid = all(lows[i] <= lows[i - j] for j in range(1, min(lookback + 1, i + 1)))
        right_low_valid = (i == n - 1) or all(lows[i] <= lows[i + j] for j in range(1, min(lookback + 1, n - i)))
        if left_low_valid and right_low_valid:
            swing_lows.append((i, lows[i]))

    if not swing_highs:
        # Fallback: find rolling peak
        hs = pd.Series(highs)
        roll_max = hs.rolling(5, min_periods=3).max()
        for i in range(3, n):
            if highs[i] == roll_max.iloc[i]:
                swing_highs.append((i, highs[i]))

    if not swing_highs:
        return None

    # 2. Identify Bullish CHoCH in recent bars (within last 25 bars)
    # Bullish CHoCH: Price breaks above a previous Swing High
    recent_choch = None
    for i in range(max(1, n - 25), n):
        prior_shs = [sh for sh in swing_highs if sh[0] < i]
        if not prior_shs:
            continue
        last_sh_idx, last_sh_val = prior_shs[-1]
        
        # Bullish break
        if closes[i] > last_sh_val and closes[i - 1] <= last_sh_val:
            recent_choch = {
                'bar_idx': i,
                'date': dates[i],
                'broken_level': last_sh_val,
                'swing_high_target': max(highs[max(0, i - 5):i + 1])
            }

    # If no strict CHoCH in last 25 bars, check if recent close broke local resistance in window
    if not recent_choch:
        for i in range(max(3, n - 20), n):
            local_max_prev = max(highs[max(0, i - 10):i])
            if closes[i] > local_max_prev and closes[i - 1] <= local_max_prev:
                recent_choch = {
                    'bar_idx': i,
                    'date': dates[i],
                    'broken_level': local_max_prev,
                    'swing_high_target': max(highs[max(0, i - 5):i + 1])
                }
                break

    if not recent_choch:
        return None

    # 3. Detect Bullish FVGs (Low[i] > High[i-2]) within window around CHoCH
    # FVG can be before, during, or after CHoCH (within last 25 bars)
    active_fvgs = []
    fvg_start_idx = max(2, recent_choch['bar_idx'] - 10)
    for i in range(fvg_start_idx, n):
        if lows[i] > highs[i - 2]:
            fvg_bottom = highs[i - 2]
            fvg_top = lows[i]
            # Verify FVG is meaningful (spread > 0.3%)
            if (fvg_top - fvg_bottom) / fvg_bottom >= 0.003:
                # Check if FVG wasn't completely broken (closed below) before current bar
                is_invalid = any(closes[k] < fvg_bottom for k in range(i + 1, n - 1)) if i + 1 < n - 1 else False
                if not is_invalid:
                    active_fvgs.append({
                        'bar_idx': i,
                        'top': fvg_top,
                        'bottom': fvg_bottom
                    })

    if not active_fvgs:
        return None

    # Take the most relevant active FVG (closest to recent action)
    latest_fvg = active_fvgs[-1]
    
    # 4. Check if today's / recent daily bar tests (taps) the FVG zone
    latest_daily_low = lows[-1]
    latest_daily_high = highs[-1]
    latest_daily_close = closes[-1]

    # Retest condition: Price entered the FVG zone
    # (Low <= FVG Top and High >= FVG Bottom)
    is_retesting = (latest_daily_low <= latest_fvg['top'] * 1.01) and (latest_daily_high >= latest_fvg['bottom'] * 0.99)
    
    if not is_retesting:
        return None

    return {
        'fvg_top': latest_fvg['top'],
        'fvg_bottom': latest_fvg['bottom'],
        'swing_high_target': recent_choch['swing_high_target'],
        'choch_date': str(recent_choch['date']),
        'latest_close': float(latest_daily_close)
    }

def detect_h1_sniper_trigger(df_h1: pd.DataFrame, d1_setup: dict, target_date: str = None) -> dict | None:
    """
    Evaluates intraday H1 candles on target_date inside the D1 FVG zone:
    - Trigger A: Bullish Engulfing (Body >= 50%, Volume > Prev Volume)
    - Trigger B: Hammer / Rejection Pinbar (Lower wick >= 60%, Upper wick <= 15%, Body <= 30%)
    
    Returns trigger signal dict or None.
    """
    if df_h1 is None or len(df_h1) < 2:
        return None

    df = df_h1.copy()
    
    # Standardize column names
    col_map = {c.lower(): c for c in df.columns}
    df['open'] = df[col_map['open']].astype(float)
    df['high'] = df[col_map['high']].astype(float)
    df['low'] = df[col_map['low']].astype(float)
    df['close'] = df[col_map['close']].astype(float)
    df['volume'] = df[col_map['volume']].astype(float)
    
    # Ensure datetime format
    if 'datetime' in col_map:
        df['dt'] = pd.to_datetime(df[col_map['datetime']])
    else:
        df['dt'] = pd.to_datetime(df.index)

    df['date_str'] = df['dt'].dt.strftime('%Y-%m-%d')
    df['time_str'] = df['dt'].dt.strftime('%H:%M')
    df = df.sort_values('dt').reset_index(drop=True)

    # Determine target date to scan (if not provided, use the latest date in H1 data)
    scan_date = target_date if target_date else df['date_str'].iloc[-1]
    
    # Get bars for the target date
    day_indices = df[df['date_str'] == scan_date].index.tolist()
    if not day_indices:
        return None

    fvg_top = d1_setup['fvg_top']
    fvg_bottom = d1_setup['fvg_bottom']
    d1_target = d1_setup['swing_high_target']

    # Scan each H1 candle of the target date in chronological order
    for idx in day_indices:
        if idx < 1:
            continue
            
        curr = df.iloc[idx]
        prev = df.iloc[idx - 1]

        o_curr, h_curr, l_curr, c_curr, v_curr = curr['open'], curr['high'], curr['low'], curr['close'], curr['volume']
        o_prev, h_prev, l_prev, c_prev, v_prev = prev['open'], prev['high'], prev['low'], prev['close'], prev['volume']

        # 1. Price must interact with the D1 FVG zone
        touches_zone = (l_curr <= fvg_top * 1.01) and (h_curr >= fvg_bottom * 0.99)
        if not touches_zone:
            continue

        total_range = h_curr - l_curr
        if total_range <= 0:
            continue

        body = abs(c_curr - o_curr)
        lower_wick = min(o_curr, c_curr) - l_curr
        upper_wick = h_curr - max(o_curr, c_curr)
        
        # ── Trigger A: Bullish Engulfing ──
        is_prev_bearish = c_prev < o_prev
        is_curr_bullish = c_curr > o_curr
        is_engulfing = (c_curr >= o_prev) and (o_curr <= c_prev * 1.002)
        body_ratio_engulf = body / total_range
        vol_confirmed = (v_curr > v_prev) or (v_curr >= 500_000)

        if is_prev_bearish and is_curr_bullish and is_engulfing and (body_ratio_engulf >= 0.50) and vol_confirmed:
            entry = float(c_curr)
            sl = float(min(l_curr, l_prev))
            tp = float(max(d1_target, entry * 1.06))
            
            return {
                'strategy_name': 'Sniper_MTF_Engulfing',
                'trigger_type': 'Bullish Engulfing',
                'trigger_time': curr['time_str'],
                'signal_date': scan_date,
                'price_at_signal': entry,
                'stop_loss': sl,
                'target_price': tp,
                'fvg_top': fvg_top,
                'fvg_bottom': fvg_bottom
            }

        # ── Trigger B: Hammer / Bullish Rejection Pinbar ──
        lower_wick_ratio = lower_wick / total_range
        upper_wick_ratio = upper_wick / total_range
        body_ratio_hammer = body / total_range
        close_position_ratio = (c_curr - l_curr) / total_range

        is_hammer = (
            (lower_wick_ratio >= 0.60) and
            (upper_wick_ratio <= 0.15) and
            (body_ratio_hammer <= 0.30) and
            (close_position_ratio >= 0.65) and
            vol_confirmed
        )

        if is_hammer:
            entry = float(c_curr)
            sl = float(l_curr)
            tp = float(max(d1_target, entry * 1.06))
            
            return {
                'strategy_name': 'Sniper_MTF_Rejection',
                'trigger_type': 'Hammer Rejection',
                'trigger_time': curr['time_str'],
                'signal_date': scan_date,
                'price_at_signal': entry,
                'stop_loss': sl,
                'target_price': tp,
                'fvg_top': fvg_top,
                'fvg_bottom': fvg_bottom
            }

    return None

def scan_sniper_mtf_alerts(conn: sqlite3.Connection, target_date: str = None) -> list:
    """
    Main orchestrator for scanning Sniper MTF alerts across all eligible IDX stocks (150 <= price <= 5000).
    Runs on EOD.
    """
    logger.info("[SNIPER MTF] Starting multi-timeframe sniper scan (D1 Setup + H1 Trigger)...")
    cursor = conn.cursor()
    
    # 1. Fetch valid tickers in price range 150 - 5000 based on latest daily prices
    cursor.execute("""
        SELECT ticker, close 
        FROM daily_prices 
        WHERE date = (SELECT MAX(date) FROM daily_prices)
    """)
    rows = cursor.fetchall()
    
    valid_tickers = [t for t, c in rows if 150 <= c <= 5000 and t != 'COMPOSITE']
    if not valid_tickers:
        logger.info("[SNIPER MTF] No tickers found in price range 150-5000.")
        return []

    # 2. Identify tickers with active D1 Setup
    candidates = {}
    for ticker in valid_tickers:
        if target_date:
            q = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 60"
            df_d1 = pd.read_sql_query(q, conn, params=(ticker, target_date))
        else:
            q = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 60"
            df_d1 = pd.read_sql_query(q, conn, params=(ticker,))
        
        if len(df_d1) < 25:
            continue
            
        d1_setup = detect_d1_sniper_setup(df_d1)
        if d1_setup:
            candidates[ticker] = d1_setup

    if not candidates:
        logger.info("[SNIPER MTF] No tickers with active D1 Bullish CHoCH + FVG Retest.")
        return []

    logger.info(f"[SNIPER MTF] Found {len(candidates)} candidate tickers with active D1 setup: {list(candidates.keys())}")

    # 3. Fetch H1 Data for candidate tickers
    candidate_tickers = list(candidates.keys())
    yf_tickers = [f"{t}.JK" for t in candidate_tickers]
    
    try:
        if len(yf_tickers) == 1:
            df_h1_raw = yf.download(yf_tickers[0], period="1mo", interval="1h", progress=False)
        else:
            df_h1_raw = yf.download(yf_tickers, period="1mo", interval="1h", group_by='ticker', progress=False)
    except Exception as e:
        logger.error(f"[SNIPER MTF] Failed to download H1 data via yfinance: {e}")
        return []

    sniper_alerts = []
    
    for ticker in candidate_tickers:
        yf_t = f"{ticker}.JK"
        if len(candidate_tickers) == 1:
            ticker_h1 = df_h1_raw.copy()
        else:
            if yf_t not in df_h1_raw.columns.levels[0]:
                continue
            ticker_h1 = df_h1_raw[yf_t].dropna(subset=['Close']).copy()

        if ticker_h1.empty:
            continue

        d1_setup = candidates[ticker]
        signal = detect_h1_sniper_trigger(ticker_h1, d1_setup, target_date=target_date)
        
        if signal:
            signal['ticker'] = ticker
            sniper_alerts.append(signal)
            logger.info(f"[SNIPER MTF] 🔥 Triggered: {ticker} -> {signal['strategy_name']} at {signal['trigger_time']}")

    return sniper_alerts
