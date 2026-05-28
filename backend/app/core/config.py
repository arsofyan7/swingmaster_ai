import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    GEMINI_API_KEY: str
    
    # App Settings
    APP_NAME: str = "SwingMaster AI"
    DEBUG: bool = False
    
    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Google WebApp URL
    GOOGLE_WEBAPP_URL: str
    
    # Konfigurasi agar bisa baca dari file .env kalau ada
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Inisialisasi global
settings = Settings()
