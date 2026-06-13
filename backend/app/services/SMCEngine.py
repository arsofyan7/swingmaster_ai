import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def find_swings(df, order=5):
    """
    Menemukan swing highs dan swing lows dalam dataframe dengan pandas rolling.
    """
    # Swing High: titik tertinggi dalam window (kiri dan kanan sejauh 'order')
    high_roll = df['High'].rolling(window=2*order+1, center=True).max()
    swing_highs = df.index[df['High'] == high_roll].tolist()
    
    # Swing Low: titik terendah dalam window
    low_roll = df['Low'].rolling(window=2*order+1, center=True).min()
    swing_lows = df.index[df['Low'] == low_roll].tolist()
    
    # Konversi indeks datetime/int menjadi integer posisional
    sh_indices = [df.index.get_loc(idx) for idx in swing_highs]
    sl_indices = [df.index.get_loc(idx) for idx in swing_lows]
    
    return sorted(list(set(sh_indices))), sorted(list(set(sl_indices)))

def get_smc_buy_signals(df):
    """
    Menjalankan logika SMC pada data H1.
    Mendeteksi: CHoCH + OB/FVG Pullback.
    Returns signal dict atau None.
    """
    if len(df) < 50:
        return None
        
    # Pastikan data clean dan terurut
    df = df.copy()
    df.reset_index(drop=True, inplace=True)
    
    swing_highs, swing_lows = find_swings(df, order=4)
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None
        
    last_swing_low_idx = swing_lows[-1]
    
    # Cari swing high valid terakhir sebelum swing low ini
    sh_before_sl = [idx for idx in swing_highs if idx < last_swing_low_idx]
    if not sh_before_sl:
        return None
        
    last_swing_high_idx = sh_before_sl[-1]
    last_sh_price = df['High'].iloc[last_swing_high_idx]
    last_sl_price = df['Low'].iloc[last_swing_low_idx]
    
    # 1. Deteksi CHoCH (Change of Character)
    # Harga harus close di atas last_sh_price setelah last_swing_low_idx
    choch_idx = None
    for i in range(last_swing_low_idx + 1, len(df)):
        if df['Close'].iloc[i] > last_sh_price:
            choch_idx = i
            break
            
    if not choch_idx:
        return None # Belum ada CHoCH valid
        
    # 2. Cari Bullish Order Block (OB)
    # Candle bearish terakhir sebelum CHoCH impulse (mulai dari last SL sampai CHoCH)
    ob_idx = None
    for i in range(choch_idx - 1, max(-1, last_swing_low_idx - 1), -1):
        if df['Close'].iloc[i] < df['Open'].iloc[i]: # Bearish candle
            ob_idx = i
            break
            
    if ob_idx is None:
        # Jika tidak ada candle merah, ambil candle terendah (swing low itu sendiri)
        ob_idx = last_swing_low_idx
        
    ob_high = df['High'].iloc[ob_idx]
    ob_low = df['Low'].iloc[ob_idx]
    
    # 3. Cari Fair Value Gap (FVG) Bullish setelah OB
    # FVG Bullish terjadi jika Low candle ke-3 lebih tinggi dari High candle ke-1
    fvg_top = None
    fvg_bottom = None
    
    # Kita cari FVG dari candle setelah OB sampai candle sebelum current
    for i in range(ob_idx + 1, len(df) - 1):
        # i adalah middle candle dari FVG
        # Pastikan kita punya cukup data untuk i-1 dan i+1
        if i - 1 >= ob_idx and i + 1 < len(df):
            c1_high = df['High'].iloc[i-1]
            c3_low = df['Low'].iloc[i+1]
            
            if c3_low > c1_high:
                # FVG Bullish ditemukan!
                fvg_top = c3_low
                fvg_bottom = c1_high
                # Terus loop agar kita dapat FVG terbaru jika ada beberapa
                
    # 4. Cek apakah harga SAAT INI sedang berada di area Pullback (Masuk ke OB atau FVG)
    current_idx = len(df) - 1
    current_low = df['Low'].iloc[current_idx]
    current_close = df['Close'].iloc[current_idx]
    
    # Entry zone: dari batas bawah OB sampai batas atas area FVG (jika ada FVG), 
    # atau sampai batas atas OB jika tidak ada FVG. Kita beri sedikit toleransi.
    highest_entry_point = ob_high
    if fvg_top is not None:
        highest_entry_point = max(ob_high, fvg_top)
        
    tolerance = highest_entry_point * 1.01 # +1% toleransi
    
    # Syarat Pullback: 
    # 1. Harga menyentuh/masuk ke area tolerance (OB / FVG)
    # 2. Harga belum menembus ke bawah ob_low (belum invalidate struktur)
    if ob_low <= current_low <= tolerance:
        if current_close > ob_low: 
            sl = ob_low * 0.99
            tp = current_close + ((current_close - sl) * 2) # Risk Reward 1:2
            
            strategy_name = "SMC_CHoCH_OB_FVG" if fvg_top else "SMC_CHoCH_OB"
            
            return {
                "strategy_name": strategy_name,
                "price_at_signal": current_close,
                "target_price": round(tp, 2),
                "stop_loss": round(sl, 2)
            }
            
    return None
