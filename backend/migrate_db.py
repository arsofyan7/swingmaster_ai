import sqlite3

try:
    conn = sqlite3.connect('market_data.db')
    c = conn.cursor()

    # Migration 1: Add position_type columns (already applied, safe to re-run)
    try:
        c.execute("ALTER TABLE active_positions ADD COLUMN position_type TEXT DEFAULT 'LONG'")
    except:
        pass
    try:
        c.execute("ALTER TABLE trade_journals ADD COLUMN position_type TEXT DEFAULT 'LONG'")
    except:
        pass

    # Migration 2: Rename SMC labels from old format to new format
    # SMC-Fase1 → SMC_Reversal_Fase1
    # SMC-Fase2 → SMC_Reversal_Fase2
    c.execute("""
        UPDATE daily_alerts 
        SET strategy_name = REPLACE(strategy_name, 'SMC-Fase1', 'SMC_Reversal_Fase1')
        WHERE strategy_name LIKE '%SMC-Fase1%'
    """)
    renamed_fase1 = c.rowcount

    c.execute("""
        UPDATE daily_alerts 
        SET strategy_name = REPLACE(strategy_name, 'SMC-Fase2', 'SMC_Reversal_Fase2')
        WHERE strategy_name LIKE '%SMC-Fase2%'
    """)
    renamed_fase2 = c.rowcount

    conn.commit()
    conn.close()
    print(f"Migration successful.")
    print(f"  - Renamed {renamed_fase1} SMC-Fase1 → SMC_Reversal_Fase1")
    print(f"  - Renamed {renamed_fase2} SMC-Fase2 → SMC_Reversal_Fase2")
except Exception as e:
    print("Migration failed:", e)
