from fastapi import APIRouter, HTTPException
import sqlite3
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("/dates")
def get_alert_dates():
    """
    Get all unique dates where alerts were generated.
    """
    try:
        conn = sqlite3.connect('market_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT signal_date 
            FROM daily_alerts 
            ORDER BY signal_date DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        dates = [row['signal_date'] for row in rows]
        return {"status": "success", "data": dates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
def get_daily_alerts(date: Optional[str] = None):
    """
    Get all daily alerts generated for the current day or a specific date.
    """
    try:
        conn = sqlite3.connect('market_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if date:
            cursor.execute('''
                SELECT id, ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status
                FROM daily_alerts
                WHERE signal_date = ?
                ORDER BY signal_date DESC
            ''', (date,))
        else:
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
            if alert['price_at_signal'] > 0:
                alert['potensi_cuan_pct'] = round(((alert['target_price'] - alert['price_at_signal']) / alert['price_at_signal']) * 100, 2)
            else:
                alert['potensi_cuan_pct'] = 0
            
        return {"status": "success", "data": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
