# backend/app/services/constants.py

import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

def load_index_from_file(filename: str) -> list[str]:
    filepath = os.path.join(BACKEND_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip().upper() for line in f if line.strip()]

# 1. INDEKS LQ45
INDEX_LQ45 = load_index_from_file("LQ45.txt")

# 2. INDEKS KOMPAS 100
INDEX_KOMPAS100 = load_index_from_file("KOMPAS100.txt")

# 3. INDEKS ISSI (Indeks Saham Syariah Indonesia)
INDEX_ISSI = load_index_from_file("ISSI.txt")


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
    elif name == "issi":
        return INDEX_ISSI
    elif name == "swing_gems":
        return SWING_GEMS
    else:
        return []