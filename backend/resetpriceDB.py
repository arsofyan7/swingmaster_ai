import sqlite3

# Sambungkan ke file database lu (sesuaikan namanya, misal: market_data.db atau swingmaster.db)
DB_NAME = "market_data.db" 

try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Eksekusi DROP hanya pada tabel harga harian
    cursor.execute("DROP TABLE IF EXISTS company_fundamentals;")
    conn.commit()
    
    print(f"🔥 Sukses! Tabel 'daily_prices' berhasil di-wipe.")
    print("📋 Tabel users, portfolios, dan journals lu Tetap AMAN.")
    
except Exception as e:
    print(f"Gagal eksekusi: {e}")
finally:
    conn.close()