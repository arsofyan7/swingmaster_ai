import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str = "AIzaSyBaUEG7nia9TwEUXSbmZSiOd4AFZu0pq8g"
    
    # App Settings
    APP_NAME: str = "SwingMaster AI"
    DEBUG: bool = True
    
    # Google WebApp URL
    GOOGLE_WEBAPP_URL: str = "https://script.google.com/macros/s/AKfycbz5B2Y_piR9RCssWnZSfzCdVT_3wWvMz8MU_MV4V4iHk1vaywoJwLBZjwzJHZB5N0u9zw/exec"
    
    # Konfigurasi agar bisa baca dari file .env kalau ada
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Inisialisasi global
settings = Settings()
