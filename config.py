"""
Global Configuration for Project 'JobFluence'
"""

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Global Base settings for Akili API
    """
    # Maximum file size for uploads in bytes (e.g., 5MB)
    GOOGLE_GEMINI_API_KEY: str
    MAX_FILE_SIZE: int = 5 * 1024 * 1024        #5 MB

    class Config:
        env_file = ".env"

settings = Settings()
