import sqlite3
conn = sqlite3.connect('market_data.db')
cursor = conn.cursor()
cursor.execute("SELECT ticker, date, close, volume FROM daily_prices WHERE ticker = 'ABMM' ORDER BY date DESC LIMIT 5")
for row in cursor.fetchall():
    print(row)
