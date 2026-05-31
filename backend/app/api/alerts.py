from fastapi import APIRouter, HTTPException
import sqlite3
from datetime import datetime

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("/")
def get_daily_alerts():
    """
    Get all daily alerts generated for the current day.
    """
    try:
        conn = sqlite3.connect('market_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # We can fetch alerts for today, or just the most recent alerts if none today yet.
        # But for now let's just fetch all 'open' alerts or alerts created today.
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT id, ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status
            FROM daily_alerts
            WHERE signal_date = ? OR status = 'open'
            ORDER BY signal_date DESC
        ''', (today_str,))
        
        rows = cursor.fetchall()
        conn.close()
        
        alerts = [dict(row) for row in rows]
        
        # Calculate potency for each
        for alert in alerts:
            alert['potensi_cuan_pct'] = round(((alert['target_price'] - alert['price_at_signal']) / alert['price_at_signal']) * 100, 2)
            
        return {"status": "success", "data": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
