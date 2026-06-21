import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ─── Constants (mirrors smc.pine defaults) ────────────────────────────────────
BULLISH     = 1
BEARISH     = -1
BULLISH_LEG = 1
BEARISH_LEG = 0
NO_LEG      = -1

INTERNAL_SIZE    = 5    # Pine: getCurrentStructure(5, internal=true)
SWING_SIZE       = 50   # Pine: getCurrentStructure(50)
OB_MAX_COUNT     = 100
BUY_COOLDOWN     = 5    # bars
SELL_COOLDOWN    = 5
MIN_SL_PCT       = 0.005  # 0.5% minimum risk
RR_RATIO         = 2.0


def _run_smc_engine(opens, highs, lows, closes, n, direction="BUY"):
    """
    Core Pine Script SMC state machine translated 1:1 to Python.
    Runs bar-by-bar through all n bars and returns signals list.

    direction: "BUY" | "SELL" | "BOTH"

    Signal dict keys:
        idx, entry, sl, tp
    """
    # ── Pre-compute ATR (RMA-200, matches ta.atr(200)) ──
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
    alpha = 1.0 / 200
    atr = np.zeros(n)
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]

    # Pine: parsedHighs / parsedLows (high-volatility bar filter)
    parsed_highs = np.where((highs - lows) >= (2 * np.maximum(atr, 1e-9)), lows, highs)
    parsed_lows  = np.where((highs - lows) >= (2 * np.maximum(atr, 1e-9)), highs, lows)

    # ── Rolling max/min for leg detection ──
    hs = pd.Series(highs)
    ls = pd.Series(lows)
    roll_max_5  = hs.rolling(INTERNAL_SIZE, min_periods=INTERNAL_SIZE).max().values
    roll_min_5  = ls.rolling(INTERNAL_SIZE, min_periods=INTERNAL_SIZE).min().values
    roll_max_50 = hs.rolling(SWING_SIZE,    min_periods=SWING_SIZE).max().values
    roll_min_50 = ls.rolling(SWING_SIZE,    min_periods=SWING_SIZE).min().values

    # ── Pivot state: [current_level, last_level, crossed(0/1), bar_index] ──
    int_hi = np.array([0.0, 0.0, 0.0, 0.0])
    int_lo = np.array([0.0, 0.0, 0.0, 0.0])
    sw_hi  = np.array([0.0, 0.0, 0.0, 0.0])
    sw_lo  = np.array([0.0, 0.0, 0.0, 0.0])

    int_trend = 0
    sw_trend  = 0
    int_leg   = NO_LEG
    sw_leg    = NO_LEG

    # Internal Order Blocks: [bar_high, bar_low, bar_index, bias]
    int_obs: list = []

    # CHoCH state machine (Adventurer section)
    active_bull_choch = False
    active_bear_choch = False

    # BOS trend-following state machine
    active_bull_bos = False
    active_bear_bos = False
    bos_fired_bull  = False   # only first BOS per trend cycle
    bos_fired_bear  = False

    last_buy_bar  = -999
    last_sell_bar = -999
    last_buy_trend_bar  = -999
    last_sell_trend_bar = -999
    signals       = []

    for i in range(n):
        # ── Reset per-bar alerts ──
        int_bull_choch = False
        int_bear_choch = False
        int_bull_bos   = False
        int_bear_bos   = False
        sw_bull_choch  = False
        sw_bear_choch  = False
        sw_bull_bos    = False
        sw_bear_bos    = False

        # ══════════════════════════════════════════════════════════════
        # 1) getCurrentStructure() — update swing & internal pivots
        # ══════════════════════════════════════════════════════════════

        # --- Swing (size=50) ---
        if i >= SWING_SIZE and not np.isnan(roll_max_50[i]):
            piv_idx = i - SWING_SIZE
            new_leg_high = highs[piv_idx] > roll_max_50[i]
            new_leg_low  = lows[piv_idx]  < roll_min_50[i]
            new_sw_leg   = sw_leg
            if new_leg_high:
                new_sw_leg = BEARISH_LEG
            elif new_leg_low:
                new_sw_leg = BULLISH_LEG

            if new_sw_leg != sw_leg and new_sw_leg != NO_LEG:
                if new_sw_leg == BULLISH_LEG:
                    sw_lo[1] = sw_lo[0]
                    sw_lo[0] = lows[piv_idx]
                    sw_lo[2] = 0.0
                    sw_lo[3] = piv_idx
                else:
                    sw_hi[1] = sw_hi[0]
                    sw_hi[0] = highs[piv_idx]
                    sw_hi[2] = 0.0
                    sw_hi[3] = piv_idx
                sw_leg = new_sw_leg

        # --- Internal (size=5) ---
        if i >= INTERNAL_SIZE and not np.isnan(roll_max_5[i]):
            piv_idx = i - INTERNAL_SIZE
            new_leg_high = highs[piv_idx] > roll_max_5[i]
            new_leg_low  = lows[piv_idx]  < roll_min_5[i]
            new_int_leg  = int_leg
            if new_leg_high:
                new_int_leg = BEARISH_LEG
            elif new_leg_low:
                new_int_leg = BULLISH_LEG

            if new_int_leg != int_leg and new_int_leg != NO_LEG:
                if new_int_leg == BULLISH_LEG:
                    int_lo[1] = int_lo[0]
                    int_lo[0] = lows[piv_idx]
                    int_lo[2] = 0.0
                    int_lo[3] = piv_idx
                else:
                    int_hi[1] = int_hi[0]
                    int_hi[0] = highs[piv_idx]
                    int_hi[2] = 0.0
                    int_hi[3] = piv_idx
                int_leg = new_int_leg

        # ══════════════════════════════════════════════════════════════
        # 2) displayStructure() — detect breaks, classify BOS/CHoCH,
        #    store Internal Order Blocks
        # ══════════════════════════════════════════════════════════════

        if i < 1:
            continue

        c  = closes[i]
        pc = closes[i - 1]
        h  = highs[i]
        lo = lows[i]

        # ── Internal Bullish Break ──
        level = int_hi[0]
        extra = (int_hi[0] != sw_hi[0])          # Pine confluence filter
        if level > 0 and c > level and pc <= level and int_hi[2] == 0.0 and extra:
            tag_choch = (int_trend == BEARISH)
            if tag_choch:
                int_bull_choch = True
            else:
                int_bull_bos = True
            int_hi[2]  = 1.0
            int_trend  = BULLISH
            # Store bullish internal OB (parsedLow min in range)
            start = int(int_hi[3])
            end   = min(i, n)
            if 0 <= start < end:
                seg  = parsed_lows[start:end]
                pidx = start + int(np.argmin(seg))
                ob   = [parsed_highs[pidx], parsed_lows[pidx], pidx, BULLISH]
                if len(int_obs) >= OB_MAX_COUNT:
                    int_obs.pop()
                int_obs.insert(0, ob)

        # ── Internal Bearish Break ──
        level = int_lo[0]
        extra = (int_lo[0] != sw_lo[0])
        if level > 0 and c < level and pc >= level and int_lo[2] == 0.0 and extra:
            tag_choch = (int_trend == BULLISH)
            if tag_choch:
                int_bear_choch = True
            else:
                int_bear_bos = True
            int_lo[2]  = 1.0
            int_trend  = BEARISH
            start = int(int_lo[3])
            end   = min(i, n)
            if 0 <= start < end:
                seg  = parsed_highs[start:end]
                pidx = start + int(np.argmax(seg))
                ob   = [parsed_highs[pidx], parsed_lows[pidx], pidx, BEARISH]
                if len(int_obs) >= OB_MAX_COUNT:
                    int_obs.pop()
                int_obs.insert(0, ob)

        # ── Swing Bullish Break ──
        level = sw_hi[0]
        if level > 0 and c > level and pc <= level and sw_hi[2] == 0.0:
            if sw_trend == BEARISH:
                sw_bull_choch = True
            else:
                sw_bull_bos = True
            sw_hi[2]  = 1.0
            sw_trend  = BULLISH

        # ── Swing Bearish Break ──
        level = sw_lo[0]
        if level > 0 and c < level and pc >= level and sw_lo[2] == 0.0:
            if sw_trend == BULLISH:
                sw_bear_choch = True
            else:
                sw_bear_bos = True
            sw_lo[2]  = 1.0
            sw_trend  = BEARISH

        # ══════════════════════════════════════════════════════════════
        # 3) deleteOrderBlocks() — mitigate OBs via High/Low
        # ══════════════════════════════════════════════════════════════

        j = len(int_obs) - 1
        while j >= 0:
            ob = int_obs[j]
            if h > ob[0] and ob[3] == BEARISH:
                int_obs.pop(j)
            elif lo < ob[1] and ob[3] == BULLISH:
                int_obs.pop(j)
            j -= 1

        # ══════════════════════════════════════════════════════════════
        # 4) CHoCH State Machine (Adventurer section)
        # ══════════════════════════════════════════════════════════════

        if int_bull_choch or sw_bull_choch:
            active_bull_choch = True
            active_bear_choch = False
            # Reset BOS tracking for new trend cycle
            bos_fired_bull = False
            active_bull_bos = False
            if direction in ("BUY", "BOTH"):
                signals.append({
                    'idx': i,
                    'type': 'BUY_PHASE1',
                    'entry': c,
                    'sl': 0.0,
                    'tp': 0.0
                })

        if int_bear_choch or sw_bear_choch:
            active_bear_choch = True
            active_bull_choch = False
            # Reset BOS tracking for new trend cycle
            bos_fired_bear = False
            active_bear_bos = False
            if direction in ("SELL", "BOTH"):
                signals.append({
                    'idx': i,
                    'type': 'SELL_PHASE1',
                    'entry': c,
                    'sl': 0.0,
                    'tp': 0.0
                })

        if int_bull_bos or sw_bull_bos:
            active_bull_choch = False
            # First BOS in bullish trend = trend continuation signal
            if not bos_fired_bull and direction in ("BUY", "BOTH"):
                bos_fired_bull = True
                active_bull_bos = True
                signals.append({
                    'idx': i,
                    'type': 'BUY_TREND_PHASE1',
                    'entry': c,
                    'sl': 0.0,
                    'tp': 0.0
                })

        if int_bear_bos or sw_bear_bos:
            active_bear_choch = False
            # First BOS in bearish trend = trend continuation signal
            if not bos_fired_bear and direction in ("SELL", "BOTH"):
                bos_fired_bear = True
                active_bear_bos = True
                signals.append({
                    'idx': i,
                    'type': 'SELL_TREND_PHASE1',
                    'entry': c,
                    'sl': 0.0,
                    'tp': 0.0
                })

        # ══════════════════════════════════════════════════════════════
        # 5) Signal Check — BUY
        # ══════════════════════════════════════════════════════════════

        if direction in ("BUY", "BOTH") and active_bull_choch:
            if (i - last_buy_bar) > BUY_COOLDOWN:
                # Bullish reversal candle
                bull_reversal = (c > opens[i]) and (c > pc)
                if bull_reversal:
                    # POI check: price inside a live bullish Internal OB
                    inside_bull_poi = False
                    bull_distal     = 1e18

                    for ob in int_obs:
                        if ob[3] == BULLISH and lo <= ob[0] and h >= ob[1]:
                            inside_bull_poi = True
                            if ob[1] < bull_distal:
                                bull_distal = ob[1]

                    if inside_bull_poi:
                        if bull_distal >= 1e18:
                            bull_distal = lo

                        entry_price = c
                        sl_price    = bull_distal
                        risk        = entry_price - sl_price

                        # Fallback SL to last swing low if too tight
                        if risk <= 0 or (risk / entry_price) < MIN_SL_PCT:
                            sl_price = sw_lo[0]
                            risk     = entry_price - sl_price

                        if risk > 0:
                            tp_price    = entry_price + (risk * RR_RATIO)
                            last_buy_bar = i
                            signals.append({
                                'idx':       i,
                                'type':      'BUY',
                                'entry':     entry_price,
                                'sl':        sl_price,
                                'tp':        tp_price,
                            })

        # ══════════════════════════════════════════════════════════════
        # 6) Signal Check — SELL (Reversal after CHoCH)
        # ══════════════════════════════════════════════════════════════

        if direction in ("SELL", "BOTH") and active_bear_choch:
            if (i - last_sell_bar) > SELL_COOLDOWN:
                bear_reversal = (c < opens[i]) and (c < pc)
                if bear_reversal:
                    inside_bear_poi = False
                    bear_distal     = 0.0

                    for ob in int_obs:
                        if ob[3] == BEARISH and h >= ob[1] and lo <= ob[0]:
                            inside_bear_poi = True
                            if ob[0] > bear_distal:
                                bear_distal = ob[0]

                    if inside_bear_poi:
                        if bear_distal <= 0:
                            bear_distal = h

                        entry_price = c
                        sl_price    = bear_distal
                        risk        = sl_price - entry_price

                        # Fallback SL to last swing high if too tight
                        if risk <= 0 or (risk / entry_price) < MIN_SL_PCT:
                            sl_price = sw_hi[0]
                            risk     = sl_price - entry_price

                        if risk > 0:
                            tp_price     = entry_price - (risk * RR_RATIO)
                            last_sell_bar = i
                            signals.append({
                                'idx':   i,
                                'type':  'SELL',
                                'entry': entry_price,
                                'sl':    sl_price,
                                'tp':    tp_price,
                            })

        # ══════════════════════════════════════════════════════════════
        # 7) Signal Check — BUY TREND (Continuation after BOS)
        # ══════════════════════════════════════════════════════════════

        if direction in ("BUY", "BOTH") and active_bull_bos:
            if (i - last_buy_trend_bar) > BUY_COOLDOWN:
                bull_reversal = (c > opens[i]) and (c > pc)
                if bull_reversal:
                    inside_bull_poi = False
                    bull_distal     = 1e18

                    for ob in int_obs:
                        if ob[3] == BULLISH and lo <= ob[0] and h >= ob[1]:
                            inside_bull_poi = True
                            if ob[1] < bull_distal:
                                bull_distal = ob[1]

                    if inside_bull_poi:
                        if bull_distal >= 1e18:
                            bull_distal = lo

                        entry_price = c
                        sl_price    = bull_distal
                        risk        = entry_price - sl_price

                        if risk <= 0 or (risk / entry_price) < MIN_SL_PCT:
                            sl_price = sw_lo[0]
                            risk     = entry_price - sl_price

                        if risk > 0:
                            tp_price    = entry_price + (risk * RR_RATIO)
                            last_buy_trend_bar = i
                            active_bull_bos = False  # consumed
                            signals.append({
                                'idx':       i,
                                'type':      'BUY_TREND',
                                'entry':     entry_price,
                                'sl':        sl_price,
                                'tp':        tp_price,
                            })

        # ══════════════════════════════════════════════════════════════
        # 8) Signal Check — SELL TREND (Continuation after BOS)
        # ══════════════════════════════════════════════════════════════

        if direction in ("SELL", "BOTH") and active_bear_bos:
            if (i - last_sell_trend_bar) > SELL_COOLDOWN:
                bear_reversal = (c < opens[i]) and (c < pc)
                if bear_reversal:
                    inside_bear_poi = False
                    bear_distal     = 0.0

                    for ob in int_obs:
                        if ob[3] == BEARISH and h >= ob[1] and lo <= ob[0]:
                            inside_bear_poi = True
                            if ob[0] > bear_distal:
                                bear_distal = ob[0]

                    if inside_bear_poi:
                        if bear_distal <= 0:
                            bear_distal = h

                        entry_price = c
                        sl_price    = bear_distal
                        risk        = sl_price - entry_price

                        if risk <= 0 or (risk / entry_price) < MIN_SL_PCT:
                            sl_price = sw_hi[0]
                            risk     = sl_price - entry_price

                        if risk > 0:
                            tp_price     = entry_price - (risk * RR_RATIO)
                            last_sell_trend_bar = i
                            active_bear_bos = False  # consumed
                            signals.append({
                                'idx':   i,
                                'type':  'SELL_TREND',
                                'entry': entry_price,
                                'sl':    sl_price,
                                'tp':    tp_price,
                            })

    return signals


# ─── Public API (called by AlertEngine) ───────────────────────────────────────

def get_smc_buy_signals(df: pd.DataFrame) -> list | None:
    """
    Run SMC engine on H1 DataFrame (columns: Open/High/Low/Close).
    Returns list of BUY signal dicts if current bar (last row) triggers, else None.

    Expected columns (case-insensitive): Open, High, Low, Close
    """
    if len(df) < SWING_SIZE + 10:
        return None

    df = df.copy()
    df.reset_index(drop=True, inplace=True)

    # Normalise column names
    col_map = {c.lower(): c for c in df.columns}
    opens  = df[col_map.get('open',  'Open')].values.astype(np.float64)
    highs  = df[col_map.get('high',  'High')].values.astype(np.float64)
    lows   = df[col_map.get('low',   'Low')].values.astype(np.float64)
    closes = df[col_map.get('close', 'Close')].values.astype(np.float64)
    n      = len(df)

    signals = _run_smc_engine(opens, highs, lows, closes, n, direction="BUY")

    # Only care if the LAST bar triggered
    last_bar_signals = [sig for sig in signals if sig['idx'] == n - 1]
    if not last_bar_signals:
        return None

    results = []
    for sig in last_bar_signals:
        if sig['type'] == 'BUY_PHASE1':
            results.append({
                "strategy_name":   "SMC_Reversal_Fase1",
                "price_at_signal": sig['entry'],
                "target_price":    0.0,
                "stop_loss":       0.0,
                "type":            "BUY_PHASE1",
            })
        elif sig['type'] == 'BUY':
            results.append({
                "strategy_name":   "SMC_Reversal_Fase2",
                "price_at_signal": sig['entry'],
                "target_price":    round(sig['tp'], 5),
                "stop_loss":       round(sig['sl'], 5),
                "type":            "BUY",
            })
        elif sig['type'] == 'BUY_TREND_PHASE1':
            results.append({
                "strategy_name":   "SMC_Trend_Fase1",
                "price_at_signal": sig['entry'],
                "target_price":    0.0,
                "stop_loss":       0.0,
                "type":            "BUY_TREND_PHASE1",
            })
        elif sig['type'] == 'BUY_TREND':
            results.append({
                "strategy_name":   "SMC_Trend_Fase2",
                "price_at_signal": sig['entry'],
                "target_price":    round(sig['tp'], 5),
                "stop_loss":       round(sig['sl'], 5),
                "type":            "BUY_TREND",
            })

    return results if results else None


def get_smc_sell_signals(df: pd.DataFrame) -> list | None:
    """
    Run SMC engine on H1 DataFrame.
    Returns list of SELL signal dicts if current bar triggers, else None.
    Only used for forex pairs.
    """
    if len(df) < SWING_SIZE + 10:
        return None

    df = df.copy()
    df.reset_index(drop=True, inplace=True)

    col_map = {c.lower(): c for c in df.columns}
    opens  = df[col_map.get('open',  'Open')].values.astype(np.float64)
    highs  = df[col_map.get('high',  'High')].values.astype(np.float64)
    lows   = df[col_map.get('low',   'Low')].values.astype(np.float64)
    closes = df[col_map.get('close', 'Close')].values.astype(np.float64)
    n      = len(df)

    signals = _run_smc_engine(opens, highs, lows, closes, n, direction="SELL")

    last_bar_signals = [sig for sig in signals if sig['idx'] == n - 1]
    if not last_bar_signals:
        return None

    results = []
    for sig in last_bar_signals:
        if sig['type'] == 'SELL_PHASE1':
            results.append({
                "strategy_name":   "SMC_Reversal_Fase1",
                "price_at_signal": sig['entry'],
                "target_price":    0.0,
                "stop_loss":       0.0,
                "type":            "SELL_PHASE1",
            })
        elif sig['type'] == 'SELL':
            results.append({
                "strategy_name":   "SMC_Reversal_Fase2",
                "price_at_signal": sig['entry'],
                "target_price":    round(sig['tp'], 5),
                "stop_loss":       round(sig['sl'], 5),
                "type":            "SELL",
            })
        elif sig['type'] == 'SELL_TREND_PHASE1':
            results.append({
                "strategy_name":   "SMC_Trend_Fase1",
                "price_at_signal": sig['entry'],
                "target_price":    0.0,
                "stop_loss":       0.0,
                "type":            "SELL_TREND_PHASE1",
            })
        elif sig['type'] == 'SELL_TREND':
            results.append({
                "strategy_name":   "SMC_Trend_Fase2",
                "price_at_signal": sig['entry'],
                "target_price":    round(sig['tp'], 5),
                "stop_loss":       round(sig['sl'], 5),
                "type":            "SELL_TREND",
            })

    return results if results else None
