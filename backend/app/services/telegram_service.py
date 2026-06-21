import os
import requests
import logging
import sqlite3
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.yfinance_service import get_db_connection

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def send_telegram_message(text: str, chat_id: str = None, reply_markup=None):
    """
    Mengirim pesan ke Telegram secara graceful.
    Jika token kosong, fungsi ini akan me-skip pengiriman.
    Jika chat_id tidak diberikan, akan di-skip (tidak pakai .env default lagi).
    """
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.info("[TELEGRAM] Token atau Chat ID kosong. Skip notifikasi telegram.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if reply_markup:
        # Jika ada inline keyboard, konversi ke json dictionary
        payload["reply_markup"] = reply_markup.to_dict() if hasattr(reply_markup, 'to_dict') else reply_markup
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"[TELEGRAM] Gagal mengirim pesan ke {chat_id}: {e}")
        return False

def broadcast_telegram_message(text: str, category: str, ticker: str = None):
    """
    Mengirim pesan ke semua user yang memiliki portofolio dengan kategori yang sesuai.
    category: 'saham' atau 'forex'
    ticker: untuk generate link TradingView
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Cari user yang punya telegram_chat_id dan portofolio dengan tipe tertentu
        query = """
            SELECT DISTINCT u.telegram_chat_id 
            FROM users u
            JOIN portfolios p ON u.id = p.user_id
            WHERE p.portfolio_type = ? AND u.telegram_chat_id IS NOT NULL
        """
        cursor.execute(query, (category,))
        users = cursor.fetchall()
        
        if not users:
            logger.info(f"[TELEGRAM BROADCAST] Tidak ada user yang berlangganan sinyal {category}.")
            return
            
        # Siapkan Inline Keyboard untuk Buka Chart di TradingView
        reply_markup = None
        if ticker:
            markup = InlineKeyboardMarkup()
            # Asumsi ticker saham format .JK, forex misal EURUSD=X
            symbol = ticker.replace(".JK", "").replace("=X", "")
            exchange = "IDX" if category == "saham" else "FX"
            tv_url = f"https://id.tradingview.com/chart/?symbol={exchange}%3A{symbol}"
            markup.add(InlineKeyboardButton("📊 Buka Chart di TradingView", url=tv_url))
            reply_markup = markup

        success_count = 0
        for u in users:
            chat_id = u['telegram_chat_id']
            if send_telegram_message(text, chat_id=chat_id, reply_markup=reply_markup):
                success_count += 1
                
        logger.info(f"[TELEGRAM BROADCAST] Berhasil mengirim alert {category} ke {success_count}/{len(users)} user.")
        
    except Exception as e:
        logger.error(f"[TELEGRAM BROADCAST] Error: {e}")
    finally:
        conn.close()
