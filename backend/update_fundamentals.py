import yfinance as yf
import sqlite3
import json
import time

conn = sqlite3.connect('market_data.db')
cursor = conn.cursor()

cursor.execute('SELECT ticker, raw_info_json FROM company_fundamentals')
rows = cursor.fetchall()

tickers_list = [row[0] for row in rows]
yf_symbols = [f"{t}.JK" for t in tickers_list]

print(f"Fetching info for {len(yf_symbols)} tickers...")

tickers_data = yf.Tickers(" ".join(yf_symbols))

updated_count = 0
for i, ticker in enumerate(tickers_list):
    try:
        info = tickers_data.tickers[f"{ticker}.JK"].info
        
        long_name = info.get('longName', ticker)
        
        cursor.execute("SELECT raw_info_json FROM company_fundamentals WHERE ticker=?", (ticker,))
        raw_info = cursor.fetchone()[0]
        
        if raw_info:
            try:
                data_json = json.loads(raw_info)
            except:
                data_json = {}
        else:
            data_json = {}
            
        data_json['long_name'] = long_name
        
        keys_to_extract = [
            'sector', 'industry', 'website', 'longBusinessSummary',
            'trailingPE', 'forwardPE', 'priceToBook', 'returnOnEquity', 'returnOnAssets',
            'trailingEps', 'forwardEps', 'bookValue', 'marketCap', 'totalRevenue', 'netIncomeToCommon',
            'dividendRate', 'dividendYield', 'payoutRatio', 'exDividendDate'
        ]
        
        updated_count_fields = 0
        for key in keys_to_extract:
            if key in info and info[key] is not None:
                # Map specific keys to match the old naming if needed
                if key == 'priceToBook': data_json['pbv'] = info[key]
                elif key == 'returnOnEquity': data_json['roe'] = info[key]
                elif key == 'trailingPE': data_json['trailing_pe'] = info[key]
                elif key == 'trailingEps': data_json['eps'] = info[key]
                else: data_json[key] = info[key]
                
                updated_count_fields += 1
        
        cursor.execute('''
            UPDATE company_fundamentals 
            SET company_name = ?, raw_info_json = ? 
            WHERE ticker = ?
        ''', (long_name, json.dumps(data_json), ticker))
        
        updated_count += 1
        
        print(f"[{i+1}/{len(tickers_list)}] Updated {ticker} - {long_name} | Fields updated: {updated_count_fields}")
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"[{i+1}/{len(tickers_list)}] Failed to update {ticker}: {e}")

conn.commit()
conn.close()
print(f"Update completed. Updated {updated_count} tickers.")
