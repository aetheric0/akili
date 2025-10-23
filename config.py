"""
Global Configuration for Project 'Akili'
"""

from pydantic_settings import BaseSettings
from datetime import timedelta

SUBSCRIPTION_PLANS = {
"free": {
        "daily_doc_uploads": 5,
        "daily_image_uploads": 2,
        "monthly_exam_analyses": 0,
        "max_sessions": 5,
    },
    "basic": {
        "daily_doc_uploads": 15,
        "daily_image_uploads": 15,
        "monthly_exam_analyses": 10,
        "max_sessions": 15,
    },
    "premium": {
        "daily_doc_uploads": 50,
        "daily_image_uploads": 100,
        "monthly_exam_analyses": 999,
        "max_sessions": 999,
    },
    "lifetime": None
}

class Settings(BaseSettings):
    """
    Global Base settings for Akili API
    """
    # App Configuration
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    REDIS_HOST: str

    # Client Host
    UI_HOST: str

    # Payment Provider
    PAYSTACK_SECRET_KEY: str

    # SUPABASE
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Configuration for external services
    GOOGLE_GEMINI_API_KEY: str

    # Max upload size
    MAX_FILE_SIZE: int = 5 * 1024 * 1024        #5 MB

    class Config:
        env_file = ".env"

settings = Settings()
