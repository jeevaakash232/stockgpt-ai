import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

# Load environment file
load_dotenv(dotenv_path=env_path)

class Settings:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    
    @property
    def DATABASE_URL(self) -> str:
        # Check direct DATABASE_URL override (e.g. Supabase connection string)
        direct_url = os.getenv("DATABASE_URL")
        if direct_url:
            # SQLAlchemy 1.4+ expects postgresql:// instead of postgres://
            if direct_url.startswith("postgres://"):
                return direct_url.replace("postgres://", "postgresql://", 1)
            return direct_url
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "")
    ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "")
    ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD", "")
    ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = BASE_DIR / "logs"

# Ensure logs directory exists
Settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
