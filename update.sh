#!/bin/bash

# Pindah ke direktori utama project (sesuaikan jika perlu)
cd /root/swingmaster_ai

echo "Menarik update terbaru dari Git..."
git pull

echo "Pindah ke folder backend..."
cd backend

echo "Fixing permissions for SQLite database files..."
# Ubah owner ke UID 1000 (sesuai appuser di dalam docker) dan berikan akses read-write
sudo chown 1000:1000 *.db
sudo chmod 666 *.db

echo "Membangun ulang image dan me-restart container..."
docker compose up -d --build

echo "Update selesai! Aplikasi sudah berjalan dengan versi terbaru."
