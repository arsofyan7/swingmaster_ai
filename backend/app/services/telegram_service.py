import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    """
    Mengirim pesan ke Telegram secara graceful.
    Jika token atau chat_id kosong, fungsi ini akan me-skip pengiriman.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("[TELEGRAM] Token atau Chat ID belum diset di .env. Skip notifikasi telegram.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("[TELEGRAM] Berhasil mengirim pesan notifikasi.")
        return True
    except Exception as e:
        logger.error(f"[TELEGRAM] Gagal mengirim pesan: {e}")
        return False
