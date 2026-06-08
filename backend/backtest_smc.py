#!/usr/bin/env python3
"""
=============================================================================
 SMC Sniper Backtester v2 — Pandas Optimized
=============================================================================
 Source: smc.pine (Swingmaster : SMC Sniper Visualizer by LuxAlgo)

 Strategi BUY:
   1. Detect internal (size=5) & swing (size=50) structure
   2. Classify breakouts as BOS or CHoCH
   3. Store Internal Order Blocks on structure breaks
      (Swing OB OFF by default, FVG OFF by default)
   4. Track active CHoCH state
   5. BUY when: activeBullCHoCH + price inside bullish Internal OB (POI)
                + bullish reversal candle + cooldown 5 bar
   6. SL = distal OB, fallback ke swing low jika SL terlalu kecil
   7. TP = Entry + 2×Risk (RR 2:1)
   8. Position sizing: risk 1% modal per trade

 Matching Pine defaults:
   - showInternalOrderBlocksInput = true  → internal OBs STORED
   - showSwingOrderBlocksInput    = false → swing OBs NOT stored
   - showFairValueGapsInput       = false → FVGs NOT detected
   - orderBlockMitigationInput    = 'High/Low' → mitigate via high/low
   - useSession                   = OFF for saham BEI
=============================================================================
"""

import sqlite3
import os
import sys
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime

# ─── Constants ─────────────────────────────────────────────────────────────────
BULLISH = 1
BEARISH = -1
BULLISH_LEG = 1
BEARISH_LEG = 0
NO_LEG = -1

INTERNAL_SIZE = 5
SWING_SIZE = 50
OB_MAX_COUNT = 100
BUY_COOLDOWN_BARS = 5
RR_RATIO = 2.0
RISK_PCT = 0.01          # 1% risk per trade
INITIAL_CAPITAL = 100_000_000  # 100 juta
MIN_SL_PCT = 0.005       # Minimum 0.5% risk → fallback ke swing low
PRICE_MIN = 150          # Harga minimum saham
PRICE_MAX = 5000         # Harga maksimum saham


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class Trade:
    ticker: str
    entry_date: str
    entry_price: float
    sl_price: float
    tp_price: float
    shares: int
    position_value: float
    exit_date: str = ""
    exit_price: float = 0.0
    pnl: float = 0.0
    pnl_pct_capital: float = 0.0  # PnL as % of capital at entry
    result: str = ""               # WIN / LOSS / OPEN


# ─── SMC Engine (numpy arrays for speed) ───────────────────────────────────────

class SMCEngine:
    """
    Core SMC logic translated 1:1 from smc.pine.
    Operates on numpy arrays. Only internal OBs are tracked (matching Pine defaults).
    """

    def __init__(self, opens, highs, lows, closes, n):
        self.opens = opens
        self.highs = highs
        self.lows = lows
        self.closes = closes
        self.n = n

        # Pre-compute ATR & parsed highs/lows
        self.tr = np.empty(n)
        self.tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            self.tr[i] = max(highs[i] - lows[i],
                             abs(highs[i] - closes[i - 1]),
                             abs(lows[i] - closes[i - 1]))

        # Calculate RMA for ATR (matches TradingView's ta.atr)
        alpha = 1.0 / 200
        atr = np.zeros(n)
        atr[0] = self.tr[0]
        for i in range(1, n):
            atr[i] = alpha * self.tr[i] + (1 - alpha) * atr[i - 1]
        self.atr = atr

        self.parsed_highs = np.where(
            (highs - lows) >= (2 * np.maximum(self.atr, 1e-9)),
            lows, highs
        )
        self.parsed_lows = np.where(
            (highs - lows) >= (2 * np.maximum(self.atr, 1e-9)),
            highs, lows
        )

        # Pre-compute rolling max/min for leg detection
        hs = pd.Series(highs)
        ls = pd.Series(lows)
        self.roll_max_5 = hs.rolling(INTERNAL_SIZE, min_periods=INTERNAL_SIZE).max().values
        self.roll_min_5 = ls.rolling(INTERNAL_SIZE, min_periods=INTERNAL_SIZE).min().values
        self.roll_max_50 = hs.rolling(SWING_SIZE, min_periods=SWING_SIZE).max().values
        self.roll_min_50 = ls.rolling(SWING_SIZE, min_periods=SWING_SIZE).min().values

    def run(self):
        """Run the full SMC backtest, return list of signal dicts"""
        n = self.n
        highs = self.highs
        lows = self.lows
        closes = self.closes
        opens = self.opens

        # Pivot state: [current_level, last_level, crossed(0/1), bar_index]
        int_hi = np.array([0.0, 0.0, 0.0, 0.0])
        int_lo = np.array([0.0, 0.0, 0.0, 0.0])
        sw_hi = np.array([0.0, 0.0, 0.0, 0.0])
        sw_lo = np.array([0.0, 0.0, 0.0, 0.0])

        int_trend = 0
        sw_trend = 0

        # Leg state
        int_leg = NO_LEG
        sw_leg = NO_LEG

        # Internal Order Blocks: list of [bar_high, bar_low, bar_index, bias]
        int_obs: list[list[float]] = []

        # CHoCH state
        active_bull_choch = False
        active_bear_choch = False
        bull_liquidity_swept = False

        last_buy_bar = -999
        signals = []

        for i in range(n):
            # ── Reset per-bar alerts ──
            int_bull_choch = False
            int_bear_choch = False
            int_bull_bos = False
            int_bear_bos = False
            sw_bull_choch = False
            sw_bear_choch = False
            sw_bull_bos = False
            sw_bear_bos = False

            # ══════════════════════════════════════════════════════════════
            # 1) STRUCTURE DETECTION: update pivots (getCurrentStructure)
            # ══════════════════════════════════════════════════════════════

            # --- Swing (size=50) ---
            if i >= SWING_SIZE and not np.isnan(self.roll_max_50[i]):
                piv_idx = i - SWING_SIZE
                new_leg_high = highs[piv_idx] > self.roll_max_50[i]
                new_leg_low = lows[piv_idx] < self.roll_min_50[i]
                new_sw_leg = sw_leg
                if new_leg_high:
                    new_sw_leg = BEARISH_LEG
                elif new_leg_low:
                    new_sw_leg = BULLISH_LEG

                if new_sw_leg != sw_leg and new_sw_leg != NO_LEG:
                    if new_sw_leg == BULLISH_LEG:  # new pivot low
                        sw_lo[1] = sw_lo[0]
                        sw_lo[0] = lows[piv_idx]
                        sw_lo[2] = 0.0  # crossed = false
                        sw_lo[3] = piv_idx
                    else:  # new pivot high
                        sw_hi[1] = sw_hi[0]
                        sw_hi[0] = highs[piv_idx]
                        sw_hi[2] = 0.0
                        sw_hi[3] = piv_idx
                    sw_leg = new_sw_leg

            # --- Internal (size=5) ---
            if i >= INTERNAL_SIZE and not np.isnan(self.roll_max_5[i]):
                piv_idx = i - INTERNAL_SIZE
                new_leg_high = highs[piv_idx] > self.roll_max_5[i]
                new_leg_low = lows[piv_idx] < self.roll_min_5[i]
                new_int_leg = int_leg
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
            # 2) STRUCTURE BREAKS: displayStructure(internal=true)
            #    Only internal OBs stored (showSwingOrderBlocksInput=false)
            # ══════════════════════════════════════════════════════════════

            if i < 1:
                continue

            c = closes[i]
            pc = closes[i - 1]

            # ── Internal Bullish Break ──
            level = int_hi[0]
            extra = (int_hi[0] != sw_hi[0])  # Pine: internalHigh != swingHigh
            if level > 0 and c > level and pc <= level and int_hi[2] == 0.0 and extra:
                tag_choch = (int_trend == BEARISH)
                if tag_choch:
                    int_bull_choch = True
                else:
                    int_bull_bos = True
                int_hi[2] = 1.0  # crossed
                int_trend = BULLISH
                # Store internal OB (BULLISH)
                start = int(int_hi[3])
                end = min(i, n)
                if 0 <= start < end:
                    seg = self.parsed_lows[start:end]
                    pidx = start + int(np.argmin(seg))
                    ob = [self.parsed_highs[pidx], self.parsed_lows[pidx], pidx, BULLISH]
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
                int_lo[2] = 1.0
                int_trend = BEARISH
                start = int(int_lo[3])
                end = min(i, n)
                if 0 <= start < end:
                    seg = self.parsed_highs[start:end]
                    pidx = start + int(np.argmax(seg))
                    ob = [self.parsed_highs[pidx], self.parsed_lows[pidx], pidx, BEARISH]
                    if len(int_obs) >= OB_MAX_COUNT:
                        int_obs.pop()
                    int_obs.insert(0, ob)

            # ── Swing Bullish Break (CHoCH/BOS only, NO OB stored) ──
            level = sw_hi[0]
            if level > 0 and c > level and pc <= level and sw_hi[2] == 0.0:
                if sw_trend == BEARISH:
                    sw_bull_choch = True
                else:
                    sw_bull_bos = True
                sw_hi[2] = 1.0
                sw_trend = BULLISH

            # ── Swing Bearish Break ──
            level = sw_lo[0]
            if level > 0 and c < level and pc >= level and sw_lo[2] == 0.0:
                if sw_trend == BULLISH:
                    sw_bear_choch = True
                else:
                    sw_bear_bos = True
                sw_lo[2] = 1.0
                sw_trend = BEARISH

            # ── Liquidity Sweep Detection (Bullish) ──
            # Candle wicks below the current internal low but closes above it
            level_int_lo = int_lo[0]
            if level_int_lo > 0 and lows[i] < level_int_lo and c >= level_int_lo:
                bull_liquidity_swept = True
            
            # Reset sweep if there is a real break (close) below the low
            if int_bear_choch or int_bear_bos:
                bull_liquidity_swept = False

            # ══════════════════════════════════════════════════════════════
            # 3) OB MITIGATION: deleteOrderBlocks(internal=true)
            #    Pine: mitigationSource = High/Low (default)
            # ══════════════════════════════════════════════════════════════

            h = highs[i]
            lo = lows[i]
            j = len(int_obs) - 1
            while j >= 0:
                ob = int_obs[j]
                if h > ob[0] and ob[3] == BEARISH:
                    int_obs.pop(j)
                elif lo < ob[1] and ob[3] == BULLISH:
                    int_obs.pop(j)
                j -= 1

            # ══════════════════════════════════════════════════════════════
            # 4) CHoCH STATE MACHINE (Adventurer section)
            # ══════════════════════════════════════════════════════════════

            if int_bull_choch or sw_bull_choch:
                active_bull_choch = True
                active_bear_choch = False

            if int_bear_choch or sw_bear_choch:
                active_bear_choch = True
                active_bull_choch = False

            if int_bull_bos or sw_bull_bos:
                active_bull_choch = False

            if int_bear_bos or sw_bear_bos:
                active_bear_choch = False

            # ══════════════════════════════════════════════════════════════
            # 5) BUY SIGNAL CHECK
            # ══════════════════════════════════════════════════════════════

            if not active_bull_choch:
                continue
            # if not bull_liquidity_swept:
            #     continue
            if (i - last_buy_bar) <= BUY_COOLDOWN_BARS:
                continue

            # Price range filter: only trade stocks priced 150-5000
            if c < PRICE_MIN or c > PRICE_MAX:
                continue

            # Bullish reversal candle
            if c <= opens[i]:
                continue
            if c <= pc:
                continue

            # POI check: price inside a bullish Internal OB
            inside_bull_poi = False
            bull_distal = 1e18

            for ob in int_obs:
                if ob[3] == BULLISH and lo <= ob[0] and h >= ob[1]:
                    inside_bull_poi = True
                    if ob[1] < bull_distal:
                        bull_distal = ob[1]

            if not inside_bull_poi:
                continue

            if bull_distal >= 1e18:
                bull_distal = lo

            # ── SL / TP Determination ──
            entry_price = c
            sl_price = bull_distal
            risk = entry_price - sl_price

            # Fallback: if SL too tight, use last swing low
            if risk <= 0 or (risk / entry_price) < MIN_SL_PCT:
                sl_price = sw_lo[0]
                risk = entry_price - sl_price

            if risk <= 0:
                continue

            tp_price = entry_price + (risk * RR_RATIO)
            last_buy_bar = i

            signals.append({
                'idx': i,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
            })

        return signals


# ─── Trade Resolution with Position Sizing ────────────────────────────────────

def resolve_trades(signals, highs, lows, closes, dates, n, ticker):
    """
    Resolve signals → trades with proper 1% risk position sizing.
    One position at a time per ticker. Compounding.
    """
    trades: list[Trade] = []
    capital = float(INITIAL_CAPITAL)
    current_exit_idx = -1  # track open position

    for sig in signals:
        entry_idx = sig['idx']

        # Skip if still in a position
        if entry_idx <= current_exit_idx:
            continue

        entry_price = sig['entry']
        sl_price = sig['sl']
        tp_price = sig['tp']
        risk_per_share = entry_price - sl_price

        if risk_per_share <= 0 or capital <= 0:
            continue

        # Position sizing: risk 1% of current capital
        risk_amount = capital * RISK_PCT
        shares = int(risk_amount / risk_per_share)
        max_shares = int(capital / entry_price)
        shares = min(shares, max_shares)

        if shares <= 0:
            continue

        position_value = shares * entry_price

        trade = Trade(
            ticker=ticker,
            entry_date=dates[entry_idx],
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            shares=shares,
            position_value=position_value,
        )

        # Walk forward to find exit
        exit_found = False
        for j in range(entry_idx + 1, n):
            # SL hit first (conservative)
            if lows[j] <= sl_price:
                trade.exit_date = dates[j]
                trade.exit_price = sl_price
                trade.pnl = shares * (sl_price - entry_price)
                trade.result = "LOSS"
                current_exit_idx = j
                exit_found = True
                break

            # TP hit
            if highs[j] >= tp_price:
                trade.exit_date = dates[j]
                trade.exit_price = tp_price
                trade.pnl = shares * (tp_price - entry_price)
                trade.result = "WIN"
                current_exit_idx = j
                exit_found = True
                break

        if not exit_found:
            trade.exit_date = dates[n - 1]
            trade.exit_price = closes[n - 1]
            trade.pnl = shares * (closes[n - 1] - entry_price)
            trade.result = "OPEN"
            current_exit_idx = n - 1

        trade.pnl_pct_capital = (trade.pnl / capital) * 100 if capital > 0 else 0
        capital += trade.pnl
        if capital < 0:
            capital = 0

        trades.append(trade)

    return trades, capital


# ─── Statistics ────────────────────────────────────────────────────────────────

def compute_stats(trades: list[Trade], final_capital: float = None) -> dict:
    if not trades:
        return {
            'total': 0, 'wins': 0, 'losses': 0, 'open': 0,
            'win_rate': 0.0, 'total_pnl': 0.0, 'return_pct': 0.0,
            'final_capital': INITIAL_CAPITAL,
            'avg_win_pct': 0.0, 'avg_loss_pct': 0.0,
            'max_win_pct': 0.0, 'max_loss_pct': 0.0,
            'profit_factor': 0.0,
        }

    wins = [t for t in trades if t.result == "WIN"]
    losses = [t for t in trades if t.result == "LOSS"]
    open_t = [t for t in trades if t.result == "OPEN"]

    total_pnl = sum(t.pnl for t in trades)
    fc = final_capital if final_capital is not None else INITIAL_CAPITAL + total_pnl

    win_pcts = [t.pnl_pct_capital for t in wins]
    loss_pcts = [t.pnl_pct_capital for t in losses]

    gross_profit = sum(t.pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0

    return {
        'total': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'open': len(open_t),
        'win_rate': (len(wins) / len(trades) * 100) if trades else 0,
        'total_pnl': total_pnl,
        'return_pct': ((fc - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100,
        'final_capital': fc,
        'avg_win_pct': (sum(win_pcts) / len(win_pcts)) if win_pcts else 0,
        'avg_loss_pct': (sum(loss_pcts) / len(loss_pcts)) if loss_pcts else 0,
        'max_win_pct': max(win_pcts) if win_pcts else 0,
        'max_loss_pct': min(loss_pcts) if loss_pcts else 0,
        'profit_factor': (gross_profit / gross_loss) if gross_loss > 0 else float('inf'),
    }


def fmt_rp(amount: float) -> str:
    if abs(amount) >= 1e12:
        return f"Rp {amount/1e12:,.2f} T"
    elif abs(amount) >= 1e9:
        return f"Rp {amount/1e9:,.2f} M"
    elif abs(amount) >= 1e6:
        return f"Rp {amount/1e6:,.2f} Jt"
    else:
        return f"Rp {amount:,.0f}"


# ─── Report Generator ─────────────────────────────────────────────────────────

def generate_report(all_trades, ticker_results, output_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L = []

    L.append("=" * 100)
    L.append("  SMC SNIPER BACKTEST REPORT v2 — Swingmaster Strategy")
    L.append(f"  Generated     : {now}")
    L.append(f"  Modal Awal    : {fmt_rp(INITIAL_CAPITAL)}")
    L.append(f"  Risk per Trade: {RISK_PCT*100:.0f}% of capital")
    L.append(f"  RR Ratio      : 1:{RR_RATIO:.0f}")
    L.append(f"  Strategi      : CHoCH + Pullback ke Internal OB → BUY")
    L.append(f"  SL Fallback   : Swing Low (if OB SL < {MIN_SL_PCT*100:.1f}% from entry)")
    L.append(f"  Session Filter: OFF (Saham BEI)")
    L.append("=" * 100)

    # ── OVERALL ──
    # ticker_results values are (trades_list, stats_dict) tuples
    overall_total = sum(s['total'] for _, (_, s) in ticker_results.items())
    overall_wins = sum(s['wins'] for _, (_, s) in ticker_results.items())
    overall_losses = sum(s['losses'] for _, (_, s) in ticker_results.items())
    overall_open = sum(s['open'] for _, (_, s) in ticker_results.items())
    overall_wr = (overall_wins / overall_total * 100) if overall_total > 0 else 0

    # Recalculate from all_trades
    wins_list = [t for t in all_trades if t.result == "WIN"]
    losses_list = [t for t in all_trades if t.result == "LOSS"]
    gp = sum(t.pnl for t in wins_list) if wins_list else 0
    gl = abs(sum(t.pnl for t in losses_list)) if losses_list else 0
    pf = gp / gl if gl > 0 else float('inf')

    avg_win = np.mean([t.pnl_pct_capital for t in wins_list]) if wins_list else 0
    avg_loss = np.mean([t.pnl_pct_capital for t in losses_list]) if losses_list else 0
    max_win = max([t.pnl_pct_capital for t in wins_list]) if wins_list else 0
    max_loss = min([t.pnl_pct_capital for t in losses_list]) if losses_list else 0

    L.append("")
    L.append("┌──────────────────────────────────────────────────────────────────────┐")
    L.append("│                  RESUME KESELURUHAN (ALL TICKERS)                   │")
    L.append("│                  * Per ticker dimulai dari Rp 100Jt                 │")
    L.append("├──────────────────────────────────────────────────────────────────────┤")
    L.append(f"│  Total Trades         : {overall_total:>42d}  │")
    L.append(f"│  Wins                 : {overall_wins:>42d}  │")
    L.append(f"│  Losses               : {overall_losses:>42d}  │")
    L.append(f"│  Open (belum close)   : {overall_open:>42d}  │")
    L.append(f"│  Win Rate             : {overall_wr:>41.2f}%  │")
    L.append(f"│  Avg Win (% capital)  : {avg_win:>41.2f}%  │")
    L.append(f"│  Avg Loss (% capital) : {avg_loss:>41.2f}%  │")
    L.append(f"│  Max Win              : {max_win:>41.2f}%  │")
    L.append(f"│  Max Loss             : {max_loss:>41.2f}%  │")
    L.append(f"│  Profit Factor        : {pf:>42.2f}  │")
    L.append("└──────────────────────────────────────────────────────────────────────┘")

    # ── PER TICKER ──
    L.append("")
    L.append("=" * 100)
    L.append("  RESUME PER SAHAM (sorted by Return)")
    L.append("=" * 100)
    L.append("")

    header = (
        f"{'Ticker':<10}│{'Trades':>7}│{'Win':>5}│{'Loss':>5}│"
        f"{'WR%':>7}│{'AvgWin%':>8}│{'AvgLoss%':>9}│"
        f"{'Return%':>10}│{'Modal Akhir':>20}│{'PF':>7}│ {'Last 3 Triggers'}"
    )
    L.append(header)
    L.append("─" * len(header))

    sorted_tickers = sorted(
        ticker_results.keys(),
        key=lambda t: ticker_results[t][1]['return_pct'],
        reverse=True
    )

    profitable = 0
    losing = 0

    for tk in sorted_tickers:
        trades, stats = ticker_results[tk]
        if stats['total'] == 0:
            continue
        if stats['return_pct'] > 0:
            profitable += 1
        elif stats['return_pct'] < 0:
            losing += 1

        last_3_trades = trades[-3:]
        last_3_dates = [t.entry_date.split(' ')[0] for t in last_3_trades]
        last_3_str = ", ".join(last_3_dates)

        pf_s = f"{stats['profit_factor']:.2f}" if stats['profit_factor'] < 9999 else "∞"
        line = (
            f"{tk:<10}│{stats['total']:>7}│{stats['wins']:>5}│"
            f"{stats['losses']:>5}│{stats['win_rate']:>6.1f}%│"
            f"{stats['avg_win_pct']:>7.2f}%│{stats['avg_loss_pct']:>8.2f}%│"
            f"{stats['return_pct']:>9.2f}%│"
            f"{fmt_rp(stats['final_capital']):>20s}│{pf_s:>7s}│ {last_3_str}"
        )
        L.append(line)

    L.append("─" * len(header))
    L.append("")
    L.append(f"Total saham dibacktest     : {len(sorted_tickers)}")
    L.append(f"Saham profitable           : {profitable}")
    L.append(f"Saham rugi                 : {losing}")

    # ── TOP 20 BEST ──
    L.append("")
    L.append("=" * 100)
    L.append("  TOP 20 SAHAM TERBAIK")
    L.append("=" * 100)
    for i, tk in enumerate(sorted_tickers[:20]):
        _, s = ticker_results[tk]
        L.append(
            f"  {i+1:>2}. {tk:<10}│ Return: {s['return_pct']:>8.2f}% │ "
            f"Win Rate: {s['win_rate']:>5.1f}% │ Trades: {s['total']:>4} │ "
            f"Modal: {fmt_rp(INITIAL_CAPITAL)} → {fmt_rp(s['final_capital'])}"
        )

    # ── TOP 20 WORST ──
    L.append("")
    L.append("=" * 100)
    L.append("  TOP 20 SAHAM TERBURUK")
    L.append("=" * 100)
    worst = [tk for tk in reversed(sorted_tickers[-20:])]
    for i, tk in enumerate(worst):
        _, s = ticker_results[tk]
        L.append(
            f"  {i+1:>2}. {tk:<10}│ Return: {s['return_pct']:>8.2f}% │ "
            f"Win Rate: {s['win_rate']:>5.1f}% │ Trades: {s['total']:>4} │ "
            f"Modal: {fmt_rp(INITIAL_CAPITAL)} → {fmt_rp(s['final_capital'])}"
        )

    L.append("")
    L.append("=" * 100)
    L.append("  END OF REPORT")
    L.append("=" * 100)

    report = "\n".join(L)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return report


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_data.db')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backtest_smc_report.txt')

    if not os.path.exists(db_path):
        print(f"[ERROR] Database tidak ditemukan: {db_path}")
        sys.exit(1)

    print("=" * 60)
    print("  SMC Sniper Backtester v2 (Pandas Optimized)")
    print("  Risk: 1% per trade │ RR: 2:1 │ Buy Only")
    print("=" * 60)

    # ── Load all data at once with pandas ──
    print("\n[1/3] Loading data dari database...")
    # Note: Using read-only URI mode and parameterized query patterns
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    df = pd.read_sql_query(
        "SELECT date, ticker, open, high, low, close, volume "
        "FROM daily_prices ORDER BY ticker, date",
        conn
    )
    conn.close()

    # Filter invalid data
    df = df[(df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)]

    tickers = df['ticker'].unique()
    print(f"      {len(tickers)} ticker, {len(df)} total bars")

    # ── Run backtest per ticker ──
    print(f"\n[2/3] Running backtest...")

    all_trades: list[Trade] = []
    ticker_results: dict[str, tuple[list[Trade], dict]] = {}

    processed = 0
    skipped = 0

    for ticker in tickers:
        grp = df[df['ticker'] == ticker]
        n = len(grp)

        if n < SWING_SIZE + 10:
            skipped += 1
            continue

        opens = grp['open'].values.astype(np.float64)
        highs = grp['high'].values.astype(np.float64)
        lows = grp['low'].values.astype(np.float64)
        closes = grp['close'].values.astype(np.float64)
        dates = grp['date'].values.astype(str)

        # Run SMC engine
        engine = SMCEngine(opens, highs, lows, closes, n)
        signals = engine.run()

        # Resolve trades with position sizing
        trades, final_cap = resolve_trades(signals, highs, lows, closes, dates, n, ticker)
        stats = compute_stats(trades, final_cap)

        ticker_results[ticker] = (trades, stats)
        all_trades.extend(trades)

        processed += 1
        if processed % 100 == 0:
            print(f"      {processed}/{len(tickers)} tickers... "
                  f"({len(all_trades)} trades)")

    print(f"\n      Selesai! {processed} diproses, {skipped} diskip")
    print(f"      Total trades: {len(all_trades)}")

    # ── Generate Report ──
    print(f"\n[3/3] Generating report...")
    generate_report(all_trades, ticker_results, output_path)
    print(f"      Saved: {output_path}")

    # ── Quick Summary ──
    wins = sum(1 for t in all_trades if t.result == "WIN")
    losses = sum(1 for t in all_trades if t.result == "LOSS")
    total = len(all_trades)
    wr = (wins / total * 100) if total > 0 else 0

    print()
    print("┌───────────────── QUICK SUMMARY ──────────────────┐")
    print(f"│  Total Trades  : {total:>30}  │")
    print(f"│  Win / Loss    : {wins:>13} / {losses:<15}  │")
    print(f"│  Win Rate      : {wr:>29.2f}%  │")
    print(f"│  Risk per Trade: {RISK_PCT*100:>28.0f}%  │")
    print(f"│  RR Ratio      : {'1:' + str(int(RR_RATIO)):>30}  │")
    print("└──────────────────────────────────────────────────┘")


if __name__ == "__main__":
    main()
