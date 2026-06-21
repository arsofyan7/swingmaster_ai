import sqlite3
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate():
    db_path = 'market_data.db'
    if not os.path.exists(db_path):
        logger.error(f"Database {db_path} tidak ditemukan.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Menambahkan kolom telegram_chat_id tanpa constraint UNIQUE
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_chat_id INTEGER;")
        logger.info("Berhasil menambahkan kolom telegram_chat_id ke tabel users.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("Kolom telegram_chat_id sudah ada, skip.")
        else:
            logger.error(f"Error menambahkan telegram_chat_id: {e}")

    # Menambahkan index unik
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON users(telegram_chat_id);")
        logger.info("Berhasil membuat unique index idx_users_telegram_chat_id.")
    except Exception as e:
        logger.error(f"Error membuat index: {e}")

    conn.commit()
    conn.close()
    logger.info("Migrasi selesai.")

if __name__ == "__main__":
    migrate()
