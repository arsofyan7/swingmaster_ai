from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
from datetime import date
from app.services.yfinance_service import get_db_connection

router = APIRouter(prefix="/api/v1/portfolios", tags=["dashboard"])

class TransactionRequest(BaseModel):
    type: str # "deposit" or "withdraw"
    amount: float

@router.get("/{portfolio_id}/dashboard")
def get_dashboard(portfolio_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Portfolio Info
    cursor.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,))
    portfolio = cursor.fetchone()
    if not portfolio:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    current_balance = portfolio['current_balance']
    
    # 2. Active Positions
    cursor.execute("SELECT * FROM active_positions WHERE portfolio_id = ?", (portfolio_id,))
    positions = cursor.fetchall()
    
    active_positions = []
    total_invested = 0.0
    sector_allocation = {}
    
    for p in positions:
        ticker = p['ticker'].upper().replace('.JK', '')
        # Fast fetch current price from live_prices first, then fallback to daily_prices
        try:
            cursor.execute("SELECT price FROM live_prices WHERE ticker = ?", (ticker,))
            price_row = cursor.fetchone()
            if price_row:
                current_price = float(price_row[0])
            else:
                cursor.execute("SELECT close FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", (ticker,))
                price_row = cursor.fetchone()
                if price_row:
                    current_price = float(price_row[0])
                else:
                    current_price = p['buy_price'] # fallback
        except:
            current_price = p['buy_price'] # fallback
            
        invested = p['buy_price'] * p['total_lot'] * 100
        current_value = current_price * p['total_lot'] * 100
        floating_pnl = current_value - invested
        
        dist_tp = ((p['target_tp'] - current_price) / current_price) * 100 if p['target_tp'] else 0
        dist_sl = ((current_price - p['target_sl']) / current_price) * 100 if p['target_sl'] else 0
        
        # Calculate days held
        buy_date_str = p['buy_date'] if p['buy_date'] else None
        days_held = 0
        if buy_date_str:
            try:
                buy_dt = date.fromisoformat(buy_date_str[:10])
                days_held = (date.today() - buy_dt).days
            except:
                pass

        active_positions.append({
            "id": p['id'],
            "ticker": p['ticker'],
            "sector": p['sector'],
            "buy_price": p['buy_price'],
            "buy_date": buy_date_str,
            "days_held": days_held,
            "current_price": round(current_price, 2),
            "total_lot": p['total_lot'],
            "target_tp": p['target_tp'],
            "target_sl": p['target_sl'],
            "floating_pnl": floating_pnl,
            "distance_to_tp_pct": round(dist_tp, 2),
            "distance_to_sl_pct": round(dist_sl, 2)
        })
        
        total_invested += invested
        sector = p['sector'] or "Unknown"
        sector_allocation[sector] = sector_allocation.get(sector, 0) + current_value
        
    total_equity = current_balance + total_invested
    
    # 3. Trade Journals (Win Rate)
    cursor.execute("SELECT * FROM trade_journals WHERE portfolio_id = ?", (portfolio_id,))
    journals = cursor.fetchall()
    total_trades = len(journals)
    winning_trades = sum(1 for j in journals if j['pnl_amount'] > 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    # 4. Equity History (Equity Curve & MDD)
    cursor.execute("SELECT date, total_equity FROM equity_history WHERE portfolio_id = ? ORDER BY date ASC", (portfolio_id,))
    history = cursor.fetchall()
    
    equity_curve = [{"date": h['date'], "total_equity": h['total_equity']} for h in history]
    
    mdd = 0.0
    if history:
        peak = history[0]['total_equity']
        for h in history:
            if h['total_equity'] > peak:
                peak = h['total_equity']
            drawdown = (peak - h['total_equity']) / peak * 100
            if drawdown > mdd:
                mdd = drawdown
                
    # 5. Alerts
    alerts = []
    for pos in active_positions:
        if pos['distance_to_tp_pct'] > 0 and pos['distance_to_tp_pct'] <= 2:
            alerts.append(f"Mendekati TP: {pos['ticker']} tersisa {pos['distance_to_tp_pct']}% lagi!")
        if pos['distance_to_sl_pct'] > 0 and pos['distance_to_sl_pct'] <= 2:
            alerts.append(f"AWAS SL: {pos['ticker']} tersisa {pos['distance_to_sl_pct']}% menuju Stop Loss!")
            
    # 6. Fetch IHSG History (^JKSE -> COMPOSITE)
    ihsg_history = []
    try:
        cursor.execute("SELECT date, open, high, low, close FROM daily_prices WHERE ticker = 'COMPOSITE' ORDER BY date ASC")
        rows = cursor.fetchall()
        for row in rows:
            ihsg_history.append({
                "time": row["date"],
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2)
            })
    except Exception as e:
        print(f"Error fetching IHSG history: {e}")

    conn.close()
    
    return {
        "status": "success",
        "balance_info": {
            "current_balance": current_balance,
            "total_invested": total_invested,
            "total_equity": total_equity
        },
        "metrics": {
            "win_rate": round(win_rate, 2),
            "mdd": round(mdd, 2),
            "total_trades": total_trades
        },
        "active_positions": active_positions,
        "sector_allocation": sector_allocation,
        "equity_curve": equity_curve,
        "alerts": alerts,
        "ihsg_history": ihsg_history
    }

@router.post("/{portfolio_id}/transaction")
def make_transaction(portfolio_id: int, payload: TransactionRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT current_balance FROM portfolios WHERE id = ?", (portfolio_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    balance = row[0]
    if payload.type == "deposit":
        balance += payload.amount
    elif payload.type == "withdraw":
        if payload.amount > balance:
            conn.close()
            raise HTTPException(status_code=400, detail="Insufficient balance")
        balance -= payload.amount
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid transaction type")
        
    cursor.execute("UPDATE portfolios SET current_balance = ? WHERE id = ?", (balance, portfolio_id))
    conn.commit()
    conn.close()
    
    return {"status": "success", "new_balance": balance}

@router.post("/{portfolio_id}/reset")
def reset_portfolio(portfolio_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT initial_balance FROM portfolios WHERE id = ?", (portfolio_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    initial_balance = row[0]
    
    cursor.execute("DELETE FROM active_positions WHERE portfolio_id = ?", (portfolio_id,))
    cursor.execute("DELETE FROM trade_journals WHERE portfolio_id = ?", (portfolio_id,))
    cursor.execute("DELETE FROM equity_history WHERE portfolio_id = ?", (portfolio_id,))
    cursor.execute("UPDATE portfolios SET current_balance = ? WHERE id = ?", (initial_balance, portfolio_id))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Portfolio resetted successfully"}

@router.get("/ihsg-chart")
def get_ihsg_chart():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT date, open, high, low, close, volume FROM daily_prices WHERE ticker = 'COMPOSITE' ORDER BY date ASC")
        rows = cursor.fetchall()
        
        chart_data = []
        for row in rows:
            chart_data.append({
                "time": row["date"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"])
            })
            
        conn.close()
        return {"status": "success", "data": chart_data}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error fetching IHSG chart data: {e}")
