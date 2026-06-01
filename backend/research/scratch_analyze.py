import json

file_path = r"d:\Coding\swingmaster_ai\backend\matrix_saham.json"

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

strategies = {
    "V8_Pullback": [],
    "V3_Breakout": [],
    "V6_Bandar": [],
    "Swing_Reversal": []
}

for ticker, ranks in data.items():
    for rank_key, metrics in ranks.items():
        # Only consider peringkat_1 to signify it's the best strategy for this ticker
        # Or we can just collect all instances and sort them globally.
        # Let's collect all instances for each strategy
        strat = metrics.get("strategi")
        if strat in strategies:
            strategies[strat].append({
                "ticker": ticker,
                "win_rate": metrics.get("win_rate_pct", 0),
                "cuan": metrics.get("total_cuan_rupiah", 0),
                "total_trade": metrics.get("total_trade", 0),
                "rank": rank_key
            })

output_data = {}

for strat, items in strategies.items():
    # Filter valid items, e.g., total_trade >= 5 to have enough sample size
    valid_items = [x for x in items if x["total_trade"] >= 5 and x["cuan"] > 0]
    # Sort by cuan
    valid_items.sort(key=lambda x: x["cuan"], reverse=True)
    
    # Store top 10
    output_data[strat] = valid_items[:10]

output_file = r"d:\Coding\swingmaster_ai\backend\research\rekap_strategi_saham.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4)

print(f"Hasil rekap analisis berhasil disimpan di: {output_file}")
