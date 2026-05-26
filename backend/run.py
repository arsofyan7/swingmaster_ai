import os
import sys
import time
import subprocess

# Konfigurasi Path (Gaya Linux/WSL)
REQUIREMENTS_FILE = "requirements.txt"
VENV_PIP = os.path.join("env", "bin", "pip")
VENV_UVICORN = os.path.join("env", "bin", "uvicorn")

def install_requirements():
    print("\n[Mandor] 📦 Memeriksa & menginstal requirements...")
    try:
        # Menjalankan pip install menggunakan pip milik virtual environment
        subprocess.run([VENV_PIP, "install", "-r", REQUIREMENTS_FILE], check=True)
        print("[Mandor] ✅ Semua library aman dan up-to-date!")
    except Exception as e:
        print(f"[Mandor] ❌ Gagal menginstal library: {e}")

def start_server():
    print("[Mandor] 🚀 Menyalakan FastAPI Server...")
    # Menjalankan uvicorn dengan --reload bawaan untuk memantau file .py
    cmd = [VENV_UVICORN, "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    return subprocess.Popen(cmd)

def main():
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"[Core Error] File {REQUIREMENTS_FILE} tidak ditemukan!")
        return

    # Jalankan instalasi pertama kali saat script dinyalakan
    install_requirements()
    server_process = start_server()
    
    # Ambil waktu modifikasi terakhir dari requirements.txt
    last_mtime = os.path.getmtime(REQUIREMENTS_FILE)

    print("\n[Mandor] 👀 Sistem pemantau aktif! Mengawasi 'requirements.txt' & kode anda...")
    
    try:
        while True:
            time.sleep(2) # Cek setiap 2 detik
            if os.path.exists(REQUIREMENTS_FILE):
                current_mtime = os.path.getmtime(REQUIREMENTS_FILE)
                
                # Jika file requirements.txt diubah oleh lu
                if current_mtime > last_mtime:
                    print("\n[Mandor] ⚡ Deteksi perubahan di requirements.txt! Mereload proyek...")
                    last_mtime = current_mtime
                    
                    # Matikan server uvicorn yang lama
                    print("[Mandor] 🛑 Mematikan server sementara...")
                    server_process.terminate()
                    server_process.wait()
                    
                    # Install ulang library baru
                    install_requirements()
                    
                    # Nyalakan kembali servernya
                    server_process = start_server()
                    
    except KeyboardInterrupt:
        print("\n[Mandor] 🔌 Mematikan seluruh sistem dev server...")
        server_process.terminate()
        server_process.wait()
        print("[Mandor] 👋 Bye! Sampai jumpa di sesi coding berikutnya.")

if __name__ == "__main__":
    main()