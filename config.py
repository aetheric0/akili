"""
Global Configuration for Project 'JobFluence'
"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Global Base settings for Akili API
    """
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    
    # Max upload size
    GOOGLE_GEMINI_API_KEY: str
    MAX_FILE_SIZE: int = 5 * 1024 * 1024        #5 MB

    class Config:
        env_file = ".env"

settings = Settings()
