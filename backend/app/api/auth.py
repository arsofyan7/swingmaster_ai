from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import sqlite3
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.services.yfinance_service import get_db_connection
from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class PortfolioCreateRequest(BaseModel):
    name: str
    portfolio_type: str = "saham"
    initial_balance: float = 100000000.0

class PortfolioSettingsRequest(BaseModel):
    risk_per_trade_pct: float

class AdminChangePasswordRequest(BaseModel):
    new_password: str

class AdminUpdateUserRequest(BaseModel):
    username: str
    email: str

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

from app.core.rate_limit import limiter

@router.post("/auth/register")
@limiter.limit("3/minute")
def register_user(request: Request, payload: RegisterRequest):
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
            "INSERT INTO portfolios (user_id, name, portfolio_type, initial_balance, current_balance) VALUES (?, ?, ?, ?, ?)",
            (user_id, "Main Portfolio", "saham", 100000000.0, 100000000.0)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username atau email sudah terdaftar.")
    
    conn.close()
    
    access_token = create_access_token(data={"sub": payload.username, "id": user_id})
    return {"status": "success", "user": {"id": user_id, "username": payload.username, "email": payload.email}, "access_token": access_token}

@router.post("/auth/login")
@limiter.limit("5/minute")
def login_user(request: Request, payload: LoginRequest):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, email, password FROM users WHERE username = ?", (payload.username,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not verify_password(payload.password, user['password']):
        raise HTTPException(status_code=401, detail="Username atau password salah.")
        
    user_dict = dict(user)
    del user_dict['password']
    
    access_token = create_access_token(data={"sub": user_dict['username'], "id": user_dict['id']})
    
    return {"status": "success", "user": user_dict, "access_token": access_token}

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
        "INSERT INTO portfolios (user_id, name, portfolio_type, initial_balance, current_balance) VALUES (?, ?, ?, ?, ?)",
        (user_id, payload.name, payload.portfolio_type, payload.initial_balance, payload.initial_balance)
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

@router.delete("/portfolios/{id}")
def delete_portfolio(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM active_positions WHERE portfolio_id = ?", (id,))
    cursor.execute("DELETE FROM trade_journals WHERE portfolio_id = ?", (id,))
    cursor.execute("DELETE FROM equity_history WHERE portfolio_id = ?", (id,))
    cursor.execute("DELETE FROM watchlists WHERE portfolio_id = ?", (id,))
    
    cursor.execute("DELETE FROM portfolios WHERE id = ?", (id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio tidak ditemukan.")
        
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Portfolio beserta seluruh data terkait berhasil dihapus."}

@router.get("/admin/dashboard")
def get_admin_dashboard(request: Request):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Users
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT id, username, email, created_at FROM users ORDER BY id ASC")
    users = [dict(row) for row in cursor.fetchall()]
    
    # 2. Portfolios total
    cursor.execute("SELECT portfolio_type, COUNT(*) as count FROM portfolios GROUP BY portfolio_type")
    portfolios_group = cursor.fetchall()
    total_saham = 0
    total_forex = 0
    for row in portfolios_group:
        if row['portfolio_type'] == 'saham':
            total_saham = row['count']
        elif row['portfolio_type'] == 'forex':
            total_forex = row['count']
            
    # 3. Portfolios per user
    cursor.execute("""
        SELECT u.id as user_id, u.username, 
               SUM(CASE WHEN p.portfolio_type = 'saham' THEN 1 ELSE 0 END) as saham_count,
               SUM(CASE WHEN p.portfolio_type = 'forex' THEN 1 ELSE 0 END) as forex_count
        FROM users u
        LEFT JOIN portfolios p ON u.id = p.user_id
        GROUP BY u.id, u.username
        ORDER BY u.id ASC
    """)
    portfolio_stats = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "status": "success",
        "data": {
            "total_users": total_users,
            "total_saham_portfolios": total_saham,
            "total_forex_portfolios": total_forex,
            "users": users,
            "portfolio_stats": portfolio_stats
        }
    }

@router.put("/admin/users/{user_id}/password")
def admin_change_password(user_id: int, payload: AdminChangePasswordRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        
    hashed_pw = hash_password(payload.new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_pw, user_id))
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Password user berhasil diubah."}

@router.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUpdateUserRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
        
    cursor.execute("UPDATE users SET username = ?, email = ? WHERE id = ?", (payload.username, payload.email, user_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Data user berhasil diperbarui."}

@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    if not u:
        conn.close()
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    
    if u[0] == 'admin':
        conn.close()
        raise HTTPException(status_code=400, detail="Tidak dapat menghapus akun admin utama.")
        
    cursor.execute("SELECT id FROM portfolios WHERE user_id = ?", (user_id,))
    portfolios = cursor.fetchall()
    for (p_id,) in portfolios:
        cursor.execute("DELETE FROM active_positions WHERE portfolio_id = ?", (p_id,))
        cursor.execute("DELETE FROM trade_journals WHERE portfolio_id = ?", (p_id,))
        cursor.execute("DELETE FROM equity_history WHERE portfolio_id = ?", (p_id,))
        cursor.execute("DELETE FROM watchlists WHERE portfolio_id = ?", (p_id,))
    
    cursor.execute("DELETE FROM portfolios WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "User berhasil dihapus beserta seluruh datanya."}
