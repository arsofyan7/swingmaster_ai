from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
from app.services.yfinance_service import get_db_connection
from app.services import ai_service
from typing import Optional

router = APIRouter(prefix="/api/v1/portfolios", tags=["trade"])

class BuyRequest(BaseModel):
    ticker: str
    buy_price: float
    total_lot: float
    target_tp: float
    target_sl: float
    position_type: str = "LONG"

class WatchlistRequest(BaseModel):
    ticker: str
    ai_recom_price: str
    ai_tp: float = 0.0
    ai_sl: float = 0.0
    ai_rr: str = ""

def get_trade_multiplier(ticker: str, p_type: str) -> int:
    if p_type == 'forex':
        if ticker == 'XAUUSD':
            return 100
        elif ticker == 'USDJPY':
            return 1000
        return 100000
    return 100

@router.post("/{portfolio_id}/buy")
def execute_buy(portfolio_id: int, payload: BuyRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Cek balance portfolio & type
    cursor.execute("SELECT current_balance, portfolio_type FROM portfolios WHERE id = ?", (portfolio_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    current_balance = row[0]
    p_type = row[1]
    
    multiplier = get_trade_multiplier(payload.ticker, p_type)
    
    # 1. Hitung total cost (margin)
    if p_type == 'forex':
        leverage = 100 # Default paper leverage 1:100 for forex
        total_cost = (payload.buy_price * payload.total_lot * multiplier) / leverage
    else:
        total_cost = payload.buy_price * payload.total_lot * multiplier
    
    if current_balance < total_cost:
        conn.close()
        raise HTTPException(status_code=400, detail="Insufficient Funds. Modal tidak cukup untuk membuka posisi ini.")
        
    # 3. Eksekusi Pembelian (Kurangi modal & catat posisi)
    # Untuk paper trade forex, margin dikembalikan saat close. Sementara ini kita deduksi dari balance.
    new_balance = current_balance - total_cost
    
    cursor.execute("UPDATE portfolios SET current_balance = ? WHERE id = ?", (new_balance, portfolio_id))
    
    cursor.execute('''
        INSERT INTO active_positions (portfolio_id, ticker, buy_price, total_lot, target_tp, target_sl, position_type, buy_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', (portfolio_id, payload.ticker, payload.buy_price, payload.total_lot, payload.target_tp, payload.target_sl, payload.position_type))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": f"{payload.position_type} executed successfully", "remaining_balance": new_balance}

@router.post("/{portfolio_id}/watchlist")
def add_to_watchlist(portfolio_id: int, payload: WatchlistRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Cek apakah portfolio ada
    cursor.execute("SELECT id FROM portfolios WHERE id = ?", (portfolio_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    # Cek duplikasi di watchlist
    cursor.execute("SELECT id FROM watchlists WHERE portfolio_id = ? AND ticker = ?", (portfolio_id, payload.ticker))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Saham ini sudah ada di watchlist Anda.")
    
    cursor.execute('''
        INSERT INTO watchlists (portfolio_id, ticker, ai_recom_price, ai_tp, ai_sl, ai_rr)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (portfolio_id, payload.ticker, payload.ai_recom_price, payload.ai_tp, payload.ai_sl, payload.ai_rr))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Added to watchlist"}

import re
from fastapi.responses import StreamingResponse
import io
import csv

@router.get("/{portfolio_id}/watchlists")
def get_watchlists(portfolio_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticker, ai_recom_price, added_at, ai_tp, ai_sl, ai_rr FROM watchlists WHERE portfolio_id = ?", (portfolio_id,))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        ticker = r[1]
        recom_str = r[2] or ""
        
        # Get live price from SQLite
        live_price = 0
        try:
            ticker_clean = ticker.upper().replace(".JK", "")
            cursor.execute("SELECT price FROM live_prices WHERE ticker = ?", (ticker_clean,))
            price_row = cursor.fetchone()
            if price_row:
                live_price = float(price_row[0])
            else:
                cursor.execute("SELECT close FROM daily_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", (ticker_clean,))
                price_row = cursor.fetchone()
                if price_row:
                    live_price = float(price_row[0])
        except:
            pass
            
        # Parse upper bound of ai_recom_price
        upper_bound = 0
        numbers = re.findall(r'\d+', recom_str)
        if numbers:
            upper_bound = max(map(float, numbers))
            
        distance = 0
        if upper_bound > 0 and live_price > 0:
            distance = ((live_price - upper_bound) / upper_bound) * 100

        results.append({
            "id": r[0],
            "ticker": ticker,
            "ai_recom_price": recom_str,
            "added_at": r[3],
            "ai_tp": r[4] or 0.0,
            "ai_sl": r[5] or 0.0,
            "ai_rr": r[6] or "",
            "live_price": live_price,
            "upper_bound": upper_bound,
            "distance_to_entry_pct": round(distance, 2)
        })

    conn.close()
    return {"status": "success", "watchlists": results}

@router.delete("/{portfolio_id}/watchlists/{ticker}")
def delete_watchlist(portfolio_id: int, ticker: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlists WHERE portfolio_id = ? AND ticker = ?", (portfolio_id, ticker))
    conn.commit()
    conn.close()
    return {"status": "success"}

class ClosePositionRequest(BaseModel):
    sell_price: float
    tag: str = ""
    notes: str = ""

@router.post("/{portfolio_id}/positions/{ticker}/close")
def close_position(portfolio_id: int, ticker: str, payload: ClosePositionRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, buy_price, total_lot, target_sl, position_type FROM active_positions WHERE portfolio_id = ? AND ticker = ?", (portfolio_id, ticker))
    pos = cursor.fetchone()
    
    if not pos:
        conn.close()
        raise HTTPException(status_code=404, detail="Position not found")
        
    pos_id, buy_price, total_lot, target_sl, position_type = pos
    
    cursor.execute("SELECT current_balance, portfolio_type FROM portfolios WHERE id = ?", (portfolio_id,))
    row = cursor.fetchone()
    current_balance = row[0]
    p_type = row[1]
    
    multiplier = get_trade_multiplier(ticker, p_type)
    
    # Kalkulasi PnL Nominal & Persentase
    if position_type == 'SHORT':
        pnl_nominal = (buy_price - payload.sell_price) * total_lot * multiplier
        pnl_pct = ((buy_price - payload.sell_price) / buy_price) * 100
    else:
        pnl_nominal = (payload.sell_price - buy_price) * total_lot * multiplier
        pnl_pct = ((payload.sell_price - buy_price) / buy_price) * 100
    
    # Kalkulasi R-Multiple
    target_sl = target_sl or buy_price
    if position_type == 'SHORT':
        one_r_risk = (target_sl - buy_price) * total_lot * multiplier
    else:
        one_r_risk = (buy_price - target_sl) * total_lot * multiplier
        
    if one_r_risk <= 0:
        one_r_risk = 1 # Avoid division by zero
        
    r_multiple = pnl_nominal / one_r_risk
    
    # Update Balance: Kembalikan margin awal + profit/loss
    if p_type == 'forex':
        leverage = 100
        margin_awal = (buy_price * total_lot * multiplier) / leverage
    else:
        margin_awal = buy_price * total_lot * multiplier
        
    new_balance = current_balance + margin_awal + pnl_nominal
    cursor.execute("UPDATE portfolios SET current_balance = ? WHERE id = ?", (new_balance, portfolio_id))
    
    status = "TP" if pnl_nominal > 0 else "SL" if pnl_nominal < 0 else "Manual"
    
    # Insert to Trade Journals
    cursor.execute('''
        INSERT INTO trade_journals (portfolio_id, ticker, buy_price, sell_price, total_lot, pnl_amount, pnl_percentage, status, r_multiple, tag, notes, position_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (portfolio_id, ticker, buy_price, payload.sell_price, total_lot, pnl_nominal, pnl_pct, status, round(r_multiple, 2), payload.tag, payload.notes, position_type))
    
    # Delete from active_positions
    cursor.execute("DELETE FROM active_positions WHERE id = ?", (pos_id,))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Position closed successfully"}

@router.get("/{portfolio_id}/journals")
def get_journals(portfolio_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticker, buy_price, sell_price, total_lot, pnl_amount, pnl_percentage, close_date, status, r_multiple, tag, notes, position_type FROM trade_journals WHERE portfolio_id = ? ORDER BY close_date DESC", (portfolio_id,))
    rows = cursor.fetchall()
    conn.close()
    
    journals = []
    for r in rows:
        journals.append({
            "id": r[0],
            "ticker": r[1],
            "buy_price": r[2],
            "sell_price": r[3],
            "total_lot": r[4],
            "pnl_amount": r[5],
            "pnl_percentage": r[6],
            "close_date": r[7],
            "status": r[8],
            "r_multiple": r[9],
            "tag": r[10],
            "notes": r[11],
            "position_type": r[12]
        })
        
    return {"status": "success", "journals": journals}

@router.get("/{portfolio_id}/journals/export")
def export_journals(portfolio_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, buy_price, sell_price, total_lot, pnl_amount, pnl_percentage, close_date, status, r_multiple, tag, notes FROM trade_journals WHERE portfolio_id = ? ORDER BY close_date DESC", (portfolio_id,))
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ticker', 'Buy Price', 'Sell Price', 'Lot', 'PnL (Rp)', 'PnL (%)', 'Close Date', 'Status', 'R-Multiple', 'Tag', 'Notes'])
    
    for r in rows:
        writer.writerow(r)
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trade_journal_portfolio_{portfolio_id}.csv"}
    )

class AnalyzeJournalRequest(BaseModel):
    days_ago: Optional[int] = None

@router.post("/{portfolio_id}/journals/analyze")
async def analyze_journal(portfolio_id: int, payload: AnalyzeJournalRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if payload.days_ago:
        cursor.execute("SELECT ticker, buy_price, sell_price, pnl_percentage, r_multiple, status, notes FROM trade_journals WHERE portfolio_id = ? AND close_date >= date('now', ?)", (portfolio_id, f"-{payload.days_ago} days"))
    else:
        cursor.execute("SELECT ticker, buy_price, sell_price, pnl_percentage, r_multiple, status, notes FROM trade_journals WHERE portfolio_id = ?", (portfolio_id,))
        
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"status": "error", "message": "Tidak ada data jurnal untuk rentang waktu ini."}
        
    # Format the rows to string
    journal_text = "Ticker | Buy | Sell | PnL(%) | R-Mult | Status | Notes\n"
    journal_text += "-" * 70 + "\n"
    for r in rows:
        journal_text += f"{r[0]} | {r[1]} | {r[2]} | {r[3]:.2f}% | {r[4]} | {r[5]} | {r[6]}\n"
        
    # Call AI Service
    ai_response = await ai_service.analyze_trading_journal(journal_text)
    
    return {"status": "success", "analysis": ai_response}
