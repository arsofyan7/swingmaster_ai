import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('market_data.db')
cursor = conn.cursor()
cursor.execute('SELECT DISTINCT ticker FROM daily_prices LIMIT 5')
tickers = [row[0] for row in cursor.fetchall()]
print('Sample tickers in DB:', tickers)

with open('matrix_saham.json', 'r') as f:
    matrix = json.load(f)
print('Sample tickers in matrix:', list(matrix.keys())[:5])

cursor.execute('SELECT MAX(date) FROM daily_prices')
print('Max date in DB:', cursor.fetchone()[0])

query = """
SELECT date, open, high, low, close, volume 
FROM daily_prices 
WHERE ticker = 'ABMM.JK' OR ticker = 'ABMM'
ORDER BY date DESC 
LIMIT 20
"""
df = pd.read_sql_query(query, conn)
print('Rows for ABMM:', len(df))
if len(df) > 0:
    print('Last 5 rows for ABMM:')
    print(df.head())
