# backend/app/services/constants.py

# 1. INDEKS LQ45 (Saham dengan Likuiditas Tertinggi & Kapitalisasi Pasar Besar)
INDEX_LQ45 = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", 
    "ASII", "AMRT", "UNVR", "GOTO", "ANTM", 
    "PGAS", "PTBA", "ADRO", "KLBF", "MAPI", 
    "CPIN", "ICBP", "INDF", "INCO", "MEDC", 
    "AKRA", "BRIS", "EXCL", "JSMR", "CTRA", 
    "SMGR", "TOWR", "EMTK", "SCMA", "ERAA",
    "INKP", "TKIM", "SMRA", "BSDE", "UNTR"
]

# 2. INDEKS KOMPAS 100 (Gabungan LQ45 + Saham Mid-Cap Potensial)
INDEX_KOMPAS100 = INDEX_LQ45 + [
    "MIDI", "MMLP", "ERAL", "WOOD", "TBLA", 
    "ACES", "MYOR", "ROTI", "ULTJ", "GJTL", 
    "BIRD", "SSIA", "PTPP", "WIKA", "ADHI", 
    "PWON", "BEST", "MAPA", "HEAL", "MIKA", 
    "SILO", "SAME", "PNLF", "PNBN", "BDMN", 
    "BJBR", "BJTM", "BBTN", "AALI", "LSIP", 
    "DSNG", "TAPG", "MAIN", "JPFA", "AUTO",
    "DRMA", "SMSM", "IMAS", "MIDI", "ACST",
    "BUKA", "SCNP", "AVIA", "MARK", "BSSR"
]

# 3. BONUS: SWING GEMS WATCHLIST (Saham rentang Rp 200 - Rp 1.500 yang volatilitasnya asyik buat trading)
SWING_GEMS = [
    "MIDI", "MMLP", "ERAL", "WOOD", "TBLA",
    "GJTL", "BIRD", "SSIA", "CTRA", "SMRA",
    "BSDE", "ERAA", "ACES", "EXCL", "MAPI"
]

# Helper function untuk validasi nama indeks yang diminta frontend
def get_tickers_by_index(index_name: str) -> list[str]:
    name = index_name.lower().strip()
    if name == "lq45":
        return INDEX_LQ45
    elif name == "kompas100":
        return INDEX_KOMPAS100
    elif name == "swing_gems":
        return SWING_GEMS
    else:
        return []