import sqlite3
import json

conn = sqlite3.connect('market_data.db')
cursor = conn.cursor()

# Get 5 tickers from DB
cursor.execute('SELECT DISTINCT ticker FROM daily_prices LIMIT 5')
db_tickers = [row[0] for row in cursor.fetchall()]
print('DB Tickers sample:', db_tickers)

# Get 5 tickers from JSON
with open('matrix_saham.json', 'r') as f:
    matrix = json.load(f)
print('JSON Tickers sample:', list(matrix.keys())[:5])

# Find overlap
overlap = set(db_tickers).intersection(set(matrix.keys()))
print('Overlap sample:', list(overlap)[:5])
if len(overlap) == 0:
    print("NO OVERLAP BETWEEN DB TICKERS AND MATRIX TICKERS!")
    
    # Are there .JK extensions in DB but not in JSON?
    db_tickers_no_jk = [t.replace('.JK', '') for t in db_tickers]
    overlap_no_jk = set(db_tickers_no_jk).intersection(set(matrix.keys()))
    if len(overlap_no_jk) > 0:
        print("There is an overlap if we remove .JK from DB tickers!")

