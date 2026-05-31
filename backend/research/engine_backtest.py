import os
import sqlite3
import pandas as pd
import numpy as np
import json
import time

def get_db_connection():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, '..', 'market_data.db')
    return sqlite3.connect(db_path)

def process_ihsg_regime():
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

def run_sniper_v8_real_money():
    start_time = time.time()
    
    # KONFIGURASI UANG NYATA
    MODAL_AWAL = 10_000_000
    ALOKASI_PER_TRADE = 1_000_000 # 1 Peluru = 50 Juta
    
    print(f"[1] Memulai Simulasi Uang Nyata | Modal: Rp {MODAL_AWAL:,} | Per Trade: Rp {ALOKASI_PER_TRADE:,}...")
    ihsg_regime = process_ihsg_regime()
    
    print("[2] Memuat 3 Tahun Data 900+ Saham...")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT date, ticker, open, high, low, close, volume FROM daily_prices WHERE ticker NOT IN ('COMPOSITE', '^JKSE') ORDER BY ticker, date ASC", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    
    print("[3] Kalkulasi Indikator Pullback (V8)...")
    df['EMA_20'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=20, adjust=False).mean())
    df['EMA_200'] = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=200, adjust=False).mean())
    df['VMA_20'] = df.groupby('ticker')['volume'].transform(lambda x: x.rolling(20).mean())
    df['close_prev'] = df.groupby('ticker')['close'].shift(1)

    print("[4] Menyusun Logika Sinyal Beli...")
    df['Filter_Harga'] = (df['close'] >= 200) & (df['close'] <= 5000)
    df['Uptrend_Makro'] = df['close'] > df['EMA_200']
    df['Near_EMA20'] = (df['close'] >= df['EMA_20']) & (df['close'] <= (df['EMA_20'] * 1.02))
    df['Lagi_Merah'] = df['close'] < df['close_prev']
    df['Volume_Kering'] = df['volume'] < df['VMA_20']
    
    df['Sinyal_Buy_Raw'] = df['Filter_Harga'] & df['Uptrend_Makro'] & df['Near_EMA20'] & df['Lagi_Merah'] & df['Volume_Kering']

    print("[5] Membangun SISTEM RISK-FREE (21 Hari)...")
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
        
        hit_sl = open_mask & (low_i <= df['Current_SL'])
        df.loc[hit_sl, 'PnL_Pct'] = ((df.loc[hit_sl, 'Current_SL'] - df.loc[hit_sl, 'close']) / df.loc[hit_sl, 'close']) * 100
        df.loc[hit_sl, 'Status_Open'] = False
        
        open_mask = df['Status_Open'] == True
        
        hit_tp = open_mask & (high_i >= df['Target_Profit'])
        df.loc[hit_tp, 'PnL_Pct'] = 10.0
        df.loc[hit_tp, 'Status_Open'] = False
        
        open_mask = df['Status_Open'] == True
        
        hit_trigger = open_mask & (high_i >= df['Risk_Free_Trigger'])
        df.loc[hit_trigger, 'Current_SL'] = np.maximum(df.loc[hit_trigger, 'Current_SL'], df.loc[hit_trigger, 'close'])

    close_21 = df.groupby('ticker')['close'].shift(-21)
    open_mask = df['Status_Open'] == True
    df.loc[open_mask, 'PnL_Pct'] = ((close_21[open_mask] - df.loc[open_mask, 'close']) / df.loc[open_mask, 'close']) * 100
    df['Tutup_Hari_21'] = close_21

    print("[6] FILTER MAKRO & KALKULASI RUPIAH...")
    df = df.merge(ihsg_regime, left_on='date', right_index=True, how='left')
    df = df.dropna(subset=['Regime', 'Tutup_Hari_21']) 
    
    # Ambil baris yang VALID Trade
    strat_df = df[(df['Sinyal_Buy_Raw'] == True) & (df['Regime'] == 'Uptrend')].copy()
    
    # HITUNG UANG NYATA (Rupiah)
    # Jika cuan 10%, berarti 10% dari 50 Juta = 5 Juta.
    strat_df['PnL_Rupiah'] = (strat_df['PnL_Pct'] / 100) * ALOKASI_PER_TRADE
    strat_df['Is_Win'] = strat_df['PnL_Pct'] > 0
    strat_df['Is_Loss'] = strat_df['PnL_Pct'] < 0
    strat_df['Is_BEP'] = strat_df['PnL_Pct'] == 0

    total_trades = len(strat_df)
    
    if total_trades > 0:
        win_rate = (strat_df['Is_Win'].sum() / total_trades) * 100
        total_profit_rp = strat_df['PnL_Rupiah'].sum()
        saldo_akhir = MODAL_AWAL + total_profit_rp
        
        # BIKIN REKAP PER SAHAM
        print("[7] Menyusun Statistik Per Emiten...")
        stats_per_ticker = []
        
        for ticker, group in strat_df.groupby('ticker'):
            t_trade = len(group)
            t_win = group['Is_Win'].sum()
            t_loss = group['Is_Loss'].sum()
            t_bep = group['Is_BEP'].sum()
            t_pnl_rp = group['PnL_Rupiah'].sum()
            w_rate = (t_win / t_trade) * 100
            
            stats_per_ticker.append({
                "ticker": ticker,
                "total_trade": int(t_trade),
                "win": int(t_win),
                "loss": int(t_loss),
                "risk_free_bep": int(t_bep),
                "win_rate_pct": round(w_rate, 2),
                "total_cuan_rupiah": int(t_pnl_rp)
            })
            
        # Urutkan dari Cuan paling besar ke paling boncos
        stats_per_ticker = sorted(stats_per_ticker, key=lambda x: x['total_cuan_rupiah'], reverse=True)
        
        # Simpan Statistik Emiten
        with open('statistik_per_saham.json', 'w') as f:
            json.dump(stats_per_ticker, f, indent=4)
            
    else:
        saldo_akhir = MODAL_AWAL
        total_profit_rp = 0
        win_rate = 0

    print("[8] Mencetak Laporan Ringkasan Utama...")
    final_json = {
        "metadata_simulasi": {
            "deskripsi": "Simulasi Uang Nyata V8 (Hold 21 Hari, Trailing Stop BEP)",
            "modal_awal_rp": MODAL_AWAL,
            "alokasi_per_peluru_rp": ALOKASI_PER_TRADE
        },
        "hasil_keseluruhan": {
            "total_trade_dieksekusi": total_trades,
            "total_win": int(strat_df['Is_Win'].sum()),
            "total_loss": int(strat_df['Is_Loss'].sum()),
            "total_bep_risk_free": int(strat_df['Is_BEP'].sum()),
            "win_rate_pct": round(win_rate, 2),
            "total_profit_bersih_rp": int(total_profit_rp),
            "saldo_akhir_rp": int(saldo_akhir),
            "roi_keseluruhan_pct": round((total_profit_rp / MODAL_AWAL) * 100, 2)
        }
    }

    with open('backtest_summary.json', 'w') as f:
        json.dump(final_json, f, indent=4)

    exec_time = time.time() - start_time
    print(f"\n[🎯] OPERASI SELESAI dalam {round(exec_time, 2)} detik!")
    print(f"File 1: 'backtest_summary.json' (Ringkasan Saldo)")
    print(f"File 2: 'statistik_per_saham.json' (Rapor Detail tiap Ticker)")
    print("Sikat Komandan, bongkar file-nya!")

if __name__ == "__main__":
    run_sniper_v8_real_money()