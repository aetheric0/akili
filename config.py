"""
Global Configuration for Project 'Akili'
"""

from pydantic_settings import BaseSettings
from datetime import timedelta

SUBSCRIPTION_PLANS = {
    "basic_weekly": timedelta(days=7),
    "standard_monthly": timedelta(days=30),
    "premium-quarterly": timedelta(days=30),
    "lifetime": None    # No enquiry
}

class Settings(BaseSettings):
    """
    Global Base settings for Akili API
    """
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    REDIS_HOST: str
    UI_HOST: str
    PAYSTACK_SECRET_KEY: str
    
    # Configuration for external services
    GOOGLE_GEMINI_API_KEY: str

    # Max upload size
    MAX_FILE_SIZE: int = 5 * 1024 * 1024        #5 MB

    class Config:
        env_file = ".env"

settings = Settings()
