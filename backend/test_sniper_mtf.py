import sqlite3
import pandas as pd
from app.services.SniperMTFEngine import detect_d1_sniper_setup, detect_h1_sniper_trigger

def test_unit_logic():
    print("=== Testing Unit Logic Sniper MTF ===")
    
    # 1. Test Dummy D1 Setup (Bullish CHoCH + FVG)
    dates = pd.date_range(end='2026-10-01', periods=30, freq='D')
    d1_data = []
    # Create downtrend -> swing high at 1000 -> break to 1050 with FVG -> pullback to 1020
    for i in range(30):
        if i < 15: # downtrend
            p = 1000 - i * 10
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': p+5, 'high': p+10, 'low': p-10, 'close': p, 'volume': 1_000_000})
        elif i == 15: # Swing low
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 850, 'high': 860, 'low': 840, 'close': 855, 'volume': 2_000_000})
        elif i == 16: # Candle 1
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 855, 'high': 880, 'low': 850, 'close': 875, 'volume': 3_000_000})
        elif i == 17: # Candle 2 (impulsive break / CHoCH)
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 875, 'high': 960, 'low': 870, 'close': 950, 'volume': 6_000_000})
        elif i == 18: # Candle 3 (leaves FVG between 880 and 910)
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 950, 'high': 980, 'low': 920, 'close': 970, 'volume': 4_000_000})
        elif i < 29: # holding up
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 970, 'high': 990, 'low': 940, 'close': 960, 'volume': 2_000_000})
        else: # Today pullback into FVG (880-920)
            d1_data.append({'date': dates[i].strftime('%Y-%m-%d'), 'open': 950, 'high': 955, 'low': 900, 'close': 910, 'volume': 1_500_000})

    df_d1 = pd.DataFrame(d1_data)
    setup = detect_d1_sniper_setup(df_d1)
    print("D1 Setup detected:", setup)
    assert setup is not None, "D1 setup detection should return valid dict"

    # 2. Test Dummy H1 Triggers (Target Date: 2026-10-01)
    # Inside FVG [880, 920]:
    # Bar 1: Bearish candle (open 915, close 895)
    # Bar 2: Bullish Engulfing candle (open 895, high 925, low 890, close 920, vol > prev)
    h1_data = [
        {'datetime': '2026-10-01 09:00:00', 'open': 915, 'high': 920, 'low': 890, 'close': 895, 'volume': 1_000_000},
        {'datetime': '2026-10-01 10:00:00', 'open': 895, 'high': 925, 'low': 890, 'close': 920, 'volume': 2_500_000},
        {'datetime': '2026-10-01 11:00:00', 'open': 920, 'high': 930, 'low': 915, 'close': 925, 'volume': 1_200_000},
    ]
    df_h1 = pd.DataFrame(h1_data)
    
    signal = detect_h1_sniper_trigger(df_h1, setup, target_date='2026-10-01')
    print("H1 Trigger detected (Engulfing):", signal)
    assert signal is not None, "H1 Bullish Engulfing should trigger"
    assert signal['strategy_name'] == 'Sniper_MTF_Engulfing'

    # 3. Test Hammer Rejection Trigger
    # Bar 2: Hammer (open 905, high 910, low 880, close 908, lower wick = 25 / range 30 = 83%)
    h1_data_hammer = [
        {'datetime': '2026-10-01 09:00:00', 'open': 915, 'high': 920, 'low': 900, 'close': 905, 'volume': 1_000_000},
        {'datetime': '2026-10-01 10:00:00', 'open': 905, 'high': 910, 'low': 880, 'close': 908, 'volume': 2_000_000},
    ]
    df_h1_hammer = pd.DataFrame(h1_data_hammer)
    signal_hammer = detect_h1_sniper_trigger(df_h1_hammer, setup, target_date='2026-10-01')
    print("H1 Trigger detected (Hammer):", signal_hammer)
    assert signal_hammer is not None, "H1 Hammer should trigger"
    assert signal_hammer['strategy_name'] == 'Sniper_MTF_Rejection'

    print("=== All Unit Tests Passed Successfully! ===")

if __name__ == '__main__':
    test_unit_logic()
