import sqlite3
import pandas as pd

def show_db():
    try:
        # Koneksi ke database
        conn = sqlite3.connect('market_data.db')
        
        # 1. Cek jumlah total data
        print("=== TOTAL DATA DI DATABASE ===")
        total = pd.read_sql_query("SELECT COUNT(*) as total_rows FROM daily_prices", conn)
        print(f"Total baris keseluruhan: {total.iloc[0]['total_rows']}\n")
        
        # 2. Cek ringkasan data per ticker (jumlah hari & rentang tanggal)
        print("=== RINGKASAN PER TICKER ===")
        summary_query = """
        SELECT 
            ticker, 
            COUNT(*) as jumlah_hari, 
            MIN(date) as tanggal_awal, 
            MAX(date) as tanggal_akhir 
        FROM daily_prices 
        GROUP BY ticker
        ORDER BY ticker ASC
        """
        summary = pd.read_sql_query(summary_query, conn)
        
        if summary.empty:
            print("Database saat ini masih kosong.")
        else:
            print(summary.to_string(index=False))
            
        # 3. Tampilkan 5 baris data paling baru sebagai sampel
        print("\n=== SAMPEL 5 DATA TERBARU ===")
        sample = pd.read_sql_query("SELECT * FROM daily_prices ORDER BY date DESC, ticker ASC LIMIT 5", conn)
        if not sample.empty:
            print(sample.to_string(index=False))
            
        conn.close()
    except Exception as e:
        print(f"Error membaca database: {e}")

if __name__ == "__main__":
    show_db()
