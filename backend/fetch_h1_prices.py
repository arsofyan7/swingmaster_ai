import sqlite3
import yfinance as yf
import pandas as pd
import time

def main():
    print("Membuka koneksi ke database market_data.db...")
    conn = sqlite3.connect('market_data.db')
    cursor = conn.cursor()

    # Buat tabel h1_prices jika belum ada
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS h1_prices (
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
    print("Tabel h1_prices siap.")

    # Ambil semua ticker unik dari tabel daily_prices
    cursor.execute("SELECT DISTINCT ticker FROM daily_prices")
    tickers = [row[0] for row in cursor.fetchall()]
    
    if not tickers:
        print("Tidak ada ticker yang ditemukan di daily_prices.")
        return

    print(f"Ditemukan {len(tickers)} ticker. Mulai mengambil data H1 untuk 3 bulan terakhir...")

    sukses = 0
    gagal = 0

    for i, ticker in enumerate(tickers, 1):
        yf_ticker = f"{ticker}.JK"
        print(f"[{i}/{len(tickers)}] Mengambil data H1 untuk {yf_ticker}...")
        
        try:
            # Ambil data H1
            df = yf.download(yf_ticker, interval="1h", period="3mo", progress=False)
            
            if df.empty:
                print(f"  -> Data kosong untuk {yf_ticker}.")
                gagal += 1
                continue

            # Karena yfinance mengembalikan MultiIndex untuk kolom (jika yf versi baru), 
            # kita perlu meratakan nama kolom atau mengambil kolom level 0.
            if isinstance(df.columns, pd.MultiIndex):
                # Ambil level 0 (Price names: Open, High, dsb)
                df.columns = df.columns.get_level_values(0)
            
            # Konversi semua nama kolom ke huruf kecil (lowercase) agar seragam
            df.columns = [c.lower() for c in df.columns]

            # Masukkan ke database
            records = []
            for dt, row in df.iterrows():
                # Format datetime menjadi string ISO
                dt_str = dt.isoformat()
                records.append((
                    ticker,
                    dt_str,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume'])
                ))

            # Simpan menggunakan REPLACE agar kalau data sudah ada akan di-update
            cursor.executemany("""
            INSERT OR REPLACE INTO h1_prices 
            (ticker, datetime, open, high, low, close, volume) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

            print(f"  -> Berhasil menyimpan {len(records)} baris data.")
            sukses += 1
            
        except Exception as e:
            print(f"  -> Error mengambil data {yf_ticker}: {e}")
            gagal += 1

        # Beri jeda sedikit agar tidak kena rate limit Yahoo Finance
        time.sleep(0.5)

    print("\n=== SELESAI ===")
    print(f"Berhasil: {sukses} ticker")
    print(f"Gagal/Kosong: {gagal} ticker")
    
    # Tampilkan summary database
    cursor.execute("SELECT COUNT(*) FROM h1_prices")
    total_h1 = cursor.fetchone()[0]
    print(f"Total baris data di tabel h1_prices saat ini: {total_h1}")

    conn.close()

if __name__ == "__main__":
    main()
