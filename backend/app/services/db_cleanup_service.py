import sqlite3
import logging
from app.core.logger import logger

def cleanup_old_market_data(max_d1_bars: int = 300, max_h1_bars: int = 200, max_forex_h1_bars: int = 700, max_alert_days: int = 90):
    """
    Automated Database Pruning & Maintenance.
    Maintains clean, fast, and compact SQLite storage by retaining only the optimal
    number of historical candles needed for indicators, SMC, AI, and chart visualization.
    """
    logger.info("[DB CLEANUP] Memulai pembersihan berkala dan optimasi database...")
    try:
        conn = sqlite3.connect('market_data.db')
        cursor = conn.cursor()

        # 1. Pruning D1 daily_prices (Simpan max 300 candle per ticker)
        cursor.execute(f"""
            DELETE FROM daily_prices 
            WHERE rowid IN (
                SELECT rowid FROM (
                    SELECT rowid, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                    FROM daily_prices
                ) WHERE rn > {max_d1_bars}
            )
        """)
        d1_deleted = cursor.rowcount

        # 2. Pruning H1 h1_prices (Simpan max 200 candle per ticker untuk IDX)
        try:
            cursor.execute(f"""
                DELETE FROM h1_prices 
                WHERE rowid IN (
                    SELECT rowid FROM (
                        SELECT rowid, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY datetime DESC) as rn
                        FROM h1_prices
                    ) WHERE rn > {max_h1_bars}
                )
            """)
            h1_deleted = cursor.rowcount
        except Exception:
            h1_deleted = 0

        # 3. Pruning Forex H1 h1_Forex_prices (Simpan max 700 candle per pair)
        try:
            cursor.execute(f"""
                DELETE FROM h1_Forex_prices 
                WHERE rowid IN (
                    SELECT rowid FROM (
                        SELECT rowid, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY datetime DESC) as rn
                        FROM h1_Forex_prices
                    ) WHERE rn > {max_forex_h1_bars}
                )
            """)
            forex_h1_deleted = cursor.rowcount
        except Exception:
            forex_h1_deleted = 0

        # 4. Pruning History Daily Alerts Lama (> 90 hari)
        try:
            cursor.execute(f"DELETE FROM daily_alerts WHERE signal_date < date('now', '-{max_alert_days} days')")
            alerts_deleted = cursor.rowcount
        except Exception:
            alerts_deleted = 0

        # 5. Pruning AI Analyses Lama (> 30 hari)
        try:
            cursor.execute("DELETE FROM ai_analyses WHERE created_at < datetime('now', '-30 days')")
            ai_deleted = cursor.rowcount
        except Exception:
            ai_deleted = 0

        conn.commit()

        # 6. Jalankan VACUUM untuk mereclaim disk space fisik
        logger.info("[DB CLEANUP] Menjalankan VACUUM untuk mereclaim storage...")
        cursor.execute("VACUUM")
        conn.close()

        logger.info(
            f"[DB CLEANUP] Sukses! Terhapus: {d1_deleted} baris D1 lama, "
            f"{h1_deleted} baris H1 lama, {forex_h1_deleted} baris Forex H1, "
            f"{alerts_deleted} alert kadaluarsa (>90 hari), {ai_deleted} AI cache lama. Database kini optimal & ramping!"
        )
        return {
            "status": "success",
            "d1_deleted": d1_deleted,
            "h1_deleted": h1_deleted,
            "forex_h1_deleted": forex_h1_deleted,
            "alerts_deleted": alerts_deleted,
            "ai_deleted": ai_deleted
        }

    except Exception as e:
        logger.error(f"[DB CLEANUP] Gagal membersihkan database: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    cleanup_old_market_data()
