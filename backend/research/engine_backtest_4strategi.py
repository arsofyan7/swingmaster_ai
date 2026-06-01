import os
import sqlite3
import pandas as pd
import numpy as np
import json
import time

def get_db_connection():
    """Mengambil koneksi ke database SQLite lokal"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Pastikan path ini mengarah ke lokasi market_data.db lu
    db_path = os.path.join(current_dir, '..', 'market_data.db') 
    
    # Fallback kalau dijalankan di folder yang sama
    if not os.path.exists(db_path):
        db_path = 'market_data.db'
        
    return sqlite3.connect(db_path)

def process_ihsg_regime():
    """Menentukan Rezim Makro IHSG (Uptrend / Downtrend)"""
    conn = get_db_connection()
    df_ihsg = pd.read_sql_query("SELECT date, close FROM daily_prices WHERE ticker IN ('COMPOSITE', '^JKSE') ORDER BY date ASC", conn)
    conn.close()
    
    df_ihsg['date'] = pd.to_datetime(df_ihsg['date'])
    df_ihsg = df_ihsg.set_index('date')
    df_ihsg['EMA_50'] = df_ihsg['close'].ewm(span=50, adjust=False).mean()
    df_ihsg['EMA_200'] = df_ihsg['close'].ewm(span=200, adjust=False).mean()
    
    conditions = [
        (df_ihsg['close'] > df_ihsg['EMA_50']) & (df_ihsg['close'] > df_ihsg['EMA_200']),
        (df_ihsg['close'] < df_ihsg['EMA_50']) & (df_ihsg['close'] < df_ihsg['EMA_200'])
    ]
    df_ihsg['Regime'] = np.select(conditions, ['Uptrend', 'Downtrend'], default='Sideways')
    return df_ihsg[['Regime']]

def run_strategy_matrix():
    start_time = time.time()
    ALOKASI_PER_TRADE = 50_000_000 # Rp 50 Juta per peluru
    
    print("[1] Membaca Radar Makro IHSG...")
    ihsg_regime = process_ihsg_regime()
    
    print("[2] Memuat 3 Tahun Data 900+ Saham...")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT date, ticker, open, high, low, close, volume FROM daily_prices WHERE ticker NOT IN ('COMPOSITE', '^JKSE') ORDER BY ticker, date ASC", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    
    print("[3] Kalkulasi Semua Indikator (EMA, MACD, OBV, ADL, & PineScript)...")
    # --- 3.1 Indikator Dasar & VMA ---
    df['EMA_12'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=12, adjust=False).mean())
    df['EMA_26'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=26, adjust=False).mean())
    df['EMA_20'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=20, adjust=False).mean())
    df['EMA_200'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=200, adjust=False).mean())
    df['VMA_20'] = df.groupby('ticker')['volume'].transform(lambda x: x.rolling(20).mean())
    
    # --- 3.2 MACD Slope ---
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_prev'] = df.groupby('ticker')['MACD'].shift(1)
    
    # --- 3.3 OBV & ADL (Untuk V6 Bandar) ---
    df['Price_Dir'] = np.sign(df.groupby('ticker')['close'].diff())
    df['OBV'] = (df['Price_Dir'] * df['volume']).fillna(0)
    df['OBV'] = df.groupby('ticker')['OBV'].cumsum()
    df['OBV_EMA'] = df.groupby('ticker')['OBV'].transform(lambda x: x.ewm(span=20, adjust=False).mean())
    
    high_low_diff = df['high'] - df['low']
    high_low_diff = high_low_diff.replace(0, 0.001)
    df['MFM'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / high_low_diff
    df['MFV'] = df['MFM'] * df['volume']
    df['ADL'] = df.groupby('ticker')['MFV'].cumsum()
    df['ADL_EMA'] = df.groupby('ticker')['ADL'].transform(lambda x: x.ewm(span=20, adjust=False).mean())

    df['close_prev'] = df.groupby('ticker')['close'].shift(1)
    df['EMA_20_prev'] = df.groupby('ticker')['EMA_20'].shift(1)

    # --- 3.4 Injeksi Logika PineScript (Swing Reversal) ---
    df['low_prev'] = df.groupby('ticker')['low'].shift(1)
    df['low_prev2'] = df.groupby('ticker')['low'].shift(2)
    df['high_prev'] = df.groupby('ticker')['high'].shift(1)
    
    # Pivot Low Logic (Harga kemarin adalah titik terendah dari hari ini dan 2 hari lalu)
    df['is_pivot_low'] = (df['low_prev'] < df['low']) & (df['low_prev'] < df['low_prev2'])

    print("[4] Membangun MATRIX 4 STRATEGI (V8, V3, V6, & Swing_Reversal)...")
    # Filter Universal: Harga 200 - 5000 + Makro Uptrend
    df['Filter_Harga'] = (df['close'] >= 200) & (df['close'] <= 5000)
    df['Uptrend_Makro'] = df['close'] > df['EMA_200']
    
    # Komponen Sinyal V-Series
    Near_EMA20 = (df['close'] >= df['EMA_20']) & (df['close'] <= (df['EMA_20'] * 1.02))
    Lagi_Merah = df['close'] < df['close_prev']
    Volume_Kering = df['volume'] < df['VMA_20']
    Volume_Spike = df['volume'] >= (2 * df['VMA_20'])
    Close_Cross_EMA20 = (df['close'] > df['EMA_20']) & (df['close_prev'] <= df['EMA_20_prev'])
    MACD_Menanjak = df['MACD'] > df['MACD_prev']
    Bandar_Akumulasi = (df['OBV'] > df['OBV_EMA']) & (df['ADL'] > df['ADL_EMA'])

    # --- INJEKSI FINAL STRATEGI ---
    df['Sinyal_V8_Pullback'] = df['Filter_Harga'] & df['Uptrend_Makro'] & Near_EMA20 & Lagi_Merah & Volume_Kering
    df['Sinyal_V3_Breakout'] = df['Filter_Harga'] & Volume_Spike & Close_Cross_EMA20 & MACD_Menanjak
    df['Sinyal_V6_Bandar']   = df['Filter_Harga'] & df['Uptrend_Makro'] & Near_EMA20 & Bandar_Akumulasi
    
    # PineScript Sinyal: Harga menembus High kemarin setelah membentuk Pivot Low
    df['Sinyal_Swing_Reversal'] = df['Filter_Harga'] & df['Uptrend_Makro'] & df['is_pivot_low'] & (df['close'] > df['high_prev'])

    print("[5] Simulasi Universal Smart Exit (21 Hari, Trailing BEP)...")
    df['Target_Profit'] = df['close'] * 1.10   
    df['Initial_SL'] = df['close'] * 0.94      
    df['Risk_Free_Trigger'] = df['close'] * 1.05 
    
    df['PnL_Pct'] = np.nan
    df['Status_Open'] = True
    df['Current_SL'] = df['Initial_SL']
    
    for i in range(1, 22):
        high_i = df.groupby('ticker')['high'].shift(-i)
        low_i = df.groupby('ticker')['low'].shift(-i)
        open_mask = df['Status_Open'] == True
        
        # Kena Stop Loss / Trailing
        hit_sl = open_mask & (low_i <= df['Current_SL'])
        df.loc[hit_sl, 'PnL_Pct'] = ((df.loc[hit_sl, 'Current_SL'] - df.loc[hit_sl, 'close']) / df.loc[hit_sl, 'close']) * 100
        df.loc[hit_sl, 'Status_Open'] = False
        
        # Kena Target Profit 10%
        open_mask = df['Status_Open'] == True
        hit_tp = open_mask & (high_i >= df['Target_Profit'])
        df.loc[hit_tp, 'PnL_Pct'] = 10.0
        df.loc[hit_tp, 'Status_Open'] = False
        
        # Aktifkan Trailing BEP jika kena Trigger 5%
        open_mask = df['Status_Open'] == True
        hit_trigger = open_mask & (high_i >= df['Risk_Free_Trigger'])
        df.loc[hit_trigger, 'Current_SL'] = np.maximum(df.loc[hit_trigger, 'Current_SL'], df.loc[hit_trigger, 'close'])

    close_21 = df.groupby('ticker')['close'].shift(-21)
    open_mask = df['Status_Open'] == True
    df.loc[open_mask, 'PnL_Pct'] = ((close_21[open_mask] - df.loc[open_mask, 'close']) / df.loc[open_mask, 'close']) * 100
    df['Tutup_Hari_21'] = close_21

    # Gabung dengan Makro IHSG
    df = df.merge(ihsg_regime, left_on='date', right_index=True, how='left')
    df = df.dropna(subset=['Regime', 'Tutup_Hari_21']) 
    
    # Hanya Valid saat IHSG Uptrend
    kondisi_ihsg = df['Regime'] == 'Uptrend'
    df['Sinyal_V8_Pullback'] = df['Sinyal_V8_Pullback'] & kondisi_ihsg
    df['Sinyal_V3_Breakout'] = df['Sinyal_V3_Breakout'] & kondisi_ihsg
    df['Sinyal_V6_Bandar']   = df['Sinyal_V6_Bandar'] & kondisi_ihsg
    df['Sinyal_Swing_Reversal'] = df['Sinyal_Swing_Reversal'] & kondisi_ihsg

    # Kalkulasi Rupiah
    df['PnL_Rupiah'] = (df['PnL_Pct'] / 100) * ALOKASI_PER_TRADE
    df['Is_Win'] = df['PnL_Pct'] > 0
    df['Is_Loss'] = df['PnL_Pct'] < 0
    df['Is_BEP'] = df['PnL_Pct'] == 0

    print("[6] Menyusun Papan Klasemen Matrix Per Saham (Top 5 + Tanggal Trigger)...")
    hasil_matrix = {}
    
    # Ditambah "Swing_Reversal" hasil injeksi PineScript
    daftar_strategi = {
        "V8_Pullback": "Sinyal_V8_Pullback",
        "V3_Breakout": "Sinyal_V3_Breakout",
        "V6_Bandar": "Sinyal_V6_Bandar",
        "Swing_Reversal": "Sinyal_Swing_Reversal"
    }

    # Looping per Ticker untuk ngadu strategi
    for ticker, group in df.groupby('ticker'):
        hasil_strat_ticker = []
        
        for strat_name, strat_col in daftar_strategi.items():
            # Filter hanya baris yang menghasilkan sinyal beli (True)
            strat_df = group[group[strat_col] == True].copy()
            t_trade = len(strat_df)
            
            if t_trade == 0:
                continue
            
            # AMBIL 5 TANGGAL TERAKHIR (Format YYYY-MM-DD)
            tgl_terakhir = strat_df['date'].dt.strftime('%Y-%m-%d').sort_values(ascending=False).head(5).tolist()
            
            t_win = strat_df['Is_Win'].sum()
            t_loss = strat_df['Is_Loss'].sum()
            t_bep = strat_df['Is_BEP'].sum()
            t_pnl_rp = strat_df['PnL_Rupiah'].sum()
            w_rate = (t_win / t_trade) * 100
            
            hasil_strat_ticker.append({
                "strategi": strat_name,
                "total_trade": int(t_trade),
                "5_tanggal_trigger": tgl_terakhir,  # INJEKSI TANGGAL DISINI
                "win": int(t_win),
                "loss": int(t_loss),
                "risk_free_bep": int(t_bep),
                "win_rate_pct": round(w_rate, 2),
                "total_cuan_rupiah": int(t_pnl_rp)
            })
            
        # Jika saham ini punya sinyal dari strategi apapun
        if hasil_strat_ticker:
            # Urutkan berdasarkan cuan tertinggi
            hasil_strat_ticker = sorted(hasil_strat_ticker, key=lambda x: x['total_cuan_rupiah'], reverse=True)
            
            # AMBIL MAKSIMAL 5 TERATAS
            top_5 = hasil_strat_ticker[:5]
            
            peringkat_dict = {}
            for idx, res in enumerate(top_5):
                peringkat_dict[f"peringkat_{idx+1}"] = res
                
            hasil_matrix[ticker] = peringkat_dict

    with open('matrix_saham.json', 'w') as f:
        json.dump(hasil_matrix, f, indent=4)

    exec_time = time.time() - start_time
    print(f"\n[🎯] OPERASI MATRIX SELESAI dalam {round(exec_time, 2)} detik!")
    print("Silakan buka file 'matrix_saham.json' untuk melihat pertarungan Bandar vs Price Action (PineScript)!")

if __name__ == "__main__":
    run_strategy_matrix()