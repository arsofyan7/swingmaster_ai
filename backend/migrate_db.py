import sqlite3

try:
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()
    c.execute("ALTER TABLE active_positions ADD COLUMN position_type TEXT DEFAULT 'LONG'")
    c.execute("ALTER TABLE trade_journals ADD COLUMN position_type TEXT DEFAULT 'LONG'")
    conn.commit()
    conn.close()
    print("Migration successful.")
except Exception as e:
    print("Migration failed or already applied:", e)
