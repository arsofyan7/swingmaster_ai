from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api.stock import router as stock_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.trade import router as trade_router
from app.api.history import router as history_router
from app.api.alerts import router as alerts_router
from app.core.logger import logger
import time
import sqlite3
import httpx
from datetime import datetime
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

from app.core.rate_limit import limiter

async def scheduled_eod_price_sync():
    logger.info("[CORE SCHEDULER] Syncing End-Of-Day prices...")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(settings.GOOGLE_WEBAPP_URL, params={"action": "get_prices_sheet"})
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success" and "data" in data:
                prices_data = data["data"]
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                records = []
                for ticker, info in prices_data.items():
                    price = info.get("price", 0.0)
                    records.append((today_str, ticker, 0.0, 0.0, 0.0, price, 0))
                
                if records:
                    conn = sqlite3.connect('market_data.db')
                    cursor = conn.cursor()
                    cursor.executemany('''
                        INSERT OR REPLACE INTO daily_prices (date, ticker, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    conn.commit()
                    conn.close()
                    logger.info(f"[CORE SCHEDULER] Successfully locked EOD prices for {len(records)} tickers.")
                    
            # --- UPDATE COMPOSITE (IHSG) ---
            import asyncio
            from app.services.yfinance_service import sync_historical_data
            logger.info("[CORE SCHEDULER] Syncing COMPOSITE (IHSG) historical data...")
            await asyncio.to_thread(sync_historical_data, ["COMPOSITE"])
            logger.info("[CORE SCHEDULER] Successfully synced COMPOSITE (IHSG).")
            
    except Exception as e:
        logger.error(f"[CORE SCHEDULER] Error during EOD price sync: {e}")

async def scheduled_live_price_tick():
    if datetime.now().weekday() >= 5:
        return
        
    logger.info("[CORE SCHEDULER] Syncing live intraday prices...")
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(settings.GOOGLE_WEBAPP_URL, params={"action": "get_prices_sheet"})
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success" and "data" in data:
                prices_data = data["data"]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                records = []
                for ticker, info in prices_data.items():
                    price = info.get("price", 0.0)
                    records.append((ticker, price, now_str))
                
                if records:
                    conn = sqlite3.connect('market_data.db')
                    cursor = conn.cursor()
                    cursor.executemany('''
                        INSERT OR REPLACE INTO live_prices (ticker, price, updated_at)
                        VALUES (?, ?, ?)
                    ''', records)
                    conn.commit()
                    conn.close()
                    logger.info(f"[CORE SCHEDULER] Successfully refreshed live prices for {len(records)} tickers.")
    except Exception as e:
        logger.error(f"[CORE SCHEDULER] Error during live price tick: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[CORE SCHEDULER] Initializing database for live prices...")
    conn = sqlite3.connect('market_data.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS live_prices (
            ticker TEXT PRIMARY KEY,
            price REAL,
            updated_at TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            signal_date DATE NOT NULL,
            price_at_signal REAL NOT NULL,
            target_price REAL,
            stop_loss REAL,
            status TEXT DEFAULT 'open'
        )
    ''')
    conn.commit()
    conn.close()
    
    from app.services.AlertEngine import run_daily_alerts
    logger.info("[CORE SCHEDULER] Starting APScheduler...")
    scheduler.add_job(scheduled_eod_price_sync, 'cron', day_of_week='mon-fri', hour=17, minute=0)
    scheduler.add_job(run_daily_alerts, 'cron', day_of_week='mon-fri', hour=17, minute=30)
    scheduler.add_job(scheduled_live_price_tick, 'cron', day_of_week='mon-fri', hour='8-16', minute='*/15')
    scheduler.start()
    
    import asyncio
    from app.services.yfinance_service import sync_historical_data
    logger.info("[CORE SCHEDULER] Syncing COMPOSITE (IHSG) at startup...")
    asyncio.create_task(asyncio.to_thread(sync_historical_data, ["COMPOSITE"]))
    
    
    yield
    
    logger.info("[CORE SCHEDULER] Shutting down APScheduler...")
    scheduler.shutdown()

app = FastAPI(
    title="SwingMaster AI API", 
    description="Backend Modular untuk Aplikasi Trading SwingMaster AI",
    version="1.2",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log incoming request url and method
    query = request.url.query
    url_path = f"{request.url.path}?{query}" if query else request.url.path
    
    # Body cannot be easily read in middleware without consuming the stream, 
    # but for JSON endpoints we can try to log basic info or just log the hit.
    logger.info(f"[INBOUND API HIT] {request.method} {url_path} | Client: {request.client.host}")
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(f"[INBOUND API RES] {request.method} {url_path} | Status: {response.status_code} | Time: {process_time:.3f}s")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://siberhub.id:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(trade_router)
app.include_router(history_router)
app.include_router(alerts_router)

# Mount folder static untuk melayani file UI
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")

@app.get("/service-worker.js")
async def serve_sw():
    return FileResponse("app/static/js/service-worker.js", media_type="application/javascript")

@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse("app/static/manifest.json", media_type="application/json")
