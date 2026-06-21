from fastapi import APIRouter, HTTPException
import sqlite3
import asyncio
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.post("/run")
async def trigger_run_alerts():
    """
    Manually trigger the daily alert generation process (run AlertEngine).
    Useful for manual refresh from the frontend.
    """
    try:
        from app.services.AlertEngine import run_daily_alerts
        from app.services.run_h1_alerts import run_h1_alerts_job
        
        await run_daily_alerts()
        # Jalankan juga SMC H1 Alerts secara sinkron
        run_h1_alerts_job()
        
        return {"status": "success", "message": "Alert generation completed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-telegram")
async def test_telegram_alert():
    """
    Dummy endpoint to test Telegram message sending.
    """
    try:
        from app.services.telegram_service import broadcast_telegram_message
        
        # Sample cool format for testing
        today_str = datetime.now().strftime("%Y-%m-%d")
        msg = f"""<b>🚀 SWINGMASTER AI ALERTS 🚀</b>
<i>📅 Date: {today_str}</i>

<b>1. BBCA</b> (V3_Breakout)
🏷️ <b>Current Price:</b> 10,000
💰 <b>Entry:</b> 10,000
🎯 <b>TP:</b> 10,500
🛑 <b>SL:</b> 9,500
────────────────────
<b>2. GOTO</b> (Swing_Reversal)
🏷️ <b>Current Price:</b> 60
💰 <b>Entry:</b> 60
🎯 <b>TP:</b> 65
🛑 <b>SL:</b> 55
────────────────────

💡 <i>Total Alerts Today: 2 (TEST MODE)</i>
⚠️ <i>Disclaimer: Always do your own research (DYOR). Trading carries risks!</i>"""
        
        try:
            broadcast_telegram_message(msg, category="saham")
            return {"status": "success", "message": "Pesan test terkirim (jika ada subscriber saham)!"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
            # Default ke tanggal alert terbaru yang ada di database (handle weekend)
            cursor.execute("SELECT MAX(signal_date) FROM daily_alerts")
            max_date_row = cursor.fetchone()
            latest_alert_date = max_date_row[0] if max_date_row and max_date_row[0] else datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute('''
                SELECT id, ticker, strategy_name, signal_date, price_at_signal, target_price, stop_loss, status
                FROM daily_alerts
                WHERE signal_date = ?
                ORDER BY signal_date DESC
            ''', (latest_alert_date,))
            
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
