import sqlite3
import yfinance as yf
import pandas as pd
import time

def main():
    print("Membuka koneksi ke database market_data.db...")
    conn = sqlite3.connect('market_data.db')
    cursor = conn.cursor()

    # Buat tabel h1_Forex_prices jika belum ada
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS h1_Forex_prices (
        ticker TEXT,
        datetime TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (ticker, datetime)
    )
    """)
    conn.commit()
    print("Tabel h1_Forex_prices siap.")

    # List pair Forex (Spot) dan Gold (Futures)
    # yfinance symbol: Nama Pair yang akan kita simpan di DB
    forex_pairs = {
        "EURUSD=X": "EURUSD",
        "GBPUSD=X": "GBPUSD",
        "JPY=X": "USDJPY",
        "CHF=X": "USDCHF",
        "GC=F": "XAUUSD" # Gold Futures sebagai substitusi XAUUSD Spot
    }

    print(f"Mulai mengambil data H1 untuk 6 bulan terakhir...")

    sukses = 0
    gagal = 0

    for yf_ticker, db_ticker in forex_pairs.items():
        print(f"Mengambil data H1 untuk {db_ticker} (via {yf_ticker})...")
        
        try:
            # Ambil data H1 dengan periode 6 bulan
            df = yf.download(yf_ticker, interval="1h", period="6mo", progress=False)
            
            if df.empty:
                print(f"  -> Data kosong untuk {db_ticker} ({yf_ticker}).")
                gagal += 1
                continue

            # Handle format kolom yfinance versi terbaru (MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df.columns = [c.lower() for c in df.columns]

            # Masukkan ke database
            records = []
            for dt, row in df.iterrows():
                records.append((
                    db_ticker, # Kita simpan nama pair yang rapi (misal EURUSD)
                    dt.isoformat(),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume'])
                ))

            # Simpan ke tabel h1_Forex_prices
            cursor.executemany("""
            INSERT OR REPLACE INTO h1_Forex_prices 
            (ticker, datetime, open, high, low, close, volume) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

            print(f"  -> Berhasil menyimpan {len(records)} baris data untuk {db_ticker}.")
            sukses += 1
            
        except Exception as e:
            print(f"  -> Error mengambil data {db_ticker} ({yf_ticker}): {e}")
            gagal += 1

        time.sleep(0.5)

    print("\n=== SELESAI ===")
    print(f"Berhasil: {sukses} pair")
    print(f"Gagal/Kosong: {gagal} pair")
    
    # Tampilkan summary
    cursor.execute("SELECT ticker, COUNT(*) FROM h1_Forex_prices GROUP BY ticker")
    summary = cursor.fetchall()
    
    print("\nTotal baris data per pair di tabel h1_Forex_prices:")
    for row in summary:
        print(f"- {row[0]}: {row[1]} baris")

    conn.close()

if __name__ == "__main__":
    main()
