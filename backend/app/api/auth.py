from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sqlite3
import hashlib
from app.services.yfinance_service import get_db_connection

router = APIRouter(prefix="/api/v1", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class PortfolioCreateRequest(BaseModel):
    name: str
    initial_balance: float = 100000000.0

class PortfolioSettingsRequest(BaseModel):
    risk_per_trade_pct: float

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.post("/auth/register")
def register_user(payload: RegisterRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    hashed_pw = hash_password(payload.password)
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (payload.username, payload.email, hashed_pw)
        )
        user_id = cursor.lastrowid
        
        # Create Main Portfolio
        cursor.execute(
            "INSERT INTO portfolios (user_id, name, initial_balance, current_balance) VALUES (?, ?, ?, ?)",
            (user_id, "Main Portfolio", 100000000.0, 100000000.0)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username atau email sudah terdaftar.")
    
    conn.close()
    return {"status": "success", "user": {"id": user_id, "username": payload.username, "email": payload.email}}

@router.post("/auth/login")
def login_user(payload: LoginRequest):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    hashed_pw = hash_password(payload.password)
    cursor.execute("SELECT id, username, email FROM users WHERE username = ? AND password = ?", (payload.username, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
        
    return {"status": "success", "user": dict(user)}

@router.get("/users/{user_id}/portfolios")
def get_user_portfolios(user_id: int):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return {"status": "success", "portfolios": [dict(row) for row in rows]}

@router.post("/users/{user_id}/portfolios")
def create_portfolio(user_id: int, payload: PortfolioCreateRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        
    cursor.execute(
        "INSERT INTO portfolios (user_id, name, initial_balance, current_balance) VALUES (?, ?, ?, ?)",
        (user_id, payload.name, payload.initial_balance, payload.initial_balance)
    )
    portfolio_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"status": "success", "portfolio": {"id": portfolio_id, "name": payload.name, "initial_balance": payload.initial_balance}}

@router.put("/portfolios/{id}/settings")
def update_portfolio_settings(id: int, payload: PortfolioSettingsRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE portfolios SET risk_per_trade_pct = ? WHERE id = ?", (payload.risk_per_trade_pct, id))
    conn.commit()
    
    conn.row_factory = sqlite3.Row
    cursor2 = conn.cursor()
    cursor2.execute("SELECT * FROM portfolios WHERE id = ?", (id,))
    row = cursor2.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Portfolio tidak ditemukan.")
        
    return {"status": "success", "portfolio": dict(row)}
