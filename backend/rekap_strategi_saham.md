# Rekapan Saham Terbaik per Strategi Trading

Berikut adalah rekapan top 10 saham yang paling bagus digunakan untuk masing-masing strategi berdasarkan hasil backtest di `matrix_saham.json`. Parameter "terbaik" ini difilter berdasarkan **Total Cuan Rupiah** tertinggi dengan syarat minimal sudah terjadi **5 kali trade** (agar datanya valid secara statistik).

## 1. Strategi V8_Pullback (`Sinyal_V8_Pullback`)
| No | Ticker | Cuan (Rp) | Win Rate | Total Trade |
|---|---|---|---|---|
| 1 | **TOTL** | Rp 78.310.847 | 61.11% | 36 |
| 2 | **EXCL** | Rp 57.001.915 | 62.96% | 27 |
| 3 | **TSPC** | Rp 54.378.167 | 62.50% | 24 |
| 4 | **PGAS** | Rp 51.650.692 | 52.78% | 36 |
| 5 | **SILO** | Rp 48.143.152 | 45.16% | 31 |

*(Top 5 lainnya: KEEN, HRUM, SCCO, KEJU, JTPE)*

## 2. Strategi V3_Breakout (`Sinyal_V3_Breakout`)
| No | Ticker | Cuan (Rp) | Win Rate | Total Trade |
|---|---|---|---|---|
| 1 | **SHID** | Rp 20.000.000 | 80.00% | 5 |
| 2 | **MBMA** | Rp 18.999.999 | 71.43% | 7 |
| 3 | **MREI** | Rp 17.000.000 | 66.67% | 6 |
| 4 | **AIMS** | Rp 16.999.999 | 80.00% | 5 |
| 5 | **GPSO** | Rp 16.999.999 | 80.00% | 5 |

*(Top 5 lainnya: SGER, TUGU, BBTN, SURE, PNGO)*

## 3. Strategi V6_Bandar (`Sinyal_V6_Bandar`)
| No | Ticker | Cuan (Rp) | Win Rate | Total Trade |
|---|---|---|---|---|
| 1 | **JRPT** | Rp 250.980.798 | 93.85% | 65 |
| 2 | **YULE** | Rp 144.781.127 | 50.00% | 72 |
| 3 | **KEJU** | Rp 124.161.984 | 86.67% | 30 |
| 4 | **JTPE** | Rp 122.515.151 | 71.43% | 42 |
| 5 | **BSSR** | Rp 100.135.129 | 85.29% | 34 |

*(Top 5 lainnya: BOLT, PTIS, SCCO, MPRO, TSPC)*

## 4. Strategi Swing_Reversal (`Sinyal_Swing_Reversal`)
| No | Ticker | Cuan (Rp) | Win Rate | Total Trade |
|---|---|---|---|---|
| 1 | **DGNS** | Rp 37.000.000 | 80.00% | 10 |
| 2 | **HRTA** | Rp 36.015.228 | 61.11% | 18 |
| 3 | **ASPI** | Rp 36.000.000 | 52.94% | 17 |
| 4 | **TOTL** | Rp 32.999.999 | 52.94% | 17 |
| 5 | **DSSA** | Rp 32.343.137 | 50.00% | 22 |

*(Top 5 lainnya: TRIM, RMKE, BIKE, CASS, CLAY)*

---
**Kesimpulan Singkat:**
- **V6_Bandar** memiliki potensi *cuan* terbesar, terutama di saham **JRPT**, **YULE**, dan **KEJU** dengan frekuensi trade yang sangat aktif dan win rate yang tinggi (di atas 80% kecuali YULE).
- **V8_Pullback** stabil untuk saham lapis kedua & blue chip seperti **TOTL**, **EXCL**, dan **PGAS** dengan win rate berkisar di 50-60%.
- **V3_Breakout** memiliki frekuensi trade yang cenderung lebih sedikit (hanya sekitar 5-9 kali), tapi win ratenya cukup bagus (di atas 70%) untuk saham seperti **SHID** dan **MBMA**.
- **Swing_Reversal** bekerja cukup baik di saham dengan volatilitas medium seperti **DGNS** dan **HRTA**.
