from fastapi import APIRouter
from app.services.yfinance_service import get_db_connection
import sqlite3

router = APIRouter(prefix="/api/v1/history", tags=["History Analysis"])

@router.get("/dates")
def get_history_dates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM ai_analyses ORDER BY date DESC")
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"status": "success", "data": dates}

@router.get("/stocks")
def get_history_stocks(date: str):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = """
        SELECT a.*, 
               c.company_name,
               c.raw_info_json,
               (SELECT p.close FROM daily_prices p WHERE p.ticker = a.ticker AND p.date <= a.date ORDER BY p.date DESC LIMIT 1) as price
        FROM ai_analyses a
        LEFT JOIN company_fundamentals c ON a.ticker = c.ticker
        WHERE a.date = ?
        ORDER BY a.ticker ASC
    """
    cursor.execute(query, (date,))
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    import json
    for row in rows:
        d = dict(row)
        raw_info = d.get('raw_info_json')
        per = 0.0
        eps = 0.0
        if raw_info:
            try:
                info = json.loads(raw_info)
                per = info.get("trailingPE", 0)
                eps = info.get("earningsPerShare", 0)
            except:
                pass
        d['per'] = per
        d['eps'] = eps
        if 'raw_info_json' in d:
            del d['raw_info_json']
        data.append(d)
        
    return {"status": "success", "data": data}
