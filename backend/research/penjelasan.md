# 🛡️ Dokumentasi Strategi Sniper V8: The Holy Grail
**Status:** *Live Execution Ready* **Deskripsi:** Sistem perdagangan algoritmik berbasis *Macro-Pullback* dan *Risk-Free Trailing Stop*.

---

## 🚀 Ringkasan Performa Simulasi
Sistem ini telah melalui proses *backtest* dengan modal simulasi **Rp 500.000.000** menggunakan alokasi **Rp 50.000.000 per posisi**.

* **ROI Keseluruhan:** 67.88% (Data 3 Tahun)
* **Total Profit Bersih:** Rp 339.423.060
* **Win Rate:** 31.36%
* **Total Trade:** 4.952
* **Fitur Penyelamat:** 1.122 transaksi terselamatkan dengan *Risk-Free Trailing Stop*.

---

## ⚙️ Logika Inti Strategi (V8)
Sistem ini bekerja berdasarkan sinyal *Pullback* yang dikonfirmasi oleh kondisi makro IHSG:

1.  **Filter Dasar:**
    * Harga Saham: Rp 200 - Rp 5.000.
    * IHSG Regime: **WAJIB UPTREND**.
2.  **Sinyal Entry (Pullback):**
    * Tren Makro Saham: `Close > EMA 200`.
    * Area Beli: Harga menyentuh EMA 20 (Toleransi +2%).
    * Kondisi: `Close < Close_Prev` (sedang merah/koreksi) + Volume Transaksi < VMA 20 (Volume Kering).
3.  **Smart Exit Management:**
    * Target Profit (TP): +10%.
    * Stop Loss Awal (SL): -6%.
    * **Trailing Stop (Risk-Free):** Jika harga naik +5%, SL otomatis digeser ke titik *Break Even* (0%).

---

## 📊 Klasifikasi Strategi Per Saham (DNA Cuan)
Setiap emiten memiliki karakter yang berbeda. Berdasarkan hasil *Strategy Matrix*, berikut adalah panduan penggunaan strategi:

### 🏆 TOP PERFORMANCES (The Master Whitelist)
Saham-saham ini harus menjadi prioritas eksekusi Anda:

| Ticker | Strategi Terbaik | Win Rate | Total Cuan (Rp) |
| :--- | :--- | :--- | :--- |
| **TOTL** | V8_Pullback | 61.11% | Rp 78.310.847 |
| **EXCL** | V8_Pullback | 62.96% | Rp 57.001.915 |
| **TSPC** | V8_Pullback | 62.50% | Rp 54.378.167 |
| **PGAS** | V8_Pullback | 52.78% | Rp 51.650.692 |
| **SILO** | V6_Bandar | 45.16% | Rp 48.143.152 |
| **KEEN** | V8_Pullback | 61.90% | Rp 41.181.184 |

*(Lengkapnya lihat file `matrix_saham.json`)*

---

## ⚠️ Daftar Hitam (Blacklist - AVOID!)
Saham-saham di bawah ini memiliki performa buruk di semua strategi yang diuji. **JANGAN EKSEKUSI SINYAL** pada ticker berikut:

* **BBTN**: Loss -Rp 41.072.982
* **BDMN**: Loss -Rp 30.606.070
* **WOOD**: Loss -Rp 31.000.000
* **OBMD**: Loss -Rp 32.000.000
* **KAEF**: Win Rate 0% (Parasit Sistem)

---

## 💡 Rekomendasi Langkah Selanjutnya
1.  **Live Scanner:** Gunakan daftar *Master Whitelist* (Saham dengan Cuan > Rp 20 Juta) sebagai filter utama untuk scanner harian Anda.
2.  **Disiplin Risk-Free:** Jangan pernah mematikan fitur *Trailing Stop BEP*, karena inilah yang memangkas kerugian sistem Anda hingga mencapai angka *PnL* positif.
3.  **Update Database:** Pastikan data `market_data.db` Anda selalu *up-to-date* setiap hari bursa sebelum menjalankan skrip `Sniper V8`.

---
*Dokumen ini dibuat secara otomatis berdasarkan hasil simulasi sistem kuantitatif.*