# 🛡️ PAKEM SECURE CODING & CYBER DEFENSE (PYTHON API EDITION) 🛡️

**DOKUMEN KLASIFIKASI: SANGAT RAHASIA / WAJIB DITERAPKAN**
Dokumen ini berisi Standar Operasional Prosedur (SOP) Keamanan Siber khusus untuk arsitektur Backend Python, SQLite, Data Science (Pandas), dan Integrasi AI. Tidak ada toleransi untuk kelalaian keamanan (Zero Trust Architecture).

---

## ⚔️ 1. PERTAHANAN BASIS DATA (SQLITE & ANTI-INJECTION)
Karena kita menggunakan `sqlite3` bawaan Python, risiko *SQL Injection* sangat fatal jika salah menyambung string.

* **[WAJIB] Parameterized Queries:** DILARANG KERAS menggunakan *f-strings* (`f"SELECT * FROM users WHERE id={user_id}"`) atau `.format()` untuk memasukkan variabel ke dalam kueri SQL.
    * **BENAR:** `cursor.execute("SELECT * FROM ai_analyses WHERE ticker = ?", (ticker,))`
    * **SALAH:** `cursor.execute(f"SELECT * FROM ai_analyses WHERE ticker = '{ticker}'")`
* **[WAJIB] Validasi Tipe Data Input:** Semua data yang masuk dari klien wajib divalidasi ketat menggunakan **Pydantic Models** sebelum menyentuh fungsi *database*. Jangan pernah memproses JSON mentah tanpa skema.

## ⚔️ 2. PERTAHANAN API & INTEGRASI AI (PROMPT INJECTION)
Sistem ini berinteraksi dengan API eksternal (Google Gemini) dan melayani klien web/mobile.

* **[WAJIB] Sanitasi Input Klien:** Pastikan parameter seperti `ticker` dibersihkan (misal: `ticker.upper().strip().replace(".JK", "")`) untuk mencegah injeksi karakter aneh ke dalam sistem atau *prompt* AI.
* **[WAJIB] Isolasi Prompt AI (Anti-Jailbreak):** Pisahkan dengan tegas antara "Instruksi Sistem" (SOP Kaku) dengan "Data Variabel" di dalam *prompt* LLM. Gunakan kata pemisah (seperti `---` atau tag XML) agar AI tidak bisa diakali oleh data emiten buatan yang mengandung instruksi manipulatif.
* **[WAJIB] Manajemen Kredensial (Secrets):** DILARANG menulis (hardcode) API Key di dalam file `.py`. Wajib menggunakan modul `pydantic-settings` atau `os.getenv` untuk membaca dari file `.env` yang tidak di-commit ke Git.

## ⚔️ 3. PENGENDALIAN AKSES & AUTENTIKASI (ZERO TRUST)
Semua *endpoint* API wajib dilindungi secara berlapis.

* **[WAJIB] Keamanan Password:** Seluruh kata sandi pengguna wajib di-*hash* menggunakan `passlib` dengan algoritma **Bcrypt** (cost minimal 12). Modul `hashlib.sha256()` biasa tidak direkomendasikan untuk produksi karena rentan *brute-force* cepat.
* **[WAJIB] Otorisasi Berbasis Token (JWT):** Gunakan JSON Web Tokens (JWT) dengan umur sesi (ekspirasi) yang singkat. Jangan menyimpan data sensitif di dalam *payload* JWT.
* **[WAJIB] CORS & Rate Limiting:** Konfigurasi *CORS middleware* di FastAPI hanya untuk domain *frontend* yang diizinkan. Terapkan *Rate Limiting* (misal via `slowapi`) di *endpoint* kritikal seperti `/login` atau *endpoint* yang memicu *request* ke AI untuk mencegah pembengkakan tagihan API (DDoS tagihan).

## ⚔️ 4. PERTAHANAN PANDAS & PEMROSESAN DATA
Mesin data *quant* sangat membebani CPU/RAM dan berpotensi menjadi celah jika memproses file eksternal.

* **[WAJIB] Hindari Eksekusi Dinamis Pandas:** DILARANG menggunakan fungsi `pd.eval()` atau `df.query()` yang menerima *string* dari input pengguna secara langsung, karena ini bisa memicu Arbitrary Code Execution (ACE) di level Python. Gunakan *boolean indexing* standar.
* **[WAJIB] Penanganan Nilai Tak Terhingga (Inf/NaN):** Selalu lakukan `.replace([np.inf, -np.inf], 0).fillna(0)` pada setiap hasil perhitungan indikator teknikal untuk mencegah aplikasi API *crash* (*Denial of Service* karena *Unhandled Exception*).

## ⚔️ 5. PERTAHANAN INFRASTRUKTUR & DOCKER (VPS HARDENING)
Menjaga *container* dan server tetap ramping dan kebal dari pemindaian otomatis.

* **[WAJIB] Docker Non-Root User:** *Container* Docker tidak boleh dijalankan menggunakan *user root*. Buat *user* khusus di dalam `Dockerfile` (misal: `USER appuser`) untuk mencegah eksploitasi jika *container* tembus.
* **[WAJIB] Limitasi Memori (OOM Protection):** Tambahkan parameter batas memori di `docker-compose.yml` (misal: `mem_limit: 512m`) agar proses Pandas yang memakan RAM besar tidak membuat seluruh VPS Ubuntu ikut *hang* atau mati.
* **[WAJIB] Proteksi Lapis Pertama (Reverse Proxy):** Aplikasi FastAPI uvicorn/gunicorn DILARANG terekspos langsung ke internet publik. Wajib dilewatkan melalui Nginx/Apache sebagai *Reverse Proxy* yang dilengkapi sertifikat SSL/TLS, UFW (Uncomplicated Firewall), dan ModSecurity/Fail2Ban untuk memblokir IP penyerang.

---
*Dokumen ini merupakan komitmen terhadap arsitektur perangkat lunak yang tangguh. Keamanan bukanlah fitur opsional, melainkan fondasi utama dari ekosistem algoritma kita.*