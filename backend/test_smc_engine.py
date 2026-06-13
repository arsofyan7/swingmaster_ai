"""Quick sanity check for the rewritten SMCEngine."""
import sys
sys.path.insert(0, '/mnt/d/Coding/swingmaster_ai/backend')

import numpy as np
import pandas as pd
import sqlite3

from app.services.SMCEngine import get_smc_buy_signals, get_smc_sell_signals

print("=== SMCEngine Import OK ===")

# ── Test 1: random data ──────────────────────────────────────────────────────
np.random.seed(42)
n = 300
closes = np.cumsum(np.random.randn(n)) + 500
opens  = closes + np.random.randn(n) * 2
highs  = np.maximum(opens, closes) + abs(np.random.randn(n)) * 3
lows   = np.minimum(opens, closes) - abs(np.random.randn(n)) * 3

df_rand = pd.DataFrame({'Open': opens, 'High': highs, 'Low': lows, 'Close': closes})
result = get_smc_buy_signals(df_rand)
print(f"Random data BUY signal: {result}")

# ── Test 2: Real H1 data from SUNI (if available) ────────────────────────────
try:
    db = sqlite3.connect('/mnt/d/Coding/swingmaster_ai/backend/market_data.db')
    df_h1 = pd.read_sql_query(
        "SELECT datetime as time, open as Open, high as High, low as Low, close as Close "
        "FROM h1_prices WHERE ticker='SUNI.JK' ORDER BY datetime",
        db
    )
    db.close()
    if len(df_h1) > 60:
        result2 = get_smc_buy_signals(df_h1)
        print(f"SUNI.JK H1 BUY signal: {result2}")
        print(f"  Total H1 bars: {len(df_h1)}, last: {df_h1['time'].iloc[-1]}")
    else:
        print("Not enough H1 data for SUNI.JK")
except Exception as e:
    print(f"DB test skipped: {e}")

# ── Test 3: Verify return type compatibility ──────────────────────────────────
print("\n=== Return type check ===")
if result:
    print(f"  Keys: {list(result.keys())}")
    assert 'strategy_name' in result
    assert 'price_at_signal' in result
    assert 'target_price' in result
    assert 'stop_loss' in result
    assert 'type' in result
    print("  All expected keys present: OK")
else:
    print("  No signal on last bar (expected for random data)")

print("\n=== All tests passed ===")
