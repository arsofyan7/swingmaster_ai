#!/bin/bash

# Pindah ke direktori utama project (sesuaikan jika perlu)
cd /root/swingmaster_ai

echo "Menarik update terbaru dari Git..."
git pull

echo "Pindah ke folder backend..."
cd backend

echo "Membangun ulang image dan me-restart container..."
docker-compose up -d --build

echo "Update selesai! Aplikasi sudah berjalan dengan versi terbaru."
